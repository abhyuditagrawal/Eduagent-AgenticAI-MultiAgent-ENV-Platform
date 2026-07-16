"""Smart study planner: generates personalized schedules based on mastery + SM-2 data."""

import json
import re
from datetime import datetime, timezone, timedelta

import structlog
import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study import StudyPlan
from app.models.concept import Concept
from app.models.student import StudentConcept
from app.services.llm import get_gemini_model
from app.services.student_state import (
    get_weak_concepts,
    get_overdue_concepts,
    get_mastery_summary,
    get_study_priority_queue,
)

logger = structlog.get_logger()

PLANNER_PROMPT = """You are an expert study planner. Create a personalized study schedule.

Student's current state:
- Overall mastery: {mastery_pct}%
- Days until exam: {days_until_exam}
- Study hours per day: {hours_per_day}
- Weak concepts: {weak_concepts}
- Overdue reviews: {overdue_concepts}
- Priority queue: {priority_queue}

Generate a day-by-day study plan. For each day, specify:
1. Topics to study (prioritize overdue reviews and weak concepts)
2. Recommended activities (review, practice questions, teach-back)
3. Estimated time for each activity

Return ONLY a JSON array of daily plans:
[
  {{
    "day": 1,
    "date_label": "Day 1",
    "focus": "Review fundamentals",
    "tasks": [
      {{"topic": "...", "activity": "review|practice|teach", "duration_minutes": 30}},
      ...
    ],
    "priority": "high"
  }},
  ...
]

Create plans for up to {num_days} days. Be realistic about time constraints."""


async def generate_study_plan(
    db: AsyncSession,
    student_id,
    subject_id,
    exam_date: datetime | None = None,
    study_hours_per_day: float = 2.0,
) -> dict:
    """Generate a personalized study plan using AI + student mastery data."""
    # Gather student state
    mastery = await get_mastery_summary(db, student_id, subject_id)
    weak = await get_weak_concepts(db, student_id, subject_id, threshold=0.5)
    overdue = await get_overdue_concepts(db, student_id, subject_id)
    priority = await get_study_priority_queue(db, student_id, subject_id)

    now = datetime.now(timezone.utc)
    if exam_date:
        days_until = max(1, (exam_date - now).days)
    else:
        days_until = 14  # default 2 weeks

    num_days = min(days_until, 14)

    weak_names = [w["concept_name"] for w in weak[:10]]
    overdue_names = [o["concept_name"] for o in overdue[:10]]
    priority_names = [p["concept_name"] for p in priority[:10]]

    prompt = PLANNER_PROMPT.format(
        mastery_pct=round(mastery.get("overall_score", 0) * 100),
        days_until_exam=days_until,
        hours_per_day=study_hours_per_day,
        weak_concepts=", ".join(weak_names) or "None identified",
        overdue_concepts=", ".join(overdue_names) or "None",
        priority_queue=", ".join(priority_names) or "No priority data",
        num_days=num_days,
    )

    model = get_gemini_model()
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.4, max_output_tokens=4096
            ),
        )
        raw = response.text.strip()
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if json_match:
            raw = json_match.group(1).strip()
        plan_data = json.loads(raw)
    except Exception as e:
        logger.error("study_plan_generation_failed", error=str(e))
        plan_data = _fallback_plan(weak_names, overdue_names, num_days, study_hours_per_day)

    # Save plan
    plan = StudyPlan(
        student_id=student_id,
        subject_id=subject_id,
        exam_date=exam_date,
        study_hours_per_day=study_hours_per_day,
        plan_data={"days": plan_data, "generated_at": now.isoformat()},
    )
    db.add(plan)
    await db.commit()

    return {
        "id": str(plan.id),
        "exam_date": exam_date.isoformat() if exam_date else None,
        "study_hours_per_day": study_hours_per_day,
        "days_until_exam": days_until,
        "mastery_pct": round(mastery.get("overall_score", 0) * 100),
        "plan": plan_data,
    }


def _fallback_plan(
    weak: list[str], overdue: list[str], num_days: int, hours: float
) -> list[dict]:
    """Generate a simple fallback plan without LLM."""
    all_topics = list(dict.fromkeys(overdue + weak))  # deduplicate, preserve order
    plan = []
    for i in range(num_days):
        idx = i % max(len(all_topics), 1)
        topic = all_topics[idx] if all_topics else "General review"
        plan.append({
            "day": i + 1,
            "date_label": f"Day {i + 1}",
            "focus": f"Study: {topic}",
            "tasks": [
                {"topic": topic, "activity": "review", "duration_minutes": int(hours * 30)},
                {"topic": topic, "activity": "practice", "duration_minutes": int(hours * 30)},
            ],
            "priority": "high" if i < 3 else "medium",
        })
    return plan


async def get_study_plans(db: AsyncSession, student_id, subject_id=None) -> list[dict]:
    query = select(StudyPlan).where(StudyPlan.student_id == student_id)
    if subject_id:
        query = query.where(StudyPlan.subject_id == subject_id)
    query = query.order_by(StudyPlan.created_at.desc()).limit(10)

    result = await db.execute(query)
    plans = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "subject_id": str(p.subject_id),
            "exam_date": p.exam_date.isoformat() if p.exam_date else None,
            "study_hours_per_day": p.study_hours_per_day,
            "plan": p.plan_data,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in plans
    ]
