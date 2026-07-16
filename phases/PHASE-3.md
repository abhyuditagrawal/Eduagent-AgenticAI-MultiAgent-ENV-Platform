# PHASE 3: Weak-Point Tracker Agent + SSE Streaming + Spaced Repetition

## Overview
Implement the **Weak-Point Tracker Agent**, add **Server-Sent Events (SSE) streaming** for real-time token-by-token responses, and build the full spaced repetition engine. This phase makes the app feel responsive and intelligent.

**Depends on**: Phase 2 fully complete and working.

---

## Deliverables Checklist

### 1. SSE Streaming Infrastructure

- [ ] Create `backend/app/services/streaming.py`:
  - `stream_agent_response(orchestrator_graph, initial_state) -> AsyncGenerator[str, None]`:
    - Runs the LangGraph orchestrator
    - Yields SSE-formatted events as the LLM generates tokens
    - Event types (each is a JSON-encoded SSE `data` field):
      ```
      event: agent_start
      data: {"agent": "concept_qa", "intent": "conceptual_doubt"}

      event: rag_results
      data: {"sources": [{"file": "ml_notes.pdf", "page": 12, "score": 0.89}]}

      event: token
      data: {"content": "Poly"}

      event: token
      data: {"content": "morphism"}

      event: concept_update
      data: {"concept": "Polymorphism", "old_confidence": 0.3, "new_confidence": 0.45}

      event: done
      data: {"conversation_id": "...", "message_id": "..."}

      event: error
      data: {"message": "Something went wrong"}
      ```

- [ ] Modify `backend/app/services/llm.py`:
  - Add `generate_response_stream(messages, system_prompt, context_chunks) -> AsyncGenerator[str, None]`:
    - Uses Gemini's streaming API: `model.generate_content(..., stream=True)`
    - Yields each chunk's text as it arrives
  - Keep the non-streaming `generate_response` for backward compatibility

- [ ] Modify `backend/app/agents/base.py`:
  - Add `async def run_streaming(self, state: AgentState) -> AsyncGenerator[tuple[str, dict], None]`:
    - Yields `(event_type, event_data)` tuples
    - First yields `agent_start`, then `rag_results`, then `token` events, then `concept_update`, then `done`

- [ ] Modify `backend/app/routers/chat.py`:
  - Add SSE endpoint:
    ```python
    @router.post("/api/chat/stream")
    async def chat_stream(request: ChatRequest, user = Depends(get_current_user), db = Depends(get_db)):
        async def event_generator():
            # Build state, run orchestrator with streaming
            async for event_type, event_data in stream_agent_response(...):
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    ```
  - The original `POST /api/chat` remains for non-streaming fallback

- [ ] **Frontend SSE consumption**:
  - Create `frontend/src/lib/sse.ts`:
    - `streamChat(message, conversationId, subjectId, onEvent)` function:
      - Uses `fetch` with `POST` to `/api/chat/stream`
      - Parses the SSE stream using `ReadableStream` + `TextDecoder`
      - Calls `onEvent(type, data)` callback for each event
    - Handle reconnection on network errors
    - Handle `event: error` events

  - Modify `frontend/src/stores/chat-store.ts`:
    - Add `isStreaming: boolean` state
    - Add `streamingContent: string` state (accumulates tokens during streaming)
    - Add `streamingMetadata: object` state (accumulates trace info during streaming)
    - `sendMessage` action now uses SSE:
      1. Set `isStreaming = true`
      2. Add user message to messages array immediately
      3. Add empty assistant message placeholder
      4. Call `streamChat()`, on each `token` event → append to `streamingContent`
      5. On `done` event → finalize message, set `isStreaming = false`

  - Modify `frontend/src/components/chat/message-bubble.tsx`:
    - Show typing indicator / cursor animation while streaming
    - Render markdown progressively as tokens arrive

  - Modify `frontend/src/components/chat/agent-trace-panel.tsx`:
    - Update in real-time during streaming:
      - On `agent_start` → show which agent is handling (with a "thinking..." animation)
      - On `rag_results` → populate sources list
      - On `concept_update` → show confidence changes with animated bars
      - On `done` → finalize all trace info

### 2. Weak-Point Tracker Agent

- [ ] Create `backend/app/agents/weak_point_tracker.py`:
  - Extends `BaseAgent`
  - **System Prompt**:
    ```
    You are a learning diagnostician for {subject_name}. Your role is to help students identify and address their weak areas.

    CAPABILITIES:
    1. WEAK POINT ANALYSIS: Review the student's concept mastery data and identify patterns:
       - Concepts with low confidence scores
       - Concepts that are prerequisites for many others (high-impact gaps)
       - Concepts where confidence is decaying (not reviewed recently)
       - Concepts with many attempts but low success rate (persistent confusion)

    2. TARGETED REVIEW: Generate focused review material for weak concepts:
       - Concise concept summaries
       - Key points to remember
       - Common misconceptions to avoid
       - Quick self-test questions

    3. STUDY SCHEDULING: Suggest which concepts to review next based on:
       - Spaced repetition schedule (concepts overdue for review)
       - Prerequisite ordering (review foundations before advanced topics)
       - Exam proximity (if mentioned by student)

    4. PROGRESS TRACKING: When the student asks about their progress:
       - Summarise mastery levels across the subject
       - Highlight improvements since last check
       - Identify persistent weak areas

    Student's full concept mastery data:
    {concept_mastery_table}

    Concepts overdue for review (next_review_at < now):
    {overdue_concepts}

    Prerequisite gaps (concepts with unmastered prerequisites):
    {prerequisite_gaps}

    Course material context:
    {rag_context}

    IMPORTANT: Always be encouraging. Frame weaknesses as "opportunities for growth" not failures.
    When listing weak areas, also acknowledge concepts the student has mastered well.
    ```

  - **retrieve_context**:
    1. Load full student state for the subject
    2. Identify weak concepts (confidence < 0.4)
    3. Identify overdue concepts (next_review_at < now())
    4. For weak concepts, find prerequisite gaps
    5. RAG search for weak concept names to get relevant material
    6. Sort by priority: overdue > prerequisite gaps > low confidence

  - **Tools available to this agent**:
    - `get_weak_concepts(threshold)` → returns weak concept list
    - `get_overdue_reviews()` → returns concepts past their review date
    - `get_concept_details(concept_id)` → returns full concept info + prerequisites
    - `generate_review_card(concept_id)` → generates a focused review summary using RAG
    - `schedule_review(concept_id, quality)` → updates SM-2 schedule

  - **assess_understanding**:
    - If the student answers review questions → evaluate → update confidence via SM-2
    - If just reviewing weak points → mark concepts as "seen" (update `last_seen_at`)

### 3. Enhanced SM-2 Engine

- [ ] Update `backend/app/services/student_state.py`:
  - Add `get_overdue_concepts(db, student_id, subject_id) -> list`:
    - Returns concepts where `next_review_at < now()`, ordered by how overdue they are
  - Add `get_mastery_summary(db, student_id, subject_id) -> dict`:
    - Returns aggregated stats:
      ```python
      {
          "total_concepts": 45,
          "mastered": 12,        # confidence >= 0.8
          "proficient": 18,      # confidence 0.5-0.8
          "developing": 8,       # confidence 0.2-0.5
          "not_started": 7,      # confidence < 0.2
          "overdue_reviews": 5,
          "overall_score": 0.56, # weighted average
          "strongest_chapter": "Chapter 3: Design Patterns",
          "weakest_chapter": "Chapter 7: Concurrency"
      }
      ```
  - Add `decay_confidence(db, student_id)`:
    - Called periodically (or on login)
    - For concepts not reviewed within 2x their interval, reduce confidence by 10%
    - This simulates natural forgetting and drives the weak-point tracker

  - Add `get_study_priority_queue(db, student_id, subject_id) -> list`:
    - Returns ordered list of concepts to study, prioritised by:
      1. Overdue reviews (most overdue first)
      2. Prerequisite gaps for upcoming concepts
      3. Low confidence concepts in high-difficulty tier
    - Each item includes: concept info, reason for priority, suggested action

### 4. Wire Up Weak-Point Agent in Orchestrator

- [ ] Update `backend/app/agents/orchestrator.py`:
  - Replace the `agent_fallback` routing for `weak_points` intent with `agent_weak_point_tracker`
  - Add the weak-point tracker node to the graph

### 5. Proactive Nudges (Background Task)

- [ ] Create `backend/app/services/nudge_engine.py`:
  - `generate_nudges(db, student_id) -> list[dict]`:
    - Checks for:
      1. Concepts overdue for review (> 2x their interval)
      2. Enrolled subjects not studied in 3+ days
      3. Upcoming exam dates (if set) with unprepared concepts
    - Returns list of nudge objects:
      ```python
      {
          "type": "review_overdue",
          "concept_name": "Binary Trees",
          "subject": "Data Structures",
          "message": "You haven't reviewed Binary Trees in 5 days. Quick 2-minute refresher?",
          "priority": "high",
          "action": "start_review"  # frontend can map this to an action
      }
      ```

- [ ] Add endpoint `GET /api/nudges` in a new router `backend/app/routers/nudges.py`:
  - Returns active nudges for the current student
  - Frontend will poll this or fetch on page load

- [ ] **Frontend nudge display**:
  - Create `frontend/src/components/nudge-banner.tsx`:
    - Shows at the top of the chat page when nudges are available
    - Dismissible
    - Clicking a nudge starts a conversation with the weak-point tracker about that concept
  - Fetch nudges on dashboard/chat page load

### 6. Frontend Streaming Polish

- [ ] Create `frontend/src/components/chat/streaming-indicator.tsx`:
  - Shows which agent is currently "thinking" with a pulsing dot animation
  - Agent name + icon
  - Disappears when streaming is done

- [ ] Add keyboard shortcuts:
  - `Ctrl+Enter` or `Cmd+Enter`: Send message (alternative to Enter)
  - `Escape`: Cancel current streaming response
  - `/qa`, `/exam`, `/weak`: Quick-switch agent override shortcuts typed in the input

- [ ] Create `frontend/src/components/chat/agent-override-toolbar.tsx`:
  - Row of agent buttons above the chat input
  - Clicking one sets `agent_override` for the next message
  - Buttons: 📚 QA, 📝 Exam, 🎯 Weak Points, 🎓 Protégé (disabled), 🎤 Viva (disabled), ✍️ Critique (disabled)
  - Active button has a highlight ring
  - "Auto" button (default) lets the orchestrator decide

---

## Verification Criteria (Phase 3 is DONE when):
1. Chat responses stream token-by-token in real-time (visible in the UI)
2. Agent trace panel updates live during streaming (agent start, sources, concept updates)
3. Sending "What are my weak points in ML?" routes to the Weak-Point Tracker and returns personalised analysis
4. The weak-point tracker correctly identifies concepts with low confidence
5. SM-2 spaced repetition scheduling works: after reviewing a concept, `next_review_at` is set correctly
6. Confidence decay runs and concepts not reviewed become weaker over time
7. Nudge banners appear when concepts are overdue for review
8. Agent override toolbar works — clicking "QA" forces the next message to the QA agent
9. Streaming can be cancelled mid-response without errors

---

## DO NOT do in this phase:
- Do NOT implement Protégé, Viva, or Critique agents (Phase 4)
- Do NOT build the dashboard visualisations (Phase 5)
- Do NOT implement concept graph visualisation on frontend (Phase 5)
