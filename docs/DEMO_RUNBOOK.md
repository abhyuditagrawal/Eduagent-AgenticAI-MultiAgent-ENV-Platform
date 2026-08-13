# Demo Runbook

A 10-minute walkthrough that shows every number on screen being derived from a PDF
the student uploads live. Nothing in this flow is seeded or simulated.

## Before the demo

```bash
# 1. Start everything (Docker Desktop must be running first)
docker compose -f docker-compose.prod.yml up -d

# 2. Wait until the backend reports healthy
curl -s http://localhost:8000/health     # {"status":"healthy",...}

# 3. Confirm the LLM key and model are live — this line must appear
docker logs eduagent-backend 2>&1 | grep gemini_api_key_valid
```

Open http://localhost:3000. Have a **course PDF ready** (lecture notes or a
textbook chapter — text-based, not scanned images).

> **Do not run `scripts/seed_demo.py`.** It fabricates mastery scores with
> `random.uniform()`. The whole point of this flow is that the data is real.

## The flow

### 1. Register a brand-new student  (~30s)
Register a fresh account. The subject list is **empty** — there is no seeded
content, which is the point: everything from here is the student's own.

### 2. Create a subject and upload your PDF  (~2 min)
**My Subjects → New Subject** → give it a code and name → drag in the PDF.

Talk through what happens while it processes:
- text extracted per page, chunked, embedded locally (`all-MiniLM-L6-v2`)
- vectors stored in Qdrant under a per-subject collection
- Gemini reads the document and extracts the concept list + prerequisite edges
- a mastery-tracking row is created for every concept

The concept list fills in on screen when it finishes. **These concept names came
out of the uploaded document** — worth saying out loud, since it is the claim
the rest of the demo rests on.

### 3. Agent 1 — Concept QA  (~2 min)
Ask a real question about a topic in the PDF, e.g.
*"Explain why thrashing happens and how it relates to page faults."*

Point out:
- the router picked `concept_qa` from the question itself
- the answer cites **your PDF, by page number**
- the concepts it touched are tagged automatically

### 4. Agent 2 — Oral Viva (the one that changes the data)  (~3 min)
Type *"Start a viva exam"*. The agent asks a question from your material.

**Answer it badly on purpose first.** Then ask the same question again and answer
it properly. This is the strongest moment in the demo: the grade is a real LLM
assessment of the answer, and it moves the mastery model in both directions.

### 5. Show the numbers moved  (~2 min)
- **Dashboard** — mastery per chapter, exam readiness, real study minutes
- **Knowledge Tracing** — Bayesian mastery probability and the Ebbinghaus
  forgetting curve, with a predicted date recall drops below threshold
- **Knowledge Frontier** — the concept just mastered moves out of the frontier;
  the next best concept to study is ranked by prerequisite readiness
- **Concept Map** — the graph built from the PDF, coloured by real mastery

Good line to land on: a wrong answer followed by a right one gives a BKT mastery
around 0.64, not 1.0 — because it is a probability estimate over evidence, not a
score.

## If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| "I've hit the AI provider's rate limit" | Gemini free tier | Wait ~60s. Ask fewer questions per minute. |
| Agents error on every message | Model retired by Google | Check `docker logs eduagent-backend \| grep gemini`, then set `GEMINI_MODEL` in `.env` to a current model and restart the backend. |
| Concept list stays empty after upload | Scanned/image-only PDF (no extractable text) | Use a text-based PDF, or paste the syllabus into the "Extract Concepts" box. |
| Dashboard all zeros | No graded answers yet | Only the viva/protégé/exam agents change mastery. Ask a question and answer it. |

## Admin view (optional)

Class analytics and custom agents need an admin account:

```bash
docker exec eduagent-backend python -m scripts.make_admin you@example.com
```

Sign out and back in. The admin links appear at the bottom of the sidebar.
