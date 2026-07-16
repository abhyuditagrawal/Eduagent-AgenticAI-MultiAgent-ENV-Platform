# EduAgent Quick Start Guide

Complete commands to run the entire EduAgent project locally and in production.

## Prerequisites

- **Docker** and **Docker Compose** (v2.0+)
- **Git**
- **Gemini API Key** (free tier available at https://ai.google.dev)

## 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/abhyuditagrawal/Capstone-AgenticAI-Educational.git
cd Capstone-AgenticAI-Educational

# Copy environment template
cp .env.example .env

# Edit .env and add your Gemini API key
# Open .env and set: GEMINI_API_KEY=your-actual-key-here
```

## 2. Development Mode (Hot Reload)

```bash
# Start all services (PostgreSQL, Qdrant, Redis, FastAPI, Next.js)
docker compose up -d

# Wait for services to be healthy (~30 seconds)
docker compose ps

# Run database migrations
docker exec eduagent-backend alembic upgrade head

# Seed demo data (optional, creates demo@eduagent.com / demo123)
docker compose --profile seed up seed

# View logs
docker compose logs -f backend    # Backend logs
docker compose logs -f frontend   # Frontend logs

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## 3. Production Mode

```bash
# Build production images
docker compose -f docker-compose.prod.yml build

# Start production stack
docker compose -f docker-compose.prod.yml up -d

# Run migrations
docker exec eduagent-backend alembic upgrade head

# Seed demo data
docker compose -f docker-compose.prod.yml --profile seed up seed

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
```

## 4. Common Commands

### Database Management

```bash
# Run migrations
docker exec eduagent-backend alembic upgrade head

# Rollback last migration
docker exec eduagent-backend alembic downgrade -1

# Create new migration
docker exec eduagent-backend alembic revision --autogenerate -m "description"

# Access PostgreSQL directly
docker exec -it eduagent-postgres psql -U eduagent -d eduagent

# Backup database
docker exec eduagent-postgres pg_dump -U eduagent eduagent > backup.sql

# Restore database
docker exec -i eduagent-postgres psql -U eduagent eduagent < backup.sql
```

### Testing

```bash
# Run backend tests
docker exec eduagent-backend pytest tests/ -v

# Run backend tests with coverage
docker exec eduagent-backend pytest tests/ --cov=app

# Run frontend tests
docker exec eduagent-frontend npm test

# Run specific test file
docker exec eduagent-backend pytest tests/test_agents.py -v
```

### Logs and Debugging

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres

# View last 100 lines
docker compose logs --tail=100 backend

# Follow logs in real-time
docker compose logs -f --timestamps backend
```

### Cleanup

```bash
# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes all data)
docker compose down -v

# Remove all images
docker compose down --rmi all

# Remove unused Docker resources
docker system prune -a
```

## 5. Environment Variables

Edit `.env` file with these required variables:

```bash
# Database
POSTGRES_USER=eduagent
POSTGRES_PASSWORD=eduagent_dev
POSTGRES_DB=eduagent
DATABASE_URL=postgresql+asyncpg://eduagent:eduagent_dev@postgres:5432/eduagent

# Qdrant Vector DB
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Redis Cache
REDIS_URL=redis://redis:6379/0

# Authentication
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM (REQUIRED - get from https://ai.google.dev)
GEMINI_API_KEY=your-gemini-api-key-here

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_SECRET=change-me-in-production
NEXTAUTH_URL=http://localhost:3000
```

## 6. Accessing the Application

### Frontend
- **URL**: http://localhost:3000
- **Demo Login**: 
  - Email: `demo@eduagent.com`
  - Password: `demo123`
- **Pages**:
  - `/` — Landing page
  - `/login` — Login
  - `/register` — Register
  - `/chat` — Main chat interface with 6 agents
  - `/dashboard` — Mastery overview and study queue
  - `/concept-map` — Concept dependency graph
  - `/flashcards` — SM-2 spaced repetition review
  - `/study-planner` — AI-generated study schedules
  - `/learning-path` — Timeline of learning events
  - `/study-groups` — WebSocket collaborative rooms
  - `/admin/upload` — Upload course PDFs
  - `/admin/subjects` — Manage subjects
  - `/admin/concepts/[subjectId]` — Manage concepts
  - `/admin/analytics` — Class-level analytics
  - `/admin/custom-agents` — Create custom agents

### Backend API
- **URL**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/health

### Databases
- **PostgreSQL**: `localhost:5432` (user: `eduagent`, password: `eduagent_dev`)
- **Qdrant**: `http://localhost:6333` (Web UI at `http://localhost:6333/dashboard`)
- **Redis**: `localhost:6379`

## 7. Troubleshooting

### Services won't start
```bash
# Check if ports are already in use
lsof -i :3000    # Frontend
lsof -i :8000    # Backend
lsof -i :5432    # PostgreSQL
lsof -i :6333    # Qdrant
lsof -i :6379    # Redis

# Kill process using port (example: port 3000)
kill -9 $(lsof -t -i:3000)
```

### Database connection errors
```bash
# Check PostgreSQL is running
docker exec eduagent-postgres pg_isready -U eduagent

# Check database exists
docker exec eduagent-postgres psql -U eduagent -l
```

### Gemini API errors
```bash
# Verify API key is set correctly
docker exec eduagent-backend python -c "from app.config import get_settings; print(get_settings().GEMINI_API_KEY[:20])"

# Check API key validity
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"contents": [{"parts": [{"text": "test"}]}]}'
```

### Build taking too long
```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker compose build

# Build specific service only
docker compose build backend
docker compose build frontend

# Clear build cache
docker builder prune
```

## 8. Project Structure

```
Capstone-AgenticAI-Educational/
├── backend/                          # FastAPI backend
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry
│   │   ├── config.py                # Configuration
│   │   ├── models/                  # SQLAlchemy models
│   │   ├── routers/                 # 15 API routers
│   │   ├── agents/                  # 6 specialized agents
│   │   └── services/                # Business logic
│   ├── tests/                       # 60+ unit/integration tests
│   ├── alembic/                     # Database migrations
│   ├── Dockerfile                   # Dev image
│   ├── Dockerfile.prod              # Production image
│   ├── pyproject.toml               # Dependencies
│   └── .dockerignore
│
├── frontend/                         # Next.js frontend
│   ├── src/
│   │   ├── app/                     # 19+ pages
│   │   ├── components/              # React components
│   │   ├── stores/                  # Zustand state
│   │   └── lib/                     # Utilities
│   ├── Dockerfile                   # Dev image
│   ├── Dockerfile.prod              # Production image
│   ├── package.json                 # Dependencies
│   └── .dockerignore
│
├── docs/                            # Documentation
│   ├── QUICK_START.md              # This file
│   ├── CONFIGURATION.md            # Configuration guide
│   ├── PLACEHOLDERS.md             # Dummy values and replacements
│   ├── DEPLOYMENT.md               # Production deployment
│   ├── DEMO_SCRIPT.md              # Demo walkthrough
│   ├── EduAgent_IEEE_Paper.pdf     # 16-page research paper
│   └── USER_STUDY.md               # User study protocol
│
├── docker-compose.yml              # Dev stack
├── docker-compose.prod.yml         # Production stack
├── .env.example                    # Environment template
├── README.md                       # Project overview
└── SPEC.md                         # Technical specification
```

## 9. Performance Tips

- **Faster builds**: Use `.dockerignore` files (already configured)
- **Faster frontend**: Use `npm install` instead of `npm ci` in dev (already configured)
- **Faster backend**: Use `--reload` flag in dev (already configured)
- **Caching**: Redis caches analytics queries (5-min TTL) and RAG results
- **Database**: PostgreSQL connection pool: `pool_size=10, max_overflow=20`

## 10. Next Steps

1. **Read the Configuration Guide**: `docs/CONFIGURATION.md`
2. **Check Placeholders**: `docs/PLACEHOLDERS.md` (dummy values to replace)
3. **Run Demo**: Follow `docs/DEMO_SCRIPT.md`
4. **Deploy to Production**: See `docs/DEPLOYMENT.md`
5. **Read Research Paper**: `docs/EduAgent_IEEE_Paper.pdf`

---

**Last Updated**: July 17, 2026  
**Version**: 1.0  
**Status**: Production-Ready
