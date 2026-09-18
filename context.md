# EduAgent — Project Context (Living Document)

_Last verified against code: 2026-09-14. This file exists because README.md, ARCHITECTURE.md, SPEC.md, docs/PROJECT_SUMMARY.md and the IEEE paper under `docs/` are stale relative to the current codebase — most importantly, none of them reflect the "dynamic subjects" pivot (commits `167badc`, `57e6bf3`, and the three follow-on fix commits). Treat this file, not the older docs, as the source of truth going forward, and update it whenever a major feature or architectural pivot lands._

## 1. What the project is

EduAgent is a full-stack, multi-agent AI tutoring platform (FastAPI/Python backend + Next.js 16 frontend) built as a capstone project. Its core idea: instead of one generic chatbot, the system runs **six specialised LLM-backed tutoring agents** that all read and write to one shared, persistent student model (per-concept mastery, chat history, cognitive profile), so switching "modes" doesn't reset what the system knows about the learner. A LangGraph orchestrator classifies each chat message's intent and routes it to the right agent, and several "learning-science" subsystems (Bayesian Knowledge Tracing, a forgetting-curve engine, a Vygotsky Zone-of-Proximal-Development recommender, a "Learning Genome" cognitive fingerprint, and multi-agent Socratic debate) sit on top of the shared student model. All of these are genuinely implemented and unit-tested, not just described in docs.

Theme fit: **Smart Education / Agentic AI in Education** — multi-agent architecture, adaptive personalization, and learning-science-grounded automation of tutoring, assessment, and study planning.

## 2. Backend architecture (`backend/app/`)

### 2.1 Agents (`backend/app/agents/`) — all Gemini-backed via a shared `BaseAgent`

- **ConceptQAAgent** (`concept_qa.py`) — RAG-grounded Q&A. Matches the question to known concepts, adapts explanation depth to per-concept confidence (simple language <30%, technical >70%), asks a comprehension-check question, and LLM-grades the student's answer (1–5 rubric) to update mastery in the same turn.
- **ExamPredictorAgent** (`exam_predictor.py`) — predicts likely exam topics from syllabus/past-paper material and generates targeted practice questions.
- **WeakPointTrackerAgent** (`weak_point_tracker.py`) — purely diagnostic: surfaces concepts below 0.4 confidence and overdue reviews, synthesizes an encouraging progress report; never itself updates mastery scores.
- **ProtegeAgent** (`protege.py`) — Feynman-technique "teach the AI" mode with probing follow-ups and rubric grading.
- **VivaAgent** (`viva.py`) — simulated oral exam with a difficulty ladder and per-answer grading.
- **CritiqueAgent** (`critique.py`) — structured essay/assignment feedback with rubric scoring and citation checking.
- **IntentClassifier** (`intent_classifier.py`) — single zero-temperature call classifying each message into 7 intents; unparseable output falls back to `general`.
- **Orchestrator** (`orchestrator.py`) — a compiled LangGraph `StateGraph`: `load_state → classify → route → agent_* → commit_state → format_response → END`. Supports **sticky active modes** — once in `teach_me` or `viva` mode, subsequent turns stay routed there until an exit phrase is said.
- **Debate** (`debate.py`) — a separate SSE-streamed pipeline (not in the orchestrator graph): Proponent (temp 0.6, RAG-grounded) → Skeptic (temp 0.8, "intellectually honest, not contrarian") → optional rebuttal → Judge (temp 0.4, synthesizes with a Confidence: High/Medium/Low line). Each stage streams as its own SSE event.
- **Inter-agent collaboration**: `BaseAgent`'s prompt builder injects other agents' findings (e.g. QA agent can see that Weak-Point Tracker flagged a concept as decaying) plus the student's Learning Genome summary into every prompt.

### 2.2 Routers (`backend/app/routers/`) — 19, all mounted in `main.py`

`auth`, `subjects` (dynamic CRUD/enroll, open to students — see §5), `chat` (largest router, SSE chat + history + agent overrides), `ingestion` (admin PDF upload → job status), `concepts` (concept-graph CRUD), `nudges`, `dashboard` (mastery heatmap, weak points, exam readiness, activity timeline from real timestamps), `flashcards` (SM-2), `analytics`, `study_planner`, `progress_report` (PDF via ReportLab), `custom_agents` (admin-defined agents with prompt+rubric), `study_rooms` + `ws_study` (WebSocket live study groups with shared AI assistant), `image_chat` (Gemini multimodal, 10MB cap), `knowledge_tracing` (BKT + forgetting endpoints), `debate`, `learning_genome`, `knowledge_frontier` (ZPD).

### 2.3 Data model (`backend/app/models/`)

SQLAlchemy 2.0 async. Key tables: `User` (student/admin role), `Subject`, `Concept` + `ConceptPrerequisite` (weighted edges), `Enrollment`, `StudentConcept` (central per-student-per-concept row carrying **both** SM-2 fields — `easiness_factor`, `interval_days`, `next_review_at` — **and** BKT/forgetting fields — `bkt_mastery`, `memory_stability`, `predicted_forget_at` — two mastery systems coexist deliberately), `Conversation`/`Message` (JSONB metadata for RAG sources/concept deltas), `Flashcard` (own SM-2 fields), `LearningGenome` (one row/student, all trait fields nullable-by-design), `StudyPlan`, `CustomAgent`, `StudyRoom`/`StudyRoomMember`, `AgentLog` (per-call latency/tokens/RAG-chunk-count/success telemetry), `LearningEvent`, `IngestionJob`.

### 2.4 Services (`backend/app/services/`)

- `knowledge_tracing.py` — BKT + Ebbinghaus forgetting engine (mechanism in §4).
- `knowledge_frontier.py` — ZPD partitioning engine (mechanism in §4).
- `learning_genome.py` — genome computation engine (mechanism in §4).
- `student_state.py` — central aggregator feeding every agent prompt: per-student concept dict, weak/overdue concepts, prerequisite gaps, mastery summaries, study-priority queue; `sync_student_concepts` backfills tracking rows when concepts are added post-enrollment (what makes dynamic subjects work without re-onboarding).
- `concept_graph.py` — **LLM-based automatic prerequisite-edge detection** from ingested PDF content (contradicts the older SPEC.md claim of manual curation — this is now automatic).
- `ingestion.py`, `flashcard_service.py`, `study_planner.py`, `progress_report.py`, `agent_analytics.py`, `nudge_engine.py`, `cache.py` (Redis), `conversation_context.py`, `llm.py` (Gemini client factory), `auth.py`, `streaming.py`.

### 2.5 RAG pipeline (`backend/app/rag/`)

PyMuPDF text extraction → 500-word chunks with 50-word overlap (page-tracked) → `sentence-transformers/all-MiniLM-L6-v2` local embeddings (384-dim, no per-call API cost) → Qdrant, **one collection per subject** (`subject_{code_lower}`, cosine distance), with `delete_collection` cleanup when a subject is removed (prevents orphaned vectors leaking into a reused subject code).

### 2.6 Operational details worth citing

- `GEMINI_MODEL` defaults to `gemini-flash-lite-latest`, not full Flash — chosen because one chat turn costs 3–4 API calls and full Flash's free-tier 5 req/min limit throttles ordinary conversation.
- `main.py` lifespan auto-runs Alembic migrations on boot via a Postgres advisory lock (safe for multiple uvicorn workers), plus startup diagnostics (DB, Qdrant, Gemini key via `count_tokens`, Redis).
- Deployment: `docker-compose.yml` (dev) and `docker-compose.prod.yml` (prod, explicit memory limits, healthchecks, a `seed` profile). `docs/DEMO_RUNBOOK.md` and `backend/scripts/make_admin.py` indicate a real live demo/deployment, consistent with the `c346e07 "Deployed and working"` commit.

## 3. Frontend (`frontend/src/`)

Next.js 16.2.10 (App Router, bleeding-edge/pre-release — `frontend/AGENTS.md` flags breaking API changes vs. older conventions), React 19.2.4, Tailwind v4, shadcn/base-ui components, Zustand (`auth-store`, `chat-store`), TanStack Query, `@xyflow/react`+`dagre` (concept-graph visualization), `recharts` (dashboards), NextAuth (JWT bridge to FastAPI), `react-markdown`.

Route groups: `(auth)` login/register; `(dashboard)` app shell with `chat`, `dashboard`, `flashcards`, `concept-map`, `knowledge-tracing`, `debate`, `learning-genome`, `knowledge-frontier`, `learning-path`, `my-subjects` (student's dynamic subject browser/creator, ~490 lines, built in the dynamic-database pivot), `study-planner`, `study-groups`, `onboarding`, `profile`, `admin/*` (subjects, per-subject concepts, custom-agents, analytics, upload). Every backend feature has a corresponding UI surface (17+ pages).

## 4. Novel/distinctive mechanisms (detail, for the proposal's "importance" and "methodology" sections)

- **Bayesian Knowledge Tracing** (`services/knowledge_tracing.py`): classic Corbett & Anderson HMM. `bkt_posterior()` applies Bayes' rule (P(Slip)=0.10, P(Guess)=0.20) to update P(learned) from one observation; `bkt_update()` then applies a difficulty-tier-dependent learning-transition probability (0.20/0.15/0.10 for tiers 1–3). Produces `bkt_mastery`, stored per `StudentConcept` alongside the older SM-2 fields — i.e. two mastery-tracking mechanisms intentionally coexist (SM-2 drives flashcard scheduling; BKT drives forgetting prediction and ZPD readiness).
- **Predictive forgetting**: Ebbinghaus exponential retention `R(t) = exp(-t/S)`, stability `S` (days) scaled 1.4×–2.4× by mastery on a correct review and halved on failure. `days_until_forgetting()` inverts the formula for a 0.5 retrievability threshold; `current_recall()` blends raw decay with BKT mastery so well-understood concepts decay slower. Feeds `get_forgetting_forecast()` (day-bucketed at-risk timeline) and the proactive nudge engine.
- **Multi-Agent Socratic Debate** (`agents/debate.py`): Proponent/Skeptic/Judge SSE pipeline described in §2.1 — used as a critical-thinking exercise rather than a single authoritative answer.
- **Learning Genome** (`services/learning_genome.py`): computed on demand, aggregates pace (attempts-to-mastery, fast ≤2/average ≤4/slow >4), preferred modality (mode of agent used), optimal study hour (mode of message hour), persistence (fraction of weak concepts re-attempted ≥2×), average session length (30-min-inactivity session splitting), and an LLM-distilled misconceptions/strengths list from recent messages. Every trait is `None`, not a default, when unobserved — this null-by-design choice avoids inventing a habit that wasn't observed. Injected verbatim into every agent's system prompt.
- **Knowledge Frontier / ZPD** (`services/knowledge_frontier.py`): partitions a student's concept graph into mastered (≥0.7), frontier (unmastered but all prerequisites ≥0.6 — literally Vygotsky's ZPD), and locked (missing prerequisites, named explicitly). Frontier concepts get `readiness_score = avg_prereq_mastery * (1 - own_mastery) * difficulty_factor`; the top-scoring one becomes `next_best` — a "what to study next" recommendation.

## 5. Recent pivot: dynamic, user-created subjects (NOT reflected in README/SPEC/ARCHITECTURE/IEEE paper)

Commits `167badc` ("Switched to dynamic database") and `57e6bf3` ("Subjects added"), plus three small fix commits, moved the system from a fixed, pre-seeded subject catalog to a **runtime, student/admin-created** structure:
- Any authenticated user can create a subject via `POST /api/subjects` (this is now open, not admin-gated — `backend/tests/test_subjects.py` still asserts a `403` here and is stale/likely failing; flag for cleanup).
- `sync_student_concepts` backfills per-student tracking rows when concepts are added to a subject after enrollment, so agents never assume a fixed, pre-known subject roster.
- `rag/vector_store.py` gained `delete_collection` for per-subject Qdrant cleanup on deletion.
- Frontend `my-subjects` page (~490 lines) lets a student browse/create/enroll/leave subjects; `admin/subjects` was extended to match.
- This is the single biggest doc/code divergence in the repo — the existing IEEE paper (`docs/EduAgent_IEEE_Paper.*`) predates it entirely and should not be relied on for describing current subject/onboarding behavior.

## 6. Testing

~1,000+ lines across 10 files in `backend/tests/`: `test_agents.py`, `test_auth.py`, `test_subjects.py` (has the stale 403 assertion above), `test_dashboard.py`, `test_debate.py`, `test_knowledge_frontier.py`, `test_knowledge_tracing.py`, `test_learning_genome.py`, `test_integration.py` (588 lines, full end-to-end API flows), `conftest.py`. Several test files inline copies of pure logic from the corresponding service (to avoid pulling in the full async/ML dependency chain) — a pragmatic but fragile pattern; if the service logic changes, these tests can silently stop verifying it.

## 7. Existing academic framing (for reference, now partly outdated)

`docs/EduAgent_IEEE_Paper.{pdf,html}` — a 16-page, team-authored IEEE-format paper (programmatically generated via `docs/generate_paper.py`), kept in sync with features up through the BKT/debate/genome/ZPD commit (`6fe5fcd`). It does **not** cover the dynamic-subjects pivot (§5), which is the most recent and one of the most functionally significant changes. `docs/PROJECT_SUMMARY.md` claims "production-ready," 19 routers, 16 tables/4 migrations, 100+ tests — roughly consistent with current code, modulo the subjects pivot.

## 8. Contributors

Git history shows two author identities in the most recent commits: `abhyuditagrawal` (the dynamic-database pivot, `167badc`) and Arpit Dash (`arpitdash729@gmail.com`, the subjects-completion and bugfix commits `57e6bf3`/`6ff4081`/`2a2c9bd`/`67b9a3e`) — a second collaborator joined for the latest feature push. Confirm with the user whether Arpit Dash should be listed as a co-investigator/co-author on any formal proposal.

## 9a. 2026-09-19 session: Future Work implementation, hallucination mitigation, full test pass

Implemented 8 of the 9 "Future Work" items from the latest paper (`docs/generate_paper.py` / `docs/EduAgent_IEEE_Paper_v2.html`), skipping only #5 (a longitudinal semester study — a research protocol, not a code deliverable):

1. **Fast intent-classification path** (`agents/intent_classifier.py`): a regex fast path for unambiguous phrasings (viva/teach-me/critique/exam-prep/weak-points/greetings) skips the LLM classification call entirely; ambiguous messages still fall through to the existing LLM classifier.
2. **Learning outcome prediction** (`services/knowledge_tracing.py::predict_learning_outcome`, `GET /api/knowledge-tracing/outcome-prediction`): projects each concept's recall forward to a future exam date (reusing `current_recall`'s existing `now` parameter) and blends it with current BKT mastery into a single predicted score. Surfaced on the Knowledge Tracing page.
3. **Collaborative whiteboard** (`routers/ws_study.py`): new `whiteboard_draw`/`whiteboard_clear` message types on the existing study-room WebSocket; ephemeral per-room stroke log, replayed to anyone who joins mid-session. Frontend: a Whiteboard tab in `study-groups/page.tsx` with an HTML canvas.
4. **Multi-LLM provider abstraction** (`services/llm_provider.py`, new): `GeminiProvider`/`OpenAIProvider`/`AnthropicProvider` behind one interface, selected via `LLM_PROVIDER` setting (falls back to Gemini if the chosen provider's key is missing). Wired into `services/llm.py` and `agents/base.py`'s shared `reason()`/`_reason_stream()`, plus each of the 4 fact-answering agents' own duplicated `reason()` overrides (concept_qa, exam_predictor, weak_point_tracker, viva, critique — **important**: each of the 6 agents fully overrides `BaseAgent.reason()` with its own copy rather than using the base implementation, so the provider swap and grounding instructions had to be applied file-by-file, not just in base.py). Protege intentionally left on direct-provider-swap without grounding notes (see below).
5. Skipped — not code.
6. **Per-student BKT parameter fitting via EM** (`services/knowledge_tracing.py`, new models `StudentBktParams`/`BktObservation`, migration `006`): a real forward-backward (Baum-Welch) implementation in pure Python, pooling soft counts across all of a student's concept-observation sequences. Requires ≥8 raw observations (`MIN_OBSERVATIONS_FOR_FITTING`) before fitting; `apply_bkt_observation` now logs every observation to `bkt_observations` and uses `get_effective_bkt_params` (personalised if fitted, else the tuned global defaults) instead of the hardcoded constants. Endpoints: `POST /api/knowledge-tracing/fit-params`, `GET /api/knowledge-tracing/params`. UI: "Personalize My Model" button on the Knowledge Tracing page.
7. **Learning Genome social signals** (`services/learning_genome.py::_compute_social_signals`, migration `006` adds `collaboration_score`/`peer_sessions_count`/`social_summary` to `learning_genomes`): derived from `StudyRoomMember` rows and authored `MaterialAnnotation` rows (peer-debate is NOT included as a signal since it's still in-memory/ephemeral, not persisted). Folded into the genome's prompt-injected `summary`.
8. **Peer-debate mode** (`routers/ws_study.py`: `debate_start`/`debate_argument`/`debate_judge` message types; `agents/debate.py::judge_peer_debate` + `PEER_JUDGE_PROMPT`): two-or-more students submit positions on a topic over the study-room WebSocket; an AI moderator (reusing the existing RAG-grounded judge pattern) issues a verdict. Ephemeral per-room state (`room_debate` dict), not persisted. Frontend: Peer Debate tab in `study-groups/page.tsx`.
9. **Collaborative material annotation** (new model `MaterialAnnotation`, new router `routers/annotations.py`, migration `006`): a note pinned to `(subject_id, source_file, page)`, persisted (unlike the whiteboard) so it outlives the study-room session; live-broadcast to the room over WS (`annotation` message type) on top of the REST CRUD. Frontend: Notes tab in `study-groups/page.tsx`.

**Hallucination mitigation** (`agents/base.py`): every fact-answering agent's prompt now appends a `GROUNDING_INSTRUCTION` block (prefer retrieved context over general knowledge, say so explicitly when context is insufficient rather than inventing specifics, never fabricate numbers/citations/quotes not present in context). After generation, `grounding_note()` does a lightweight two-signal check — (a) best RAG retrieval score below `settings.RAG_MIN_GROUNDING_SCORE` (0.35 default) while the response reads unhedged, or (b) near-zero lexical overlap between the response and the retrieved chunks — and appends a "Confidence note: ..." caveat when either fires, unless the model already hedged on its own. This is a lexical heuristic, not a fact-checker; it catches gross ungrounded-confidence cases, not subtle errors. Applied to concept_qa, exam_predictor, weak_point_tracker, viva, and critique (the agents that answer from course material); intentionally NOT applied to protege (Socratic role-play, not fact-assertion) or debate.py's existing Proponent/Skeptic/Judge (already structurally hedged by design).

**Real bugs found and fixed via live testing** (not from static review — actually running the app against real Postgres/Qdrant/Redis and a real Gemini key surfaced these):
- `app/schemas/auth.py`: `UserRegister.email`/`UserLogin.email` were typed `str`, not `EmailStr` (imported but unused!) — `"not-an-email"` passed registration validation and created a real account. Fixed; added `pydantic[email]` to `pyproject.toml`.
- `app/main.py` lifespan: the local sentence-transformers embedding model was lazily loaded on first RAG call, not at startup — a student's first chat message could time out waiting on model weights instead of getting an answer. Now pre-warmed in the lifespan startup sequence (`embed_query("warmup")`), same place as the other readiness checks.
- `app/agents/debate.py`'s `PEER_JUDGE_PROMPT` accidentally included the internal note "this is Future Work item #8: ..." directly in the LLM prompt text — the model echoed "Welcome to this Future Work peer-debate session" verbatim into a real user-facing verdict during live testing. Fixed by moving that context to a Python comment instead of the prompt string. **Lesson: never put implementation-tracking language inside an actual prompt template — it can and will leak into model output.**
- `tests/test_subjects.py::test_create_subject_student_forbidden` asserted a stale `403` for student-created subjects; the endpoint (`routers/subjects.py::create_subject`) only depends on `get_current_user`, not `get_admin_user` — this was the known stale-test drift already flagged in section 9 below. Renamed/rewritten to `test_create_subject_student_allowed`, asserting `201`.
- `tests/conftest.py`: the module-level `test_engine` had no `poolclass=NullPool`, so a pooled asyncpg connection created under one pytest-asyncio event loop got reused by a later test under a *different* function-scoped loop, corrupting the connection (`InterfaceError: another operation is in progress`). Added `NullPool`. Also added a Windows-only `WindowsSelectorEventLoopPolicy` guard (asyncpg needs raw socket ops ProactorEventLoop doesn't support) — both fixes are test-infra only, no production behaviour change, and let the full suite actually run on native Windows instead of only inside Docker's Linux containers.

**Testing**: all 132 backend tests pass (`cd backend && pytest -q`) after the fixes above. New test files: `test_annotations.py` (CRUD + ownership), `test_knowledge_tracing_api.py` (BKT params / outcome-prediction endpoints); extended `test_knowledge_tracing.py` (inlined forward-backward + EM fit), `test_debate.py` (peer-judge prompt), `test_learning_genome.py` (social-signal scoring). Frontend: `next build` compiles cleanly (24 routes) and `tsc --noEmit` reports zero errors after the study-groups/knowledge-tracing UI additions.

**Live end-to-end verification** (not just unit tests): registered a real account, created a dynamic subject as a student, ran LLM-based concept auto-detection from a pasted syllabus (8 concepts extracted correctly across 3 units), asked a real chat question and got a correctly-routed, correctly-personalised ConceptQA answer via live Gemini, drove the Knowledge Tracing page's new outcome-prediction card, and ran a full peer-debate round (start topic → submit argument → AI verdict) end-to-end over the study-room WebSocket — this is what caught the `PEER_JUDGE_PROMPT` leak above; static review would not have.

**Local dev environment note (this machine only)**: Docker Hub connectivity through this machine's Docker Desktop is extremely slow (a `hello-world` pull took ~50s; the custom backend image never finished building after over an hour), so this session's verification ran the backend directly against a local Python 3.11 venv (`C:\ve` — kept short specifically to dodge a Windows `WinError 206` path-length limit that torch's license files hit under a normally-named venv) talking to the `postgres`/`qdrant`/`redis` containers via `docker-compose.override.yml` (gitignored, remaps postgres to host port 5433 to avoid a conflict with an unrelated container already using 5432 on this machine) — pip installs from PyPI were fast (~90s for most deps, ~2.5 min including sentence-transformers/torch) even though Docker Hub was not. This is a local-machine-only workaround; the actual `docker-compose.yml`/`Dockerfile`s were not changed and remain the deployment path.

## 9. Known gaps / things to keep an eye on

- `test_subjects.py` asserting `403` for student subject creation is stale against the now-open endpoint.
- SPEC.md's "manually reviewed" concept-prerequisite claim is outdated — `concept_graph.py` now does LLM-based auto-detection.
- README's "Gemini 2.0 Flash" claim doesn't match the actual configured default model (`gemini-flash-lite-latest`).
- No dedicated docs file describes the dynamic-subjects architecture yet — this file (context.md) is currently the only accurate source; consider folding it back into ARCHITECTURE.md/SPEC.md as a follow-up.
