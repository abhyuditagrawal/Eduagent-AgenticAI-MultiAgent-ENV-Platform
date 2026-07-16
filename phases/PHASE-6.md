# PHASE 6: Testing, Polish, Documentation, and Deployment

## Overview
Final phase: comprehensive testing, UI polish, performance optimisation, full documentation, and deployment setup. This phase turns a working prototype into a capstone-quality deliverable.

**Depends on**: Phase 5 fully complete and working.

---

## Deliverables Checklist

### 1. Backend Testing

- [ ] Create `backend/tests/conftest.py`:
  - Async test fixtures using `pytest-asyncio`
  - Test database setup (use a separate test database or in-memory SQLite)
  - Test Qdrant client (mock or use a test collection)
  - Test user fixture (creates a test student + admin)
  - FastAPI test client fixture using `httpx.AsyncClient`
  - Cleanup: drop all test data after each test

- [ ] Install test dependencies — add to `pyproject.toml`:
  ```
  pytest>=8.0.0
  pytest-asyncio>=0.23.0
  httpx>=0.27.0
  pytest-cov>=5.0.0
  ```

- [ ] Create `backend/tests/test_auth.py`:
  - Test registration with valid data → 201 + tokens
  - Test registration with duplicate email → 400
  - Test registration with invalid email → 422
  - Test login with correct credentials → 200 + tokens
  - Test login with wrong password → 401
  - Test access to protected route without token → 401
  - Test access with expired token → 401
  - Test `/api/auth/me` returns correct user

- [ ] Create `backend/tests/test_subjects.py`:
  - Test list subjects → returns seeded subjects
  - Test create subject (admin) → 201
  - Test create subject (student) → 403
  - Test enroll in subject → 200
  - Test double enrollment → 400
  - Test list enrolled subjects → returns enrolled only

- [ ] Create `backend/tests/test_ingestion.py`:
  - Test PDF upload with valid PDF → 200 + job_id
  - Test PDF upload with non-PDF file → 400
  - Test ingestion status → returns correct status
  - Test ingestion completion: verify chunks are in Qdrant

- [ ] Create `backend/tests/test_chat.py`:
  - Test send message → 200 + response from agent
  - Test conversation creation → new conversation_id returned
  - Test conversation history → returns messages in order
  - Test agent override → correct agent handles message
  - Test chat without enrollment in any subject → appropriate error/handling

- [ ] Create `backend/tests/test_agents.py`:
  - Test intent classification with sample messages:
    - "What is polymorphism?" → `conceptual_doubt`
    - "What topics are important for the exam?" → `exam_prep`
    - "What are my weak areas?" → `weak_points`
    - "Let me explain binary trees to you" → `teach_me`
    - "Start a viva on databases" → `viva`
    - "Review my essay: ..." → `critique`
    - "Hello!" → `general`
  - Test QA agent returns relevant content for a known concept
  - Test weak-point tracker identifies concepts with low confidence
  - Test SM-2 algorithm updates (provide known inputs, verify outputs)

- [ ] Create `backend/tests/test_dashboard.py`:
  - Test mastery endpoint returns correct structure
  - Test weak-points endpoint returns concepts below threshold
  - Test exam-readiness calculation
  - Test activity endpoint returns daily data
  - Test concept-graph endpoint returns valid graph structure

- [ ] Add test coverage configuration:
  - `backend/pytest.ini` or `pyproject.toml [tool.pytest]` section
  - Target: ≥70% coverage on services and routers

### 2. Frontend Testing

- [ ] Install test dependencies:
  ```bash
  npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
  ```

- [ ] Create `frontend/vitest.config.ts`:
  - Setup for React component testing with jsdom

- [ ] Create `frontend/src/__tests__/components/message-bubble.test.tsx`:
  - Renders user message correctly
  - Renders assistant message with markdown
  - Shows agent badge for assistant messages
  - Shows streaming indicator when streaming

- [ ] Create `frontend/src/__tests__/components/chat-input.test.tsx`:
  - Sends message on Enter
  - Does not send empty message
  - Disabled during streaming
  - Shift+Enter creates newline

- [ ] Create `frontend/src/__tests__/pages/login.test.tsx`:
  - Renders login form
  - Shows error on invalid credentials
  - Redirects on successful login

- [ ] Create `frontend/src/__tests__/stores/chat-store.test.ts`:
  - Test message sending flow
  - Test conversation management
  - Test streaming state management

### 3. UI Polish and Responsiveness

- [ ] **Dark mode support**:
  - Add dark mode toggle in the navbar/sidebar
  - Use Tailwind's `dark:` variants throughout
  - Persist preference in localStorage
  - Default to system preference

- [ ] **Loading states everywhere**:
  - Skeleton loaders for dashboard components (not just spinners)
  - Chat message skeleton while loading history
  - Button loading states during API calls
  - Full-page loading state for initial app load

- [ ] **Error handling UI**:
  - Global error boundary component
  - Toast notifications for all API errors (using shadcn toast)
  - Retry buttons on failed loads
  - Offline indicator

- [ ] **Mobile responsiveness**:
  - Chat page: sidebar collapses to hamburger menu on mobile
  - Dashboard: grid layout stacks vertically on mobile
  - Concept graph: zoom/pan works with touch gestures
  - Agent toolbar: horizontal scroll on mobile
  - All modals are full-screen on mobile

- [ ] **Animations and micro-interactions**:
  - Message appear animation (slide up + fade in)
  - Confidence score change animation (number counting up/down)
  - Dashboard chart animations on load
  - Smooth page transitions
  - Hover effects on all interactive elements

- [ ] **Accessibility (a11y)**:
  - All interactive elements have proper aria labels
  - Keyboard navigation works for chat, dashboard, concept graph
  - Color contrast meets WCAG AA
  - Screen reader friendly message announcements

### 4. Performance Optimisation

- [ ] **Backend**:
  - Add Redis caching for frequently accessed data (optional — only if you want to add Redis to docker-compose):
    - Student state: cache for 60 seconds
    - Concept graph: cache for 5 minutes
    - Dashboard data: cache for 2 minutes
  - If not using Redis, add in-memory caching with `functools.lru_cache` or `cachetools`
  - Database query optimisation:
    - Add missing indexes (check slow queries)
    - Use eager loading for related objects (joinedload)
    - Paginate all list endpoints
  - Rate limiting on chat endpoint (max 10 messages/minute per user)

- [ ] **Frontend**:
  - Implement virtual scrolling for long chat histories (if > 100 messages)
  - Lazy load dashboard components (React.lazy + Suspense)
  - Optimise concept graph rendering for large graphs (> 50 nodes)
  - Image optimisation for any assets (Next.js Image component)
  - Bundle size analysis: `npm run build` and check for large dependencies

### 5. Documentation

- [ ] Update `README.md` at project root:
  ```markdown
  # EduAgent — Multi-Agent AI Educational Ecosystem

  ## Overview
  [2-3 paragraph description]

  ## Features
  [Bullet list of all 6 agents + dashboard + concept graph]

  ## Architecture
  [Link to ARCHITECTURE.md, brief summary]

  ## Tech Stack
  [Table from SPEC.md]

  ## Getting Started

  ### Prerequisites
  - Docker & Docker Compose
  - Google Gemini API key (free: https://aistudio.google.com/apikey)

  ### Quick Start
  1. Clone the repository
  2. Copy `.env.example` to `.env` and fill in your Gemini API key
  3. Run `docker-compose up --build`
  4. Open http://localhost:3000
  5. Register an account and start learning!

  ### Development Setup
  [Instructions for running backend and frontend separately]

  ## Project Structure
  [Directory tree]

  ## API Documentation
  - FastAPI auto-docs: http://localhost:8000/docs
  - See SPEC.md for full API design

  ## Screenshots
  [Add screenshots of: login, chat with agent trace, dashboard, concept graph, viva mode, protégé mode]

  ## Testing
  - Backend: `cd backend && pytest`
  - Frontend: `cd frontend && npm test`

  ## Authors
  - Abhyudit Agrawal

  ## License
  MIT
  ```

- [ ] Create `docs/CAPSTONE_REPORT_OUTLINE.md`:
  ```markdown
  # Suggested Capstone Report Outline

  1. Introduction
     - Problem statement: fragmented ed-tech tools, no unified learning ecosystem
     - Objectives
     - Scope

  2. Literature Review
     - RAG systems
     - Multi-agent AI architectures
     - Spaced repetition (SM-2)
     - Feynman Technique
     - Educational technology landscape

  3. System Design
     - Architecture overview (cite ARCHITECTURE.md diagrams)
     - Agent design patterns
     - Data model
     - Tech stack justification

  4. Implementation
     - Phase-by-phase development narrative
     - Key technical challenges and solutions
     - Agent-specific implementation details

  5. Results & Evaluation
     - Retrieval quality metrics
     - Agent routing accuracy
     - User study results (SUS scores)
     - Performance metrics (latency)

  6. Discussion
     - Strengths and limitations
     - Comparison with existing tools
     - Future work

  7. Conclusion

  Appendix A: Full API documentation
  Appendix B: User study questionnaire
  Appendix C: Sample agent interactions
  ```

- [ ] Add inline code documentation:
  - All backend services and agents have docstrings
  - All API endpoints have OpenAPI descriptions
  - Complex functions have comments explaining the logic
  - Frontend components have JSDoc comments for props

### 6. Deployment Configuration

- [ ] Create `docker-compose.prod.yml`:
  - Production overrides:
    - Frontend: `npm run build && npm start` (not dev mode)
    - Backend: `uvicorn` without `--reload`, with `--workers 2`
    - PostgreSQL: remove exposed ports (internal only)
    - Add health checks for all services
    - Resource limits (memory, CPU)

- [ ] Create `backend/Dockerfile.prod`:
  - Multi-stage build:
    - Stage 1: Install dependencies
    - Stage 2: Copy app, run with gunicorn + uvicorn workers

- [ ] Create `frontend/Dockerfile.prod`:
  - Multi-stage build:
    - Stage 1: `npm run build`
    - Stage 2: Serve with `node` (Next.js standalone output)

- [ ] Create deployment documentation in `docs/DEPLOYMENT.md`:
  - Option 1: Railway (recommended — free tier, easy)
    - Step-by-step Railway deployment guide
    - Environment variable configuration
  - Option 2: Render
  - Option 3: Self-hosted VPS with Docker Compose
  - Database backup and restore procedures

- [ ] Add `backend/app/main.py` startup checks:
  - Verify database connection
  - Verify Qdrant connection
  - Verify Gemini API key is valid (make a test call)
  - Log startup info (version, config summary)

### 7. Demo Data and Seed Script

- [ ] Create `backend/scripts/seed_demo.py`:
  - Seeds the database with demo data for a capstone presentation:
    - 4 subjects (MSA, HCI, Cyber Security, ML) with descriptions
    - 15-20 concepts per subject with prerequisites
    - 1 demo student account (`demo@eduagent.com` / `demo123`)
    - Pre-populated student_concepts with varied confidence scores (to show a realistic dashboard)
    - 10-15 sample conversations (so chat history isn't empty)
    - Realistic activity data for the past 30 days
  - Run with: `python -m scripts.seed_demo`
  - Add to docker-compose as an optional service: `docker-compose run seed`

- [ ] Add sample PDFs to `docs/sample-pdfs/`:
  - At least one PDF per subject (can be from open educational resources)
  - Include a README in that folder listing sources/licenses

### 8. Final Integration Smoke Test

- [ ] Create `backend/tests/test_integration.py`:
  - End-to-end test that:
    1. Registers a new user
    2. Creates a subject and populates concepts
    3. Uploads a PDF and waits for ingestion
    4. Enrolls in the subject
    5. Sends a QA question → gets a response
    6. Sends an exam prep question → gets a response
    7. Checks weak points → gets personalised analysis
    8. Starts a protégé session → has 3 exchanges
    9. Starts a viva → answers 3 questions
    10. Submits text for critique → gets rubric scores
    11. Checks dashboard data → all non-empty
    12. Checks concept graph → valid structure

---

## Verification Criteria (Phase 6 is DONE when — PROJECT IS COMPLETE):
1. All backend tests pass with ≥70% coverage
2. All frontend tests pass
3. Dark mode works across all pages
4. App is fully responsive on mobile
5. Loading states and error handling work for all interactions
6. README is complete with screenshots
7. `docker-compose up --build` starts the entire app from scratch
8. Demo seed data creates a convincing pre-populated demo
9. The integration smoke test passes end-to-end
10. FastAPI docs at `/docs` are complete and accurate
11. A fresh user can: register → onboard → upload PDF → chat with all 6 agents → view dashboard → explore concept graph
12. The entire experience feels polished and capstone-worthy

---

## Final Project Quality Checklist:
- [ ] No hardcoded API keys anywhere in the codebase
- [ ] No console.log statements left in frontend (use proper logging)
- [ ] No print statements left in backend (use structlog)
- [ ] All endpoints return proper HTTP status codes
- [ ] No CORS errors in production mode
- [ ] Database migrations are clean and sequential
- [ ] Git history is clean with meaningful commit messages
- [ ] No TODO comments left unresolved
- [ ] All dependencies have pinned versions
- [ ] .env.example is complete and up to date
