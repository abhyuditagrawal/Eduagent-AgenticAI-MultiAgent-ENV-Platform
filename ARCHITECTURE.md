# EduAgent — System Architecture

---

## 1. High-Level Architecture Diagram (Text)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 14)                        │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────────┐  │
│  │  Auth UI  │  │  Chat Window │  │ Dashboard │  │  Admin Panel  │  │
│  └──────────┘  └──────┬───────┘  └─────┬─────┘  └───────┬───────┘  │
│                       │                │                 │          │
│              Zustand Store + React Query (API layer)                │
└───────────────────────┼────────────────┼─────────────────┼──────────┘
                        │ HTTP/SSE       │ HTTP            │ HTTP
┌───────────────────────┼────────────────┼─────────────────┼──────────┐
│                     BACKEND (FastAPI)                                │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                     API Router Layer                           │  │
│  │  /auth  /chat  /dashboard  /ingest  /concepts  /subjects      │  │
│  └────────────────────────┬──────────────────────────────────────┘  │
│                           │                                         │
│  ┌────────────────────────▼──────────────────────────────────────┐  │
│  │                   ORCHESTRATOR (LangGraph)                     │  │
│  │                                                                │  │
│  │   Intent Classifier ──► Router                                 │  │
│  │        │                  │                                     │  │
│  │   ┌────┼──────┬───────┬───┼───────┬──────────┬──────────┐      │  │
│  │   ▼    ▼      ▼       ▼   ▼       ▼          ▼          ▼      │  │
│  │  QA  Exam   Weak   Protégé Viva  Critique  General             │  │
│  │ Agent Pred  Point   Agent  Agent  Agent    Fallback             │  │
│  │       Agent Tracker                                             │  │
│  └───┬────┬──────┬───────┬────┬──────┬─────────────────────────┘  │
│      │    │      │       │    │      │                              │
│  ┌───▼────▼──────▼───────▼────▼──────▼─────────────────────────┐  │
│  │              SHARED DATA LAYER                                │  │
│  │                                                                │  │
│  │  ┌─────────────┐  ┌────────────────┐  ┌───────────────────┐   │  │
│  │  │  Qdrant     │  │  PostgreSQL    │  │  PostgreSQL       │   │  │
│  │  │  (Vectors)  │  │  (Concept      │  │  (Student State   │   │  │
│  │  │             │  │   Graph)       │  │   + Chat History) │   │  │
│  │  └─────────────┘  └────────────────┘  └───────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Models

### 2.1 PostgreSQL Schema

```sql
-- ============================================================
-- AUTH & USERS
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(20) DEFAULT 'student',  -- 'student' | 'admin'
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- SUBJECTS & CONCEPTS (Concept Graph)
-- ============================================================

CREATE TABLE subjects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(20) UNIQUE NOT NULL,   -- e.g. 'MSA', 'HCI'
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE concepts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id      UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    difficulty_tier SMALLINT DEFAULT 1,  -- 1=foundational, 2=intermediate, 3=advanced
    chapter         VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(subject_id, name)
);

CREATE TABLE concept_prerequisites (
    concept_id      UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    prerequisite_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    strength        REAL DEFAULT 1.0,  -- 0.0-1.0, how strongly required
    PRIMARY KEY (concept_id, prerequisite_id),
    CHECK (concept_id != prerequisite_id)
);

-- ============================================================
-- STUDENT STATE
-- ============================================================

CREATE TABLE enrollments (
    student_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id  UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (student_id, subject_id)
);

CREATE TABLE student_concepts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    concept_id       UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    confidence_score REAL DEFAULT 0.0,          -- 0.0 to 1.0
    attempts         INTEGER DEFAULT 0,
    correct_count    INTEGER DEFAULT 0,
    last_seen_at     TIMESTAMPTZ,
    next_review_at   TIMESTAMPTZ,
    easiness_factor  REAL DEFAULT 2.5,          -- SM-2 algorithm
    interval_days    REAL DEFAULT 1.0,           -- SM-2 algorithm
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE(student_id, concept_id)
);

-- ============================================================
-- CHAT HISTORY
-- ============================================================

CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id  UUID REFERENCES subjects(id),
    title       VARCHAR(255),
    agent_type  VARCHAR(50),  -- last active agent
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,  -- 'user' | 'assistant' | 'system'
    content         TEXT NOT NULL,
    agent_type      VARCHAR(50),           -- which agent generated this
    metadata        JSONB DEFAULT '{}',    -- RAG chunks used, concept IDs touched, confidence deltas
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX idx_student_concepts_student ON student_concepts(student_id);
CREATE INDEX idx_student_concepts_review ON student_concepts(next_review_at);

-- ============================================================
-- INGESTION TRACKING
-- ============================================================

CREATE TABLE ingestion_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id  UUID NOT NULL REFERENCES subjects(id),
    filename    VARCHAR(255) NOT NULL,
    status      VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'processing' | 'completed' | 'failed'
    chunks      INTEGER DEFAULT 0,
    error       TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
```

### 2.2 Qdrant Collections

One collection per subject, created dynamically on ingestion:

```
Collection: "subject_{subject_code}"
  - Vector size: 384 (all-MiniLM-L6-v2)
  - Distance: Cosine
  - Payload fields:
    - subject_id: string
    - chapter: string
    - page: integer
    - source_file: string
    - chunk_index: integer
    - text: string (the raw chunk text for display)
```

---

## 3. Agent Architecture (LangGraph)

### 3.1 Orchestrator Graph

```python
# Pseudocode — actual implementation in backend/app/agents/orchestrator.py

StateGraph:
  State:
    messages: list[BaseMessage]
    student_id: str
    student_state: dict          # loaded from DB
    intent: str | None
    active_agent: str | None
    rag_context: list[str]
    concept_updates: list[dict]  # buffered confidence changes
    metadata: dict               # trace info for frontend

  Nodes:
    1. load_student_state    → reads student_concepts from DB
    2. classify_intent       → LLM call to determine intent
    3. route                 → conditional edge based on intent
    4. agent_*  (6 agents)   → each is a sub-graph
    5. update_student_state  → writes concept_updates back to DB
    6. format_response       → prepares final response + metadata

  Edges:
    START → load_student_state → classify_intent → route
    route →(conceptual_doubt)→ agent_qa
    route →(exam_prep)→ agent_exam
    route →(weak_points)→ agent_weak
    route →(teach_me)→ agent_protege
    route →(viva)→ agent_viva
    route →(critique)→ agent_critique
    route →(general)→ agent_qa  (fallback)
    agent_* → update_student_state → format_response → END
```

### 3.2 Individual Agent Pattern

Each agent follows the same skeleton:

```python
class AgentBase:
    """Every agent implements these three steps."""

    async def retrieve_context(self, query, subject_id, student_state):
        """RAG retrieval + concept graph lookup, filtered by student state."""
        ...

    async def reason(self, messages, context, student_state):
        """LLM call with agent-specific system prompt + tools."""
        ...

    async def update_scores(self, interaction_result) -> list[ConceptUpdate]:
        """Returns list of (concept_id, delta) pairs for the orchestrator to commit."""
        ...
```

### 3.3 Agent-Specific Tools

| Agent | Custom Tools |
|-------|-------------|
| Concept QA | `search_content(query, subject)`, `get_prerequisites(concept_id)` |
| Exam Predictor | `search_past_papers(subject, year_range)`, `get_topic_frequency(subject)` |
| Weak-Point Tracker | `get_weak_concepts(student_id, threshold)`, `schedule_review(student_id, concept_id)` |
| Protégé | `evaluate_explanation(student_text, concept_id)`, `ask_followup(depth)` |
| Viva | `generate_question(concept_id, difficulty)`, `evaluate_answer(answer, rubric)` |
| Critique | `search_content(query, subject)` (for citation checking), `score_section(text, rubric_dimension)` |

---

## 4. Streaming Architecture

- Backend uses **Server-Sent Events (SSE)** via FastAPI's `StreamingResponse`.
- The orchestrator yields partial tokens as the LLM generates them.
- Frontend consumes the SSE stream via `EventSource` API.
- Each SSE event has a `type` field: `token`, `agent_switch`, `rag_result`, `concept_update`, `done`.
- This lets the frontend show real-time agent trace updates in the side panel while the response streams.

---

## 5. SM-2 Spaced Repetition Algorithm

Used by the Weak-Point Tracker to schedule reviews:

```python
def sm2_update(quality: int, easiness: float, interval: float, repetitions: int):
    """
    quality: 0-5 (0=complete blackout, 5=perfect)
    Returns (new_easiness, new_interval, new_repetitions)
    """
    if quality >= 3:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = interval * easiness
        new_repetitions = repetitions + 1
    else:
        new_interval = 1
        new_repetitions = 0

    new_easiness = max(1.3, easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return new_easiness, new_interval, new_repetitions
```

---

## 6. Security

- Passwords hashed with **bcrypt** (passlib).
- JWT tokens (access + refresh) issued by FastAPI, verified by NextAuth on frontend.
- All API routes (except `/auth/*`) require valid JWT.
- File uploads validated: PDF only, max 50MB.
- SQL injection prevented by SQLAlchemy parameterised queries.
- CORS restricted to frontend origin.

---

## 7. Docker Compose Services

```yaml
services:
  postgres:     # PostgreSQL 16
  qdrant:       # Qdrant latest
  backend:      # FastAPI app
  frontend:     # Next.js app
```

All inter-service communication via Docker network. Environment variables in `.env` file.
