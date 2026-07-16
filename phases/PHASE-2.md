# PHASE 2: LangGraph Orchestrator + Concept QA Agent + Exam Predictor Agent

## Overview
Replace the simple RAG chat from Phase 1 with a full LangGraph-based orchestrator that classifies user intent and routes to specialised agent sub-graphs. Implement the first two agents: **Concept QA Agent** and **Exam Predictor Agent**. Also build the concept graph population pipeline and the concept-endpoint API.

**Depends on**: Phase 1 fully complete and working.

---

## Deliverables Checklist

### 1. Concept Graph Population

- [ ] Create `backend/app/services/concept_graph.py`:
  - `extract_concepts_from_syllabus(subject_id, syllabus_text) -> list[ConceptCreate]`:
    - Calls Gemini with a structured prompt to extract concepts from syllabus/TOC text
    - Prompt template:
      ```
      You are an expert curriculum designer. Given the following syllabus for the subject "{subject_name}", extract all distinct concepts/topics.

      For each concept, provide:
      1. name: A concise concept name
      2. description: A 1-2 sentence description
      3. difficulty_tier: 1 (foundational), 2 (intermediate), or 3 (advanced)
      4. chapter: Which chapter/module it belongs to
      5. prerequisites: List of other concept names from this list that must be understood first

      Return as JSON array.

      Syllabus:
      {syllabus_text}
      ```
    - Parse the JSON response into Pydantic models
    - Insert concepts into DB
    - Insert prerequisite edges into `concept_prerequisites` table
  - `populate_concepts_from_pdf(subject_id, pdf_path)`:
    - Extract TOC/first few pages from PDF
    - Call `extract_concepts_from_syllabus` with extracted text

- [ ] Create `backend/app/routers/concepts.py`:
  - `GET /api/concepts/{subject_id}` → returns all concepts for a subject with their prerequisites (as a graph structure)
  - `POST /api/concepts/{subject_id}/populate` → triggers concept extraction from syllabus text (admin only)
  - `GET /api/concepts/{subject_id}/graph` → returns concepts + edges in a format suitable for graph visualisation:
    ```json
    {
      "nodes": [{"id": "...", "name": "...", "difficulty": 1, "chapter": "..."}],
      "edges": [{"source": "...", "target": "...", "strength": 0.8}]
    }
    ```

- [ ] Create `backend/app/schemas/concept.py`:
  - `ConceptResponse(id, name, description, difficulty_tier, chapter, subject_id)`
  - `ConceptGraphResponse(nodes, edges)`
  - `ConceptPopulateRequest(syllabus_text)`

- [ ] When a student enrolls in a subject, auto-create `student_concepts` rows for all concepts in that subject (all starting at confidence 0.0).

### 2. Student State Service

- [ ] Create `backend/app/services/student_state.py`:
  - `get_student_state(db, student_id, subject_id) -> dict`:
    - Returns `{concept_id: {confidence, attempts, correct_count, last_seen, next_review}}` for all concepts in the subject
  - `update_concept_confidence(db, student_id, concept_id, quality: int)`:
    - Uses SM-2 algorithm (from ARCHITECTURE.md) to update `confidence_score`, `easiness_factor`, `interval_days`, `next_review_at`
    - `quality` is 0-5 (mapped from agent's assessment of the interaction)
  - `get_weak_concepts(db, student_id, subject_id, threshold=0.4) -> list`:
    - Returns concepts where `confidence_score < threshold`, ordered by confidence ascending
  - `get_prerequisite_gaps(db, student_id, concept_id) -> list`:
    - For a given concept, find prerequisites where the student's confidence is below 0.5
    - Returns list of gap concepts — used by QA agent to say "before we cover X, you need to understand Y"

### 3. LangGraph Orchestrator

- [ ] Create `backend/app/agents/state.py`:
  - Define the shared `AgentState` TypedDict used across all nodes:
    ```python
    class AgentState(TypedDict):
        messages: list               # Chat history (LangChain BaseMessage format)
        student_id: str
        subject_id: str | None
        student_state: dict          # From student_state service
        intent: str | None           # Classified intent
        active_agent: str | None     # Which agent is handling
        rag_context: list[dict]      # Retrieved chunks
        concept_ids_touched: list[str]  # Concepts referenced in this interaction
        concept_updates: list[dict]  # [{concept_id, quality}] to commit
        metadata: dict               # Trace info for frontend
    ```

- [ ] Create `backend/app/agents/intent_classifier.py`:
  - `classify_intent(state: AgentState) -> AgentState`:
    - Calls Gemini with the latest user message + a classification prompt
    - Classification prompt:
      ```
      Classify the user's intent into exactly one of these categories:
      - conceptual_doubt: Asking about a concept, theory, definition, or "how does X work"
      - exam_prep: Asking about exam preparation, past papers, important topics, practice questions
      - weak_points: Asking about their weak areas, what to revise, what they're struggling with
      - teach_me: Offering to explain/teach a concept (Feynman technique / protégé mode)
      - viva: Requesting a viva/oral exam simulation
      - critique: Submitting an essay, assignment, or long text for feedback
      - general: Greetings, meta questions, off-topic

      User message: "{message}"

      Respond with ONLY the category name, nothing else.
      ```
    - Sets `state["intent"]` and returns

- [ ] Create `backend/app/agents/orchestrator.py`:
  - Build the main StateGraph:
    ```
    Nodes:
      load_state       → loads student_state from DB
      classify          → calls intent_classifier
      agent_qa          → Concept QA agent
      agent_exam        → Exam Predictor agent
      agent_fallback    → Simple response for general/unhandled intents
      commit_state      → writes concept_updates back to DB
      format_response   → prepares final response with metadata

    Edges:
      START → load_state → classify → (conditional routing)
      conceptual_doubt → agent_qa
      exam_prep → agent_exam
      weak_points → agent_fallback (placeholder — Phase 3)
      teach_me → agent_fallback (placeholder — Phase 4)
      viva → agent_fallback (placeholder — Phase 4)
      critique → agent_fallback (placeholder — Phase 4)
      general → agent_fallback
      agent_* → commit_state → format_response → END
    ```
  - The `agent_fallback` node should still do basic RAG + Gemini response (like Phase 1 chat)
  - The routing uses LangGraph's `conditional_edges` based on `state["intent"]`

- [ ] Create `backend/app/agents/base.py`:
  - Abstract base class for all agents:
    ```python
    class BaseAgent:
        name: str
        system_prompt: str

        async def run(self, state: AgentState) -> AgentState:
            """Main entry point called by orchestrator."""
            context = await self.retrieve_context(state)
            response = await self.reason(state, context)
            updates = await self.assess_understanding(state, response)
            state["rag_context"] = context
            state["concept_updates"] = updates
            state["metadata"]["agent"] = self.name
            # Append assistant message
            return state

        async def retrieve_context(self, state) -> list[dict]: ...
        async def reason(self, state, context) -> str: ...
        async def assess_understanding(self, state, response) -> list[dict]: ...
    ```

### 4. Concept QA Agent

- [ ] Create `backend/app/agents/concept_qa.py`:
  - Extends `BaseAgent`
  - **System Prompt**:
    ```
    You are an expert tutor for {subject_name}. Your role is to explain concepts clearly and thoroughly.

    RULES:
    1. Before explaining a concept, check if the student has gaps in prerequisites.
       If prerequisite gaps are found, briefly explain the prerequisite first, then the main concept.
    2. Use the provided course material context to ground your explanations.
    3. Use analogies and examples to make concepts accessible.
    4. After explaining, ask a quick comprehension check question.
    5. Adapt your language complexity based on the student's confidence level:
       - Low confidence (< 0.3): Use simple language, more analogies
       - Medium confidence (0.3-0.7): Standard academic language
       - High confidence (> 0.7): Concise, can use technical jargon

    Student's current confidence in related concepts:
    {concept_confidences}

    Prerequisite gaps found:
    {prerequisite_gaps}

    Course material context:
    {rag_context}
    ```
  - **retrieve_context**: 
    1. RAG search on user's query against the subject's Qdrant collection
    2. Identify which concepts are being asked about (LLM extraction or keyword match against concept names)
    3. Check prerequisite gaps for those concepts
    4. Include gap info in context
  - **assess_understanding**:
    - If the student's message is answering a comprehension check → evaluate correctness → return quality score (0-5)
    - If the student is asking a new question → return empty (no update yet)

### 5. Exam Predictor Agent

- [ ] Create `backend/app/agents/exam_predictor.py`:
  - Extends `BaseAgent`
  - **System Prompt**:
    ```
    You are an exam preparation strategist for {subject_name}.

    Your capabilities:
    1. TOPIC PREDICTION: Analyse the syllabus structure and past paper patterns to predict likely exam topics.
    2. PRACTICE QUESTIONS: Generate exam-style questions at the appropriate difficulty level.
    3. STUDY PLAN: Suggest a prioritised study plan based on topic importance and the student's weak areas.
    4. PAST PAPER ANALYSIS: When given past paper content, identify recurring question patterns.

    Student's concept mastery:
    {concept_confidences}

    Weak areas (concepts below 40% confidence):
    {weak_concepts}

    Course material context:
    {rag_context}

    When generating practice questions:
    - Include a mix of short-answer, long-answer, and application-based questions
    - Tag each question with the concept(s) it tests
    - Provide model answers when asked

    When predicting important topics:
    - Rank topics by: (a) syllabus weight, (b) frequency in past papers if available, (c) foundational importance
    - Highlight topics the student is weak in that are also high-importance
    ```
  - **retrieve_context**:
    1. RAG search with query augmented with terms like "exam", "important", "question paper"
    2. Also retrieve concept list with difficulty tiers for the subject
    3. Retrieve student's weak concepts
  - **assess_understanding**:
    - If generating practice questions and student answers them → evaluate → return quality scores per concept
    - If just predicting topics → no update

### 6. Update Chat Router to Use Orchestrator

- [ ] Modify `backend/app/routers/chat.py`:
  - Replace the simple RAG pipeline with orchestrator invocation:
    ```python
    @router.post("/api/chat")
    async def chat(request: ChatRequest, user = Depends(get_current_user), db = Depends(get_db)):
        # 1. Get or create conversation
        # 2. Save user message
        # 3. Load conversation history
        # 4. Build initial AgentState
        # 5. Run orchestrator graph
        # 6. Extract response from final state
        # 7. Save assistant message with metadata (agent_type, rag chunks, concept updates)
        # 8. Return ChatResponse with full metadata
    ```
  - The metadata in the response should include:
    - `agent_type`: which agent handled the request
    - `intent`: classified intent
    - `rag_sources`: list of source files/pages used
    - `concepts_touched`: list of concept names referenced
    - `confidence_updates`: any student state changes made

### 7. Frontend Updates

- [ ] Update `frontend/src/components/chat/message-bubble.tsx`:
  - Show agent type badge on assistant messages (e.g. "📚 Concept QA" or "📝 Exam Prep")
  - Style badges with different colors per agent

- [ ] Create `frontend/src/components/chat/agent-trace-panel.tsx`:
  - Collapsible right sidebar panel
  - Shows for each assistant message:
    - **Intent**: What the orchestrator classified (with icon)
    - **Agent**: Which agent handled it
    - **Sources**: List of RAG source documents used (file name, page number)
    - **Concepts**: Concepts touched in this interaction
    - **Confidence Changes**: Any confidence score updates (shown as +/- deltas)
  - This panel is the key differentiator — grading committees will notice this

- [ ] Update `frontend/src/app/(dashboard)/chat/page.tsx`:
  - Add agent trace panel to the right side of the chat
  - Add toggle button to show/hide the trace panel
  - When clicking a message, highlight its trace info in the panel

- [ ] Create `frontend/src/components/chat/subject-selector.tsx`:
  - Dropdown at top of chat to select which subject the conversation is about
  - Fetches enrolled subjects from API
  - Persists selection per conversation

---

## Verification Criteria (Phase 2 is DONE when):
1. Sending "What is polymorphism?" routes to Concept QA agent (visible in trace panel)
2. Sending "What topics are most important for the exam?" routes to Exam Predictor agent
3. Sending "Hello" routes to general/fallback
4. The agent trace panel shows intent, agent, sources, and concepts for each message
5. Concept graph can be populated for a subject via the admin API
6. Student concept confidence scores update after interactions
7. The QA agent adapts its explanation depth based on student confidence
8. All unimplemented agent intents (weak_points, teach_me, viva, critique) fall back gracefully

---

## DO NOT do in this phase:
- Do NOT implement SSE streaming yet (Phase 3)
- Do NOT implement the Weak-Point Tracker, Protégé, Viva, or Critique agents (Phases 3-4)
- Do NOT build the dashboard (Phase 5)
- Do NOT add the concept graph visualisation to the frontend (Phase 5)
