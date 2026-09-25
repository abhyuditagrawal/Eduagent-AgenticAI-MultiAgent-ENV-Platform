"""Security Tools agent - Cyber Forensics / Cryptography & Network Security.

Follows the same shape as every other agent (BaseAgent subclass, retrieved
via the normal orchestrator node), with one difference: retrieve_context()
detects a tool command in the student's message and, if present, computes it
deterministically (app.services.security_tools - pure stdlib, no LLM) and
injects the result as a synthetic RAG chunk. The LLM then narrates/explains
a real computed value instead of trying to do arithmetic or cryptography
itself, which it is unreliable at - the same "ground the model, don't trust
it with numbers" principle the rest of the platform already uses for course
material.

Recognised commands (case-insensitive, typed as the whole message):
  /caesar encode shift=<n> <text>
  /caesar decode shift=<n> <text>
  /caesar crack <ciphertext>
  /vigenere encode key=<key> <text>
  /vigenere decode key=<key> <text>
  /freq <text>
  /hash <md5|sha1|sha256|sha512> <text>
  /rsa p=<n> q=<n> [e=<n>] [m=<n>]
  /logscan <log lines>
"""

import re

import structlog

from app.agents.base import BaseAgent
from app.agents.state import AgentState
from app.rag.retriever import retrieve
from app.services import security_tools as tools

logger = structlog.get_logger()

SECURITY_TOOLS_SYSTEM_PROMPT = """You are a Cyber Forensics / Cryptography & Network Security tutor.

A "Security Tool Output" block may appear in the Retrieved Context below. If it does:
- Treat every number and string in it as ground truth from a deterministic tool - it was computed by real code, not guessed. Never recompute, "correct", or contradict it.
- Walk the student through HOW that result was produced, step by step, connecting it to the underlying concept (e.g. modular arithmetic for RSA, frequency analysis for a Caesar crack, why a hash algorithm is or isn't collision-resistant).
- If the tool reported an error (invalid input), explain what was wrong in plain terms and show the correct command syntax rather than inventing a result.

If no Security Tool Output block is present, the student is asking a conceptual question - answer normally, grounded in the course material context, exactly as you would for any other topic.

Available commands you can tell the student to use:
  /caesar encode shift=<n> <text>   /caesar decode shift=<n> <text>   /caesar crack <ciphertext>
  /vigenere encode key=<word> <text>   /vigenere decode key=<word> <text>
  /freq <text>                       (letter-frequency table for cryptanalysis)
  /hash <md5|sha1|sha256|sha512> <text>
  /rsa p=<prime> q=<prime> [e=<n>] [m=<n>]   (textbook RSA key generation, optionally encrypt/decrypt a small message m)
  /logscan <pasted log lines>         (rule-based IOC scanner)"""

_HASH_ALGOS = {"md5", "sha1", "sha256", "sha512"}

_COMMANDS: list[tuple[str, re.Pattern]] = [
    ("caesar_encode", re.compile(r"^/caesar\s+encode\s+shift=(-?\d+)\s+(.+)$", re.I | re.S)),
    ("caesar_decode", re.compile(r"^/caesar\s+decode\s+shift=(-?\d+)\s+(.+)$", re.I | re.S)),
    ("caesar_crack", re.compile(r"^/caesar\s+crack\s+(.+)$", re.I | re.S)),
    ("vigenere_encode", re.compile(r"^/vigenere\s+encode\s+key=(\S+)\s+(.+)$", re.I | re.S)),
    ("vigenere_decode", re.compile(r"^/vigenere\s+decode\s+key=(\S+)\s+(.+)$", re.I | re.S)),
    ("freq", re.compile(r"^/freq\s+(.+)$", re.I | re.S)),
    ("hash", re.compile(r"^/hash\s+(md5|sha1|sha256|sha512)\s+(.+)$", re.I | re.S)),
    ("rsa", re.compile(r"^/rsa\s+(.+)$", re.I | re.S)),
    ("logscan", re.compile(r"^/logscan\s+(.+)$", re.I | re.S)),
]

_RSA_PARAM = re.compile(r"(p|q|e|m)\s*=\s*(-?\d+)", re.I)


def _run_tool_command(message: str) -> dict | None:
    """Parse a /command message and run it. Returns a result dict with either
    'output' (success) or 'error' (bad input), or None if no command matched."""
    message = message.strip()
    for name, pattern in _COMMANDS:
        m = pattern.match(message)
        if not m:
            continue
        try:
            if name == "caesar_encode":
                shift, text = int(m.group(1)), m.group(2)
                return {"command": name, "output": {"shift": shift, "input": text, "encoded": tools.caesar_encode(text, shift)}}
            if name == "caesar_decode":
                shift, text = int(m.group(1)), m.group(2)
                return {"command": name, "output": {"shift": shift, "input": text, "decoded": tools.caesar_decode(text, shift)}}
            if name == "caesar_crack":
                return {"command": name, "output": tools.caesar_crack(m.group(1))}
            if name == "vigenere_encode":
                key, text = m.group(1), m.group(2)
                return {"command": name, "output": {"key": key, "input": text, "encoded": tools.vigenere_encode(text, key)}}
            if name == "vigenere_decode":
                key, text = m.group(1), m.group(2)
                return {"command": name, "output": {"key": key, "input": text, "decoded": tools.vigenere_decode(text, key)}}
            if name == "freq":
                return {"command": name, "output": {"table": tools.frequency_analysis(m.group(1))}}
            if name == "hash":
                algo, text = m.group(1), m.group(2)
                return {"command": name, "output": tools.compute_hash(text, algo)}
            if name == "rsa":
                params = {k.lower(): int(v) for k, v in _RSA_PARAM.findall(m.group(1))}
                if "p" not in params or "q" not in params:
                    return {"command": name, "error": "RSA demo needs at least p=<prime> and q=<prime>, e.g. /rsa p=61 q=53"}
                return {"command": name, "output": tools.rsa_demo(
                    params["p"], params["q"], params.get("e"), params.get("m"),
                )}
            if name == "logscan":
                return {"command": name, "output": {"findings": tools.scan_log(m.group(1))}}
        except (ValueError, ZeroDivisionError) as e:
            return {"command": name, "error": str(e)}
    return None


def _format_tool_chunk(result: dict) -> str:
    if "error" in result:
        return f"Command: /{result['command']}\nERROR: {result['error']}"
    return f"Command: /{result['command']}\nResult: {result['output']}"


class SecurityToolsAgent(BaseAgent):
    name = "security_tool"
    system_prompt = SECURITY_TOOLS_SYSTEM_PROMPT

    async def retrieve_context(self, state: AgentState) -> list[dict]:
        subject_code = state.get("subject_code")
        messages = state.get("messages", [])
        if not messages:
            return []

        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        chunks: list[dict] = []
        if subject_code:
            chunks = retrieve(user_message, subject_code, top_k=3)

        tool_result = _run_tool_command(user_message)
        if tool_result is not None:
            chunks.insert(0, {
                "text": _format_tool_chunk(tool_result),
                "source_file": "Security Tools Engine (deterministic, not LLM-generated)",
                "page": 0,
                "score": 1.0,
            })
            logger.info("security_tool_invoked", command=tool_result["command"], ok="error" not in tool_result)

        return chunks

    # reason() / _reason_stream() are inherited from BaseAgent unchanged: both
    # call _build_full_prompt(), which already appends the Retrieved Context
    # (including our synthetic tool-output chunk), grounding rules, history,
    # and Learning Genome personalisation - no need to duplicate any of that
    # here.
