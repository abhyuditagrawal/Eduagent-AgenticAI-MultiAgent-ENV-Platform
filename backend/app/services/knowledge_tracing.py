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
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept
from app.models.student import StudentConcept, StudentBktParams, BktObservation

logger = structlog.get_logger()

# Minimum raw observations before per-student EM fitting is attempted at all -
# below this, a fit would just be overfitting noise, so global defaults stay in effect.
MIN_OBSERVATIONS_FOR_FITTING = 8

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


def bkt_update(
    prior: float, correct: bool, difficulty_tier: int = 1,
    p_slip: float = BKT_P_SLIP, p_guess: float = BKT_P_GUESS,
    p_transit: float | None = None,
) -> float:
    """Full BKT step: Bayesian conditioning + learning transition.

    p_slip/p_guess/p_transit are overridable so a student with fitted,
    personalised parameters (StudentBktParams) updates against their own
    calibration instead of the tuned global defaults.
    """
    posterior = bkt_posterior(prior, correct, p_slip=p_slip, p_guess=p_guess)
    p_t = p_transit if p_transit is not None else _difficulty_transit(difficulty_tier)
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
    """Record an observation and update BKT mastery + forgetting forecast.

    Uses the student's personalised BKT parameters (StudentBktParams) once
    enough history exists to have fitted them; otherwise falls back to the
    tuned global defaults, same as before personalisation existed.
    """
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

    # Log the raw observation - this is the sequence per-student EM fitting needs.
    db.add(BktObservation(
        student_id=student_id,
        concept_id=concept_id,
        difficulty_tier=concept.difficulty_tier,
        correct=correct,
    ))

    params = await get_effective_bkt_params(db, student_id)

    now = datetime.now(timezone.utc)
    prior = sc.bkt_mastery if sc.bkt_mastery is not None else params["p_l0"]
    p_transit = params["p_transit"].get(concept.difficulty_tier, params["p_transit"][1])
    new_mastery = bkt_update(
        prior, correct, concept.difficulty_tier,
        p_slip=params["p_slip"], p_guess=params["p_guess"], p_transit=p_transit,
    )
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
        personalized=params["personalized"],
    )

    return {
        "concept_id": str(concept_id),
        "bkt_mastery": round(new_mastery, 4),
        "memory_stability": round(new_stability, 2),
        "predicted_forget_at": sc.predicted_forget_at.isoformat(),
        "days_until_forget": round(days, 1),
        "personalized_params": params["personalized"],
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


async def predict_learning_outcome(
    db: AsyncSession, student_id, subject_id, exam_date: datetime | None = None,
) -> dict:
    """Forecast likely assessment performance on a future date (Future Work item #2).

    Projects each concept's recall forward to `exam_date` (default: 14 days
    out) using the same forgetting-curve model as get_forgetting_forecast,
    then aggregates into a single predicted score - the number a student
    actually wants ("if the exam were today, how would I do?").
    """
    now = datetime.now(timezone.utc)
    target = exam_date or (now + timedelta(days=14))
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    horizon_days = max(0.0, (target - now).total_seconds() / 86400.0)

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
    if not rows:
        return {
            "exam_date": target.isoformat(),
            "horizon_days": round(horizon_days, 1),
            "predicted_score": None,
            "concepts": [],
            "at_risk_concepts": [],
        }

    concepts_out = []
    at_risk = []
    for sc, concept in rows:
        projected_recall = current_recall(sc, target)
        # Blend today's BKT mastery (what they've actually learned) with the
        # projected recall (whether they'll still remember it by exam day) -
        # a mastered-but-decayed concept scores lower than a fresh one.
        predicted = round(0.5 * sc.bkt_mastery + 0.5 * projected_recall, 4)
        entry = {
            "concept_id": str(concept.id),
            "concept_name": concept.name,
            "chapter": concept.chapter,
            "current_mastery": round(sc.bkt_mastery, 4),
            "projected_recall_at_exam": round(projected_recall, 4),
            "predicted_score": predicted,
        }
        concepts_out.append(entry)
        if predicted < RETENTION_THRESHOLD:
            at_risk.append(entry)

    overall = round(sum(c["predicted_score"] for c in concepts_out) / len(concepts_out), 4)
    at_risk.sort(key=lambda c: c["predicted_score"])

    return {
        "exam_date": target.isoformat(),
        "horizon_days": round(horizon_days, 1),
        "predicted_score": overall,
        "predicted_score_pct": round(overall * 100, 1),
        "readiness_label": (
            "strong" if overall >= 0.75 else "moderate" if overall >= 0.5 else "at risk"
        ),
        "concepts": concepts_out,
        "at_risk_concepts": at_risk,
        "at_risk_count": len(at_risk),
    }


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


# --- Per-student BKT parameter fitting via EM (Future Work item #6) --------
#
# Standard two-state (unlearned/learned) BKT HMM, fitted with the classic
# Baum-Welch forward-backward algorithm. Each concept the student has
# observations for is one independent sequence; per-sequence soft counts are
# pooled across all of the student's concepts to fit one set of parameters,
# since a single concept rarely has enough observations to fit alone.

def _forward_backward(obs: list[bool], p_l0: float, p_t: float, p_s: float, p_g: float):
    """Return per-timestep P(state=learned | all observations) for one sequence."""
    n = len(obs)
    if n == 0:
        return []

    def emit(learned: bool, correct: bool) -> float:
        if learned:
            return (1 - p_s) if correct else p_s
        return p_g if correct else (1 - p_g)

    alpha = [[0.0, 0.0] for _ in range(n)]
    scales = [0.0] * n

    alpha[0][0] = (1 - p_l0) * emit(False, obs[0])
    alpha[0][1] = p_l0 * emit(True, obs[0])
    scales[0] = alpha[0][0] + alpha[0][1] or 1.0
    alpha[0][0] /= scales[0]
    alpha[0][1] /= scales[0]

    for t in range(1, n):
        pred_unlearned = alpha[t - 1][0] * (1 - p_t)
        pred_learned = alpha[t - 1][0] * p_t + alpha[t - 1][1]
        alpha[t][0] = pred_unlearned * emit(False, obs[t])
        alpha[t][1] = pred_learned * emit(True, obs[t])
        scales[t] = alpha[t][0] + alpha[t][1] or 1.0
        alpha[t][0] /= scales[t]
        alpha[t][1] /= scales[t]

    beta = [[1.0, 1.0] for _ in range(n)]
    for t in range(n - 2, -1, -1):
        e0 = emit(False, obs[t + 1])
        e1 = emit(True, obs[t + 1])
        beta[t][0] = ((1 - p_t) * e0 * beta[t + 1][0] + p_t * e1 * beta[t + 1][1]) / scales[t + 1]
        beta[t][1] = (e1 * beta[t + 1][1]) / scales[t + 1]

    gamma = []
    for t in range(n):
        u = alpha[t][0] * beta[t][0]
        l = alpha[t][1] * beta[t][1]
        total = (u + l) or 1.0
        gamma.append(l / total)  # P(learned) at time t
    return gamma


def _em_fit(sequences: list[list[bool]], difficulty_tiers: list[list[int]], iterations: int = 8) -> dict:
    """Fit pooled BKT parameters across several observation sequences.

    difficulty_tiers mirrors `sequences` (same shape) so the transition rate
    can be estimated per difficulty tier while slip/guess/L0 stay pooled.
    """
    p_l0, p_t_default, p_s, p_g = BKT_P_L0, BKT_P_TRANSIT, BKT_P_SLIP, BKT_P_GUESS
    p_transit_by_tier = {1: 0.20, 2: 0.15, 3: 0.10}

    for _ in range(iterations):
        l0_sum = 0.0
        n_seqs = 0
        learned_correct = 0.0
        learned_total = 0.0
        unlearned_correct = 0.0
        unlearned_total = 0.0
        transit_num = defaultdict(float)
        transit_den = defaultdict(float)

        for obs, tiers in zip(sequences, difficulty_tiers):
            if not obs:
                continue
            gamma = _forward_backward(obs, p_l0, p_t_default, p_s, p_g)
            l0_sum += gamma[0]
            n_seqs += 1

            for t, (correct, tier) in enumerate(zip(obs, tiers)):
                p_learned = gamma[t]
                p_unlearned = 1 - p_learned
                if correct:
                    learned_correct += p_learned
                    unlearned_correct += p_unlearned
                learned_total += p_learned
                unlearned_total += p_unlearned

                if t > 0:
                    # Soft transition estimate: was unlearned at t-1, learned at t.
                    prev_unlearned = 1 - gamma[t - 1]
                    transit_num[tier] += prev_unlearned * p_learned
                    transit_den[tier] += prev_unlearned

        if n_seqs == 0:
            break

        p_l0 = min(0.95, max(0.02, l0_sum / n_seqs))
        p_s = min(0.45, max(0.01, 1 - (learned_correct / learned_total))) if learned_total > 0 else p_s
        p_g = min(0.45, max(0.01, unlearned_correct / unlearned_total)) if unlearned_total > 0 else p_g
        for tier in (1, 2, 3):
            if transit_den.get(tier, 0) > 0:
                p_transit_by_tier[tier] = min(0.6, max(0.02, transit_num[tier] / transit_den[tier]))
        p_t_default = p_transit_by_tier[1]

    return {
        "p_l0": round(p_l0, 4),
        "p_slip": round(p_s, 4),
        "p_guess": round(p_g, 4),
        "p_transit": {k: round(v, 4) for k, v in p_transit_by_tier.items()},
    }


async def fit_student_bkt_params(db: AsyncSession, student_id) -> dict:
    """(Re)fit personalised BKT parameters for one student from their raw
    observation log, if there's enough history; otherwise no-op.

    Returns a dict describing the outcome either way, so callers/endpoints
    can tell a genuine fit apart from "not enough data yet".
    """
    result = await db.execute(
        select(BktObservation)
        .where(BktObservation.student_id == student_id)
        .order_by(BktObservation.concept_id, BktObservation.created_at)
    )
    rows = result.scalars().all()

    if len(rows) < MIN_OBSERVATIONS_FOR_FITTING:
        return {
            "fitted": False,
            "reason": "not_enough_observations",
            "n_observations": len(rows),
            "min_required": MIN_OBSERVATIONS_FOR_FITTING,
        }

    by_concept: dict = defaultdict(list)
    for r in rows:
        by_concept[r.concept_id].append(r)

    sequences = [[r.correct for r in seq] for seq in by_concept.values()]
    tiers = [[r.difficulty_tier for r in seq] for seq in by_concept.values()]

    fitted = _em_fit(sequences, tiers)

    result = await db.execute(
        select(StudentBktParams).where(StudentBktParams.student_id == student_id)
    )
    params_row = result.scalar_one_or_none()
    if params_row is None:
        params_row = StudentBktParams(student_id=student_id)
        db.add(params_row)

    now = datetime.now(timezone.utc)
    params_row.p_l0 = fitted["p_l0"]
    params_row.p_slip = fitted["p_slip"]
    params_row.p_guess = fitted["p_guess"]
    params_row.p_transit_tier1 = fitted["p_transit"][1]
    params_row.p_transit_tier2 = fitted["p_transit"][2]
    params_row.p_transit_tier3 = fitted["p_transit"][3]
    params_row.n_observations = len(rows)
    params_row.fitted_at = now

    await db.commit()

    logger.info(
        "bkt_params_fitted", student_id=str(student_id),
        n_observations=len(rows), n_concepts=len(by_concept), **fitted,
    )

    return {
        "fitted": True,
        "n_observations": len(rows),
        "n_concepts": len(by_concept),
        **fitted,
    }


async def get_effective_bkt_params(db: AsyncSession, student_id) -> dict:
    """The parameters apply_bkt_observation() should actually use right now:
    personalised if fitted, otherwise the tuned global defaults.
    """
    result = await db.execute(
        select(StudentBktParams).where(StudentBktParams.student_id == student_id)
    )
    row = result.scalar_one_or_none()

    if row is None or row.fitted_at is None:
        return {
            "personalized": False,
            "p_l0": BKT_P_L0,
            "p_slip": BKT_P_SLIP,
            "p_guess": BKT_P_GUESS,
            "p_transit": {1: 0.20, 2: 0.15, 3: 0.10},
            "n_observations": row.n_observations if row is not None else 0,
        }

    return {
        "personalized": True,
        "p_l0": row.p_l0 if row.p_l0 is not None else BKT_P_L0,
        "p_slip": row.p_slip if row.p_slip is not None else BKT_P_SLIP,
        "p_guess": row.p_guess if row.p_guess is not None else BKT_P_GUESS,
        "p_transit": {
            1: row.p_transit_tier1 if row.p_transit_tier1 is not None else 0.20,
            2: row.p_transit_tier2 if row.p_transit_tier2 is not None else 0.15,
            3: row.p_transit_tier3 if row.p_transit_tier3 is not None else 0.10,
        },
        "n_observations": row.n_observations,
        "fitted_at": row.fitted_at.isoformat() if row.fitted_at else None,
    }
