"""Bayesian Knowledge Tracing (BKT) + Predictive Forgetting engine.

This module augments the SM-2 scheduler with two probabilistic models:

1. Bayesian Knowledge Tracing (Corbett & Anderson, 1994):
   A Hidden Markov Model that estimates P(L) - the probability a latent
   skill is "learned" - from a sequence of observed correct/incorrect
   responses. Four parameters govern the model:
     - P(L0): prior probability the skill is already known
     - P(T):  probability of transitioning from unlearned -> learned
     - P(S):  slip - probability of answering incorrectly when learned
     - P(G):  guess - probability of answering correctly when unlearned

2. Ebbinghaus Predictive Forgetting:
   Retrievability R(t) = exp(-t / S), where S is the memory *stability*
   (in days). Each successful review multiplies stability; failures reset
   it. We solve R(t) = threshold for t to predict the exact day a concept
   will be forgotten, enabling proactive interventions.
"""

import math
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept
from app.models.student import StudentConcept

logger = structlog.get_logger()

# --- BKT parameters (tuned defaults, per-difficulty overrides below) ---
BKT_P_L0 = 0.10   # prior mastery
BKT_P_TRANSIT = 0.15  # learning rate per opportunity
BKT_P_SLIP = 0.10  # slip
BKT_P_GUESS = 0.20  # guess

# Retention threshold below which we consider the concept "forgotten"
RETENTION_THRESHOLD = 0.5


def _difficulty_transit(difficulty_tier: int) -> float:
    """Harder concepts are learned more slowly per opportunity."""
    return {1: 0.20, 2: 0.15, 3: 0.10}.get(difficulty_tier, 0.15)


def bkt_posterior(prior: float, correct: bool,
                  p_slip: float = BKT_P_SLIP,
                  p_guess: float = BKT_P_GUESS) -> float:
    """Update P(L) given a single observation using Bayes' rule.

    Returns the posterior P(L_t | evidence) BEFORE applying the learning
    transition. Caller applies the transition afterwards.
    """
    if correct:
        # P(correct | learned) = 1 - slip ; P(correct | unlearned) = guess
        numerator = prior * (1 - p_slip)
        denom = prior * (1 - p_slip) + (1 - prior) * p_guess
    else:
        numerator = prior * p_slip
        denom = prior * p_slip + (1 - prior) * (1 - p_guess)
    if denom <= 0:
        return prior
    return numerator / denom


def bkt_update(prior: float, correct: bool, difficulty_tier: int = 1) -> float:
    """Full BKT step: Bayesian conditioning + learning transition."""
    posterior = bkt_posterior(prior, correct)
    p_t = _difficulty_transit(difficulty_tier)
    # Probability learned at next step = posterior + (1 - posterior) * P(T)
    updated = posterior + (1 - posterior) * p_t
    return max(0.0, min(1.0, updated))


def update_memory_stability(current_stability: float, mastery: float,
                            correct: bool) -> float:
    """Update memory stability (days) following a review.

    Successful recall increases stability multiplicatively (spacing effect),
    scaled by current mastery. Failure contracts stability toward 1 day.
    """
    if correct:
        # Higher mastery -> larger stability gains (well-consolidated memories)
        growth = 1.4 + mastery  # 1.4x - 2.4x
        return min(365.0, max(1.0, current_stability * growth))
    else:
        return max(0.5, current_stability * 0.5)


def retrievability(stability: float, days_elapsed: float) -> float:
    """Ebbinghaus retention: R(t) = exp(-t / S)."""
    if stability <= 0:
        return 0.0
    return math.exp(-days_elapsed / stability)


def days_until_forgetting(stability: float,
                          threshold: float = RETENTION_THRESHOLD) -> float:
    """Solve exp(-t/S) = threshold  =>  t = -S * ln(threshold)."""
    if stability <= 0:
        return 0.0
    return -stability * math.log(threshold)


def current_recall(sc: StudentConcept, now: datetime | None = None) -> float:
    """Compute current recall probability for a StudentConcept row."""
    now = now or datetime.now(timezone.utc)
    anchor = sc.last_seen_at or sc.created_at
    if anchor is None:
        return sc.bkt_mastery
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    days_elapsed = max(0.0, (now - anchor).total_seconds() / 86400.0)
    r = retrievability(sc.memory_stability or 1.0, days_elapsed)
    # Blend forgetting curve with BKT mastery (a learned skill decays slower)
    return round(r * (0.5 + 0.5 * sc.bkt_mastery), 4)


async def apply_bkt_observation(
    db: AsyncSession, student_id, concept_id, correct: bool,
    commit: bool = True,
) -> dict | None:
    """Record an observation and update BKT mastery + forgetting forecast."""
    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == student_id,
            StudentConcept.concept_id == concept_id,
        )
    )
    row = result.first()
    if not row:
        return None
    sc, concept = row

    now = datetime.now(timezone.utc)
    prior = sc.bkt_mastery if sc.bkt_mastery is not None else BKT_P_L0
    new_mastery = bkt_update(prior, correct, concept.difficulty_tier)
    new_stability = update_memory_stability(
        sc.memory_stability or 1.0, new_mastery, correct
    )

    sc.bkt_mastery = new_mastery
    sc.memory_stability = new_stability
    sc.last_seen_at = now
    days = days_until_forgetting(new_stability)
    sc.predicted_forget_at = now + timedelta(days=days)

    if commit:
        await db.commit()

    logger.info(
        "bkt_observation",
        student_id=str(student_id),
        concept_id=str(concept_id),
        correct=correct,
        mastery=round(new_mastery, 3),
        stability=round(new_stability, 2),
        days_until_forget=round(days, 1),
    )

    return {
        "concept_id": str(concept_id),
        "bkt_mastery": round(new_mastery, 4),
        "memory_stability": round(new_stability, 2),
        "predicted_forget_at": sc.predicted_forget_at.isoformat(),
        "days_until_forget": round(days, 1),
    }


async def get_mastery_probabilities(
    db: AsyncSession, student_id, subject_id
) -> list[dict]:
    """Return per-concept BKT mastery + current recall + forgetting forecast."""
    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == student_id,
            Concept.subject_id == subject_id,
        )
        .order_by(Concept.chapter, Concept.name)
    )
    rows = result.all()
    now = datetime.now(timezone.utc)

    out = []
    for sc, concept in rows:
        recall = current_recall(sc, now)
        forget_at = sc.predicted_forget_at
        days_left = None
        if forget_at:
            if forget_at.tzinfo is None:
                forget_at = forget_at.replace(tzinfo=timezone.utc)
            days_left = round((forget_at - now).total_seconds() / 86400.0, 1)
        out.append({
            "concept_id": str(concept.id),
            "concept_name": concept.name,
            "chapter": concept.chapter,
            "difficulty": concept.difficulty_tier,
            "bkt_mastery": round(sc.bkt_mastery, 4),
            "current_recall": recall,
            "memory_stability_days": round(sc.memory_stability, 2),
            "predicted_forget_at": forget_at.isoformat() if forget_at else None,
            "days_until_forget": days_left,
            "at_risk": recall < RETENTION_THRESHOLD,
        })
    return out


async def get_forgetting_forecast(
    db: AsyncSession, student_id, subject_id, horizon_days: int = 14
) -> dict:
    """Timeline of concepts predicted to fall below retention threshold."""
    probs = await get_mastery_probabilities(db, student_id, subject_id)
    now = datetime.now(timezone.utc)

    upcoming = []
    for p in probs:
        if p["days_until_forget"] is None:
            continue
        if p["days_until_forget"] <= horizon_days:
            upcoming.append(p)
    upcoming.sort(key=lambda x: (x["days_until_forget"] if x["days_until_forget"] is not None else 999))

    # Build a day-bucketed forecast for charting
    buckets: dict[int, list[str]] = {}
    for p in upcoming:
        d = max(0, int(math.floor(p["days_until_forget"])))
        buckets.setdefault(d, []).append(p["concept_name"])

    timeline = [
        {
            "day_offset": d,
            "date": (now + timedelta(days=d)).strftime("%Y-%m-%d"),
            "concepts": names,
            "count": len(names),
        }
        for d, names in sorted(buckets.items())
    ]

    at_risk_now = [p for p in probs if p["at_risk"]]

    return {
        "horizon_days": horizon_days,
        "at_risk_now": at_risk_now,
        "at_risk_count": len(at_risk_now),
        "upcoming": upcoming,
        "timeline": timeline,
        "total_concepts": len(probs),
        "avg_mastery": round(
            sum(p["bkt_mastery"] for p in probs) / len(probs), 3
        ) if probs else 0.0,
    }
