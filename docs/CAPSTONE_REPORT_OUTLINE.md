# Suggested Capstone Report Outline

## 1. Introduction
- **Problem statement**: Fragmented ed-tech tools fail to provide a unified, intelligent learning ecosystem. Students juggle multiple apps for Q&A, exam prep, revision, and self-assessment with no continuity or personalization.
- **Objectives**: Build a multi-agent AI platform that adapts to each student's learning state, tracks concept mastery, and provides six specialized pedagogical agents in one unified interface.
- **Scope**: Four engineering subjects (MSA, HCI, Cyber Security, ML), six agents, real-time streaming, spaced repetition, concept graph visualization.

## 2. Literature Review
- **RAG systems**: Retrieval-Augmented Generation for domain-specific Q&A
- **Multi-agent AI architectures**: LangGraph orchestration, intent classification, agent routing
- **Spaced repetition (SM-2)**: SuperMemo algorithm for optimal review scheduling
- **Feynman Technique**: Learning through teaching — the Protégé agent approach
- **Educational technology landscape**: Comparison with Quizlet, Khan Academy, ChatGPT, Duolingo

## 3. System Design
- **Architecture overview**: Cite ARCHITECTURE.md diagrams — three-tier (frontend, orchestrator, data layer)
- **Agent design patterns**: BaseAgent → specialized agents, shared context retrieval, reasoning, assessment
- **Data model**: PostgreSQL (users, subjects, concepts, student state) + Qdrant (document embeddings)
- **Tech stack justification**: Next.js (React SSR), FastAPI (async Python), Gemini 2.0 Flash (free tier), Qdrant (vector search)

## 4. Implementation
- **Phase-by-phase development narrative**: 6 phases from scaffolding to deployment
- **Key technical challenges and solutions**:
  - SSE streaming for real-time LLM responses
  - Multi-turn conversation state persistence
  - Concept graph extraction from unstructured syllabus text
  - SM-2 confidence decay and review scheduling
- **Agent-specific implementation details**: Intent classification, context retrieval, reasoning chains

## 5. Results & Evaluation
- **Retrieval quality metrics**: Precision/recall of RAG retrievals
- **Agent routing accuracy**: Intent classification correctness across 7 intents
- **User study results**: SUS (System Usability Scale) scores
- **Performance metrics**: Token streaming latency, API response times, concept graph rendering

## 6. Discussion
- **Strengths**: Unified platform, adaptive learning, six specialized agents, real-time feedback
- **Limitations**: Gemini free tier rate limits, limited evaluation data, no mobile app
- **Comparison with existing tools**: Feature matrix vs Quizlet, ChatGPT, Notion AI
- **Future work**: Mobile app, collaborative learning, voice-based viva, multi-modal content

## 7. Conclusion
Summary of contributions, impact on learning outcomes, path to production deployment.

---

## Appendices
- **Appendix A**: Full API documentation (link to FastAPI /docs)
- **Appendix B**: User study questionnaire and raw results
- **Appendix C**: Sample agent interactions (screenshots + transcripts for all 6 agents)
- **Appendix D**: Concept graph examples per subject
