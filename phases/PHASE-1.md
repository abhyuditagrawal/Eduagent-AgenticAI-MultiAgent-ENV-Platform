# PHASE 1: Foundation — Project Scaffolding, Database, Auth, and Ingestion Pipeline

## Overview
Set up the entire project skeleton: Docker Compose with PostgreSQL + Qdrant, FastAPI backend with auth, Next.js frontend with auth UI, PDF ingestion pipeline, and basic RAG retrieval. By the end of this phase, a user can sign up, log in, upload a PDF, and ask a simple question that retrieves relevant chunks from the vector store.

**Estimated effort**: This is the largest phase. It sets up all infrastructure that every subsequent phase depends on.

---

## Pre-requisites
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- A Google Gemini API key (free tier: https://aistudio.google.com/apikey)

---

## Deliverables Checklist

### 1. Docker Compose Setup
- [ ] Create `docker-compose.yml` at project root with 4 services:
  - `postgres`: image `postgres:16`, port 5432, volume for data persistence, env vars for user/password/db
  - `qdrant`: image `qdrant/qdrant:latest`, port 6333 (REST) and 6334 (gRPC), volume for storage
  - `backend`: builds from `./backend/Dockerfile`, port 8000, depends on postgres + qdrant
  - `frontend`: builds from `./frontend/Dockerfile`, port 3000, depends on backend
- [ ] Create `.env.example` with all required environment variables:
  ```
  # Database
  POSTGRES_USER=eduagent
  POSTGRES_PASSWORD=eduagent_dev
  POSTGRES_DB=eduagent
  DATABASE_URL=postgresql+asyncpg://eduagent:eduagent_dev@postgres:5432/eduagent

  # Qdrant
  QDRANT_HOST=qdrant
  QDRANT_PORT=6333

  # Auth
  JWT_SECRET_KEY=change-me-in-production
  JWT_ALGORITHM=HS256
  JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
  JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

  # LLM
  GEMINI_API_KEY=your-gemini-api-key-here

  # Frontend
  NEXT_PUBLIC_API_URL=http://localhost:8000
  NEXTAUTH_SECRET=change-me-in-production
  NEXTAUTH_URL=http://localhost:3000
  ```
- [ ] Create `.env` as a copy of `.env.example` (gitignored)
- [ ] Create `.gitignore` covering Python, Node, Docker, .env, __pycache__, .next, node_modules

### 2. Backend Scaffolding (FastAPI)
- [ ] Create `backend/pyproject.toml` with dependencies:
  ```
  fastapi[standard]>=0.115.0
  uvicorn[standard]>=0.30.0
  sqlalchemy[asyncio]>=2.0.30
  asyncpg>=0.29.0
  alembic>=1.13.0
  pydantic>=2.7.0
  pydantic-settings>=2.3.0
  python-jose[cryptography]>=3.3.0
  passlib[bcrypt]>=1.7.4
  python-multipart>=0.0.9
  pymupdf>=1.24.0
  sentence-transformers>=3.0.0
  qdrant-client>=1.9.0
  google-generativeai>=0.7.0
  langgraph>=0.2.0
  langchain-google-genai>=1.0.0
  langchain-core>=0.2.0
  structlog>=24.1.0
  httpx>=0.27.0
  ```
- [ ] Create `backend/Dockerfile`:
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY pyproject.toml .
  RUN pip install --no-cache-dir .
  COPY . .
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
  ```
- [ ] Create `backend/app/main.py`:
  - FastAPI app instance with title "EduAgent API"
  - CORS middleware (allow frontend origin)
  - Lifespan handler: on startup, run DB connection check + Qdrant connection check
  - Include all routers
  - Health check endpoint at `GET /health`
- [ ] Create `backend/app/config.py`:
  - Pydantic `Settings` class reading from environment variables
  - All settings from `.env.example` as typed fields
- [ ] Create `backend/app/database.py`:
  - Async SQLAlchemy engine + sessionmaker
  - `get_db()` dependency for FastAPI
  - Base declarative model

### 3. Database Models & Migrations
- [ ] Create `backend/app/models/__init__.py` exporting all models
- [ ] Create `backend/app/models/user.py`: `User` model matching ARCHITECTURE.md schema
- [ ] Create `backend/app/models/subject.py`: `Subject` model
- [ ] Create `backend/app/models/concept.py`: `Concept` + `ConceptPrerequisite` models
- [ ] Create `backend/app/models/student.py`: `Enrollment` + `StudentConcept` models
- [ ] Create `backend/app/models/chat.py`: `Conversation` + `Message` models
- [ ] Create `backend/app/models/ingestion.py`: `IngestionJob` model
- [ ] Set up Alembic:
  - `alembic init backend/alembic`
  - Configure `alembic.ini` to read `DATABASE_URL` from env
  - Configure `env.py` to use async engine and import all models
  - Generate initial migration: `alembic revision --autogenerate -m "initial schema"`
  - Migration should run automatically on backend startup (or via entrypoint script)

### 4. Pydantic Schemas
- [ ] Create `backend/app/schemas/auth.py`:
  - `UserRegister(email, password, full_name)`
  - `UserLogin(email, password)`
  - `UserResponse(id, email, full_name, role, created_at)`
  - `TokenResponse(access_token, refresh_token, token_type)`
- [ ] Create `backend/app/schemas/subject.py`:
  - `SubjectResponse(id, code, name, description)`
- [ ] Create `backend/app/schemas/chat.py`:
  - `ChatRequest(message, conversation_id?, agent_override?, subject_id?)`
  - `ChatResponse(response, conversation_id, agent_type, metadata)`
  - `MessageResponse(id, role, content, agent_type, metadata, created_at)`
  - `ConversationResponse(id, title, agent_type, created_at, updated_at)`
- [ ] Create `backend/app/schemas/ingestion.py`:
  - `IngestionResponse(id, subject_id, filename, status, chunks, created_at)`

### 5. Auth System
- [ ] Create `backend/app/services/auth.py`:
  - `hash_password(password) -> str` using passlib bcrypt
  - `verify_password(plain, hashed) -> bool`
  - `create_access_token(data, expires_delta) -> str` using python-jose
  - `create_refresh_token(data) -> str`
  - `verify_token(token) -> dict` (decode + validate)
  - `register_user(db, user_data) -> User`
  - `authenticate_user(db, email, password) -> User | None`
- [ ] Create `backend/app/routers/auth.py`:
  - `POST /api/auth/register` → creates user, returns tokens
  - `POST /api/auth/login` → validates credentials, returns tokens
  - `POST /api/auth/refresh` → accepts refresh token, returns new access token
  - `GET /api/auth/me` → returns current user (requires auth)
- [ ] Create `backend/app/dependencies.py`:
  - `get_current_user` dependency: extracts JWT from Authorization header, validates, returns User
  - This dependency is used by all protected routes

### 6. Subject & Enrollment Endpoints
- [ ] Create `backend/app/routers/subjects.py`:
  - `GET /api/subjects` → list all subjects
  - `POST /api/subjects` → create subject (admin only)
  - `POST /api/subjects/{id}/enroll` → enroll current student
  - `GET /api/subjects/enrolled` → list student's enrolled subjects
- [ ] Seed initial subjects on first startup (or via a seed script):
  - MSA (Microservices Architecture)
  - HCI (Human-Computer Interaction)
  - Cyber Security
  - ML (Machine Learning)

### 7. PDF Ingestion Pipeline
- [ ] Create `backend/app/rag/__init__.py`
- [ ] Create `backend/app/rag/embeddings.py`:
  - Initialize `SentenceTransformer('all-MiniLM-L6-v2')` as a singleton
  - `embed_texts(texts: list[str]) -> list[list[float]]` — batch embedding
  - `embed_query(query: str) -> list[float]` — single query embedding
- [ ] Create `backend/app/rag/chunker.py`:
  - `extract_text_from_pdf(file_path: str) -> list[dict]` — returns `[{text, page_number}]` using PyMuPDF
  - `chunk_text(pages: list[dict], chunk_size=500, overlap=50) -> list[dict]` — semantic chunking with metadata
    - Each chunk: `{text, page, chunk_index, source_file}`
- [ ] Create `backend/app/rag/vector_store.py`:
  - `get_qdrant_client() -> QdrantClient` — singleton
  - `ensure_collection(subject_code: str)` — creates collection if not exists (384-dim, cosine)
  - `upsert_chunks(subject_code: str, chunks: list[dict], embeddings: list[list[float]])` — batch upsert with metadata
  - `search(subject_code: str, query_embedding: list[float], top_k=5) -> list[dict]` — returns top-k chunks with scores
- [ ] Create `backend/app/rag/retriever.py`:
  - `retrieve(query: str, subject_code: str, top_k=5) -> list[dict]` — high-level: embed query → search → return results
- [ ] Create `backend/app/services/ingestion.py`:
  - `process_pdf(db, subject_id, file_path, filename)` — orchestrates: extract → chunk → embed → upsert → update job status
  - Runs as a background task (FastAPI BackgroundTasks)
- [ ] Create `backend/app/routers/ingestion.py`:
  - `POST /api/ingest/upload` — accepts PDF file + subject_id, saves to temp dir, kicks off background ingestion, returns job_id
  - `GET /api/ingest/status/{job_id}` — returns ingestion job status
  - `GET /api/ingest/jobs` — list all ingestion jobs (admin)

### 8. Basic Chat Endpoint (Pre-Agent — Simple RAG)
- [ ] Create `backend/app/routers/chat.py`:
  - `POST /api/chat` — for now, a simple RAG pipeline (no agent routing yet):
    1. Receive message + optional conversation_id + optional subject_id
    2. If no conversation_id, create a new conversation
    3. Save user message to DB
    4. Retrieve relevant chunks from Qdrant (using subject_id or inferring from conversation)
    5. Call Gemini with: system prompt + retrieved chunks + conversation history
    6. Save assistant message to DB
    7. Return response
  - `GET /api/chat/history` — list conversations for current user (paginated)
  - `GET /api/chat/conversations/{id}` — get all messages in a conversation
- [ ] Create `backend/app/services/llm.py`:
  - `get_gemini_model() -> GenerativeModel` — singleton using google-generativeai
  - `generate_response(messages, system_prompt, context_chunks) -> str` — calls Gemini API
  - Handle rate limits with exponential backoff

### 9. Frontend Scaffolding (Next.js)
- [ ] Initialize Next.js 14 project in `frontend/`:
  ```bash
  npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
  ```
- [ ] Install additional dependencies:
  ```bash
  npm install next-auth @next-auth/prisma-adapter zustand @tanstack/react-query axios lucide-react
  npx shadcn@latest init
  npx shadcn@latest add button input card dialog dropdown-menu avatar badge separator scroll-area sheet tabs textarea toast
  ```
- [ ] Create `frontend/Dockerfile`:
  ```dockerfile
  FROM node:20-slim
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci
  COPY . .
  CMD ["npm", "run", "dev"]
  ```
- [ ] Create `frontend/src/lib/api.ts`:
  - Axios instance with base URL from env
  - Request interceptor: attach JWT from session
  - Response interceptor: handle 401 → redirect to login
- [ ] Create `frontend/src/stores/auth-store.ts`:
  - Zustand store for user state, tokens
- [ ] Create `frontend/src/stores/chat-store.ts`:
  - Zustand store for conversations list, active conversation, messages

### 10. Frontend Auth Pages
- [ ] Set up NextAuth in `frontend/src/app/api/auth/[...nextauth]/route.ts`:
  - CredentialsProvider that calls FastAPI `/api/auth/login`
  - JWT callback to store access token
  - Session callback to expose user data
- [ ] Create `frontend/src/app/(auth)/login/page.tsx`:
  - Clean login form (email + password)
  - Link to register page
  - Error handling with toast notifications
  - Redirect to `/chat` on success
- [ ] Create `frontend/src/app/(auth)/register/page.tsx`:
  - Registration form (full name + email + password + confirm password)
  - Client-side validation
  - Calls FastAPI register endpoint, then auto-login
- [ ] Create `frontend/src/app/(auth)/layout.tsx`:
  - Centered card layout for auth pages
  - App logo/title at top

### 11. Frontend Chat Page (Basic)
- [ ] Create `frontend/src/app/(dashboard)/layout.tsx`:
  - Sidebar with: conversation list, "New Chat" button, user avatar + dropdown (profile, logout)
  - Main content area
  - Responsive: sidebar collapses on mobile
- [ ] Create `frontend/src/app/(dashboard)/chat/page.tsx`:
  - Chat message list (scrollable, auto-scroll to bottom)
  - Message input bar with send button
  - Each message shows: role avatar, content (markdown rendered), agent badge
  - Loading state while waiting for response
- [ ] Create `frontend/src/components/chat/message-bubble.tsx`:
  - Renders a single message with proper styling (user vs assistant)
  - Markdown rendering for assistant messages (use react-markdown)
  - Shows agent type badge if present
- [ ] Create `frontend/src/components/chat/chat-input.tsx`:
  - Textarea with auto-resize
  - Send on Enter (Shift+Enter for newline)
  - Disabled while loading

### 12. Frontend Admin: Upload Page
- [ ] Create `frontend/src/app/(dashboard)/admin/upload/page.tsx`:
  - Subject selector dropdown
  - PDF file upload with drag-and-drop zone
  - Upload progress indicator
  - List of past ingestion jobs with status badges (pending/processing/completed/failed)
  - Only accessible to admin role users

---

## Verification Criteria (Phase 1 is DONE when):
1. `docker-compose up` starts all 4 services without errors
2. A user can register and log in via the frontend
3. An admin can upload a PDF and see it processed (status goes to "completed")
4. A user can send a message in chat and receive a RAG-augmented response from Gemini
5. Chat history persists across page refreshes
6. All API endpoints return proper error responses (400, 401, 404, 500)
7. Database migrations run automatically on startup

---

## Important Implementation Notes

### Gemini API Setup
```python
import google.generativeai as genai

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# For chat:
response = model.generate_content(
    contents=[...],
    generation_config=genai.GenerationConfig(
        temperature=0.7,
        max_output_tokens=2048,
    )
)
```

### Qdrant Setup
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
client.create_collection(
    collection_name=f"subject_{code}",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)
```

### Folder Structure After Phase 1
```
backend/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── subject.py
│   │   ├── concept.py
│   │   ├── student.py
│   │   ├── chat.py
│   │   └── ingestion.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── subject.py
│   │   ├── chat.py
│   │   └── ingestion.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── subjects.py
│   │   ├── chat.py
│   │   └── ingestion.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── ingestion.py
│   │   └── llm.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── embeddings.py
│   │   ├── chunker.py
│   │   ├── vector_store.py
│   │   └── retriever.py
│   └── utils/
│       └── __init__.py
frontend/
├── package.json
├── Dockerfile
├── next.config.js
├── tailwind.config.ts
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx (redirect to /chat or /login)
│   │   ├── api/auth/[...nextauth]/route.ts
│   │   ├── (auth)/
│   │   │   ├── layout.tsx
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   └── (dashboard)/
│   │       ├── layout.tsx
│   │       ├── chat/page.tsx
│   │       └── admin/upload/page.tsx
│   ├── components/
│   │   ├── ui/ (shadcn components)
│   │   └── chat/
│   │       ├── message-bubble.tsx
│   │       └── chat-input.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   └── utils.ts
│   └── stores/
│       ├── auth-store.ts
│       └── chat-store.ts
```

---

## DO NOT do in this phase:
- Do NOT implement the LangGraph orchestrator or any agent logic (that's Phase 2)
- Do NOT implement SSE streaming (that's Phase 3)
- Do NOT implement the dashboard (that's Phase 5)
- Do NOT implement concept graph population (that's Phase 2)
- Keep the chat endpoint as a simple RAG pipeline for now
