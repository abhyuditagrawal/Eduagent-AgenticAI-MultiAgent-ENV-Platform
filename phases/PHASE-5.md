# PHASE 5: Dashboard, Concept Graph Visualisation, and Analytics

## Overview
Build the student-facing **dashboard** with concept mastery heatmaps, interactive concept graph visualisation, exam readiness scores, study activity timeline, and the admin panel for managing subjects and content. This phase transforms the app from a chat tool into a full learning platform.

**Depends on**: Phase 4 fully complete and working.

---

## Deliverables Checklist

### 1. Dashboard API Endpoints

- [ ] Create `backend/app/routers/dashboard.py`:

  - `GET /api/dashboard/mastery?subject_id={id}`:
    - Returns concept mastery data for the heatmap:
      ```json
      {
        "subject": {"id": "...", "name": "ML", "code": "ML"},
        "overall_score": 0.62,
        "chapters": [
          {
            "name": "Chapter 1: Introduction",
            "average_confidence": 0.85,
            "concepts": [
              {
                "id": "...",
                "name": "Supervised Learning",
                "confidence": 0.9,
                "attempts": 12,
                "last_seen": "2025-01-15T10:30:00Z",
                "status": "mastered"
              },
              {
                "id": "...",
                "name": "Unsupervised Learning",
                "confidence": 0.3,
                "attempts": 2,
                "last_seen": "2025-01-10T14:00:00Z",
                "status": "developing"
              }
            ]
          }
        ]
      }
      ```
    - Status labels: `mastered` (≥0.8), `proficient` (0.5-0.8), `developing` (0.2-0.5), `not_started` (<0.2)

  - `GET /api/dashboard/weak-points?subject_id={id}`:
    - Returns prioritised weak concepts with actionable suggestions:
      ```json
      {
        "weak_concepts": [
          {
            "concept": {"id": "...", "name": "Backpropagation", "chapter": "Ch 4"},
            "confidence": 0.15,
            "reason": "prerequisite_gap",
            "missing_prerequisites": ["Gradient Descent", "Chain Rule"],
            "suggestion": "Review Gradient Descent first, then revisit Backpropagation",
            "days_since_review": 12,
            "priority": "high"
          }
        ],
        "total_weak": 8,
        "total_concepts": 45
      }
      ```

  - `GET /api/dashboard/exam-readiness?subject_id={id}`:
    - Returns exam readiness analysis:
      ```json
      {
        "overall_readiness": 0.65,
        "readiness_label": "Moderately Prepared",
        "by_difficulty": {
          "foundational": 0.85,
          "intermediate": 0.60,
          "advanced": 0.30
        },
        "high_risk_topics": [
          {"name": "Neural Networks", "confidence": 0.2, "difficulty": 3, "impact": "high"}
        ],
        "strengths": [
          {"name": "Linear Regression", "confidence": 0.95, "difficulty": 1}
        ],
        "recommended_study_hours": 12,
        "study_plan": [
          {"day": 1, "focus": "Gradient Descent", "duration_hours": 2, "reason": "Foundation for Neural Networks"},
          {"day": 2, "focus": "Backpropagation", "duration_hours": 3, "reason": "Critical for exam, currently weak"}
        ]
      }
      ```

  - `GET /api/dashboard/activity?days=30`:
    - Returns study activity timeline:
      ```json
      {
        "daily_activity": [
          {
            "date": "2025-01-15",
            "messages_sent": 15,
            "concepts_reviewed": 4,
            "agents_used": {"concept_qa": 8, "exam_predictor": 5, "viva": 2},
            "confidence_gained": 0.12,
            "time_spent_minutes": 45
          }
        ],
        "streak": {
          "current": 5,
          "longest": 12,
          "total_days_active": 28
        },
        "totals": {
          "total_messages": 342,
          "total_concepts_mastered": 18,
          "total_study_hours": 24.5
        }
      }
      ```

  - `GET /api/dashboard/concept-graph?subject_id={id}`:
    - Returns the concept graph with student mastery data overlaid:
      ```json
      {
        "nodes": [
          {
            "id": "...",
            "name": "Linear Regression",
            "chapter": "Ch 2",
            "difficulty": 1,
            "confidence": 0.9,
            "status": "mastered",
            "x": null, "y": null
          }
        ],
        "edges": [
          {"source": "...", "target": "...", "strength": 1.0}
        ]
      }
      ```

### 2. Frontend Dashboard Layout

- [ ] Create `frontend/src/app/(dashboard)/dashboard/page.tsx`:
  - Subject tabs at the top (one tab per enrolled subject)
  - Grid layout with 4 sections:
    1. **Top left**: Overall mastery score (large radial progress chart)
    2. **Top right**: Exam readiness gauge
    3. **Middle**: Concept mastery heatmap
    4. **Bottom left**: Weak points list with action buttons
    5. **Bottom right**: Activity timeline / streak

- [ ] Update sidebar navigation in `frontend/src/app/(dashboard)/layout.tsx`:
  - Add "Dashboard" link with chart icon
  - Add "Concept Map" link with network icon
  - Active page highlighting

### 3. Mastery Heatmap Component

- [ ] Install visualization library:
  ```bash
  npm install recharts
  ```

- [ ] Create `frontend/src/components/dashboard/mastery-heatmap.tsx`:
  - Grid of concept tiles, grouped by chapter
  - Each tile shows concept name + confidence score
  - Color-coded:
    - `mastered` (≥0.8): Green
    - `proficient` (0.5-0.8): Blue
    - `developing` (0.2-0.5): Orange
    - `not_started` (<0.2): Red/Grey
  - Hover tooltip: shows attempts, last seen date, next review date
  - Click: opens a popover with options:
    - "Review this concept" → navigates to chat with QA agent + concept context
    - "Teach this concept" → navigates to chat with Protégé agent
    - "Get quizzed" → navigates to chat with Viva agent on this concept

### 4. Exam Readiness Gauge

- [ ] Create `frontend/src/components/dashboard/exam-readiness.tsx`:
  - Large circular gauge showing overall readiness percentage
  - Color: red (<40%), orange (40-60%), yellow (60-80%), green (>80%)
  - Below the gauge: three smaller bars for foundational/intermediate/advanced readiness
  - "High Risk Topics" list below with red badges
  - "Generate Study Plan" button → calls the exam readiness API and displays the day-by-day plan

### 5. Weak Points Widget

- [ ] Create `frontend/src/components/dashboard/weak-points-list.tsx`:
  - Ordered list of weak concepts
  - Each item shows:
    - Concept name + chapter
    - Confidence bar (colored)
    - Priority badge (high/medium/low)
    - Reason icon (prerequisite gap / low confidence / overdue review)
    - Quick action buttons: "Review" | "Practice" | "Teach"
  - "Review" → opens chat with QA agent
  - "Practice" → opens chat with Exam Predictor for practice questions on this concept
  - "Teach" → opens chat with Protégé agent

### 6. Activity Timeline

- [ ] Create `frontend/src/components/dashboard/activity-timeline.tsx`:
  - GitHub-style contribution heatmap (last 30 days)
  - Each cell = one day, color intensity = number of interactions
  - Below: streak counter with fire emoji 🔥
  - Totals bar: messages sent, concepts mastered, study hours

- [ ] Create `frontend/src/components/dashboard/activity-chart.tsx`:
  - Line chart (recharts) showing daily confidence gain over time
  - Toggleable: by subject or all subjects combined

### 7. Interactive Concept Graph Visualisation

- [ ] Install graph visualisation library:
  ```bash
  npm install @xyflow/react
  ```

- [ ] Create `frontend/src/app/(dashboard)/concept-map/page.tsx`:
  - Full-page interactive concept graph using React Flow
  - Subject selector at top
  - Loads graph data from `/api/dashboard/concept-graph`

- [ ] Create `frontend/src/components/dashboard/concept-graph-view.tsx`:
  - Uses React Flow to render the concept graph:
    - Each node = a concept, sized by importance (number of dependents)
    - Node color = confidence level (same color scheme as heatmap)
    - Node label = concept name + confidence percentage
    - Edges = prerequisite relationships, with arrows showing direction
    - Edge color: green if both source and target are mastered, red if there's a gap
  - Interactive features:
    - Zoom and pan
    - Click a node → shows popover with concept details, confidence history, and action buttons
    - Highlight path: click a concept to highlight all its prerequisites and dependents
    - Filter: toggle to show only weak concepts, only a specific chapter, etc.
  - Layout: automatic hierarchical layout (dagre algorithm) — prerequisites at top, advanced concepts at bottom
  - Legend showing color meanings

- [ ] Install dagre for layout:
  ```bash
  npm install dagre @types/dagre
  ```

### 8. Admin Panel Enhancements

- [ ] Create `frontend/src/app/(dashboard)/admin/subjects/page.tsx`:
  - List all subjects with concept counts and enrolled student counts
  - "Add Subject" button → modal with form (code, name, description)
  - Per-subject actions:
    - "Manage Concepts" → shows concept list with edit/delete
    - "Upload Material" → links to upload page
    - "View Graph" → links to concept graph view

- [ ] Create `frontend/src/app/(dashboard)/admin/concepts/[subjectId]/page.tsx`:
  - Table of all concepts for a subject
  - Columns: name, chapter, difficulty, prerequisites count
  - Inline edit for name, description, difficulty
  - "Populate from Syllabus" button at top → calls concept extraction API
  - Manual "Add Concept" button
  - "Add Prerequisite" button per concept → dropdown to select prerequisite concept

### 9. Onboarding Flow

- [ ] Create `frontend/src/app/(dashboard)/onboarding/page.tsx`:
  - Shown after first login (if user has 0 enrollments)
  - Step 1: "Welcome! Select your subjects" → shows all available subjects as cards
  - Step 2: "Upload your study material" → PDF upload per selected subject (optional, can skip)
  - Step 3: "You're all set!" → redirects to dashboard
  - Progress bar at top showing current step

- [ ] Add a check in the dashboard layout: if user has 0 enrollments, redirect to onboarding

### 10. Profile Page

- [ ] Create `frontend/src/app/(dashboard)/profile/page.tsx`:
  - User info (name, email, joined date)
  - Enrolled subjects with option to unenroll
  - Study statistics summary
  - Change password form
  - "Export My Data" button (downloads JSON of all student state — nice for capstone demo)

---

## Verification Criteria (Phase 5 is DONE when):
1. Dashboard loads with real data for an enrolled subject
2. Mastery heatmap correctly shows all concepts colour-coded by confidence
3. Clicking a concept in the heatmap navigates to chat with the right agent and context
4. Exam readiness gauge shows correct readiness score and high-risk topics
5. Weak points list shows prioritised concepts with actionable buttons
6. Activity timeline shows daily interaction data (including streak)
7. Concept graph visualisation renders with correct nodes, edges, and confidence colors
8. Clicking a node in the concept graph highlights its prerequisites
9. Admin can create subjects, populate concepts from syllabus, and manage concept relationships
10. New user onboarding flow works end-to-end (register → select subjects → dashboard)
11. Profile page shows correct stats and allows password change

---

## DO NOT do in this phase:
- Do NOT modify agent logic (agents are done in Phase 4)
- Do NOT add deployment configuration (Phase 6)
- Do NOT write automated tests (Phase 6)
