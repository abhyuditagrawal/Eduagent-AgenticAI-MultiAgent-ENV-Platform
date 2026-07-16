# PHASE 4: Protégé Agent + Oral Viva Agent + Essay Critique Agent

## Overview
Implement the remaining three agents: **Protégé (Feynman Technique)**, **Oral Viva Simulator**, and **Essay/Assignment Critique**. These are the most novel agents and will differentiate the project from standard RAG chatbots. Wire all three into the orchestrator so the full 6-agent ecosystem is operational.

**Depends on**: Phase 3 fully complete and working.

---

## Deliverables Checklist

### 1. Protégé Agent (Feynman Technique)

The student *teaches* a concept to the AI. The AI plays the role of a confused but curious student, asking naive questions and probing for gaps in understanding. This operationalises the Feynman Technique — you don't truly understand something until you can explain it simply.

- [ ] Create `backend/app/agents/protege.py`:
  - Extends `BaseAgent`
  - **System Prompt**:
    ```
    You are a curious student learning {subject_name} from your peer (the user). The user will try to explain a concept to you. Your job is to:

    1. LISTEN carefully to their explanation
    2. ASK NAIVE QUESTIONS: Ask "why?" and "what do you mean by...?" like a genuine beginner
    3. PROBE FOR GAPS: If their explanation skips a step or uses jargon without defining it, ask about it
    4. REQUEST ANALOGIES: Ask "Can you give me an example?" or "Can you explain it in simpler terms?"
    5. INTRODUCE EDGE CASES: Ask "But what about [edge case]?" to test depth
    6. NEVER CORRECT THEM DIRECTLY: If they say something wrong, express confusion ("Wait, I thought X was Y? I'm confused now...")
    7. GRADUALLY INCREASE DEPTH: Start with surface-level questions, go deeper as they explain well

    IMPORTANT RULES:
    - You are NOT the tutor. You are the student. The user is teaching YOU.
    - Stay in character as a confused but eager learner throughout
    - Keep your questions short (1-2 sentences max)
    - Ask only ONE question at a time
    - After 5-7 exchanges, provide a structured evaluation (break character for this)

    The concept the user is explaining:
    {target_concept}

    Ground truth about this concept (from course material — DO NOT reveal this, only use it to assess accuracy):
    {rag_context}

    Student's current confidence in this concept: {current_confidence}
    ```

  - **State tracking within conversation**:
    - Track `exchange_count` in conversation metadata
    - Track `misconceptions_detected: list[str]`
    - Track `gaps_found: list[str]`
    - Track `strengths_noted: list[str]`

  - **Evaluation phase** (after 5-7 exchanges or when student says "how did I do?"):
    ```
    ## 🎓 Teaching Evaluation

    **Concept**: {concept_name}
    **Overall Score**: {score}/10

    ### ✅ Strengths
    - {strength_1}
    - {strength_2}

    ### ⚠️ Gaps Found
    - {gap_1}: {brief_explanation_of_what_was_missed}

    ### ❌ Misconceptions
    - {misconception_1}: {correction}

    ### 💡 Suggestions
    - {suggestion_for_improvement}

    **Confidence Update**: Your confidence in {concept_name} has been updated from {old} to {new}.
    ```

  - **assess_understanding**:
    - Map evaluation score to SM-2 quality:
      - 9-10 → quality 5, 7-8 → quality 4, 5-6 → quality 3, 3-4 → quality 2, 1-2 → quality 1
    - Return concept update with quality score

  - **retrieve_context**:
    1. Identify which concept the student wants to teach (from their first message or explicit concept selection)
    2. RAG search for that concept to get ground truth
    3. Load student's current confidence for that concept
    4. Load concept's prerequisites

- [ ] Create `frontend/src/components/chat/protege-mode-indicator.tsx`:
  - Special UI indicator when in Protégé mode:
    - Shows "🎓 Teaching Mode" banner at top of chat
    - Progress bar showing exchange count (e.g. "Exchange 3/7")
    - Concept being taught
    - Small "End & Evaluate" button

### 2. Oral Viva Agent

Simulates a viva-voce examination. The AI asks questions, evaluates answers, probes deeper, and provides structured feedback — like a real examiner.

- [ ] Create `backend/app/agents/viva.py`:
  - Extends `BaseAgent`
  - **System Prompt**:
    ```
    You are an academic examiner conducting a viva voce (oral examination) for {subject_name}.

    BEHAVIOUR:
    1. Start by greeting the student and announcing the topic area
    2. Ask questions in increasing difficulty order:
       - Start with a foundational definition/concept question (Tier 1)
       - Progress to application questions (Tier 2)
       - End with analysis/synthesis questions (Tier 3)
    3. After each student answer:
       - Internally score it (do not reveal score yet)
       - Either: (a) probe deeper on the same topic, (b) move to next question, or (c) redirect if answer was off-track
    4. Probing techniques:
       - "Can you elaborate on that?"
       - "How would that apply in [specific scenario]?"
       - "What's the difference between X and Y?"
       - "That's interesting — but what about [edge case]?"
    5. After 6-8 questions, conclude the viva with a structured evaluation

    DIFFICULTY ADAPTATION:
    - Check student's confidence levels for each concept
    - Skip easy questions on concepts with confidence > 0.8
    - Spend more time on concepts with confidence 0.3-0.6
    - Gently introduce concepts with confidence < 0.3

    Available concepts for this subject (with student confidence):
    {concept_confidences}

    Concepts to focus on (based on priority):
    {priority_concepts}

    Course material for reference:
    {rag_context}

    EVALUATION FORMAT (at end):
    ## 📋 Viva Evaluation

    **Subject**: {subject_name}
    **Duration**: {num_questions} questions
    **Overall Grade**: {A/B/C/D/F}

    ### Question-by-Question Breakdown
    | # | Topic | Score | Notes |
    |---|-------|-------|-------|
    | 1 | {topic} | {x}/10 | {brief_note} |
    ...

    ### Strengths
    - ...

    ### Areas for Improvement
    - ...

    ### Recommended Study Areas
    - ...
    ```

  - **State tracking within conversation**:
    - `viva_questions: list[dict]` — each with `{question, concept_id, difficulty, student_answer, score, feedback}`
    - `current_question_index: int`
    - `difficulty_level: int` (1-3, adjusts based on performance)

  - **retrieve_context**:
    1. Load all concepts for the subject with student confidence
    2. Generate a question plan: select 6-8 concepts to cover, ordered by priority
    3. RAG search for the first concept to ask about
    4. As viva progresses, RAG search for each subsequent concept

  - **assess_understanding**:
    - After each answer, score it and update the concept's confidence
    - At the end, batch update all concepts touched

- [ ] Create `frontend/src/components/chat/viva-mode-indicator.tsx`:
  - Special UI for viva mode:
    - Shows "🎤 Viva Mode" banner
    - Question counter (e.g. "Question 3 of 8")
    - Difficulty indicator (Easy / Medium / Hard)
    - "End Viva" button to request early evaluation

### 3. Essay / Assignment Critique Agent

Accepts long-form text and returns structured critique with section-level feedback, rubric scoring, and citation checking against ingested course material.

- [ ] Create `backend/app/agents/critique.py`:
  - Extends `BaseAgent`
  - **System Prompt**:
    ```
    You are an academic writing tutor and assignment reviewer for {subject_name}.

    When a student submits text for review, provide a thorough critique covering:

    1. STRUCTURE ANALYSIS:
       - Does it have a clear introduction, body, and conclusion?
       - Is the argument logically structured?
       - Are paragraphs well-organised with topic sentences?

    2. CONTENT ACCURACY:
       - Check claims against the course material provided
       - Flag any factual errors or misconceptions
       - Note where citations/references are needed but missing
       - Identify claims that are well-supported vs unsupported

    3. DEPTH OF ANALYSIS:
       - Surface-level description vs deep analysis
       - Are concepts merely stated or actually explained and applied?
       - Are counterarguments considered?

    4. TECHNICAL WRITING QUALITY:
       - Clarity and conciseness
       - Appropriate use of technical terminology
       - Grammar and style (academic register)

    5. RUBRIC SCORING:
       Rate each dimension on a scale of 1-10:
       - Content Accuracy: {score}/10
       - Depth of Analysis: {score}/10
       - Structure & Organisation: {score}/10
       - Technical Writing: {score}/10
       - Use of Evidence: {score}/10
       - Overall: {weighted_average}/10

    Course material for fact-checking:
    {rag_context}

    IMPORTANT:
    - Be specific in your feedback — quote the student's text when pointing out issues
    - Provide concrete suggestions for improvement, not just criticism
    - Use a supportive, constructive tone
    - If the text is a code explanation, also evaluate the technical accuracy of the code discussion

    FORMAT YOUR RESPONSE AS:
    ## ✍️ Assignment Critique

    ### 📊 Rubric Scores
    | Dimension | Score | Comment |
    |-----------|-------|---------|
    | Content Accuracy | {x}/10 | {brief} |
    | Depth of Analysis | {x}/10 | {brief} |
    | Structure | {x}/10 | {brief} |
    | Technical Writing | {x}/10 | {brief} |
    | Use of Evidence | {x}/10 | {brief} |
    | **Overall** | **{x}/10** | |

    ### ✅ Strengths
    - ...

    ### ⚠️ Areas for Improvement

    #### Section-by-Section Feedback
    **[Section/Paragraph identifier]**
    > [Quoted student text]
    💬 [Your feedback]

    ### 💡 Specific Suggestions
    1. ...
    2. ...

    ### 📚 Missing References
    - [Topic X] — consider citing [relevant concept from course material]
    ```

  - **retrieve_context**:
    1. Extract key topics/terms from the submitted text (LLM extraction)
    2. RAG search for each key topic to get reference material
    3. Use reference material for fact-checking in the critique

  - **assess_understanding**:
    - Map overall rubric score to SM-2 quality for touched concepts
    - Identify which concepts the essay/assignment covers and update confidence accordingly

- [ ] Create `frontend/src/components/chat/critique-upload.tsx`:
  - Special input mode for critique:
    - Large textarea (not the normal chat input)
    - "Paste Essay" or "Upload .txt / .md" option
    - Character/word count
    - Subject selector (for context)
    - "Submit for Review" button
  - This component activates when the user selects the Critique agent from the toolbar

### 4. Wire All Agents into Orchestrator

- [ ] Update `backend/app/agents/orchestrator.py`:
  - Add nodes for all three new agents: `agent_protege`, `agent_viva`, `agent_critique`
  - Update conditional routing:
    ```
    teach_me → agent_protege
    viva → agent_viva
    critique → agent_critique
    ```
  - Remove all `agent_fallback` routing — every intent now has a proper agent

- [ ] Ensure all agents work with SSE streaming (implemented in Phase 3):
  - Each agent's `run_streaming` method yields proper events

### 5. Conversation Context: Multi-Turn Agent State

- [ ] Create `backend/app/services/conversation_context.py`:
  - `get_agent_context(db, conversation_id) -> dict`:
    - For multi-turn agent interactions (especially protégé and viva), load the ongoing agent-specific state:
      - Protégé: exchange_count, misconceptions, gaps, concept being taught
      - Viva: question_list, current_question_index, scores so far, difficulty_level
    - Stored in the conversation's metadata (JSONB) or in message metadata
  - `update_agent_context(db, conversation_id, context: dict)`:
    - Persists agent-specific state between turns

- [ ] The orchestrator's `classify_intent` should recognise when a conversation is already in protégé/viva mode and route back to the same agent without re-classifying:
  - Check conversation metadata for `active_mode: "protege" | "viva"`
  - If active mode is set and user hasn't explicitly ended it, route to that agent
  - User can end a mode by saying "end viva", "stop teaching", etc. — or clicking the UI button

### 6. Frontend: Agent Mode Switching UI

- [ ] Update `frontend/src/components/chat/agent-override-toolbar.tsx`:
  - Enable all 6 agent buttons (remove "disabled" state from protégé, viva, critique)
  - Each button now works:
    - 📚 **QA**: Normal QA mode
    - 📝 **Exam**: Exam predictor mode
    - 🎯 **Weak Points**: Weak point tracker
    - 🎓 **Protégé**: Starts teaching mode — shows concept selector first
    - 🎤 **Viva**: Starts viva mode — shows subject/topic selector first
    - ✍️ **Critique**: Shows essay submission textarea

- [ ] Create `frontend/src/components/chat/concept-picker.tsx`:
  - Modal/popover that shows when starting Protégé or Viva mode
  - Lists concepts for the selected subject, grouped by chapter
  - Shows confidence level next to each concept (colour-coded: red/yellow/green)
  - For Protégé: "Which concept do you want to teach?"
  - For Viva: "Which topics should the viva cover?" (multi-select)

- [ ] Update `frontend/src/components/chat/message-bubble.tsx`:
  - Handle special message formats:
    - Rubric tables (from critique agent) render as proper styled tables
    - Evaluation cards (from protégé/viva) render with coloured score badges
    - Progress bars for scores (e.g. 7/10 shows a 70% filled bar)

---

## Verification Criteria (Phase 4 is DONE when):

### Protégé Agent:
1. Selecting "Protégé" and choosing a concept starts teaching mode
2. The AI asks naive questions and probes the student's explanation
3. After 5-7 exchanges, or on demand, it provides a structured evaluation with scores
4. Student confidence updates based on teaching performance
5. Teaching mode indicator shows in the UI with exchange counter

### Viva Agent:
6. Selecting "Viva" starts a simulated oral exam
7. Questions progress from easy to hard
8. The AI probes answers and adjusts difficulty based on performance
9. After all questions, provides a structured evaluation with per-question scores
10. All concepts tested get confidence updates

### Critique Agent:
11. Submitting an essay via the critique textarea returns structured section-level feedback
12. Rubric scoring table is generated with per-dimension scores
13. Specific suggestions reference course material
14. Concepts covered in the essay get confidence updates

### Integration:
15. All 6 agents are accessible via the toolbar
16. Intent classification correctly routes to all 6 agents
17. Multi-turn conversations in protégé/viva mode maintain state across messages
18. SSE streaming works for all 6 agents

---

## DO NOT do in this phase:
- Do NOT build the dashboard (Phase 5)
- Do NOT implement concept graph visualisation (Phase 5)
- Do NOT add deployment configuration (Phase 6)
- Do NOT write tests (Phase 6)
