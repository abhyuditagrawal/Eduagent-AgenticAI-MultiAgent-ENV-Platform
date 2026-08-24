# EduAgent — Viva / Demo Q&A Preparation Guide

> Prepared for the capstone demonstration. Every answer below is grounded in the
> actual code in this repository, with file pointers so you can open the source
> mid-answer if a panel member asks "show me".
>
> **Rule for the team:** never answer with a feature name alone. Answer with
> *mechanism* (what the code does), then *justification* (why that choice), then
> *limitation* (what it does not do). Panels reward candour; they punish bluffing.

---

## 0. How to use this document

| Section | Who should own it |
|---------|-------------------|
| §1 Project & Vision, §2 Architecture | Team lead / presenter |
| §3 RAG pipeline, §4 LLM & prompting | ML / backend member |
| §5 Multi-agent orchestration, §6 Debate | Agents member |
| §7 Learning science (BKT, SM-2, ZPD, Genome) | Algorithms member |
| §8 Data model, §9 API & streaming | Backend member |
| §10 Frontend, §11 Auth & security | Frontend member |
| §12 DevOps, §13 Testing & evaluation | Infra member |
| §14 Limitations, §15 Demo contingency, §16 Numbers | **Everyone memorises** |

Rapid-fire drill is at §17. Run it twice before the demo.

---

## 0.1 The 60-second pitch (memorise this)

> EduAgent is a multi-agent AI learning platform. A student uploads their own
> course PDFs; we chunk, embed and index them in Qdrant, and extract a concept
> graph from them with an LLM. Six specialised agents — Concept QA, Exam
> Predictor, Weak-Point Tracker, Protégé, Oral Viva and Essay Critique — sit
> behind a LangGraph orchestrator that classifies intent and routes each message
> to the right agent. What makes it an *ecosystem* rather than six chatbots is
> the shared student model: every agent reads the student's per-concept mastery
> before answering and writes an updated estimate afterwards, so using the Viva
> agent makes the Concept QA agent better. On top of that we run Bayesian
> Knowledge Tracing to estimate latent mastery, an Ebbinghaus forgetting curve to
> predict the day a concept will be forgotten, and a Vygotsky ZPD partition that
> recommends the single best next concept to study.

---

## 1. Project and vision — general questions

**Q1.1 — What problem does this solve?**
Exam preparation is fragmented. A general chatbot knows nothing about your
syllabus, a flashcard app knows nothing about your weaknesses, and a revision
planner knows nothing about what you actually understand. None of them share
state. EduAgent unifies them behind one knowledge layer — RAG store + concept
graph + persistent student model — serving six task-specialised agents.

**Q1.2 — Why six agents instead of one big prompt?**
Three reasons:
1. **Contradictory objectives.** The Protégé agent must *refuse* to explain and
   probe instead; the Concept QA agent must explain fully. One prompt cannot hold
   both instructions without degrading on each.
2. **Different state reads and writes.** The Weak-Point Tracker reads SM-2
   scheduling fields; Concept QA reads prerequisite gaps. Splitting keeps every
   prompt short and every retrieval targeted.
3. **Observability.** Routing is explicit, so the agent-trace panel can show the
   student *why* a given agent answered — useful pedagogically and for grading.

**Q1.3 — Isn't this just ChatGPT with extra steps?**
No — answer this one forcefully. A vanilla chatbot is stateless and ungrounded.
EduAgent (a) grounds every answer in the student's own uploaded material through
retrieval, (b) persists a per-concept mastery model that changes the *content* of
the next answer — see the confidence tiers in `backend/app/agents/concept_qa.py`,
(c) takes autonomous actions nobody asked for: scheduling reviews, raising
nudges, re-ranking the ZPD frontier, generating flashcards, and (d) routes
between behaviours automatically. Grounding + persistent user model + autonomous
side effects + routing is what makes it agentic.

**Q1.4 — Define "agentic" as used in this project.**
The system decides *which* behaviour to run (intent classification → routing),
*what* evidence to fetch (retrieval + concept-graph lookup), and *what side
effects to commit* (mastery updates, review scheduling), none of which the user
specifies. See `backend/app/agents/orchestrator.py` and
`backend/app/services/streaming.py`.

**Q1.5 — Who are the users?**
Two roles, on `users.role` (`student` | `admin`). Admins upload PDFs, manage
subjects and concepts, build custom agents, and see class-level analytics.
Students chat, revise, and view their own dashboards.

**Q1.6 — What was the hardest part?**
Keeping the shared student model coherent across six agents *and* two execution
paths (streaming and non-streaming) while a free-tier LLM budget allowed only
3–4 model calls per turn. Most design decisions in this repo fall out of that
constraint: Flash-Lite as the default model, several sub-tasks folded into one
prompt, best-effort concept extraction.

**Q1.7 — What would you build next?**
A retrieval evaluation harness (recall@k and faithfulness on a labelled question
set), BKT parameters fitted per concept by EM instead of literature defaults, and
a hybrid BM25 + dense retriever with a cross-encoder reranker.

**Q1.8 — How is the work split / what is the scale of it?**
~8 400 lines of Python across 19 API routers, 7 agent modules and 16 services;
~9 300 lines of TypeScript across 17+ pages; 5 Alembic migrations; 106 backend
test functions. See §16 for the full numbers table.

---

## 2. Architecture

**Q2.1 — Walk me through the architecture.**
Four layers:
1. **Frontend** — Next.js 16 (App Router), React 19. Speaks HTTP, SSE and WebSocket.
2. **API layer** — FastAPI; 19 routers registered in `backend/app/main.py`.
3. **Agent layer** — LangGraph orchestrator, intent classifier, six agents plus a
   general fallback, and a separate debate module.
4. **Shared data layer** — Qdrant (vectors), PostgreSQL (users, concept graph,
   student state, chat history, genome), Redis (cache).

**Q2.2 — Trace one chat message end to end.**
From `backend/app/routers/chat.py`:
1. Get-or-create the `Conversation`; persist the user `Message`.
2. Resolve the subject: explicit `subject_id` → conversation's subject → the
   student's single enrolment if unambiguous.
3. Load the last 10 messages as history.
4. Load `student_state` — every concept in the subject with confidence, attempts,
   last-seen and next-review (`services/student_state.py::get_student_state`).
5. Build the `AgentState` TypedDict (`agents/state.py`).
6. Run the orchestrator: `load_state → classify → route → agent → commit_state → format_response`.
7. Commit the buffered `concept_updates` (SM-2 + BKT).
8. Persist the assistant message with metadata: agent, RAG sources, updates.

**Q2.3 — Why FastAPI?**
Async-native, which we need for SSE token streaming and WebSocket study rooms;
Pydantic typing end to end; auto-generated OpenAPI docs at `/docs` that we use as
the live API reference during the demo.

**Q2.4 — Why is agent state a TypedDict rather than a class?**
LangGraph nodes are functions over a shared state dict. A `TypedDict`
(`agents/state.py`) gives static typing while staying JSON-serialisable for graph
transport and for the frontend trace panel.

**Q2.5 — Where is the knowledge layer actually *shared*?**
Three concrete places: every agent calls the same `retrieve()`; every agent
receives the same `student_state` dict; every agent returns `concept_updates`
that the orchestrator commits to one table, `student_concepts`. Explicit
cross-agent hints are injected by
`services/streaming.py::_enrich_with_inter_agent_context`.

**Q2.6 — Show me inter-agent collaboration concretely.**
`_enrich_with_inter_agent_context` derives weak (<0.4), mastered (≥0.8) and
overdue concept lists from shared state, then injects an intent-specific
directive: Concept QA receives a "PREREQUISITE ALERT"; Exam Predictor is told
which topics are already mastered so it stops generating questions on them;
Protégé and Viva receive a "WEAK AREA PROBE" list; Weak-Point Tracker receives
the overdue list.

**Q2.7 — Why is there both an orchestrator graph and a streaming service?**
Honest architectural answer. `/api/chat` (non-streaming) runs the compiled
LangGraph graph. `/api/chat/stream` needs to emit tokens as they are produced, so
`services/streaming.py` re-implements the same classify → enrich → route sequence
around the agent's `run_streaming()` async generator. Two paths, one behaviour —
the duplication is a real maintenance risk and we call it out in §14.

---

## 3. RAG — deep dive

**Q3.1 — Describe your RAG pipeline end to end.**
*Ingestion* (`services/ingestion.py::process_pdf`): PDF → PyMuPDF page-wise text
extraction (`rag/chunker.py::extract_text_from_pdf`) → 500-word chunks with
50-word overlap (`chunk_text`) → local embedding with `all-MiniLM-L6-v2`
(`rag/embeddings.py::embed_texts`) → `ensure_collection` → batched upsert of 100
points into Qdrant (`rag/vector_store.py::upsert_chunks`). A best-effort second
pass then extracts the concept graph from the same PDF.

*Query* (`rag/retriever.py::retrieve`): question → `embed_query` → cosine search
in `subject_{code}` → top-5 chunks carrying `text`, `page`, `source_file`,
`score` → formatted into the prompt as `[Source i: file, Page p]` blocks
(`agents/base.py::_build_full_prompt`).

**Q3.2 — Why 500 words with 50-word overlap?**
500 words (~650–700 tokens) is large enough to contain a full definition plus its
surrounding explanation, and small enough that five of them fit alongside the
system prompt, cross-agent context, genome summary and ten turns of history. The
10% overlap keeps a definition that straddles a boundary from being split
irrecoverably.

**Q3.3 — Is your chunking semantic?**
No — say so plainly. It is fixed-size word-count chunking over the concatenated
document text. It is structure-agnostic: it does not respect headings, paragraphs
or table boundaries. A layout-aware or recursive-character splitter is the first
improvement we would make.

**Q3.4 — How do you know which page a chunk came from?**
`chunk_text` records `(start, end)` character boundaries per page while building
the concatenated text, then locates the chunk's first word and maps that offset
back to a page. It is a heuristic and can mis-attribute by a page when words
repeat. Page numbers drive citation display only; they never affect retrieval.

**Q3.5 — Which embedding model, and why that one?**
`sentence-transformers/all-MiniLM-L6-v2`, 384-dimensional, running **locally**
(`rag/embeddings.py`). Zero API cost and zero rate limit — ingestion embeds
thousands of chunks and an API embedder would have exhausted the free tier;
~14M parameters so it runs on CPU inside the container; strong MTEB retrieval
baseline for its size. Trade-off: weaker than large API embedders on
domain-specific jargon, and effectively English-only.

**Q3.6 — Why is the embedding model a module-level singleton?**
`_get_model()` loads it lazily, once per process. Loading MiniLM takes seconds;
doing it per request would dominate latency. The cost is that the first request
after a cold start pays that load — relevant to the demo (§15).

**Q3.7 — Why Qdrant rather than FAISS, pgvector or Pinecone?**
Qdrant is open-source and self-hosted (no vendor cost), runs as one Docker
service, persists to a volume, has a first-class Python client, and ships a
dashboard at `:6333/dashboard` that we can show live. FAISS is a library, not a
service — no persistence, filtering or multi-process access out of the box.
pgvector would work but couples index scaling to the OLTP database. Pinecone is
managed and paid.

**Q3.8 — Why one collection per subject instead of one collection with a filter?**
`retrieve()` targets `subject_{subject_code.lower()}`. Physical isolation gives
hard tenancy between subjects — a Machine Learning question can never retrieve
Cybersecurity text — keeps each index small, and lets a subject be dropped by
deleting one collection. The cost is that cross-subject retrieval needs a fan-out,
which is acceptable because syllabus scope is per-subject by definition.

**Q3.9 — What distance metric, and why?**
Cosine — `VectorParams(size=384, distance=Distance.COSINE)`. MiniLM produces
normalised sentence embeddings where direction carries the semantics and
magnitude is uninformative, so cosine is the metric the model was trained under.

**Q3.10 — Why top_k = 5?**
A prompt-budget choice: 5 × ~500 words ≈ 2 500 words of context, leaving room for
the system prompt, cross-agent context, genome summary and history inside one
request while keeping latency and token cost low. The debate module uses
`top_k=4` with each chunk truncated to 600 characters because it makes three
sequential LLM calls.

**Q3.11 — Do you re-rank retrieved chunks?**
No. Retrieval is single-stage dense similarity — no cross-encoder reranker, no
MMR diversity step, no hybrid BM25 channel. Known limitation (§14). The fix we
would ship: retrieve top-20, re-rank with a cross-encoder such as
`ms-marco-MiniLM-L-6-v2`, keep top-5.

**Q3.12 — Do you drop low-scoring chunks?**
No similarity threshold is applied — `search()` returns the top-5 whatever their
scores. The mitigation is at the prompt level: the base prompt instructs the
model to say honestly when the context does not contain the answer. A score
cutoff is a one-line improvement we identified but did not ship.

**Q3.13 — How do you prevent hallucination?**
Four layers, none of which is a guarantee:
1. Retrieved chunks are injected with explicit source and page labels and the
   prompt instructs the model to ground its explanation in them.
2. The default prompt tells the model to admit insufficient context.
3. Sources are surfaced to the student through the `rag_results` SSE event and
   the trace panel, so any claim can be checked against the real PDF page.
4. For ambiguous questions the debate module runs a Skeptic persona explicitly
   tasked with surfacing errors and edge cases, and a Judge that emits a
   confidence rating.
We do **not** do automated citation verification: the model is not forced to
quote, and no post-hoc check maps generated claims back to specific chunks.

**Q3.14 — What if a subject has no ingested content?**
`search()` checks the collection list and returns `[]` when the collection does
not exist; `retrieve_context` returns `[]` when there is no subject code. The
agent still answers, from the model's parametric knowledge, with an empty context
block. That is deliberate graceful degradation — but it also means an unseeded
demo silently produces ungrounded answers (§15).

**Q3.15 — How are vectors kept in sync with the relational database?**
They are not transactionally coupled. Qdrant point IDs are fresh UUIDs and are
not stored in Postgres; `ingestion_jobs` records only the chunk count. So
re-uploading the same PDF duplicates vectors. The correct fix — worth stating
before the panel finds it — is a deterministic ID (hash of `source_file` +
`chunk_index`) which makes upsert idempotent.

**Q3.16 — Why batch upserts of 100 points?**
Bounded request size keeps memory and payload predictable for large textbooks and
prevents one oversized request from failing an entire ingest.

**Q3.17 — Is ingestion synchronous? What about a 300-page PDF?**
Ingestion runs as a background task tracked by an `ingestion_jobs` row
(`pending → processing → completed | failed`) that the admin UI polls. The upload
request returns immediately with a job id; extraction plus embedding of a large
PDF takes minutes.

**Q3.18 — How is the concept graph built from a PDF?**
`services/concept_graph.py::extract_concepts_from_syllabus`. Because a textbook
does not fit in a prompt, `_build_concept_source_text` samples pages at an even
stride — at most 40 pages and 24 000 characters — so extraction sees the whole
document rather than only the introduction. The LLM returns a JSON array of up to
40 concepts with `name`, `description`, `difficulty_tier`, `chapter` and
`prerequisites`; `auto_detect_dependencies` adds edges; `sync_student_concepts`
creates the per-student tracking rows.

**Q3.19 — What if the model returns truncated JSON?**
`_parse_concept_json` handles it: strip markdown fences, seek the opening `[`,
and if `json.loads` fails, truncate back to the last complete `}` and close the
array — recovering every complete concept instead of losing all 40. Logged as
`concept_extraction_truncated_recovered`.

**Q3.20 — What if concept extraction fails entirely?**
It sits in its own `try/except` inside `process_pdf` and logs
`concept_generation_failed`. The vector store is already populated by then, so
RAG answers keep working and the job still completes. Deliberate: failure of a
secondary feature must not fail the primary one.

**Q3.21 — Do you cache retrieval results?**
Redis caching (`services/cache.py`) is implemented and currently wired to the
**analytics** endpoints only (`routers/analytics.py`, TTL 300 s). `cache_get` /
`cache_set` are imported in `services/streaming.py` but not yet used on the
retrieval path — the README's "Redis caching for RAG queries" overstates today's
state. Own that if asked; the hook and the key function (`_cache_key`, MD5 of the
joined arguments) are in place.

**Q3.22 — How would you evaluate RAG quality?**
We have no quantitative retrieval metrics today. The protocol we would run: build
~100 syllabus questions with gold chunk IDs, measure recall@5 and MRR for
retrieval, and faithfulness / answer-relevance (RAGAS-style, LLM-judged) for
generation. Present it as designed future work, never as completed work.

**Q3.23 — Why not fine-tune a model instead of RAG?**
Three reasons: course material changes every semester and re-indexing is minutes
while re-training is not; RAG gives per-chunk citations that a fine-tune cannot;
and fine-tuning a model per subject per institution does not scale, whereas one
Qdrant collection per subject does.

---

## 4. LLM and prompting

**Q4.1 — Which LLM, and why?**
Google Gemini via `google-generativeai`, model configurable through
`GEMINI_MODEL` (`backend/app/config.py`), defaulting to `gemini-flash-lite-latest`.
Free tier, multimodal (needed for the diagram-understanding feature), large
context window, and fast enough for token streaming.

**Q4.2 — Why Flash-Lite specifically, and why the `-latest` alias?**
Both are documented in the config comments. A single chat turn costs 3–4 API
calls (intent classification, concept matching, generation, and sometimes answer
grading); the full Flash tier allows only 5 requests per minute on the free plan,
which rate-limits an ordinary conversation. The `-latest` alias tracks the current
model rather than pinning to a version Google will eventually retire, and the
setting is env-driven so a retired model can be swapped without a rebuild.

**Q4.3 — How is the prompt assembled?**
`agents/base.py::_build_full_prompt` concatenates, in order: agent system prompt →
retrieved context block with source/page labels → cross-agent intelligence block →
Learning Genome block → last 10 turns of conversation history → the student's
message. Concept QA overrides this with a templated prompt that additionally
injects per-concept confidence and prerequisite gaps.

**Q4.4 — Why one flat string instead of structured chat roles?**
Simplicity and portability across the sections we inject (context, genome,
cross-agent hints do not map cleanly to user/assistant turns). The trade-off is
weaker separation between instructions and data — a prompt-injection surface we
acknowledge in §11.

**Q4.5 — What temperature do you use, and why does it differ?**
0.7 for student-facing generation (explanations benefit from varied phrasing and
analogies); 0.0 for intent classification, concept matching and answer grading —
these are classification tasks where determinism and reproducibility matter;
0.3 for concept extraction, which needs structure but some flexibility.

**Q4.6 — Why is `max_output_tokens` 256 for the intent classifier when the answer is one word?**
This is a genuinely interesting detail and the code comments it. Current models
spend output tokens on internal reasoning before emitting the answer; capped too
low, the call returns nothing at all because it was cut off mid-thought. 256 is
headroom, not answer length.

**Q4.7 — How do you handle LLM failures and rate limits?**
Three mechanisms. `services/llm.py::generate_response` retries 3 times with
exponential backoff (1s, 2s, 4s). `agents/base.py::describe_llm_error` inspects
the error and, for 429/quota errors, returns a student-actionable message — "wait
about a minute and ask again" — instead of a generic failure, because on the free
tier retrying really is the right advice. Every agent call is wrapped so a model
failure degrades to a message rather than a 500.

**Q4.8 — What if the LLM returns something outside your expected format?**
Every structured call validates. Intent is checked against `VALID_INTENTS` and
falls back to `general` with a `invalid_intent_classified` warning. Grading uses
`re.search(r"[1-5]")` and returns **`None`** if nothing matches — deliberately
not a default score, because recording an ungradable turn as evidence of
understanding would corrupt the mastery model. Concept-JSON parsing has the
salvage path described in Q3.19.

**Q4.9 — How many LLM calls does one chat turn cost?**
Typically 3–4: intent classification (skipped when a multi-turn mode is active or
the agent is overridden), concept matching in Concept QA, the main generation,
and answer grading when the previous turn asked a comprehension question. A
debate costs 3 more (Proponent, Skeptic, Judge) plus one retrieval.

**Q4.10 — Are the LLM calls actually asynchronous?**
Not fully, and this is a fair criticism to concede. The agent methods are `async`,
but `model.generate_content(...)` from `google-generativeai` is a synchronous
call executed inside them, so it blocks the event loop for its duration. The
correct fix is `asyncio.to_thread` / `run_in_executor` or the async client. Under
demo-scale concurrency this is invisible; under load it caps throughput.

**Q4.11 — How does multimodal image understanding work?**
`routers/image_chat.py`: validates MIME type (JPEG/PNG/GIF/WebP) and a 10 MB
limit, then sends `[prompt, {mime_type, data}]` to the same Gemini model with a
prompt tailored to diagrams, flowcharts and handwritten notes. It reuses the LLM
service but bypasses RAG — image analysis is not currently grounded in the vector
store.

---

## 5. Multi-agent orchestration

**Q5.1 — Why LangGraph rather than plain function calls or LangChain agents?**
LangGraph models the flow as an explicit state machine: typed shared state, nodes
as pure functions, conditional edges for routing. That gives us (a) a routing
decision we can log and display in the trace panel, (b) shared state that every
node mutates in one place rather than parameters threaded through call chains,
and (c) room to add cycles later (multi-turn viva loops, retry-on-low-confidence)
without restructuring. A LangChain ReAct-style agent would hand tool choice to
the model; we wanted routing to be deterministic and auditable.

**Q5.2 — Describe the graph.**
`agents/orchestrator.py::build_orchestrator_graph`. Nodes: `load_state`,
`classify`, seven agent nodes (`agent_qa`, `agent_exam`, `agent_weak_point`,
`agent_protege`, `agent_viva`, `agent_critique`, `agent_fallback`),
`commit_state`, `format_response`. Entry point `load_state`; a conditional edge
from `classify` selects the agent via `route_intent`; every agent converges on
`commit_state → format_response → END`. The compiled graph is a module-level
singleton (`get_orchestrator`) so it is built once.

**Q5.3 — How does intent classification work?**
`agents/intent_classifier.py`. A zero-temperature LLM call classifies the message
into exactly one of seven intents: `conceptual_doubt`, `exam_prep`,
`weak_points`, `teach_me`, `viva`, `critique`, `general`. The result is
lowercased, whitespace-normalised, validated against `VALID_INTENTS`, and
defaults to `general` on anything unexpected or on exception.

**Q5.4 — Why an LLM classifier instead of keywords or a trained model?**
Keywords fail on paraphrase — "quiz me like an examiner" and "conduct my viva"
must both route to Viva. A fine-tuned classifier would need labelled data we do
not have. The LLM classifier is zero-shot, costs one cheap call at temperature 0,
and is bounded by a validated enum so a bad output cannot corrupt routing. The
trade-off is one extra call per turn and non-determinism at the margins.

**Q5.5 — What if classification is wrong?**
Two safety valves. The student can force an agent from the UI toolbar
(`agent_override` in the chat request → `intent` is pre-set and classification is
skipped). And misrouting is visible: the trace panel names the acting agent, so
the student sees it and can switch.

**Q5.6 — How do multi-turn modes (Protégé, Viva) survive across messages?**
`services/conversation_context.py` stores an `active_mode` on the conversation.
When set, `classify_node` short-circuits classification and routes straight back
to that agent — otherwise a mid-viva answer like "because entropy increases"
would classify as `conceptual_doubt` and break the exam. Exit is by keyword —
"end viva", "stop teaching", "exit mode", "quit" — which sets `ending_mode`.

**Q5.7 — What does the BaseAgent contract look like?**
`agents/base.py::BaseAgent` defines three steps every agent implements:
`retrieve_context()` (RAG plus any agent-specific lookup), `reason()` (the LLM
call with the agent's system prompt), `assess_understanding()` (returns
`concept_id` / `quality` pairs for the orchestrator to commit). `run()` executes
them in order; `run_streaming()` is the async-generator variant that yields SSE
events. Subclasses override only what differs.

**Q5.8 — What does the Concept QA agent do beyond plain RAG?**
Three things (`agents/concept_qa.py`): it makes an extra LLM call to identify
*which* syllabus concepts the question touches, so mastery updates land on the
right rows; it adapts explanation depth to measured confidence — simple language
and more analogies below 0.3, standard academic language 0.3–0.7, concise and
technical above 0.7; and it grades the student's answer to its own previous
comprehension-check question, feeding the result back into the mastery model.

**Q5.9 — How does the Protégé agent implement the Feynman technique?**
The student teaches; the agent plays a naive learner and asks deliberately
probing follow-ups, then grades the explanation against a rubric. Weak concepts
from the shared state are injected as a "WEAK AREA PROBE" list so the probing is
targeted rather than random.

**Q5.10 — How is a viva answer scored?**
`agents/base.py::grade_answer` — a zero-temperature LLM call with an explicit
1–5 rubric (1 = completely wrong, 5 = excellent and precise), optionally given
retrieved material as reference. It returns `None` rather than a default when the
response cannot be parsed. `match_concepts_in_text` then attributes the score to
the concepts whose names actually appear in the question, sorted longest-name
first so "Demand Paging" wins over "Paging".

**Q5.11 — Do agents call each other?**
Not directly — that would be an uncontrolled call graph and multiplied LLM cost.
Collaboration is mediated through shared state: one agent's writes to
`student_concepts` become another agent's prompt context, plus the explicit
cross-agent hints in `_enrich_with_inter_agent_context`.

**Q5.12 — What is the custom agent builder?**
`routers/custom_agents.py` lets an admin define an agent with a custom system
prompt and rubric without code changes — useful for a department that wants, say,
a lab-report critic. It reuses the same BaseAgent execution path.

---

## 6. Multi-agent debate

**Q6.1 — What is the debate feature and why does it exist?**
`agents/debate.py`. For hard or ambiguous questions a single tutor answer can
hide nuance or propagate a subtle error. Three LLM personas run in sequence:
**Proponent** gives the textbook-standard position; **Skeptic** attacks it with
edge cases, common misconceptions and alternative interpretations — explicitly
instructed not to be contrarian for its own sake; **Judge** synthesises a
balanced consensus and ends with `Confidence: High/Medium/Low`.

**Q6.2 — Is the debate grounded or free-floating?**
Grounded. `retrieve(question, subject_code, top_k=4)` runs first and the same
course-material block (each chunk truncated to 600 characters) is passed to all
three personas, so the debate stays faithful to the syllabus.

**Q6.3 — What is the theoretical basis?**
Socratic dialectic, and the LLM-debate line of work showing that adversarial
critique plus a judge reduces confident errors relative to a single pass. The
mechanism is simple: an independent critic surfaces failure modes the first
generation glossed over.

**Q6.4 — How is it streamed?**
As SSE tuples `(event_type, data)` — `debate_start`, `turn_start`, `turn`,
`turn_end`, `done` — so the UI can render each persona's turn as it arrives
rather than after ~3 sequential model calls.

**Q6.5 — What does it cost, and when should it be used?**
Three sequential LLM calls plus one retrieval — roughly 3× a normal answer in
latency and quota. It is therefore user-invoked from its own page, not automatic.
An automatic trigger on low retrieval confidence is future work.

**Q6.6 — Does the Judge actually change the answer, or rubber-stamp the Proponent?**
Honest answer: we have not measured this. The Judge prompt requires it to keep
what is correct from both sides and note remaining conditions, and in practice it
usually qualifies rather than reverses. Quantifying disagreement rate would be
the right evaluation, and we have not run it.

---

## 7. Learning science — BKT, forgetting, SM-2, ZPD, Genome

**Q7.1 — What is Bayesian Knowledge Tracing and why use it?**
`services/knowledge_tracing.py`. BKT (Corbett & Anderson, 1994) is a Hidden
Markov Model over a latent binary skill state. Four parameters: P(L0) prior
mastery, P(T) learning rate per opportunity, P(S) slip — answering wrongly while
knowing, P(G) guess — answering rightly without knowing. Each observation updates
P(L) by Bayes' rule, then a learning transition is applied. It is the standard
model in intelligent tutoring systems because it separates *observed performance*
from *latent knowledge* — one lucky guess should not equal mastery.

**Q7.2 — Write the update.**
Conditioning (`bkt_posterior`): if correct,
`P(L|obs) = P(L)(1−S) / [P(L)(1−S) + (1−P(L))G]`; if incorrect,
`P(L|obs) = P(L)S / [P(L)S + (1−P(L))(1−G)]`.
Then transition (`bkt_update`): `P(L') = posterior + (1 − posterior) × P(T)`,
clamped to [0, 1].

**Q7.3 — What parameter values, and where do they come from?**
P(L0) = 0.10, P(S) = 0.10, P(G) = 0.20, P(T) = 0.15 by default, with a
difficulty-scaled transition: 0.20 for tier 1 (foundational), 0.15 for tier 2,
0.10 for tier 3 — harder concepts are learned more slowly per opportunity. These
are literature-standard defaults, **not fitted to our data**. Fitting them per
concept by expectation-maximisation over real response logs is the correct next
step and requires a dataset we do not yet have.

**Q7.4 — Why P(G) = 0.20?**
It corresponds roughly to a 1-in-5 chance of being right without knowing, the
conventional value for open-response items in the BKT literature. For genuine
multiple-choice with four options, 0.25 would be the principled value.

**Q7.5 — Explain the forgetting model.**
Ebbinghaus exponential decay: retrievability `R(t) = exp(−t / S)` where `S` is
memory *stability* in days. `update_memory_stability` multiplies stability by
`1.4 + mastery` (so 1.4×–2.4×) on successful recall — the spacing effect, larger
gains for better-consolidated memories — capped at 365 days; a failure halves it,
floored at 0.5 days. Solving `exp(−t/S) = 0.5` gives
`days_until_forgetting = −S · ln(0.5) ≈ 0.693 · S`, which is what populates
`predicted_forget_at`.

**Q7.6 — What is `current_recall` and why is it blended?**
`current_recall = R(t) × (0.5 + 0.5 × bkt_mastery)`. Pure decay would treat a
well-learned concept and a barely-learned one identically after the same elapsed
time. Blending with mastery encodes that a consolidated skill decays more slowly.
It is a pragmatic heuristic, not a result from the literature — say so.

**Q7.7 — What does the forgetting forecast produce?**
`get_forgetting_forecast` returns concepts predicted to fall below the 0.5
retention threshold within a horizon (default 14 days), bucketed by day for
charting, plus `at_risk_now` and average mastery. This is what makes the system
*proactive*: it tells a student to revise a concept before they lose it, rather
than after they fail a question on it.

**Q7.8 — You already have SM-2. Why also BKT?**
They answer different questions. SM-2 answers *when* to review — it is a
scheduling heuristic over easiness factor and interval. BKT answers *how likely
is it that they know this* — a probabilistic state estimate. The forgetting curve
converts BKT's state into a predicted date, which is the bridge between them.
Both run: `services/student_state.py::update_concept_confidence` applies the SM-2
update and the BKT update on the same observation.

**Q7.9 — Explain SM-2 as implemented.**
`sm2_update(quality, easiness, interval, repetitions)`: quality ≥ 3 counts as a
successful recall — interval becomes 1 day on the first success, 6 days on the
second, then `interval × easiness`; quality < 3 resets interval to 1 and
repetitions to 0. Easiness updates by
`EF + 0.1 − (5−q)(0.08 + 0.02(5−q))`, floored at 1.3 so an item can never be
scheduled with a degenerate multiplier.

**Q7.10 — Explain the Knowledge Frontier / ZPD.**
`services/knowledge_frontier.py`. Vygotsky's Zone of Proximal Development is the
band of concepts a learner cannot master alone but *can* master with guidance.
We operationalise it on the concept graph: a concept is **mastered** if own
mastery ≥ 0.7; **frontier** (the ZPD) if not yet mastered but every prerequisite
is ≥ 0.6; **locked** if any prerequisite is still below 0.6. Frontier concepts are
ranked by
`readiness = avg_prereq_mastery × (1 − own_mastery) × 1/(1 + 0.15(difficulty − 1))`,
and the top one is returned as `next_best` — the "learning GPS".

**Q7.11 — Justify each term in the readiness score.**
`avg_prereq_mastery` — the better the foundation, the more likely success now.
`(1 − own_mastery)` — prefer concepts with the most headroom, so effort buys the
most learning. The difficulty factor mildly prefers foundational concepts when
everything else ties, giving a natural easy-to-hard ordering. The thresholds
(0.7 / 0.6) are tuned by inspection, not derived — concede that.

**Q7.12 — Why is the prerequisite threshold (0.6) lower than the mastery threshold (0.7)?**
Because the ZPD is precisely the zone where the foundation is *good enough to
build on but not perfect*. Requiring full mastery of every prerequisite would
make the frontier almost always empty and stall the learner.

**Q7.13 — What is the Learning Genome?**
`services/learning_genome.py` — a per-student cognitive fingerprint aggregated
from behavioural signals: **pace** (average attempts to reach mastery: ≤2 fast,
≤4 average, else slow), **preferred modality** (most-used agent type mapped to a
human label), **optimal study hour** (hour with most activity), **persistence**
(fraction of weak concepts revisited), **average session length**, and an
LLM-distilled list of recurring **misconceptions** and **strengths** from recent
messages. A short natural-language `summary` is injected into every agent prompt
so a slow-pace student automatically gets more scaffolding.

**Q7.14 — What if there is no data yet?**
`_compute_pace` returns `None` rather than "average" when the student has
mastered nothing. That is deliberate: reporting an unknown trait as a measured
average would be fabrication, and the genome block is simply omitted from the
prompt.

**Q7.15 — Isn't the Learning Genome just learning-styles pseudoscience?**
Anticipate this — it is the sharpest question in this section. Our position: we
do not claim a fixed "visual/auditory learner" typology, which is indeed
discredited. Every genome trait is a *behavioural measurement* — attempts to
mastery, which agent the student actually uses, when they are active, whether
they return to weak concepts — used to adjust scaffolding depth, not to gate
content by a supposed innate style.

**Q7.16 — There appear to be two mastery numbers. Which is authoritative?**
Correct, and worth stating before it is found: `student_concepts.confidence_score`
is the SM-2-driven score used by the dashboards and the ZPD partition, while
`student_concepts.bkt_mastery` is the probabilistic estimate used by the
knowledge-tracing views and the forgetting forecast. Both are updated from the
same observation. They are consistent in direction but not numerically identical,
and unifying on BKT with confidence derived from it is a clean-up we would make.

**Q7.17 — How do you validate that any of this improves learning?**
We do not have outcome data — say so. `docs/USER_STUDY.md` contains the designed
protocol (task-based sessions, SUS questionnaire, scoring). The honest claim is
that the mechanisms implement established models correctly; the efficacy claim
would require a controlled study with pre/post assessment, which is out of scope
for the capstone timeline.

---

## 8. Data model and database

**Q8.1 — Walk through the schema.**
`users` → `enrollments` → `subjects` → `concepts` (with `concept_prerequisites`
as the adjacency table forming the DAG) → `student_concepts` (the student model:
confidence, attempts, correct_count, last_seen_at, next_review_at,
easiness_factor, interval_days, plus `bkt_mastery`, `memory_stability`,
`predicted_forget_at` added in migration 004). Chat lives in `conversations` →
`messages` (with a JSONB `metadata` column holding RAG chunks used and confidence
deltas). Plus `ingestion_jobs`, `flashcards`, analytics tables, `study` tables and
`learning_genomes`.

**Q8.2 — Why PostgreSQL and not MongoDB?**
The core of this system is relational: student ↔ concept ↔ prerequisite is a
many-to-many graph with referential integrity requirements, and mastery updates
must be transactional. We also use JSONB where a document shape genuinely fits
(message metadata, genome traits) — so we get both without a second database.

**Q8.3 — Why is the concept graph in Postgres rather than a graph database?**
Graph depth is shallow — prerequisite lookups are one or two hops, done in
`compute_frontier` with a single `IN` query and an in-memory partition. Neo4j
would add a service and a query language for no benefit at this scale. If we
needed multi-hop path finding across thousands of concepts, that calculus changes.

**Q8.4 — How do you prevent cycles in the prerequisite graph?**
There is a `CHECK (concept_id != prerequisite_id)` constraint preventing
self-loops, and the LLM extraction is prompted to list prerequisites only from
within the extracted set. Longer cycles are **not** structurally prevented — the
frontier computation would simply keep such concepts locked rather than crash. A
topological validation pass on ingestion is the proper fix.

**Q8.5 — What is `sync_student_concepts` for?**
Ordering robustness. A student may enrol before any PDF is uploaded, so the
concepts do not exist yet; or concepts may be added later by a new upload. Without
a sync step that student would have no tracking rows and every dashboard would
stay permanently empty. It is called after ingestion and again defensively at the
top of `get_student_state`, creating only the missing rows.

**Q8.6 — Why async SQLAlchemy?**
The whole request path is async (SSE, WebSocket); a synchronous driver would
block the event loop during every query. We use `asyncpg` through SQLAlchemy 2.0's
async engine, with `AsyncSession` injected by the `get_db` dependency.

**Q8.7 — How are migrations managed?**
Alembic, five revisions (`001` initial schema → `005` genome traits nullable).
They are applied automatically at application startup (`main.py::run_migrations`).

**Q8.8 — Auto-migrating at startup with multiple workers — doesn't that race?**
It would, which is why it does not. Every uvicorn worker runs the lifespan hook,
so `run_migrations` takes a **PostgreSQL advisory lock** (`pg_advisory_lock`,
constant `727314001`) before invoking `alembic upgrade head`. The winner
migrates; the others acquire the lock afterwards and find the schema already at
head. The lock is released in a `finally` block.

**Q8.9 — Is auto-migration on startup a good idea in production?**
It is a deliberate convenience trade-off for a project deployed by
`docker compose up`, and it is made safe by the advisory lock and by logging
rather than crashing on failure. In a production system with a release pipeline,
migrations belong in a separate deploy step so a bad migration cannot take down
every replica at once.

---

## 9. API and streaming

**Q9.1 — What endpoints exist?**
19 routers in `main.py`: `auth`, `subjects`, `chat`, `ingestion`, `concepts`,
`nudges`, `dashboard`, `flashcards`, `analytics`, `study_planner`,
`progress_report`, `custom_agents`, `study_rooms`, `image_chat`, `ws_study`,
`knowledge_tracing`, `debate`, `learning_genome`, `knowledge_frontier`. Full live
reference at `http://localhost:8000/docs`.

**Q9.2 — Why SSE and not WebSocket for chat?**
Chat streaming is unidirectional server→client after the request; SSE gives that
over plain HTTP with automatic reconnection, no upgrade handshake, and it passes
through proxies that block WebSocket. We *do* use WebSocket where the traffic is
genuinely bidirectional and multi-party — the live study rooms
(`routers/ws_study.py`).

**Q9.3 — What SSE events do you emit and why does it matter?**
`agent_start` (which agent took the message, and the intent), `rag_results` (the
sources with file, page and score), `token` (each generated fragment),
`concept_update` (mastery deltas), `concepts_touched` (concepts this turn
covered), `done` (conversation/message ids, agent, intent, `response_time_ms`,
`rag_chunks_used`), and `error`. Together they drive the agent-trace panel — the
feature that makes the system's reasoning visible rather than a black box.

**Q9.4 — Where do the performance numbers in the `done` event come from?**
`services/streaming.py` times the whole turn from entry to completion
(`response_time_ms`) and reports `rag_chunks_used` from the state. Those feed the
analytics tables via `log_agent_invocation`.

**Q9.5 — What happens if the stream fails midway?**
The generator catches the exception, emits an `error` event with the message and
returns, so the client always terminates cleanly rather than hanging on an open
connection.

**Q9.6 — How are concept updates persisted if the user closes the tab mid-stream?**
The mastery update happens in `assess_understanding` after generation completes,
so a disconnect before completion means that turn is not recorded. Acceptable —
the alternative (writing on partial evidence) is worse.

**Q9.7 — How does the progress-report PDF work?**
`routers/progress_report.py` with ReportLab, generating a downloadable report
containing mastery data — server-side rendering so the exact same data the
dashboard shows is what appears in the document.

---

## 10. Frontend

**Q10.1 — What is the frontend stack and why?**
Next.js 16 App Router with React 19 (server components for static shell, client
components for the interactive chat), TailwindCSS v4 with shadcn/ui on base-ui for
an accessible component layer, Zustand for lightweight client state, TanStack
Query for server-state caching and refetching, Recharts for dashboards,
`@xyflow/react` (React Flow) with dagre for the concept-graph layout,
`react-markdown` for rendering agent output, `next-themes` for dark mode, and
`sonner` for toasts.

**Q10.2 — Why Zustand *and* React Query?**
They solve different problems. React Query owns server state — caching,
invalidation, refetch of mastery/dashboard data. Zustand owns ephemeral client
state — the active conversation, streaming buffer, selected subject, trace-panel
open/closed. Mixing them into one store is a common mistake we avoided.

**Q10.3 — Why React Flow with dagre for the concept graph?**
React Flow handles pan/zoom, node/edge rendering and interaction; it has no
opinion on layout. Dagre computes a layered DAG layout, which is exactly right
for a prerequisite graph — prerequisites end up above dependants, so the picture
reads top-down as a learning order.

**Q10.4 — How does the frontend consume SSE?**
The chat page opens the stream and dispatches on the event `type`, appending
`token` payloads to the streaming buffer and routing `agent_start`,
`rag_results`, `concept_update` and `concepts_touched` into the agent-trace panel
state, so the trace populates live while the answer is still being written.

**Q10.5 — How does voice mode work?**
`components/chat/voice-mode.tsx` uses the browser's Web Speech API —
`SpeechRecognition` for speech-to-text input and `speechSynthesis` for spoken
output — so the Viva agent can be used as an actual oral exam. No audio ever
leaves the browser for transcription; it is a client-side API.

**Q10.6 — How is the frontend structured?**
Route groups: `(auth)` for login/register with its own minimal layout, and
`(dashboard)` for the 17+ authenticated pages (chat, dashboard, flashcards,
concept-map, debate, knowledge-tracing, knowledge-frontier, learning-genome,
learning-path, study-planner, study-groups, onboarding, profile, my-subjects,
plus the admin subtree). Shared UI in `components/ui`, feature components grouped
by domain.

**Q10.7 — What about error and loading states?**
`components/error-boundary.tsx` catches render failures per section rather than
whitescreening the app, and `components/skeletons.tsx` provides skeleton loaders
so dashboards do not flash empty while queries resolve.

---

## 11. Auth and security

**Q11.1 — How does authentication work?**
Registration hashes the password with **bcrypt** and a per-password salt
(`services/auth.py::hash_password`). Login verifies and issues two JWTs signed
HS256: an access token (30 minutes) and a refresh token (7 days), each carrying a
`type` claim so a refresh token cannot be replayed as an access token. NextAuth's
credentials provider on the frontend holds the session; the FastAPI dependency
`get_current_user` verifies the token on every protected route.

**Q11.2 — Why bcrypt rather than SHA-256?**
SHA-256 is designed to be fast, which is exactly wrong for passwords. bcrypt is
deliberately slow with a tunable work factor and salts each hash, so identical
passwords produce different digests and offline brute force is expensive.

**Q11.3 — Why both an access and a refresh token?**
Short-lived access tokens bound the damage from a leaked token; the refresh token
avoids forcing a login every 30 minutes. Since JWTs cannot be revoked before
expiry, a short access lifetime is the primary mitigation.

**Q11.4 — What are your known security limitations?**
State them proactively: JWTs are not revocable before expiry (no denylist);
secrets default to `change-me-in-production` in `.env.example` and must be
replaced on deploy — `config.py` does not enforce it; there is no rate limiting on
auth endpoints; uploads are stored on a local volume with no malware scanning;
and because prompts are assembled as one flat string, a hostile PDF could in
principle carry prompt-injection text into the context block.

**Q11.5 — What *is* protected?**
CORS is restricted to the configured frontend origin; every route outside
`/auth/*` requires a valid JWT; uploads are restricted by type and size (PDF for
ingestion, 10 MB and four image MIME types for image chat); all queries go
through SQLAlchemy's parameterised layer, so SQL injection is not a vector; and
subject collections are physically separated in Qdrant.

**Q11.6 — Can one student read another's data?**
Ownership is checked at the router level — for example the chat router rejects a
`conversation_id` whose `student_id` is not the caller with a 404 rather than a
403, which also avoids leaking existence. Every student-scoped query filters on
`current_user.id` from the verified token, not on a client-supplied id.

**Q11.7 — Is student data sent to Google?**
Yes, and it should be stated plainly: message text and retrieved course-material
chunks are sent to the Gemini API for generation. Embeddings are computed
**locally**, so the bulk corpus is never shipped to a third party — only the
retrieved excerpts that a given question surfaces. A production deployment for an
institution would need a data-processing agreement or a self-hosted model.

---

## 12. DevOps and deployment

**Q12.1 — How do I run this?**
`cp .env.example .env`, set `GEMINI_API_KEY`, `JWT_SECRET_KEY` and
`NEXTAUTH_SECRET`, then `docker-compose up --build`. Five services: postgres,
qdrant, redis, backend, frontend. Frontend on 3000, API on 8000, Qdrant dashboard
on 6333. A production compose file (`docker-compose.prod.yml`) with production
Dockerfiles and a seed service also exists.

**Q12.2 — What is the difference between the dev and prod compose files?**
Dev bind-mounts source for hot reload and runs the dev servers; prod builds
optimised images (`Dockerfile.prod`), drops source mounts, and includes a seed
service for demo data.

**Q12.3 — What happens at application startup?**
`main.py` lifespan runs an ordered health sequence and logs each step: verify the
DB connection, run migrations under the advisory lock, check Qdrant, validate the
Gemini API key with a cheap `count_tokens("test")` call, and ping Redis. Only the
database is treated as fatal — Qdrant, Gemini and Redis failures log warnings and
the app still starts, so a partial outage degrades instead of crashing.

**Q12.4 — Why is Redis in the stack if it caches only analytics?**
Class-level analytics aggregate across all students and are the most expensive
queries in the system; a 300-second TTL makes the admin dashboard responsive. The
generic `cache_get`/`cache_set` interface is deliberately domain-agnostic so the
retrieval path can adopt it without new infrastructure (see Q3.21).

**Q12.5 — How would you scale this?**
Backend is stateless behind the JWT, so horizontal replicas work today (the
advisory lock already handles concurrent migrations). The real bottlenecks in
order: the LLM provider rate limit — fix with a request queue and caching of
repeated questions; blocking sync LLM calls inside async handlers (Q4.10);
ingestion, which should move to a proper worker queue (Celery/RQ) instead of
FastAPI background tasks; and Qdrant, which supports sharding and replication
when the corpus outgrows one node.

**Q12.6 — Where can it deploy?**
Docker Compose on any VPS, or Railway/Render with managed Postgres and Qdrant as
a Docker service — see `docs/DEPLOYMENT.md`. The current build is deployed and
running.

---

## 13. Testing and evaluation

**Q13.1 — What is tested?**
106 test functions across 10 files: `test_integration.py` (29),
`test_knowledge_tracing.py` (14), `test_knowledge_frontier.py` (12),
`test_agents.py` (11), `test_debate.py` (10), `test_learning_genome.py` (9),
`test_auth.py` (8), `test_subjects.py` (6), `test_dashboard.py` (5). Run with
`cd backend && pytest --cov=app`.

**Q13.2 — How do you test code that calls an LLM?**
LLM calls are mocked at the `get_gemini_model` boundary, so tests assert on our
logic — routing decisions, state transitions, JSON-parsing salvage, error
handling — rather than on model output, which is neither deterministic nor free.

**Q13.3 — What is *not* tested? (Answer before they ask.)**
Retrieval quality has no quantitative benchmark; there is no end-to-end test
through a real model; frontend coverage is minimal (Vitest is configured, tests
are thin); and there is no load testing. We know precisely which of these matters
most — retrieval evaluation — and Q3.22 describes the protocol.

**Q13.4 — How do you know the maths is right?**
The learning-science modules are pure functions and are unit-tested directly:
BKT posteriors against hand-computed Bayes updates, monotonicity of stability
growth, `days_until_forgetting` against the closed form `−S·ln(0.5)`, and the
frontier partition against constructed prerequisite graphs. That is the part of
the system where correctness is provable, and it is tested accordingly.

---

## 14. Known limitations — rehearse these, do not get caught by them

Volunteering a limitation with its fix reads as engineering maturity. Getting
caught by one reads as not understanding your own system.

| # | Limitation | The answer to give |
|---|-----------|--------------------|
| 1 | Routing is implemented twice (LangGraph graph + `streaming.py`) | LangGraph does not stream tokens out of a node cleanly, so the streaming path re-implements classify → enrich → route. Divergence risk; the fix is to make the graph nodes async generators. |
| 2 | Dense-only retrieval, fixed top-5, no reranker, no score threshold | Known. Fix: hybrid BM25 + dense, retrieve 20, cross-encoder rerank to 5, drop below a similarity floor. |
| 3 | Fixed-size chunking, heuristic page mapping | Structure-agnostic by design-for-simplicity; layout-aware splitting is the upgrade. |
| 4 | No citation verification | The model is instructed to ground but not forced to quote; nothing checks claims against chunks post-hoc. |
| 5 | No RAG evaluation metrics | Protocol designed (Q3.22), dataset not built. |
| 6 | BKT parameters are literature defaults, not fitted | Correct approach is EM fitting per concept on response logs; needs data we do not have. |
| 7 | Two parallel mastery signals (`confidence_score`, `bkt_mastery`) | Both updated from the same observation; unifying on BKT is a planned clean-up (Q7.16). |
| 8 | Redis caching claimed for RAG, wired only for analytics | Hook exists, path not enabled (Q3.21). |
| 9 | Sync LLM SDK calls inside async handlers | Blocks the event loop; fix is `asyncio.to_thread` or the async client (Q4.10). |
| 10 | Single LLM provider, no fallback | If Gemini is down, chat is down. Provider abstraction + fallback model is the fix. |
| 11 | Free-tier rate limits, 3–4 calls per turn | Mitigated by Flash-Lite default, temperature-0 short classification calls, and an explicit 429 message to the student. |
| 12 | Grading is LLM self-assessment | No human ground truth, no inter-rater reliability measured. |
| 13 | Re-uploading a PDF duplicates vectors | Deterministic point IDs make upsert idempotent (Q3.15). |
| 14 | Prerequisite cycles not structurally prevented | Self-loops are blocked by a CHECK; longer cycles would leave concepts permanently locked, not crash. Topological validation on ingest is the fix. |
| 15 | No efficacy study | Protocol exists in `docs/USER_STUDY.md`; outcome data was out of scope for the timeline. |

---

## 15. Live-demo contingency plan

| Risk | Symptom | What to do |
|------|---------|-----------|
| Gemini 429 rate limit | "I've hit the AI provider's rate limit…" | This is our own handled message — point at it as evidence of graceful degradation, wait ~60 s, continue. Do not spam retries during the demo. |
| Cold start | First message is slow | MiniLM loads lazily on first embed. **Send one warm-up message before the panel walks in.** |
| Empty vector store | Answers are generic, trace panel shows no sources | Seed and ingest **before** the demo; verify sources appear in the trace panel on a rehearsal question. |
| Qdrant collection missing | `rag_results` is empty, no error | `search()` returns `[]` by design. Check the Qdrant dashboard at `:6333/dashboard`. |
| Concept extraction failed on upload | Dashboards empty, ZPD empty | Ingestion still completes and RAG works. Check logs for `concept_generation_failed`; re-upload or seed. |
| Intent misroute live | Wrong agent answers | Use the agent-override toolbar — and narrate it as a designed safety valve, not a recovery. |
| Debate is slow | Three sequential calls | Say so up front: "this makes three model calls, so it takes about three times as long — that is the cost of adversarial verification." |

**Demo order that tells the best story:** upload a PDF → show the extracted
concept graph → ask a question and show the trace panel (routing decision +
retrieved sources with page numbers) → answer the comprehension check → show
mastery move on the dashboard → show the ZPD frontier recommending the next
concept → show the forgetting forecast → finish with a debate on a genuinely
ambiguous question. That sequence demonstrates the shared knowledge layer rather
than merely listing features.

---

## 16. Numbers cheat sheet

| Quantity | Value |
|----------|-------|
| Agents | 6 specialised + 1 general fallback |
| Intents | 7 (`conceptual_doubt`, `exam_prep`, `weak_points`, `teach_me`, `viva`, `critique`, `general`) |
| API routers | 19 |
| Frontend pages | 17+ |
| Alembic migrations | 5 |
| Backend Python | ~8 400 lines |
| Frontend TypeScript | ~9 300 lines |
| Backend tests | 106 test functions, 10 files |
| Chunk size / overlap | 500 words / 50 words |
| Embedding model / dims | all-MiniLM-L6-v2 / 384, cosine, local |
| Retrieval top_k | 5 (debate: 4, truncated to 600 chars) |
| Qdrant upsert batch | 100 points |
| Concept extraction limits | ≤40 concepts, ≤40 pages sampled, ≤24 000 chars, 16 384 output tokens |
| Default LLM | `gemini-flash-lite-latest` (env-configurable) |
| Temperatures | 0.7 generation, 0.3 concept extraction, 0.0 classification/grading |
| Max output tokens | 4 096 generation, 2 048 debate turn, 256 classifier |
| LLM calls per chat turn | 3–4 (+3 for a debate) |
| BKT parameters | P(L0)=0.10, P(S)=0.10, P(G)=0.20, P(T)=0.15 (0.20/0.15/0.10 by tier) |
| Forgetting | R(t)=exp(−t/S); stability ×(1.4+mastery) capped 365 d; failure ×0.5 floored 0.5 d |
| Retention threshold | 0.5 → days_until_forget = −S·ln(0.5) ≈ 0.693·S |
| ZPD thresholds | mastery ≥ 0.7 mastered; prerequisites ≥ 0.6 to unlock |
| SM-2 | intervals 1 d, 6 d, then I×EF; EF floor 1.3; quality ≥ 3 = pass |
| Weak / mastered cutoffs (cross-agent) | < 0.4 weak, ≥ 0.8 mastered |
| JWT lifetimes | access 30 min, refresh 7 days, HS256 |
| Cache TTL | 3 600 s default, 300 s analytics |
| Upload limits | PDF for ingestion; images ≤10 MB, JPEG/PNG/GIF/WebP |
| Docker services | 5 (postgres, qdrant, redis, backend, frontend) |

---

## 17. Rapid-fire drill

Answer each in **under 20 seconds**, out loud, without notes.

1. Chunk size and overlap, and why? → 500 words / 50 words; complete definitions, five fit in the prompt, overlap protects boundaries.
2. Embedding model and dimensions? → all-MiniLM-L6-v2, 384-dim, local, cosine.
3. Why local embeddings? → Zero cost, no rate limit at ingestion scale, CPU-friendly.
4. Why one Qdrant collection per subject? → Hard isolation, small fast indexes, trivial deletion.
5. Top-k, and do you re-rank? → 5; no reranker — known limitation, cross-encoder is the fix.
6. How is hallucination limited? → Grounded context with source labels, honest-fallback instruction, sources shown to the student, debate for ambiguity. No citation verification.
7. What are the seven intents? → conceptual_doubt, exam_prep, weak_points, teach_me, viva, critique, general.
8. What happens if the classifier returns garbage? → Validated against an enum, falls back to `general`, logged.
9. Name the graph nodes in order. → load_state → classify → route → agent → commit_state → format_response → END.
10. State the BKT update. → Bayes conditioning on correct/incorrect with slip and guess, then P(L') = post + (1−post)·P(T).
11. Why does BKT need slip and guess? → To separate observed performance from latent knowledge; one lucky guess is not mastery.
12. Give the forgetting formula and the day of forgetting. → R(t)=exp(−t/S); t = −S·ln(0.5) ≈ 0.693·S.
13. Define the ZPD partition. → Mastered ≥0.7; frontier = not mastered but all prerequisites ≥0.6; locked otherwise.
14. Write the readiness score. → avg_prereq × (1 − own) × 1/(1+0.15(difficulty−1)).
15. SM-2 intervals? → 1 day, 6 days, then interval × easiness; EF floored at 1.3; quality ≥3 passes.
16. What is the Learning Genome and what is it *not*? → Behavioural traits injected into prompts; not a learning-styles typology.
17. Why SSE for chat and WebSocket for study rooms? → Unidirectional streaming vs multi-party bidirectional.
18. Name the SSE events. → agent_start, rag_results, token, concept_update, concepts_touched, done, error.
19. How is inter-agent collaboration implemented? → Shared student state plus intent-specific injected hints; no direct agent-to-agent calls.
20. How do migrations avoid racing across workers? → A Postgres advisory lock around `alembic upgrade head`.
21. How are passwords stored? → bcrypt with per-password salt; JWT HS256, 30 min / 7 days.
22. What is your single biggest limitation? → No quantitative retrieval evaluation — here is the protocol we would run.
23. Why is this agentic rather than a chatbot? → It chooses the behaviour, chooses the evidence, and commits side effects the user never requested.
24. What would you do with three more months? → Retrieval eval harness, fitted BKT parameters, hybrid retrieval with reranking, unify the two mastery signals, and a controlled efficacy study.

---

## 18. Three questions that decide the grade

**"Show me where the agents actually share knowledge — not the diagram, the code."**
Open `services/streaming.py::_enrich_with_inter_agent_context` and
`services/student_state.py::get_student_state` side by side. One reads the shared
model, the other injects one agent's conclusions into another's prompt.

**"What in this project is genuinely yours versus a library default?"**
The concept-graph extraction pipeline with page-stride sampling and truncated-JSON
salvage; the ZPD partition and readiness ranking; the BKT + Ebbinghaus coupling
that turns a mastery probability into a predicted forgetting date; the
cross-agent context injection; the multi-turn mode latch that stops a viva answer
from being reclassified as a new question; and the concept attribution that makes
mastery move on the right rows. LangGraph, Qdrant, FastAPI and MiniLM are
infrastructure — the pedagogy layer on top is ours.

**"If I gave this to a real class tomorrow, what breaks?"**
The honest answer, in order: the free-tier LLM quota under concurrent use; the
absence of retrieval evaluation, so nobody can certify answer quality at scale;
uploads with no malware scanning; and no revocation path for issued JWTs. Each
has a known fix, none requires re-architecting.
