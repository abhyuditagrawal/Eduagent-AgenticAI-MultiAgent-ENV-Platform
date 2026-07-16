# EduAgent — Demo Recording Script (3–5 Minutes)

## Setup Before Recording

1. Start the platform: `docker compose up --build`
2. Seed demo data: `docker compose -f docker-compose.prod.yml run seed`
3. Open browser to `http://localhost:3000`
4. Use a screen recorder (OBS, Loom, or Windows Game Bar — `Win + G`)
5. Set browser zoom to 100%, resolution 1920x1080
6. Enable dark mode for a clean look (click the theme toggle in the sidebar)

---

## Recording Script

### Slide 0: Title (5 seconds)
> Show a title slide or the README header

**Voiceover**: "This is EduAgent — a multi-agent AI educational platform built as my capstone project."

---

### Scene 1: Landing & Login (20 seconds)

**Action**: Show the landing page → click "Login" → enter `demo@eduagent.com` / `demo123`

**Voiceover**: "EduAgent uses a multi-user system with JWT authentication. Let me log in with the demo account."

---

### Scene 2: Chat — Concept QA Agent (45 seconds)

**Action**: 
1. Go to Chat page
2. Select a subject (e.g., "Machine Learning")
3. Type: "Explain gradient descent and why the learning rate matters"
4. Show the streaming response arriving token by token
5. Point to the agent trace panel on the right showing: intent classification → agent selection → RAG sources

**Voiceover**: "When I ask a conceptual question, the LangGraph orchestrator classifies my intent and routes it to the Concept QA agent. It retrieves relevant context from our Qdrant vector database — you can see the RAG sources here — and generates an explanation adapted to my confidence level."

---

### Scene 3: Chat — Exam Predictor Agent (30 seconds)

**Action**:
1. Type: "Give me practice questions for the upcoming ML exam"
2. Show the response with generated questions

**Voiceover**: "The system automatically detects I'm asking about exam prep and routes to the Exam Predictor agent. It generates relevant practice questions based on the syllabus material. When I answer these questions, the system evaluates my response using the LLM and updates my concept confidence scores."

---

### Scene 4: Chat — Protégé Mode (40 seconds)

**Action**:
1. Type: "Let me teach you about neural networks"
2. Show the AI asking a naive question back
3. Provide an explanation
4. Show the AI probing for gaps
5. Type: "how did I do?"
6. Show the structured evaluation with score

**Voiceover**: "This is the Protégé mode — based on the Feynman technique. I teach the AI, and it asks probing questions to expose gaps in my understanding. After several exchanges, it provides a structured evaluation with a score that feeds back into my concept mastery."

---

### Scene 5: Dashboard (40 seconds)

**Action**:
1. Navigate to Dashboard
2. Show the overall mastery ring chart
3. Show the mastery heatmap with colour-coded concepts
4. Show the exam readiness gauge
5. Show the weak points list with actionable suggestions
6. Show the activity chart

**Voiceover**: "The dashboard gives a complete view of my learning state. The mastery heatmap shows confidence per concept — green means mastered, red means needs work. The exam readiness gauge factors in difficulty tiers. Weak points are prioritised with specific study suggestions."

---

### Scene 6: Concept Graph (30 seconds)

**Action**:
1. Navigate to Concept Map
2. Show the interactive graph with nodes and edges
3. Zoom in on a cluster
4. Point to colour-coded nodes (mastered vs weak)

**Voiceover**: "The concept graph visualises prerequisite relationships. Each node is a concept, coloured by mastery. Edges show which concepts depend on others. This helps students see exactly where gaps in their foundation are affecting advanced topics."

---

### Scene 7: Knowledge Tracing & Forgetting Forecast (30 seconds)

**Action**:
1. Navigate to Knowledge Tracing page
2. Select a subject
3. Show the mastery probability bars per concept
4. Show the forgetting forecast chart — concepts predicted to drop below threshold over the next 14 days
5. Point out at-risk concepts highlighted in red

**Voiceover**: "The Knowledge Tracing page uses Bayesian Knowledge Tracing — a Hidden Markov Model — to estimate the true probability each concept is learned. Combined with the Ebbinghaus forgetting curve, it predicts exactly when recall will drop below 50%, so students get proactive review nudges before they forget."

---

### Scene 8: Multi-Agent Debate Arena (40 seconds)

**Action**:
1. Navigate to the Debate page
2. Select a subject and type an ambiguous question, e.g. "Is normalisation always necessary before training a neural network?"
3. Show the Proponent's argument streaming in
4. Show the Skeptic's critique appearing
5. Show the Judge's consensus with a confidence rating

**Voiceover**: "For nuanced questions, a single-agent answer can hide complexity. The Debate Arena uses three LLM personas — a Proponent, a Skeptic, and a Judge — grounded in the student's course material via RAG. The structured debate exposes edge cases and produces a balanced, evidence-based consensus."

---

### Scene 9: Learning Genome (20 seconds)

**Action**:
1. Navigate to Learning Genome page
2. Show the cognitive fingerprint: pace, preferred modality, optimal study hour, persistence score
3. Show the LLM-identified misconceptions and strengths
4. Click "Recompute"

**Voiceover**: "The Learning Genome builds a cognitive fingerprint for each student — their learning pace, preferred agent type, study patterns, and recurring misconceptions. This profile is injected into every agent's system prompt, so responses are automatically personalised."

---

### Scene 10: Knowledge Frontier / ZPD (25 seconds)

**Action**:
1. Navigate to Knowledge Frontier page
2. Show the three zones: mastered (green), frontier / ZPD (amber), locked (grey)
3. Point to the "Next Best Concept" recommendation
4. Show locked concepts with their missing prerequisites listed

**Voiceover**: "The Knowledge Frontier operationalises Vygotsky's Zone of Proximal Development. It partitions every concept into mastered, frontier — concepts you're ready to learn next — and locked. The 'Next Best' recommendation guides students to the single most impactful concept to study."

---

### Scene 11: Architecture Overview (20 seconds)

**Action**: Show a quick diagram (from the IEEE paper or ARCHITECTURE.md) or the API docs at `http://localhost:8000/docs`

**Voiceover**: "Under the hood, EduAgent uses Next.js for the frontend, FastAPI for the backend, PostgreSQL for the concept graph and student state, Qdrant for vector search, and LangGraph to orchestrate six specialised AI agents — all running through a single Docker Compose command."

---

### Scene 12: Closing (15 seconds)

**Voiceover**: "EduAgent demonstrates that a multi-agent architecture with shared state produces a more effective learning experience than a generic chatbot. Thank you for watching."

---

## Tips for a Great Demo

1. **Practice twice** before recording — timing is everything
2. **Pre-seed data** so dashboards and graphs are populated
3. **Upload at least one PDF** per subject before recording so RAG works
4. **Use dark mode** — it looks more professional on video
5. **Keep mouse movements smooth** — don't click randomly
6. **Pause briefly** after each scene transition
7. **Export at 1080p** — most submission platforms expect this
8. **Add captions** if submitting without audio

## Recommended Tools

- **OBS Studio** (free, open source) — best quality
- **Loom** (free tier) — easiest, auto-hosts
- **Windows Game Bar** (`Win + G`) — built-in, no install needed
- **Canva** — for a quick title/closing slide

## File Naming
Save as: `EduAgent_Demo_<YourName>.mp4`
