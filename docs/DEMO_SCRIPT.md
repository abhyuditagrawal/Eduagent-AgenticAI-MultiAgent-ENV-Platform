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

### Scene 7: Architecture Overview (20 seconds)

**Action**: Show a quick diagram (from the IEEE paper or ARCHITECTURE.md) or the API docs at `http://localhost:8000/docs`

**Voiceover**: "Under the hood, EduAgent uses Next.js for the frontend, FastAPI for the backend, PostgreSQL for the concept graph and student state, Qdrant for vector search, and LangGraph to orchestrate six specialised AI agents — all running through a single Docker Compose command."

---

### Scene 8: Closing (15 seconds)

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
