# EduAgent — Multi-Agent AI Educational Ecosystem

> A full-stack, multi-agent AI platform that provides students with six specialised educational agents sharing a unified knowledge layer (RAG vector store, concept graph, and persistent student state).

EduAgent is designed as a unified learning companion that adapts to each student's knowledge state. Instead of juggling multiple tools for Q&A, exam prep, revision, and self-assessment, students interact with a single platform where six AI agents collaborate through a shared data layer. The LangGraph orchestrator automatically routes each query to the right agent, while SM-2 spaced repetition ensures optimal review scheduling and the concept graph tracks prerequisite relationships across the entire curriculum.

## 🚀 Project Status

| Phase | Description | Status |
|-------|------------|--------|
| Phase 1 | Foundation: Scaffolding, DB, Auth, Ingestion, Basic RAG | ✅ Complete |
| Phase 2 | LangGraph Orchestrator + Concept QA + Exam Predictor | ✅ Complete |
| Phase 3 | Weak-Point Tracker + SSE Streaming + Spaced Repetition | ✅ Complete |
| Phase 4 | Protégé + Oral Viva + Essay Critique Agents | ✅ Complete |
| Phase 5 | Dashboard, Concept Graph Visualisation, Analytics | ✅ Complete |
| Phase 6 | Testing, Polish, Documentation, Deployment | ✅ Complete |

## Features

- **6 Specialised AI Agents** with automatic intent-based routing
- **Inter-Agent Collaboration** — agents consult each other's data (weak points, mastery) before responding
- **Real-time SSE Streaming** for token-by-token LLM responses
- **Interactive Concept Graph** visualisation with React Flow + dagre layout
- **Mastery Dashboard** with heatmaps, exam readiness gauge, activity timeline
- **SM-2 Spaced Repetition** with confidence decay and review nudges
- **Auto-Generated Flashcards** from conversations with SM-2 review scheduling
- **Smart Study Planner** — AI-generated personalised study schedules based on mastery + exam dates
- **Progress Report PDF Export** — downloadable PDF reports with mastery data
- **Voice Mode** for Viva agent — Web Speech API for speech-to-text input + text-to-speech output
- **Diagram/Image Understanding** — upload images for Gemini multimodal analysis
- **Live Study Groups** — WebSocket-based rooms with shared AI assistant
- **Learning Path Timeline** — chronological visualisation of learning journey
- **Custom Agent Builder** — admin can create agents with custom prompts and rubrics
- **Class-Level Analytics** — admin dashboard with aggregated mastery, weak concepts, agent performance
- **Redis Caching** for RAG queries and analytics
- **Concept Dependency Auto-Detection** from PDF content using LLM
- **Multi-turn Modes**: Protege teaching sessions, oral viva exams
- **Essay Critique** with rubric scoring and structured feedback
- **Dark Mode** with system preference detection
- **Onboarding Flow** for new students
- **Admin Panel** for subject/concept management and PDF upload

## 🤖 The Six Agents

| Agent | What it does |
|-------|-------------|
| **Concept QA** | Answers doubts via RAG; adapts depth based on student's concept confidence; fills prerequisite gaps first |
| **Exam Predictor** | Analyses syllabus + past papers to predict exam topics; generates practice questions |
| **Weak-Point Tracker** | Monitors student state; surfaces decaying/weak concepts; SM-2 spaced repetition scheduling |
| **Protégé** | Student teaches the AI (Feynman Technique); AI probes for gaps; rubric-graded evaluation |
| **Oral Viva** | Simulates viva-voce exam; difficulty ladder; structured per-question evaluation |
| **Essay Critique** | Structured section-level critique with rubric scoring and citation checking |

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, TailwindCSS, shadcn/ui v4 (base-ui), Zustand, recharts, React Flow |
| Backend | FastAPI, Python 3.11+, SQLAlchemy 2.0, Alembic |
| LLM | Google Gemini 2.0 Flash (free tier, multimodal) |
| Orchestration | LangGraph |
| Vector DB | Qdrant |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2, local) |
| Real-time | WebSocket (study groups), SSE (chat streaming) |
| PDF Generation | ReportLab |
| Containerisation | Docker Compose |

## 🏃 Quick Start

### Prerequisites
- Docker & Docker Compose
- Google Gemini API key (free: https://aistudio.google.com/apikey)

### Run with Docker
```bash
# 1. Clone
git clone https://github.com/abhyuditagrawal/Capstone-AgenticAI-Educational.git
cd Capstone-AgenticAI-Educational

# 2. Configure
cp .env.example .env
# Edit .env — set GEMINI_API_KEY, JWT_SECRET_KEY, NEXTAUTH_SECRET

# 3. Run (development)
docker-compose up --build

# 3b. Run (production)
docker-compose -f docker-compose.prod.yml up --build -d

# 4. Seed demo data (optional)
docker-compose -f docker-compose.prod.yml run seed

# 5. Open
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Demo login: demo@eduagent.com / demo123
```

### Development Setup (without Docker)
```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── agents/          # 6 agents + orchestrator + intent classifier
│   │   ├── models/          # SQLAlchemy models (user, concept, flashcard, analytics, study)
│   │   ├── routers/         # FastAPI endpoints (15 routers including WebSocket)
│   │   ├── services/        # Business logic (auth, streaming, cache, analytics, planner, PDF)
│   │   ├── rag/             # Vector store + embedding
│   │   └── schemas/         # Pydantic schemas
│   ├── alembic/             # Database migrations (3 revisions)
│   ├── scripts/             # Seed scripts
│   └── tests/               # pytest test suite (60+ tests)
├── frontend/
│   └── src/
│       ├── app/(dashboard)/ # 13+ pages: chat, dashboard, flashcards, study-planner, etc.
│       ├── components/      # UI components (chat, dashboard, voice, image upload)
│       ├── stores/          # Zustand stores
│       └── lib/             # API client, SSE parser, utils
├── docs/                    # IEEE paper, user study, demo script, deployment guide
├── phases/                  # Phase-by-phase build specs
├── docker-compose.yml       # Development compose (5 services: postgres, qdrant, redis, backend, frontend)
└── docker-compose.prod.yml  # Production compose
```

## 📚 Documentation

- **[SPEC.md](./SPEC.md)** — Full project specification
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — System architecture and data models
- **[docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md)** — Deployment guide (Docker, Railway, VPS)
- **[docs/CAPSTONE_REPORT_OUTLINE.md](./docs/CAPSTONE_REPORT_OUTLINE.md)** — Suggested report structure
- **[docs/EduAgent_IEEE_Paper.html](./docs/EduAgent_IEEE_Paper.html)** — IEEE format research paper
- **[docs/USER_STUDY.md](./docs/USER_STUDY.md)** — User study protocol, questionnaire, and SUS scoring
- **[docs/DEMO_SCRIPT.md](./docs/DEMO_SCRIPT.md)** — 3–5 minute demo recording script
- **[docs/SCREENSHOT_GUIDE.md](./docs/SCREENSHOT_GUIDE.md)** — Screenshot capture guide for paper figures
- **API Docs** — http://localhost:8000/docs (auto-generated by FastAPI)

## 🧪 Testing

```bash
# Backend tests
cd backend && pytest --cov=app

# Frontend tests
cd frontend && npx vitest run
```

## 👤 Author

**Abhyudit Agrawal** — Capstone Project

## 📄 License

MIT
