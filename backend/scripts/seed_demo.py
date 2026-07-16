"""
Demo seed script for EduAgent capstone presentation.

Seeds the database with realistic demo data:
- 4 subjects with concepts and prerequisites
- 1 demo student account (demo@eduagent.com / demo123)
- Pre-populated student concepts with varied confidence scores
- Sample conversations and messages
- Realistic activity data for past 30 days

Run with: python -m scripts.seed_demo
"""

import asyncio
import uuid
import random
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.user import User
from app.models.subject import Subject
from app.models.concept import Concept, ConceptPrerequisite
from app.models.student import Enrollment, StudentConcept
from app.models.chat import Conversation, Message
from app.services.auth import hash_password

# Demo concepts per subject
DEMO_CONCEPTS = {
    "ML": {
        "Chapter 1: Foundations": [
            ("Linear Algebra Basics", 1),
            ("Probability & Statistics", 1),
            ("Gradient Descent", 2),
        ],
        "Chapter 2: Supervised Learning": [
            ("Linear Regression", 1),
            ("Logistic Regression", 2),
            ("Decision Trees", 2),
            ("Random Forests", 2),
            ("Support Vector Machines", 3),
        ],
        "Chapter 3: Neural Networks": [
            ("Perceptrons", 2),
            ("Backpropagation", 3),
            ("Convolutional Neural Networks", 3),
            ("Recurrent Neural Networks", 3),
        ],
        "Chapter 4: Unsupervised Learning": [
            ("K-Means Clustering", 2),
            ("PCA", 2),
            ("Autoencoders", 3),
        ],
    },
    "HCI": {
        "Chapter 1: Fundamentals": [
            ("Usability Principles", 1),
            ("User-Centered Design", 1),
            ("Heuristic Evaluation", 2),
        ],
        "Chapter 2: Design Methods": [
            ("Prototyping", 1),
            ("Wireframing", 1),
            ("A/B Testing", 2),
            ("Task Analysis", 2),
        ],
        "Chapter 3: Evaluation": [
            ("Cognitive Walkthrough", 2),
            ("SUS Questionnaire", 2),
            ("Think-Aloud Protocol", 2),
            ("Eye Tracking", 3),
        ],
        "Chapter 4: Advanced Topics": [
            ("Accessibility (WCAG)", 2),
            ("Mobile UX", 2),
            ("Voice Interfaces", 3),
        ],
    },
    "CS": {
        "Chapter 1: Foundations": [
            ("CIA Triad", 1),
            ("Threat Modeling", 2),
            ("Risk Assessment", 2),
        ],
        "Chapter 2: Cryptography": [
            ("Symmetric Encryption", 1),
            ("Asymmetric Encryption", 2),
            ("Hash Functions", 2),
            ("Digital Signatures", 2),
            ("PKI", 3),
        ],
        "Chapter 3: Network Security": [
            ("Firewalls", 1),
            ("IDS/IPS", 2),
            ("VPN", 2),
            ("TLS/SSL", 3),
        ],
        "Chapter 4: Application Security": [
            ("SQL Injection", 2),
            ("XSS", 2),
            ("CSRF", 2),
            ("OWASP Top 10", 3),
        ],
    },
    "MSA": {
        "Chapter 1: Fundamentals": [
            ("Monolith vs Microservices", 1),
            ("Service Decomposition", 2),
            ("API Design", 2),
        ],
        "Chapter 2: Communication": [
            ("REST APIs", 1),
            ("gRPC", 2),
            ("Message Queues", 2),
            ("Event-Driven Architecture", 3),
        ],
        "Chapter 3: Infrastructure": [
            ("Docker Containers", 1),
            ("Kubernetes", 3),
            ("Service Mesh", 3),
            ("CI/CD Pipelines", 2),
        ],
        "Chapter 4: Patterns": [
            ("Circuit Breaker", 2),
            ("Saga Pattern", 3),
            ("CQRS", 3),
            ("API Gateway", 2),
        ],
    },
}

DEMO_QUESTIONS = [
    ("What is gradient descent and how does it work?", "concept_qa"),
    ("Can you explain backpropagation step by step?", "concept_qa"),
    ("What topics should I focus on for the exam?", "exam_predictor"),
    ("Give me practice questions on neural networks.", "exam_predictor"),
    ("What are my weakest areas in ML?", "weak_point_tracker"),
    ("How can I improve my understanding of SVMs?", "concept_qa"),
    ("Explain the difference between L1 and L2 regularization.", "concept_qa"),
    ("Quiz me on decision trees.", "exam_predictor"),
]


async def seed_demo():
    async with async_session() as db:
        # Check if demo user already exists
        result = await db.execute(
            select(User).where(User.email == "demo@eduagent.com")
        )
        existing = result.scalar_one_or_none()
        if existing:
            print("Demo data already seeded. Skipping.")
            return

        print("Seeding demo data...")

        # Create demo student
        demo_user = User(
            id=uuid.uuid4(),
            email="demo@eduagent.com",
            full_name="Demo Student",
            hashed_password=hash_password("demo123"),
            role="student",
        )
        db.add(demo_user)
        await db.flush()
        print(f"  Created demo user: demo@eduagent.com / demo123")

        # Get existing subjects
        subject_result = await db.execute(select(Subject))
        subjects = {s.code: s for s in subject_result.scalars().all()}

        for code, chapters in DEMO_CONCEPTS.items():
            subject = subjects.get(code)
            if not subject:
                print(f"  Subject {code} not found, skipping")
                continue

            # Enroll demo user
            enrollment = Enrollment(student_id=demo_user.id, subject_id=subject.id)
            db.add(enrollment)

            concept_map = {}

            for chapter_name, concept_list in chapters.items():
                for concept_name, difficulty in concept_list:
                    # Check if concept exists
                    existing_concept = await db.execute(
                        select(Concept).where(
                            Concept.subject_id == subject.id,
                            Concept.name == concept_name,
                        )
                    )
                    concept = existing_concept.scalar_one_or_none()

                    if not concept:
                        concept = Concept(
                            id=uuid.uuid4(),
                            subject_id=subject.id,
                            name=concept_name,
                            chapter=chapter_name,
                            difficulty_tier=difficulty,
                        )
                        db.add(concept)
                        await db.flush()

                    concept_map[concept_name] = concept

                    # Create student concept with varied confidence
                    base_conf = random.choice([0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 0.95])
                    if difficulty >= 3:
                        base_conf = min(base_conf, 0.5)
                    attempts = random.randint(1, 15)
                    last_seen = datetime.now(timezone.utc) - timedelta(
                        days=random.randint(0, 20)
                    )

                    sc = StudentConcept(
                        student_id=demo_user.id,
                        concept_id=concept.id,
                        confidence_score=base_conf,
                        attempts=attempts,
                        last_seen_at=last_seen,
                        next_review_at=last_seen + timedelta(days=random.randint(1, 14)),
                        easiness_factor=2.5 + random.uniform(-0.5, 0.5),
                        repetitions=random.randint(0, 5),
                        sm2_interval=random.randint(1, 30),
                    )
                    db.add(sc)

            # Add some prerequisite relationships
            names = list(concept_map.keys())
            for i in range(min(5, len(names) - 1)):
                src = concept_map[names[i]]
                tgt = concept_map[names[min(i + 2, len(names) - 1)]]
                if src.id != tgt.id:
                    existing_prereq = await db.execute(
                        select(ConceptPrerequisite).where(
                            ConceptPrerequisite.concept_id == tgt.id,
                            ConceptPrerequisite.prerequisite_id == src.id,
                        )
                    )
                    if not existing_prereq.scalar_one_or_none():
                        prereq = ConceptPrerequisite(
                            concept_id=tgt.id,
                            prerequisite_id=src.id,
                            strength=round(random.uniform(0.5, 1.0), 2),
                        )
                        db.add(prereq)

            print(f"  Seeded {len(concept_map)} concepts for {code}")

            # Create sample conversations
            for q_text, agent_type in random.sample(DEMO_QUESTIONS, min(4, len(DEMO_QUESTIONS))):
                conv = Conversation(
                    id=uuid.uuid4(),
                    student_id=demo_user.id,
                    subject_id=subject.id,
                    title=q_text[:80],
                    created_at=datetime.now(timezone.utc) - timedelta(
                        days=random.randint(0, 25)
                    ),
                )
                db.add(conv)
                await db.flush()

                # User message
                user_msg = Message(
                    id=uuid.uuid4(),
                    conversation_id=conv.id,
                    role="user",
                    content=q_text,
                    created_at=conv.created_at,
                )
                db.add(user_msg)

                # Assistant message
                assistant_msg = Message(
                    id=uuid.uuid4(),
                    conversation_id=conv.id,
                    role="assistant",
                    content=f"This is a demo response for: {q_text}",
                    agent_type=agent_type,
                    created_at=conv.created_at + timedelta(seconds=5),
                )
                db.add(assistant_msg)

        await db.commit()
        print("Demo data seeded successfully!")
        print("\n  Login: demo@eduagent.com / demo123")


if __name__ == "__main__":
    asyncio.run(seed_demo())
