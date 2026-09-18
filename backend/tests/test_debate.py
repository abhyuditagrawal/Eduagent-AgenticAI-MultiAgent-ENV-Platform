"""Unit tests for the multi-agent debate helpers.

Inlines the pure helper and prompt constants from app.agents.debate so the
test file can run without the full backend dependency chain.
"""

# ---------- Inlined from app.agents.debate ----------

PROPONENT_PROMPT = """You are the PROPONENT in an academic debate about a student's question for the subject "{subject}".

Your role: present the clearest, most widely-accepted answer. Be rigorous and cite reasoning. Use the course material below when relevant.

{context}

Question: {question}

Give your position in 3-5 concise sentences. Be confident but precise."""


SKEPTIC_PROMPT = """You are the SKEPTIC in an academic debate about a student's question for the subject "{subject}".

Your role: critically examine the Proponent's answer. Point out edge cases, common misconceptions, oversimplifications, alternative interpretations, or conditions under which it fails. Use the course material below when relevant. Do NOT be contrarian for its own sake - be intellectually honest.

{context}

Question: {question}

Proponent's position:
{proponent}

Give your critique in 3-5 concise sentences."""


JUDGE_PROMPT = """You are the JUDGE of an academic debate for the subject "{subject}". You are neutral, precise, and pedagogical.

Synthesise the debate into a single balanced answer for the student. Resolve the disagreement, keep what is correct from both sides, and explicitly note any remaining nuance or conditions. End with a one-line "Confidence: High/Medium/Low" rating.

{context}

Question: {question}

Proponent:
{proponent}

Skeptic:
{skeptic}

Write the consensus answer for the student (4-7 sentences), then the confidence line."""


PEER_JUDGE_PROMPT = """You are moderating a debate between two students on the topic below, for the subject "{subject}". You are an encouraging but rigorous AI moderator.

{context}

Topic / Question: {topic}

{arguments_text}

Write a moderation verdict that:
1. Names one clear strength in EACH student's argument (be specific, quote a phrase if useful).
2. Identifies which position is better supported by the course material and reasoning, or says it's a genuine tie.
3. Notes anything either side got factually wrong or oversimplified, grounded in the course material above if provided.
4. Ends with a one-line "Confidence: High/Medium/Low" rating.
Keep it to 5-8 sentences, addressed to both students by name where given."""


def _format_arguments(arguments: list[dict]) -> str:
    return "\n\n".join(
        f"{a.get('name', 'A student')}'s position:\n{a.get('content', '')}"
        for a in arguments
    )


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    text = "\n--- Course Material ---\n"
    for i, c in enumerate(chunks, 1):
        src = c.get("source_file", "unknown")
        page = c.get("page", "?")
        text += f"[{i}] ({src} p.{page}) {c.get('text', '')[:600]}\n"
    text += "--- End Material ---\n"
    return text

# ---------- End inlined ----------


class TestFormatContext:
    def test_empty_chunks_returns_empty_string(self):
        assert _format_context([]) == ""

    def test_single_chunk_formatted(self):
        chunks = [{"source_file": "ch1.pdf", "page": 3, "text": "Hello world"}]
        out = _format_context(chunks)
        assert "Course Material" in out
        assert "ch1.pdf" in out
        assert "p.3" in out
        assert "Hello world" in out

    def test_multiple_chunks_numbered(self):
        chunks = [
            {"source_file": "a.pdf", "page": 1, "text": "first"},
            {"source_file": "b.pdf", "page": 2, "text": "second"},
        ]
        out = _format_context(chunks)
        assert "[1]" in out
        assert "[2]" in out

    def test_long_text_truncated(self):
        chunks = [{"source_file": "x.pdf", "page": 1, "text": "A" * 2000}]
        out = _format_context(chunks)
        # Text should be capped at 600 chars
        assert len(out) < 2000

    def test_missing_fields_graceful(self):
        chunks = [{"text": "some content"}]
        out = _format_context(chunks)
        assert "some content" in out
        assert "unknown" in out  # default source_file


class TestPromptTemplates:
    def test_proponent_has_placeholders(self):
        assert "{subject}" in PROPONENT_PROMPT
        assert "{context}" in PROPONENT_PROMPT
        assert "{question}" in PROPONENT_PROMPT

    def test_skeptic_has_placeholders(self):
        assert "{proponent}" in SKEPTIC_PROMPT
        assert "{question}" in SKEPTIC_PROMPT

    def test_judge_has_all_parties(self):
        assert "{proponent}" in JUDGE_PROMPT
        assert "{skeptic}" in JUDGE_PROMPT
        assert "{question}" in JUDGE_PROMPT

    def test_proponent_template_renders(self):
        text = PROPONENT_PROMPT.format(subject="ML", context="", question="What is SGD?")
        assert "ML" in text
        assert "SGD" in text

    def test_skeptic_template_renders(self):
        text = SKEPTIC_PROMPT.format(
            subject="HCI", context="", question="What is UX?", proponent="UX is design."
        )
        assert "HCI" in text
        assert "UX is design" in text


class TestPeerDebate:
    def test_peer_judge_prompt_has_placeholders(self):
        assert "{subject}" in PEER_JUDGE_PROMPT
        assert "{topic}" in PEER_JUDGE_PROMPT
        assert "{arguments_text}" in PEER_JUDGE_PROMPT

    def test_format_arguments_includes_both_students(self):
        args = [
            {"name": "alice@test.com", "content": "I think X because Y."},
            {"name": "bob@test.com", "content": "I disagree, Z matters more."},
        ]
        text = _format_arguments(args)
        assert "alice@test.com" in text
        assert "bob@test.com" in text
        assert "I think X because Y." in text
        assert "I disagree, Z matters more." in text

    def test_format_arguments_handles_missing_name(self):
        text = _format_arguments([{"content": "anonymous take"}])
        assert "A student's position" in text
        assert "anonymous take" in text

    def test_format_arguments_empty_list(self):
        assert _format_arguments([]) == ""

    def test_peer_judge_prompt_renders(self):
        args_text = _format_arguments([
            {"name": "alice", "content": "position A"},
            {"name": "bob", "content": "position B"},
        ])
        text = PEER_JUDGE_PROMPT.format(
            subject="OS", context="", topic="Is preemptive scheduling always better?",
            arguments_text=args_text,
        )
        assert "OS" in text
        assert "position A" in text
        assert "position B" in text
        assert "Confidence: High/Medium/Low" in text
