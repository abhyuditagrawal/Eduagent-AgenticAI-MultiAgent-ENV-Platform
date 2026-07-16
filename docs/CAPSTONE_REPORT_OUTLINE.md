# Suggested Capstone Report Outline

## 1. Introduction
- **Problem statement**: Fragmented ed-tech tools fail to provide a unified, intelligent learning ecosystem. Students juggle multiple apps for Q&A, exam prep, revision, and self-assessment with no continuity or personalization.
- **Objectives**: Build a multi-agent AI platform that adapts to each student's learning state, tracks concept mastery, and provides six specialized pedagogical agents in one unified interface.
- **Scope**: Four engineering subjects (MSA, HCI, Cyber Security, ML), six agents, real-time streaming, spaced repetition, concept graph visualization, Bayesian Knowledge Tracing, multi-agent debate, cognitive Learning Genome, and ZPD-based knowledge frontier.

## 2. Literature Review
- **RAG systems**: Retrieval-Augmented Generation for domain-specific Q&A
- **Multi-agent AI architectures**: LangGraph orchestration, intent classification, agent routing
- **Spaced repetition (SM-2)**: SuperMemo algorithm for optimal review scheduling
- **Bayesian Knowledge Tracing**: Corbett & Anderson (1994) Hidden Markov Model for skill mastery estimation
- **Ebbinghaus Forgetting Curve**: Predictive memory decay and optimal review timing
- **Feynman Technique**: Learning through teaching — the Protégé agent approach
- **Zone of Proximal Development (ZPD)**: Vygotsky (1978) — identifying concepts within reach with scaffolding
- **Adversarial / debate-based pedagogy**: Multi-perspective reasoning for deeper understanding
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
  - Bayesian Knowledge Tracing with difficulty-scaled P(T) and Ebbinghaus forgetting prediction
  - Multi-agent debate orchestration (Proponent / Skeptic / Judge) with RAG grounding
  - Learning Genome: aggregating behavioural signals + LLM-distilled misconception detection
  - Knowledge Frontier: prerequisite-graph partitioning into mastered / frontier (ZPD) / locked
- **Agent-specific implementation details**: Intent classification, context retrieval, reasoning chains

## 5. Results & Evaluation
- **Retrieval quality metrics**: Precision/recall of RAG retrievals
- **Agent routing accuracy**: Intent classification correctness across 7 intents
- **User study results**: SUS (System Usability Scale) scores
- **Performance metrics**: Token streaming latency, API response times, concept graph rendering

## 6. Discussion
- **Strengths**: Unified platform, adaptive learning, six specialized agents, real-time feedback, theoretically-grounded knowledge tracing (BKT), multi-perspective debate for critical thinking, personalised Learning Genome, ZPD-guided learning path
- **Limitations**: Gemini free tier rate limits, limited evaluation data, no mobile app, BKT parameters not yet calibrated per-student
- **Comparison with existing tools**: Feature matrix vs Quizlet, ChatGPT, Notion AI, Intelligent Tutoring Systems (ITS)
- **Future work**: Mobile app, collaborative learning, voice-based viva, multi-modal content, per-student BKT parameter fitting, social knowledge graphs, peer-debate mode

## 7. Conclusion
Summary of contributions, impact on learning outcomes, path to production deployment.

---

## Appendices
- **Appendix A**: Full API documentation (link to FastAPI /docs)
- **Appendix B**: User study questionnaire and raw results
- **Appendix C**: Sample agent interactions (screenshots + transcripts for all 6 agents)
- **Appendix D**: Concept graph examples per subject
- **Appendix E**: BKT mathematical derivation and forgetting curve analysis
- **Appendix F**: Multi-agent debate transcript examples
- **Appendix G**: Learning Genome sample profiles and agent prompt injection examples
