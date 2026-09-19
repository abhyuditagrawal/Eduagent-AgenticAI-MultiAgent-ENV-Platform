"""Seed one student with ~1.5 months (45 days) of realistic usage history.

Unlike scripts/seed_demo.py (which scatters plausible-looking but disconnected
random values), this script *simulates* the actual BKT/forgetting-curve math
observation-by-observation in chronological order, so every derived value
(bkt_mastery, memory_stability, predicted_forget_at, confidence_score, the
Learning Genome, the personalised BKT parameters) is internally consistent
with what the app itself would have computed had a real student done this
over 45 days. It then calls the real fit_student_bkt_params() and
compute_genome() so those two tables are populated by the actual app logic,
not hand-rolled.

Run from backend/ with the venv that has the app's deps and the right
DATABASE_URL/QDRANT_HOST/etc. env vars set, e.g.:

    python -m scripts.seed_full_history

Safe to re-run: if the user already exists, it deletes and recreates them
first (cascades through every table below via ON DELETE CASCADE).
"""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timezone, timedelta

# See backend/tests/conftest.py for the same fix: asyncpg needs raw socket
# ops the default Windows ProactorEventLoop doesn't support.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select

from app.database import async_session
from app.models.user import User
from app.models.subject import Subject
from app.models.concept import Concept, ConceptPrerequisite
from app.models.student import Enrollment, StudentConcept, BktObservation
from app.models.chat import Conversation, Message
from app.models.flashcard import Flashcard
from app.models.analytics import AgentLog, LearningEvent
from app.models.study import StudyRoom, StudyRoomMember, StudyPlan
from app.models.annotation import MaterialAnnotation
from app.services.auth import hash_password
from app.services.knowledge_tracing import (
    BKT_P_L0,
    bkt_update,
    update_memory_stability,
    days_until_forgetting,
    fit_student_bkt_params,
)
from app.services.learning_genome import compute_genome

random.seed(42)

STUDENT_EMAIL = "priya.sharma@eduagent.dev"
STUDENT_PASSWORD = "LongTerm@123"
STUDENT_NAME = "Priya Sharma"

SUBJECT_CODE = "OS301"
SUBJECT_NAME = "Operating Systems"
SUBJECT_DESC = "Core operating systems course: processes, concurrency, memory management, storage and I/O."

NOW = datetime.now(timezone.utc)


def days_ago(n: float, hour: int | None = None) -> datetime:
    dt = NOW - timedelta(days=n)
    if hour is not None:
        dt = dt.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
    return dt


# (name, chapter, difficulty_tier, [(days_ago, correct), ...] or [] if never attempted)
CONCEPTS: list[tuple[str, str, int, list[tuple[float, bool]]]] = [
    ("Processes", "Ch1: Process Management", 1,
     [(44, False), (42, True), (40, True), (38, True), (35, True), (30, True)]),
    ("Threads", "Ch1: Process Management", 1,
     [(43, True), (41, True), (37, True), (33, True)]),
    ("Process Scheduling", "Ch1: Process Management", 2,
     [(40, False), (32, True), (25, False), (18, True), (10, True), (3, True)]),
    ("Synchronization", "Ch2: Concurrency", 2,
     [(36, True), (29, True), (21, True), (14, True), (7, True), (2, True)]),
    ("Semaphores", "Ch2: Concurrency", 2,
     [(28, False), (20, True), (12, False), (5, True)]),
    ("Deadlocks", "Ch2: Concurrency", 2,
     [(34, False), (27, False), (19, True), (13, False), (8, False), (4, True), (1, False)]),
    ("Paging", "Ch3: Memory Management", 2,
     [(26, True), (19, True), (11, True), (6, True)]),
    ("Segmentation", "Ch3: Memory Management", 2,
     [(9, True)]),
    ("Virtual Memory", "Ch3: Memory Management", 3, []),
    ("File Systems", "Ch4: Storage & I/O", 2,
     [(24, False), (16, True), (9, False), (3, False)]),
    ("Disk Scheduling", "Ch4: Storage & I/O", 2, []),
    ("I/O Management", "Ch4: Storage & I/O", 3, []),
]

# (concept, prerequisite, strength)
PREREQS = [
    ("Threads", "Processes", 0.9),
    ("Process Scheduling", "Processes", 0.8),
    ("Semaphores", "Synchronization", 0.85),
    ("Deadlocks", "Synchronization", 0.8),
    ("Segmentation", "Paging", 0.8),
    ("Virtual Memory", "Paging", 0.9),
    ("Disk Scheduling", "File Systems", 0.75),
    ("I/O Management", "File Systems", 0.8),
]

AGENT_QUESTIONS = {
    "concept_qa": [
        "Can you explain {c} in simple terms?",
        "What's the difference between {c} and related concepts?",
        "Why does {c} matter in a real OS?",
        "I'm confused about {c}, can you walk me through it?",
    ],
    "viva": ["Quiz me on {c}."],
    "protege": ["Let me try to explain {c} back to you."],
    "exam_predictor": ["What should I focus on for {c} in the exam?"],
    "weak_point_tracker": ["What am I still getting wrong about {c}?"],
    "critique": ["Can you review my notes on {c}?"],
}

RESPONSES = {
    "concept_qa": "Here's a breakdown of {c}: it's a core OS mechanism covered in your course material, with the key trade-offs and how it fits into the surrounding chapter.",
    "viva": "Good attempt. Let's go one level deeper on {c} - here's a follow-up question.",
    "protege": "Nice explanation of {c}! Here's a gap I noticed and a follow-up question.",
    "exam_predictor": "{c} is a high-weight topic. Here are 2-3 practice questions and what to prioritise.",
    "weak_point_tracker": "Looking at your history with {c}, here's what's still shaky and a focused review plan.",
    "critique": "Reviewed your notes on {c} - solid structure, a couple of precision issues to fix.",
}


async def reset_existing_user(db):
    result = await db.execute(select(User).where(User.email == STUDENT_EMAIL))
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        print(f"Removed existing user {STUDENT_EMAIL} (cascade cleanup)")

    # Also drop the subject this script owns, so re-running is a clean
    # reseed instead of colliding with concepts left over from a prior run
    # (the user's own rows cascade away above, but Subject/Concept don't
    # belong to the user, so deleting the user alone wouldn't remove them).
    result = await db.execute(select(Subject).where(Subject.code == SUBJECT_CODE))
    existing_subject = result.scalar_one_or_none()
    if existing_subject:
        await db.delete(existing_subject)
        print(f"Removed existing subject {SUBJECT_CODE} (cascade cleanup)")

    await db.commit()


async def seed():
    async with async_session() as db:
        await reset_existing_user(db)

        student = User(
            id=uuid.uuid4(),
            email=STUDENT_EMAIL,
            full_name=STUDENT_NAME,
            hashed_password=hash_password(STUDENT_PASSWORD),
            role="student",
            created_at=days_ago(45, hour=19),
        )
        db.add(student)
        await db.flush()

        result = await db.execute(select(Subject).where(Subject.code == SUBJECT_CODE))
        subject = result.scalar_one_or_none()
        if subject is None:
            subject = Subject(
                id=uuid.uuid4(), code=SUBJECT_CODE, name=SUBJECT_NAME,
                description=SUBJECT_DESC, created_at=days_ago(45, hour=19),
            )
            db.add(subject)
            await db.flush()

        db.add(Enrollment(student_id=student.id, subject_id=subject.id, enrolled_at=days_ago(45, hour=19)))

        # --- Concepts ---
        concept_by_name: dict[str, Concept] = {}
        for name, chapter, tier, _ in CONCEPTS:
            c = Concept(id=uuid.uuid4(), subject_id=subject.id, name=name, chapter=chapter, difficulty_tier=tier)
            db.add(c)
            concept_by_name[name] = c
        await db.flush()

        for concept_name, prereq_name, strength in PREREQS:
            db.add(ConceptPrerequisite(
                concept_id=concept_by_name[concept_name].id,
                prerequisite_id=concept_by_name[prereq_name].id,
                strength=strength,
            ))

        # --- Per-concept StudentConcept + BktObservation, simulating the
        # real BKT/forgetting-curve update chronologically ---
        study_days: dict[float, list[tuple[str, bool]]] = {}
        for name, chapter, tier, timeline in CONCEPTS:
            concept = concept_by_name[name]
            mastery = BKT_P_L0
            stability = 1.0
            last_seen = None
            chronological = sorted(timeline, key=lambda t: -t[0])  # oldest (largest days_ago) first

            for offset, correct in chronological:
                mastery = bkt_update(mastery, correct, tier)
                stability = update_memory_stability(stability, mastery, correct)
                last_seen = days_ago(offset, hour=None)
                db.add(BktObservation(
                    student_id=student.id, concept_id=concept.id,
                    difficulty_tier=tier, correct=correct, created_at=last_seen,
                ))
                study_days.setdefault(offset, []).append((name, correct))

            attempts = len(timeline)
            correct_count = sum(1 for _, c in timeline if c)
            forget_days = days_until_forgetting(stability) if attempts else 0.0

            if attempts == 0:
                sc = StudentConcept(
                    student_id=student.id, concept_id=concept.id,
                    confidence_score=0.0, attempts=0, correct_count=0,
                    bkt_mastery=BKT_P_L0, memory_stability=1.0,
                    easiness_factor=2.5, interval_days=1.0,
                )
            else:
                ease = 1.8 + mastery  # weak concepts land ~1.8-2.1, mastered ~2.6-2.8
                interval = max(1.0, round(mastery * 25))
                sc = StudentConcept(
                    student_id=student.id, concept_id=concept.id,
                    confidence_score=round(mastery, 4), attempts=attempts,
                    correct_count=correct_count,
                    bkt_mastery=round(mastery, 4), memory_stability=round(stability, 2),
                    last_seen_at=last_seen,
                    predicted_forget_at=last_seen + timedelta(days=forget_days) if last_seen else None,
                    next_review_at=last_seen + timedelta(days=min(interval, 21)),
                    easiness_factor=round(ease, 2), interval_days=interval,
                )
            db.add(sc)

        await db.flush()

        # --- Conversations / messages / agent logs, one cluster per study day ---
        agent_cycle = ["concept_qa", "concept_qa", "concept_qa", "viva", "protege",
                       "concept_qa", "exam_predictor", "weak_point_tracker", "concept_qa", "critique"]
        hour_weights = [8, 9, 10, 13, 14, 16, 19, 20, 21, 22]
        hour_probs = [5, 5, 5, 8, 8, 6, 20, 22, 15, 6]

        message_count = 0
        for i, (offset, touched) in enumerate(sorted(study_days.items(), key=lambda kv: -kv[0])):
            hour = random.choices(hour_weights, weights=hour_probs, k=1)[0]
            base_time = days_ago(offset, hour=hour)
            agent_type = agent_cycle[i % len(agent_cycle)]
            # Deadlocks sessions skew toward weak-point framing more often.
            if any(name == "Deadlocks" for name, _ in touched) and random.random() < 0.4:
                agent_type = "weak_point_tracker"

            concept_name = touched[0][0]
            question = random.choice(AGENT_QUESTIONS[agent_type]).format(c=concept_name)
            answer = RESPONSES[agent_type].format(c=concept_name)

            conv = Conversation(
                id=uuid.uuid4(), student_id=student.id, subject_id=subject.id,
                title=question[:80], agent_type=agent_type, created_at=base_time,
            )
            db.add(conv)
            await db.flush()

            user_msg = Message(
                id=uuid.uuid4(), conversation_id=conv.id, role="user",
                content=question, created_at=base_time,
            )
            db.add(user_msg)

            assistant_time = base_time + timedelta(seconds=random.randint(3, 12))
            assistant_msg = Message(
                id=uuid.uuid4(), conversation_id=conv.id, role="assistant",
                content=answer, agent_type=agent_type, created_at=assistant_time,
                metadata_={"concepts_touched": [n for n, _ in touched]},
            )
            db.add(assistant_msg)
            message_count += 2

            db.add(AgentLog(
                id=uuid.uuid4(), student_id=student.id, conversation_id=conv.id,
                agent_type=agent_type, intent=agent_type if agent_type != "concept_qa" else "conceptual_doubt",
                response_time_ms=random.randint(600, 2400),
                input_tokens=random.randint(80, 400), output_tokens=random.randint(120, 600),
                rag_chunks_used=random.randint(1, 4) if agent_type == "concept_qa" else random.randint(0, 2),
                success=True, created_at=assistant_time,
            ))

            # Occasionally a same-session follow-up message, for session-length signal.
            if random.random() < 0.35:
                followup_time = assistant_time + timedelta(minutes=random.randint(2, 12))
                fu_q = Message(
                    id=uuid.uuid4(), conversation_id=conv.id, role="user",
                    content=f"Got it - one more thing about {concept_name}?", created_at=followup_time,
                )
                db.add(fu_q)
                fu_a = Message(
                    id=uuid.uuid4(), conversation_id=conv.id, role="assistant",
                    content=f"Sure - a bit more detail on {concept_name}: " + answer,
                    agent_type=agent_type, created_at=followup_time + timedelta(seconds=5),
                )
                db.add(fu_a)
                message_count += 2

        print(f"Seeded {len(study_days)} study sessions, {message_count} messages")

        # --- Flashcards (SM-2), a mix of overdue / due-soon / future ---
        flashcard_specs = [
            ("Processes", "What is a process in an OS?", "An independent execution unit with its own address space, managed by the OS.", 6, 2.7, -2),
            ("Synchronization", "Why do we need synchronization primitives?", "To coordinate access to shared resources across concurrent threads/processes safely.", 5, 2.6, -1),
            ("Paging", "What problem does paging solve?", "External fragmentation, by dividing memory into fixed-size pages/frames.", 4, 2.5, 1),
            ("Deadlocks", "State the four Coffman conditions for deadlock.", "Mutual exclusion, hold-and-wait, no preemption, circular wait.", 1, 1.9, -3),
            ("Deadlocks", "Name one deadlock prevention strategy.", "Resource ordering: always request resources in a fixed global order.", 1, 1.9, -1),
            ("Semaphores", "Binary vs counting semaphore?", "Binary is 0/1 (mutex-like); counting allows N concurrent holders.", 3, 2.2, 2),
            ("File Systems", "What does an inode store?", "Metadata about a file (permissions, size, pointers to data blocks) - not its name.", 2, 2.0, -1),
            ("Process Scheduling", "What is the goal of SJF scheduling?", "Minimise average waiting time by running the shortest job available next.", 3, 2.3, 3),
        ]
        for concept_name, front, back, reps, ef, due_offset in flashcard_specs:
            concept = concept_by_name[concept_name]
            last_reviewed = days_ago(max(1, reps * 2))
            db.add(Flashcard(
                id=uuid.uuid4(), student_id=student.id, concept_id=concept.id, subject_id=subject.id,
                front=front, back=back, source="auto", easiness_factor=ef, interval_days=float(max(1, reps)),
                repetitions=reps, last_reviewed_at=last_reviewed,
                next_review_at=NOW + timedelta(days=due_offset) if due_offset >= 0 else NOW - timedelta(days=-due_offset),
            ))

        # --- Study rooms (peer-collaboration signal for the Learning Genome) ---
        room_specs = [("OS Study Group", 30), ("Midnight Cram Session", 6)]
        for room_name, joined_days_ago in room_specs:
            room = StudyRoom(
                id=uuid.uuid4(), name=room_name, subject_id=subject.id,
                created_by=student.id, is_active=True, max_members=6,
                created_at=days_ago(joined_days_ago, hour=20),
            )
            db.add(room)
            await db.flush()
            db.add(StudyRoomMember(room_id=room.id, user_id=student.id, joined_at=days_ago(joined_days_ago, hour=20)))

        # --- Collaborative material annotations ---
        annotation_specs = [
            ("os_lecture_notes_ch2.pdf", 4, "Synchronization", "This section's mutex vs semaphore comparison table is the clearest explanation - reread before the exam."),
            ("os_lecture_notes_ch3.pdf", 2, "Paging", "Diagram on page 2 shows the page table walk step by step, very useful."),
            ("os_lecture_notes_ch2.pdf", 7, "Deadlocks", "The Coffman conditions are listed here - I keep mixing up hold-and-wait vs circular wait."),
        ]
        for source_file, page, concept_name, note in annotation_specs:
            db.add(MaterialAnnotation(
                id=uuid.uuid4(), subject_id=subject.id, author_id=student.id,
                source_file=source_file, page=page, note=note,
                created_at=days_ago(random.randint(3, 20), hour=random.randint(18, 22)),
            ))

        # --- A study plan tied to an upcoming exam ---
        # Stored in the same {"days": [...], "generated_at": ...} shape
        # generate_study_plan() persists, so the study-planner page's
        # load-most-recent-plan path renders this exactly like a real
        # LLM-generated plan rather than needing a special case for seed data.
        plan_created = days_ago(5)
        study_plan_days = [
            {
                "day": 1, "date_label": "Day 1", "focus": "Shore up Deadlocks",
                "tasks": [
                    {"topic": "Deadlocks", "activity": "review", "duration_minutes": 45},
                    {"topic": "Deadlocks", "activity": "practice", "duration_minutes": 30},
                ],
                "priority": "high",
            },
            {
                "day": 2, "date_label": "Day 2", "focus": "File Systems fundamentals",
                "tasks": [
                    {"topic": "File Systems", "activity": "review", "duration_minutes": 40},
                    {"topic": "File Systems", "activity": "teach-back", "duration_minutes": 20},
                ],
                "priority": "high",
            },
            {
                "day": 3, "date_label": "Day 3", "focus": "Unlock Disk Scheduling / I/O Management",
                "tasks": [
                    {"topic": "Disk Scheduling", "activity": "practice", "duration_minutes": 30},
                    {"topic": "I/O Management", "activity": "practice", "duration_minutes": 30},
                ],
                "priority": "medium",
            },
            {
                "day": 4, "date_label": "Day 4", "focus": "Consolidate Semaphores & Segmentation",
                "tasks": [
                    {"topic": "Semaphores", "activity": "review", "duration_minutes": 25},
                    {"topic": "Segmentation", "activity": "practice", "duration_minutes": 35},
                ],
                "priority": "medium",
            },
            {
                "day": 5, "date_label": "Day 5", "focus": "Full-syllabus refresh",
                "tasks": [
                    {"topic": "Processes", "activity": "review", "duration_minutes": 20},
                    {"topic": "Synchronization", "activity": "review", "duration_minutes": 20},
                    {"topic": "Paging", "activity": "review", "duration_minutes": 20},
                ],
                "priority": "low",
            },
        ]
        db.add(StudyPlan(
            id=uuid.uuid4(), student_id=student.id, subject_id=subject.id,
            exam_date=NOW + timedelta(days=10), study_hours_per_day=2.5,
            plan_data={"days": study_plan_days, "generated_at": plan_created.isoformat()},
            created_at=plan_created,
        ))

        # --- A few standalone learning events (nudges, reviews) ---
        for offset in (12, 6, 2):
            db.add(LearningEvent(
                id=uuid.uuid4(), student_id=student.id, event_type="nudge_shown",
                concept_id=concept_by_name["Deadlocks"].id, subject_id=subject.id,
                agent_type="weak_point_tracker", data={"reason": "overdue_review"},
                created_at=days_ago(offset, hour=9),
            ))

        await db.commit()
        student_id = student.id
        print("Raw history committed.")

    # --- Now run the REAL app logic to populate derived tables, in a fresh
    # session/connection rather than reusing the one that did all the seeding ---
    async with async_session() as db2:
        fit_result = await fit_student_bkt_params(db2, student_id)
        print(f"fit_student_bkt_params: {fit_result}")

    async with async_session() as db3:
        genome = await compute_genome(db3, student_id)
        print(f"compute_genome: pace={genome.pace_label}, modality={genome.preferred_modality}, "
              f"optimal_hour={genome.optimal_hour}, collaboration_score={genome.collaboration_score}")
        print(f"genome summary: {genome.summary}")

    print("\nDone.")
    print(f"  Login: {STUDENT_EMAIL} / {STUDENT_PASSWORD}")
    print(f"  Subject: {SUBJECT_NAME} ({SUBJECT_CODE})")


if __name__ == "__main__":
    asyncio.run(seed())
