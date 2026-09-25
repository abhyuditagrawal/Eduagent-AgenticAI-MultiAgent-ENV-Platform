"""Learning Genome - a per-student cognitive fingerprint.

Aggregates behavioural signals into a compact profile that every agent can
adapt to. Signals:
  - Pace: average attempts required to reach mastery (StudentConcept).
  - Preferred modality: most-used agent type (Message.agent_type).
  - Optimal hour: hour-of-day with the most learning activity.
  - Persistence: fraction of weak concepts the student revisits.
  - Session length: average contiguous activity span.
  - Misconceptions / strengths: an LLM narrative distilled from recent chats.

The genome is stored in `learning_genomes` and refreshed on demand. A short
natural-language `summary` is injected into agent system prompts so responses
are personalised (e.g. slower pace -> more scaffolding).
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone

import structlog
import google.generativeai as genai
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Conversation, Message
from app.models.student import StudentConcept
from app.models.genome import LearningGenome
from app.models.study import StudyRoomMember
from app.models.annotation import MaterialAnnotation
from app.services.llm import get_gemini_model

logger = structlog.get_logger()


MODALITY_LABELS = {
    "concept_qa": "conceptual Q&A",
    "teach_me": "teaching-back (Feynman)",
    "protege": "teaching-back (Feynman)",
    "viva": "oral viva practice",
    "exam_prep": "exam practice",
    "exam_predictor": "exam practice",
    "critique": "writing critique",
    "weak_point_tracker": "weak-point review",
    "security_tool": "hands-on security-tool exercises",
    "general": "open-ended chat",
}


MISCONCEPTION_PROMPT = """You are an educational diagnostician. Based on the following recent student messages, identify up to 3 recurring misconception patterns or error signatures, and up to 3 apparent strengths. Be specific and concise.

Student messages:
{messages}

Return ONLY JSON:
{{"misconceptions": ["..."], "strengths": ["..."]}}"""


async def _compute_pace(db: AsyncSession, student_id) -> tuple[str, float]:
    result = await db.execute(
        select(StudentConcept).where(StudentConcept.student_id == student_id)
    )
    rows = result.scalars().all()
    mastered = [r for r in rows if r.confidence_score >= 0.8 and r.attempts > 0]
    if not mastered:
        # No mastered concepts yet — pace is genuinely unknown, not "average".
        return None, None
    avg_attempts = sum(r.attempts for r in mastered) / len(mastered)
    # Fewer attempts to mastery => faster learner
    if avg_attempts <= 2.0:
        return "fast", min(1.0, 0.75 + (2.0 - avg_attempts) * 0.1)
    elif avg_attempts <= 4.0:
        return "average", 0.5
    else:
        return "slow", max(0.0, 0.4 - (avg_attempts - 4.0) * 0.05)


async def _compute_behaviour(db: AsyncSession, student_id) -> dict:
    result = await db.execute(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.student_id == student_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    hour_counter: Counter = Counter()
    agent_counter: Counter = Counter()
    user_texts: list[str] = []
    timestamps: list[datetime] = []

    for m in messages:
        ts = m.created_at
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            hour_counter[ts.hour] += 1
            timestamps.append(ts)
        if m.agent_type:
            agent_counter[m.agent_type] += 1
        if m.role == "user" and m.content:
            user_texts.append(m.content[:300])

    # Left as None with no activity — reporting a default here would present an
    # invented habit as an observed one.
    optimal_hour = hour_counter.most_common(1)[0][0] if hour_counter else None
    preferred = agent_counter.most_common(1)[0][0] if agent_counter else None

    # Average session length: group timestamps into sessions (>30 min gap = new)
    avg_session = 0.0
    if len(timestamps) >= 2:
        sessions = []
        start = timestamps[0]
        prev = timestamps[0]
        for ts in timestamps[1:]:
            if (ts - prev).total_seconds() > 1800:
                sessions.append((prev - start).total_seconds() / 60.0)
                start = ts
            prev = ts
        sessions.append((prev - start).total_seconds() / 60.0)
        avg_session = sum(sessions) / len(sessions) if sessions else 0.0

    return {
        "optimal_hour": optimal_hour,
        "preferred_modality": preferred,
        "avg_session_minutes": round(avg_session, 1),
        "recent_user_texts": user_texts[-25:],
        "message_count": len(messages),
    }


async def _compute_persistence(db: AsyncSession, student_id) -> float:
    result = await db.execute(
        select(StudentConcept).where(StudentConcept.student_id == student_id)
    )
    rows = result.scalars().all()
    weak = [r for r in rows if r.confidence_score < 0.5]
    if not weak:
        # Nothing to persist at yet — no evidence either way.
        return None
    revisited = [r for r in weak if r.attempts >= 2]
    return round(len(revisited) / len(weak), 3)


async def _compute_social_signals(db: AsyncSession, student_id) -> dict:
    """Peer-collaboration signals (Future Work item #7: extend the genome
    with social learning patterns from study room interactions).

    Two durable, queryable proxies for peer engagement: study-room
    membership (group study sessions) and authored material annotations
    (collaborative note-taking). Peer-debate participation is intentionally
    not included here - that mode is currently ephemeral (in-memory, per
    room) rather than persisted, so it isn't a queryable signal yet.
    """
    room_result = await db.execute(
        select(func.count()).select_from(StudyRoomMember).where(
            StudyRoomMember.user_id == student_id
        )
    )
    room_count = room_result.scalar() or 0

    annotation_result = await db.execute(
        select(func.count()).select_from(MaterialAnnotation).where(
            MaterialAnnotation.author_id == student_id
        )
    )
    annotation_count = annotation_result.scalar() or 0

    if room_count == 0 and annotation_count == 0:
        return {"collaboration_score": None, "peer_sessions_count": 0, "social_summary": None}

    # Diminishing-returns scaling: a handful of sessions/annotations already
    # signals meaningful collaboration; scores saturate rather than growing unbounded.
    score = min(1.0, room_count * 0.15 + annotation_count * 0.05)
    parts = []
    if room_count:
        parts.append(f"joined {room_count} collaborative study session{'s' if room_count != 1 else ''}")
    if annotation_count:
        parts.append(f"contributed {annotation_count} shared material annotation{'s' if annotation_count != 1 else ''}")
    summary = "This student has " + " and ".join(parts) + "."

    return {
        "collaboration_score": round(score, 3),
        "peer_sessions_count": room_count,
        "social_summary": summary,
    }


async def _llm_misconceptions(user_texts: list[str]) -> dict:
    if len(user_texts) < 3:
        return {"misconceptions": [], "strengths": []}
    model = get_gemini_model()
    prompt = MISCONCEPTION_PROMPT.format(messages="\n".join(f"- {t}" for t in user_texts))
    try:
        resp = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3, max_output_tokens=2048
            ),
        )
        raw = resp.text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            raw = match.group(1).strip()
        data = json.loads(raw)
        return {
            "misconceptions": data.get("misconceptions", [])[:3],
            "strengths": data.get("strengths", [])[:3],
        }
    except Exception as e:
        logger.warning("genome_misconception_llm_failed", error=str(e))
        return {"misconceptions": [], "strengths": []}


def _build_summary(pace_label: str | None, modality: str | None, optimal_hour: int | None,
                   persistence: float | None, misconceptions: list[str],
                   social_summary: str | None = None) -> str:
    """Describe only the traits actually observed; stay silent about the rest."""
    parts = []

    if pace_label and modality:
        parts.append(
            f"This student is a {pace_label}-paced learner who prefers "
            f"{MODALITY_LABELS.get(modality, modality)}."
        )
    elif pace_label:
        parts.append(f"This student is a {pace_label}-paced learner.")
    elif modality:
        parts.append(
            f"This student prefers {MODALITY_LABELS.get(modality, modality)}."
        )

    if optimal_hour is not None:
        parts.append(f"They are most active around {optimal_hour:02d}:00.")

    if persistence is not None:
        persistence_h = (
            "high" if persistence >= 0.66 else "moderate" if persistence >= 0.33 else "low"
        )
        parts.append(f"They show {persistence_h} persistence on weak topics.")

    if pace_label == "slow":
        parts.append("Provide extra scaffolding, break ideas into small steps, and check understanding frequently.")
    elif pace_label == "fast":
        parts.append("Move briskly, offer challenge extensions, and avoid over-explaining basics.")
    if misconceptions:
        parts.append("Watch for these recurring misconceptions: " + "; ".join(misconceptions) + ".")
    if social_summary:
        parts.append(social_summary)
    return " ".join(parts)


def _round_or_none(value, digits: int):
    return round(value, digits) if value is not None else None


async def compute_genome(db: AsyncSession, student_id) -> LearningGenome:
    """Recompute and persist the student's learning genome."""
    pace_label, pace_score = await _compute_pace(db, student_id)
    behaviour = await _compute_behaviour(db, student_id)
    persistence = await _compute_persistence(db, student_id)
    social = await _compute_social_signals(db, student_id)
    llm = await _llm_misconceptions(behaviour["recent_user_texts"])

    summary = _build_summary(
        pace_label, behaviour["preferred_modality"], behaviour["optimal_hour"],
        persistence, llm["misconceptions"], social["social_summary"],
    )

    result = await db.execute(
        select(LearningGenome).where(LearningGenome.student_id == student_id)
    )
    genome = result.scalar_one_or_none()
    if genome is None:
        genome = LearningGenome(student_id=student_id)
        db.add(genome)

    genome.pace_label = pace_label
    genome.pace_score = pace_score
    genome.preferred_modality = behaviour["preferred_modality"]
    genome.optimal_hour = behaviour["optimal_hour"]
    genome.persistence_score = persistence
    genome.avg_session_minutes = behaviour["avg_session_minutes"]
    genome.misconception_patterns = llm["misconceptions"]
    genome.strengths = llm["strengths"]
    genome.summary = summary
    genome.data_points = behaviour["message_count"]
    genome.collaboration_score = social["collaboration_score"]
    genome.peer_sessions_count = social["peer_sessions_count"]
    genome.social_summary = social["social_summary"]

    await db.commit()
    await db.refresh(genome)

    logger.info("genome_computed", student_id=str(student_id), pace=pace_label)
    return genome


async def get_genome(db: AsyncSession, student_id) -> LearningGenome | None:
    result = await db.execute(
        select(LearningGenome).where(LearningGenome.student_id == student_id)
    )
    return result.scalar_one_or_none()


async def get_genome_summary(db: AsyncSession, student_id) -> str:
    """Return the short prompt-injection summary (empty string if none)."""
    genome = await get_genome(db, student_id)
    return genome.summary if genome and genome.summary else ""


def genome_to_dict(genome: LearningGenome) -> dict:
    return {
        "pace_label": genome.pace_label,
        "pace_score": _round_or_none(genome.pace_score, 3),
        "preferred_modality": genome.preferred_modality,
        "preferred_modality_label": MODALITY_LABELS.get(
            genome.preferred_modality, genome.preferred_modality
        ),
        "optimal_hour": genome.optimal_hour,
        "persistence_score": _round_or_none(genome.persistence_score, 3),
        "avg_session_minutes": _round_or_none(genome.avg_session_minutes, 1),
        "misconception_patterns": genome.misconception_patterns or [],
        "strengths": genome.strengths or [],
        "summary": genome.summary or "",
        "collaboration_score": _round_or_none(genome.collaboration_score, 3),
        "peer_sessions_count": genome.peer_sessions_count,
        "social_summary": genome.social_summary or "",
        "data_points": genome.data_points,
        "updated_at": genome.updated_at.isoformat() if genome.updated_at else None,
    }
