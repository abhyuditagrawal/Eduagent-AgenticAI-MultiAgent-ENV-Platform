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
