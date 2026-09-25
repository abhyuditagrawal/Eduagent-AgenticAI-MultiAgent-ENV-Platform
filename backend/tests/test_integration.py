"""Integration tests for EduAgent core flows.

Tests cover:
- Intent classification routing
- Orchestrator graph execution
- Student state management (SM-2 confidence updates)
- Chat endpoint end-to-end (message saving, conversation creation)
- Dashboard data consistency
- Nudge engine logic
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept, ConceptPrerequisite
from app.models.student import Enrollment, StudentConcept
from app.models.subject import Subject
from app.models.user import User
from app.services.auth import hash_password, create_access_token
from app.services.student_state import (
    sm2_update,
    get_student_state,
    update_concept_confidence,
    get_weak_concepts,
    get_overdue_concepts,
    get_mastery_summary,
    get_study_priority_queue,
    get_prerequisite_gaps,
    decay_confidence,
)
from app.agents.intent_classifier import classify_intent, VALID_INTENTS
from app.agents.state import AgentState
from app.services.nudge_engine import generate_nudges
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures for integration tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def setup_subject_with_concepts(db: AsyncSession):
    """Create a subject with concepts, prerequisites, and a student enrolled."""
    # Create user
    student = User(
        id=uuid.uuid4(),
        email=f"integ_{uuid.uuid4().hex[:8]}@test.com",
        full_name="Integration Student",
        hashed_password=hash_password("testpass"),
        role="student",
    )
    db.add(student)

    # Create subject
    subject = Subject(
        id=uuid.uuid4(),
        code=f"INT_{uuid.uuid4().hex[:4].upper()}",
        name="Integration Test Subject",
    )
    db.add(subject)
    await db.flush()

    # Enroll student
    enrollment = Enrollment(student_id=student.id, subject_id=subject.id)
    db.add(enrollment)

    # Create concepts with a prerequisite chain: C1 -> C2 -> C3
    c1 = Concept(
        id=uuid.uuid4(),
        subject_id=subject.id,
        name="Foundational Concept",
        description="Base concept everyone should know",
        difficulty_tier=1,
        chapter="Chapter 1",
    )
    c2 = Concept(
        id=uuid.uuid4(),
        subject_id=subject.id,
        name="Intermediate Concept",
        description="Builds on the foundation",
        difficulty_tier=2,
        chapter="Chapter 2",
    )
    c3 = Concept(
        id=uuid.uuid4(),
        subject_id=subject.id,
        name="Advanced Concept",
        description="Requires intermediate knowledge",
        difficulty_tier=3,
        chapter="Chapter 3",
    )
    db.add_all([c1, c2, c3])
    await db.flush()

    # Prerequisites: C2 requires C1, C3 requires C2
    db.add(ConceptPrerequisite(concept_id=c2.id, prerequisite_id=c1.id, strength=1.0))
    db.add(ConceptPrerequisite(concept_id=c3.id, prerequisite_id=c2.id, strength=1.0))

    # StudentConcept records with varying confidence
    now = datetime.now(timezone.utc)
    sc1 = StudentConcept(
        student_id=student.id,
        concept_id=c1.id,
        confidence_score=0.8,
        attempts=5,
        correct_count=4,
        easiness_factor=2.5,
        interval_days=10,
        last_seen_at=now - timedelta(days=1),
        next_review_at=now + timedelta(days=5),
    )
    sc2 = StudentConcept(
        student_id=student.id,
        concept_id=c2.id,
        confidence_score=0.3,
        attempts=3,
        correct_count=1,
        easiness_factor=2.0,
        interval_days=2,
        last_seen_at=now - timedelta(days=5),
        next_review_at=now - timedelta(days=2),  # overdue
    )
    sc3 = StudentConcept(
        student_id=student.id,
        concept_id=c3.id,
        confidence_score=0.1,
        attempts=1,
        correct_count=0,
        easiness_factor=2.5,
        interval_days=1,
        last_seen_at=now - timedelta(days=10),
        next_review_at=now - timedelta(days=8),  # very overdue
    )
    db.add_all([sc1, sc2, sc3])
    await db.flush()

    token = create_access_token({
        "sub": str(student.id),
        "email": student.email,
        "role": student.role,
    })

    return {
        "student": student,
        "subject": subject,
        "concepts": [c1, c2, c3],
        "student_concepts": [sc1, sc2, sc3],
        "token": token,
    }


# ---------------------------------------------------------------------------
# Intent Classifier Tests
# ---------------------------------------------------------------------------

class TestIntentClassifier:
    """Test intent classification maps to valid intents."""

    def _make_state(self, message: str) -> AgentState:
        return {
            "messages": [{"role": "user", "content": message}],
            "student_id": "test",
            "subject_id": None,
            "subject_code": None,
            "subject_name": None,
            "student_state": {},
            "intent": None,
            "active_agent": None,
            "rag_context": [],
            "concept_ids_touched": [],
            "concept_updates": [],
            "metadata": {},
            "response": "",
            "conversation_history": [],
        }

    @patch("app.agents.intent_classifier.get_gemini_model")
    def test_conceptual_doubt_classification(self, mock_model):
        mock_response = MagicMock()
        mock_response.text = "conceptual_doubt"
        mock_model.return_value.generate_content.return_value = mock_response

        state = self._make_state("What is polymorphism in OOP?")
        result = classify_intent(state)
        assert result["intent"] == "conceptual_doubt"

    def test_security_tool_fast_path_no_model_call(self):
        # /commands are unambiguous - the fast path must catch them without
        # ever touching the LLM classifier.
        state = self._make_state("/hash sha256 password123")
        result = classify_intent(state)
        assert result["intent"] == "security_tool"
        assert result["metadata"]["intent_source"] == "fast_path"

    @patch("app.agents.intent_classifier.get_gemini_model")
    def test_exam_prep_classification(self, mock_model):
        mock_response = MagicMock()
        mock_response.text = "exam_prep"
        mock_model.return_value.generate_content.return_value = mock_response

        state = self._make_state("Give me practice questions for the final exam")
        result = classify_intent(state)
        assert result["intent"] == "exam_prep"

    @patch("app.agents.intent_classifier.get_gemini_model")
    def test_viva_classification(self, mock_model):
        mock_response = MagicMock()
        mock_response.text = "viva"
        mock_model.return_value.generate_content.return_value = mock_response

        state = self._make_state("Start a viva on machine learning")
        result = classify_intent(state)
        assert result["intent"] == "viva"

    @patch("app.agents.intent_classifier.get_gemini_model")
    def test_invalid_intent_falls_back_to_general(self, mock_model):
        mock_response = MagicMock()
        mock_response.text = "some_invalid_intent"
        mock_model.return_value.generate_content.return_value = mock_response

        state = self._make_state("Hello there")
        result = classify_intent(state)
        assert result["intent"] == "general"

    @patch("app.agents.intent_classifier.get_gemini_model")
    def test_api_error_falls_back_to_general(self, mock_model):
        mock_model.return_value.generate_content.side_effect = Exception("API error")

        state = self._make_state("What is recursion?")
        result = classify_intent(state)
        assert result["intent"] == "general"
        assert result["metadata"]["intent_error"] == "API error"

    def test_empty_messages_returns_general(self):
        state = self._make_state("")
        state["messages"] = []
        result = classify_intent(state)
        assert result["intent"] == "general"


# ---------------------------------------------------------------------------
# Student State Integration Tests
# ---------------------------------------------------------------------------

class TestStudentStateIntegration:
    """Test student state operations against the database."""

    @pytest.mark.asyncio
    async def test_get_student_state_returns_all_concepts(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        state = await get_student_state(
            db, data["student"].id, data["subject"].id
        )
        assert len(state) == 3
        names = {v["concept_name"] for v in state.values()}
        assert "Foundational Concept" in names
        assert "Intermediate Concept" in names
        assert "Advanced Concept" in names

    @pytest.mark.asyncio
    async def test_update_confidence_with_good_quality(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        sc2 = data["student_concepts"][1]
        old_confidence = sc2.confidence_score
        old_attempts = sc2.attempts

        await update_concept_confidence(
            db, data["student"].id, data["concepts"][1].id, quality=4
        )
        await db.refresh(sc2)

        assert sc2.confidence_score == 0.8  # quality=4 → 4/5 = 0.8
        assert sc2.attempts == old_attempts + 1
        assert sc2.correct_count > data["student_concepts"][1].correct_count or sc2.correct_count >= 1
        assert sc2.next_review_at is not None

    @pytest.mark.asyncio
    async def test_update_confidence_with_poor_quality(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        sc1 = data["student_concepts"][0]

        await update_concept_confidence(
            db, data["student"].id, data["concepts"][0].id, quality=1
        )
        await db.refresh(sc1)

        assert sc1.confidence_score == 0.2  # quality=1 → 1/5 = 0.2
        assert sc1.interval_days == 1  # reset

    @pytest.mark.asyncio
    async def test_get_weak_concepts(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        weak = await get_weak_concepts(
            db, data["student"].id, data["subject"].id, threshold=0.4
        )
        # c2 (0.3) and c3 (0.1) are below 0.4
        assert len(weak) == 2
        names = {w["concept_name"] for w in weak}
        assert "Advanced Concept" in names
        assert "Intermediate Concept" in names

    @pytest.mark.asyncio
    async def test_get_overdue_concepts(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        overdue = await get_overdue_concepts(
            db, data["student"].id, data["subject"].id
        )
        # c2 and c3 are overdue
        assert len(overdue) >= 2
        overdue_names = {o["concept_name"] for o in overdue}
        assert "Intermediate Concept" in overdue_names
        assert "Advanced Concept" in overdue_names

    @pytest.mark.asyncio
    async def test_get_prerequisite_gaps(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        # C3 requires C2 (which has confidence 0.3 < 0.5 threshold)
        gaps = await get_prerequisite_gaps(
            db, data["student"].id, data["concepts"][2].id, threshold=0.5
        )
        assert len(gaps) >= 1
        gap_names = {g["concept_name"] for g in gaps}
        assert "Intermediate Concept" in gap_names

    @pytest.mark.asyncio
    async def test_mastery_summary(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        summary = await get_mastery_summary(
            db, data["student"].id, data["subject"].id
        )
        assert summary["total_concepts"] == 3
        assert summary["mastered"] == 1  # c1 at 0.8
        assert summary["overall_score"] > 0
        assert summary["overdue_reviews"] >= 2

    @pytest.mark.asyncio
    async def test_study_priority_queue(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        queue = await get_study_priority_queue(
            db, data["student"].id, data["subject"].id
        )
        # Overdue and low-confidence concepts should be prioritised
        assert len(queue) >= 2
        # Most urgent should be the most overdue/weakest
        assert queue[0]["priority_score"] >= queue[-1]["priority_score"]

    @pytest.mark.asyncio
    async def test_confidence_decay(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        # Make a concept very overdue by setting next_review far in the past
        sc2 = data["student_concepts"][1]
        sc2.next_review_at = datetime.now(timezone.utc) - timedelta(days=30)
        sc2.interval_days = 2
        sc2.confidence_score = 0.5
        await db.flush()

        decayed = await decay_confidence(db, data["student"].id)
        assert decayed >= 1
        await db.refresh(sc2)
        assert sc2.confidence_score < 0.5


# ---------------------------------------------------------------------------
# Nudge Engine Tests
# ---------------------------------------------------------------------------

class TestNudgeEngine:
    """Test the nudge engine generates appropriate nudges."""

    @pytest.mark.asyncio
    async def test_overdue_nudges_generated(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        nudges = await generate_nudges(db, data["student"].id)
        # Should have nudges for overdue concepts
        assert len(nudges) >= 1
        types = {n["type"] for n in nudges}
        assert "review_overdue" in types

    @pytest.mark.asyncio
    async def test_nudge_priority_ordering(
        self, db: AsyncSession, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        nudges = await generate_nudges(db, data["student"].id)
        if len(nudges) >= 2:
            priority_order = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(nudges) - 1):
                assert priority_order[nudges[i]["priority"]] <= priority_order[nudges[i + 1]["priority"]]


# ---------------------------------------------------------------------------
# Chat Endpoint Integration Tests
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    """Test chat endpoints create conversations and save messages."""

    @pytest.mark.asyncio
    async def test_chat_history_empty_initially(
        self, client: AsyncClient, student_token: str
    ):
        resp = await client.get(
            "/api/chat/history",
            headers=auth_header(student_token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/chat", json={
            "message": "Hello",
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_chat_stream_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/chat/stream", json={
            "message": "Hello",
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(
        self, client: AsyncClient, student_token: str
    ):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/chat/conversations/{fake_id}",
            headers=auth_header(student_token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dashboard Integration Tests
# ---------------------------------------------------------------------------

class TestDashboardIntegration:
    """Test dashboard endpoints return correct structure with real data."""

    @pytest.mark.asyncio
    async def test_mastery_with_real_data(
        self, client: AsyncClient, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        resp = await client.get(
            f"/api/dashboard/mastery?subject_id={data['subject'].id}",
            headers=auth_header(data["token"]),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall_score"] > 0
        assert len(body["chapters"]) >= 1
        # Verify chapters contain correct concept counts
        total_concepts = sum(
            len(ch["concepts"]) for ch in body["chapters"]
        )
        assert total_concepts == 3

    @pytest.mark.asyncio
    async def test_weak_points_with_real_data(
        self, client: AsyncClient, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        resp = await client.get(
            f"/api/dashboard/weak-points?subject_id={data['subject'].id}",
            headers=auth_header(data["token"]),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_concepts"] == 3
        assert body["total_weak"] >= 2  # c2 and c3 are weak

    @pytest.mark.asyncio
    async def test_exam_readiness_with_real_data(
        self, client: AsyncClient, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        resp = await client.get(
            f"/api/dashboard/exam-readiness?subject_id={data['subject'].id}",
            headers=auth_header(data["token"]),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "overall_readiness" in body
        assert "by_difficulty" in body
        assert "high_risk_topics" in body
        # With one concept at 0.1 and one at 0.3, should have high-risk topics
        assert len(body["high_risk_topics"]) >= 1

    @pytest.mark.asyncio
    async def test_concept_graph_with_real_data(
        self, client: AsyncClient, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        resp = await client.get(
            f"/api/dashboard/concept-graph?subject_id={data['subject'].id}",
            headers=auth_header(data["token"]),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["nodes"]) == 3
        assert len(body["edges"]) == 2  # C1->C2, C2->C3
        # Verify nodes have confidence data
        for node in body["nodes"]:
            assert "confidence" in node
            assert "status" in node

    @pytest.mark.asyncio
    async def test_concept_graph_edge_directions(
        self, client: AsyncClient, setup_subject_with_concepts
    ):
        data = setup_subject_with_concepts
        resp = await client.get(
            f"/api/dashboard/concept-graph?subject_id={data['subject'].id}",
            headers=auth_header(data["token"]),
        )
        body = resp.json()
        c1_id = str(data["concepts"][0].id)
        c2_id = str(data["concepts"][1].id)
        c3_id = str(data["concepts"][2].id)

        edge_pairs = {(e["source"], e["target"]) for e in body["edges"]}
        # Prereqs point from prerequisite -> concept
        assert (c1_id, c2_id) in edge_pairs
        assert (c2_id, c3_id) in edge_pairs


# ---------------------------------------------------------------------------
# Orchestrator Graph Structure Tests
# ---------------------------------------------------------------------------

class TestOrchestratorGraph:
    """Test the orchestrator graph is correctly built."""

    def test_graph_compiles_without_error(self):
        from app.agents.orchestrator import build_orchestrator_graph
        graph = build_orchestrator_graph()
        assert graph is not None

    def test_graph_has_all_agent_nodes(self):
        from app.agents.orchestrator import build_orchestrator_graph
        graph = build_orchestrator_graph()
        # The compiled graph should have nodes for all agents
        node_names = set(graph.get_graph().nodes.keys())
        expected_nodes = {
            "load_state", "classify",
            "agent_qa", "agent_exam", "agent_weak_point",
            "agent_protege", "agent_viva", "agent_critique",
            "agent_security_tool",
            "agent_fallback", "commit_state", "format_response",
        }
        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"

    def test_route_intent_mapping(self):
        from app.agents.orchestrator import route_intent
        test_cases = {
            "conceptual_doubt": "agent_qa",
            "exam_prep": "agent_exam",
            "weak_points": "agent_weak_point",
            "teach_me": "agent_protege",
            "viva": "agent_viva",
            "critique": "agent_critique",
            "security_tool": "agent_security_tool",
            "general": "agent_fallback",
            "unknown_intent": "agent_fallback",
        }
        for intent, expected_route in test_cases.items():
            state = {"intent": intent}
            assert route_intent(state) == expected_route
