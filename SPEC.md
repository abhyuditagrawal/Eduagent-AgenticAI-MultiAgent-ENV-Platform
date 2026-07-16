# EduAgent — Multi-Agent AI Educational Ecosystem
## Full Project Specification

---

## 1. Vision

EduAgent is a **multi-agent, full-stack educational platform** that provides students with a suite of six specialised AI agents — all sharing a unified knowledge layer (RAG vector store, concept graph, and persistent student state). Unlike single-purpose chatbot projects, EduAgent is an **ecosystem**: every agent reads from and writes to the same student model, so the experience improves across all agents the more a student uses any one of them.

---

## 2. Core Agents

| # | Agent Name | Role | Key Differentiator |
|---|-----------|------|-------------------|
| 1 | **Concept QA Agent** | Answers conceptual doubts via RAG over ingested course material | Adaptive depth — checks student's concept-graph confidence before answering; fills prerequisite gaps first |
| 2 | **Exam Predictor Agent** | Analyses past papers + syllabus weighting to predict likely exam topics and generate targeted practice sets | Pattern mining across years; weighted topic heatmaps |
| 3 | **Weak-Point Tracker Agent** | Continuously monitors student state to surface concepts with decaying confidence or repeated errors | Spaced-repetition scheduling (SM-2 variant); proactive nudges |
| 4 | **Protégé Agent** | Student must *teach* a concept to this agent; agent deliberately asks naive/tricky follow-ups to test depth of understanding | Feynman Technique operationalised; rubric-graded explanations |
| 5 | **Oral Viva Agent** | Simulates a viva-voce examiner — asks questions, probes answers, gives structured feedback | Adjustable difficulty ladder; tracks "examiner" vs "student" turns |
| 6 | **Essay / Assignment Critique Agent** | Accepts long-form text (essays, reports, code explanations) and returns structured critique with rubric scoring | Section-level feedback; citation checking against ingested material |

---

## 3. Shared Data Layer

### 3.1 Content Store (Vector DB — Qdrant)
- **Purpose**: Chunked, embedded course material for RAG retrieval.
- **Namespacing**: One Qdrant *collection* per subject (e.g. `msa`, `hci`, `cybersecurity`, `ml`).
- **Ingestion pipeline**: PDF → text extraction (PyMuPDF) → semantic chunking (500-token chunks, 50-token overlap) → embedding (all-MiniLM-L6-v2 via sentence-transformers) → upsert into Qdrant with metadata `{subject, chapter, page, source_file}`.

### 3.2 Concept Graph (PostgreSQL + adjacency table)
- **Nodes**: `concepts` table — `(id, subject_id, name, description, difficulty_tier)`.
- **Edges**: `concept_prerequisites` table — `(concept_id, prerequisite_id, strength)`.
- **Population**: One-time LLM extraction pass over syllabus/TOC of each subject; manually reviewed.

### 3.3 Student State Store (PostgreSQL)
- **Table `student_concepts`**: `(student_id, concept_id, confidence_score 0-1, attempts, correct_count, last_seen_at, next_review_at)`.
- **Written to** by every agent after every meaningful interaction.
- **Read by** every agent before generating a response (personalisation).

---

## 4. Orchestrator

- **Framework**: LangGraph (graph-based multi-agent orchestration).
- **Behaviour**: Receives student message → classifies intent (one of: `conceptual_doubt`, `exam_prep`, `weak_points`, `teach_me`, `viva`, `critique`, `general`) → routes to the matching agent sub-graph → returns agent response + writes to student state.
- **Fallback**: If intent is ambiguous, orchestrator asks a one-line clarifying question rather than guessing.

---

## 5. Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| **Frontend** | Next.js 14 (App Router) + TailwindCSS + shadcn/ui | Modern, fast, great DX |
| **Icons** | Lucide React | Clean, consistent |
| **State management** | Zustand | Lightweight |
| **Backend API** | FastAPI (Python 3.11+) | Async, typing, OpenAPI docs auto-generated |
| **LLM** | Google Gemini 2.0 Flash (free tier) / Gemini 1.5 Flash | Free, fast, 1M context, tool-use support |
| **Orchestration** | LangGraph | Graph-based agent routing, state machines |
| **Vector DB** | Qdrant (Docker, self-hosted) | Free, dashboard UI, good Python SDK |
| **Relational DB** | PostgreSQL 16 (Docker) | Robust, free |
| **ORM** | SQLAlchemy 2.0 + Alembic migrations | Industry standard |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) — local | Free, no API cost, 384-dim |
| **PDF parsing** | PyMuPDF (fitz) | Fast, reliable |
| **Auth** | NextAuth.js (credentials provider → FastAPI) | Multi-user, JWT |
| **Containerisation** | Docker Compose | One command to run everything |
| **Deployment** | Railway / Render (stretch) | Free tiers available |

---

## 6. User Flows

### 6.1 Onboarding
1. Student signs up (email + password).
2. Student selects enrolled subjects from available list.
3. System bootstraps empty `student_concepts` rows for every concept in selected subjects.

### 6.2 Main Chat Interface
- Single chat window with an **agent indicator** showing which agent is currently handling the conversation.
- **Agent trace panel** (collapsible sidebar) showing: orchestrator routing decision, retrieved RAG chunks, concept graph traversal, confidence score updates. This is the "wow factor" for capstone grading.
- Students can also explicitly select an agent via a toolbar (e.g. click "Viva Mode" to force the viva agent).

### 6.3 Dashboard
- **Concept mastery heatmap** per subject (reads from `student_concepts`).
- **Weak points list** with one-click "Review this concept" action.
- **Exam readiness score** per subject.
- **Study streak / activity timeline**.

---

## 7. API Design (Key Endpoints)

```
POST   /api/auth/register
POST   /api/auth/login
GET    /api/auth/me

GET    /api/subjects
POST   /api/subjects/{id}/enroll

POST   /api/chat                  ← main entry; body: {message, conversation_id?, agent_override?}
GET    /api/chat/history           ← paginated
GET    /api/chat/conversations/{id}

GET    /api/dashboard/mastery      ← concept heatmap data
GET    /api/dashboard/weak-points
GET    /api/dashboard/exam-readiness
GET    /api/dashboard/activity

POST   /api/ingest/upload          ← admin: upload PDF for a subject
GET    /api/ingest/status/{job_id}

GET    /api/concepts/{subject_id}  ← concept graph for a subject
```

---

## 8. Non-Functional Requirements

- **Response latency**: < 5s for simple QA, < 15s for complex multi-step agent tasks.
- **Concurrency**: Must handle 5+ simultaneous users without crashing (capstone demo reality).
- **Data persistence**: All student state and chat history survives server restarts.
- **Observability**: Structured logging (structlog) with correlation IDs per request.
- **Testing**: Unit tests for agent logic, integration tests for API endpoints, E2E smoke test.

---

## 9. Evaluation Plan (Capstone Report)

| Metric | How measured |
|--------|-------------|
| Retrieval quality | Manual relevance scoring on 50 sample queries per subject |
| Agent routing accuracy | 100-query intent classification test set, measure F1 |
| Student model accuracy | Pre/post quiz comparison on 10 pilot users |
| System latency | p50/p95 response times logged over demo session |
| User satisfaction | SUS (System Usability Scale) questionnaire on 10 users |

---

## 10. Repository Structure (Target)

```
Capstone-AgenticAI-Educational/
├── SPEC.md
├── ARCHITECTURE.md
├── README.md
├── docker-compose.yml
├── .env.example
├── phases/                    ← Devin phase prompts
│   ├── PHASE-1.md
│   ├── PHASE-2.md
│   ├── PHASE-3.md
│   ├── PHASE-4.md
│   ├── PHASE-5.md
│   └── PHASE-6.md
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/           ← SQLAlchemy models
│   │   ├── schemas/          ← Pydantic schemas
│   │   ├── routers/          ← FastAPI routers
│   │   ├── services/         ← Business logic
│   │   ├── agents/           ← LangGraph agent definitions
│   │   │   ├── orchestrator.py
│   │   │   ├── concept_qa.py
│   │   │   ├── exam_predictor.py
│   │   │   ├── weak_point_tracker.py
│   │   │   ├── protege.py
│   │   │   ├── viva.py
│   │   │   └── critique.py
│   │   ├── rag/              ← Ingestion, retrieval, embedding
│   │   └── utils/
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── hooks/
│   │   └── stores/
│   └── Dockerfile
└── docs/
    └── sample-pdfs/          ← Demo course material
```
