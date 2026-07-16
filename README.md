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
- **Real-time SSE Streaming** for token-by-token LLM responses
- **Interactive Concept Graph** visualisation with React Flow + dagre layout
- **Mastery Dashboard** with heatmaps, exam readiness gauge, activity timeline
- **SM-2 Spaced Repetition** with confidence decay and review nudges
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
| LLM | Google Gemini 2.0 Flash (free tier) |
| Orchestration | LangGraph |
| Vector DB | Qdrant |
| Database | PostgreSQL 16 |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2, local) |
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
│   │   ├── models/          # SQLAlchemy models
│   │   ├── routers/         # FastAPI endpoints
│   │   ├── services/        # Business logic (auth, streaming, student state)
│   │   ├── rag/             # Vector store + embedding
│   │   └── schemas/         # Pydantic schemas
│   ├── alembic/             # Database migrations
│   ├── scripts/             # Seed scripts
│   └── tests/               # pytest test suite
├── frontend/
│   └── src/
│       ├── app/(dashboard)/ # Pages: chat, dashboard, concept-map, profile, admin
│       ├── components/      # UI components (chat, dashboard, shared)
│       ├── stores/          # Zustand stores
│       └── lib/             # API client, SSE parser, utils
├── docs/                    # Deployment guide, capstone report outline
├── phases/                  # Phase-by-phase build specs
├── docker-compose.yml       # Development compose
└── docker-compose.prod.yml  # Production compose
```

## 📚 Documentation

- **[SPEC.md](./SPEC.md)** — Full project specification
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — System architecture and data models
- **[docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md)** — Deployment guide (Docker, Railway, VPS)
- **[docs/CAPSTONE_REPORT_OUTLINE.md](./docs/CAPSTONE_REPORT_OUTLINE.md)** — Suggested report structure
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
