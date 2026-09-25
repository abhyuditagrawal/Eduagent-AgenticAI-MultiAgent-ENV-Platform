"""Unit tests for the Security Tools agent's command-parsing layer.

Inlines the regex dispatch table and _run_tool_command from
app.agents.security_tools_agent so this file can run without importing the
agent module directly, which would pull in the RAG retriever's embedding
model - the same reasoning test_debate.py documents for its own inlining.
The underlying computation (app.services.security_tools) is real and
imported normally in test_security_tools.py, since that module has no heavy
dependencies of its own.
"""

import re

from app.services import security_tools as tools

# ---------- Inlined from app.agents.security_tools_agent ----------

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


# ---------- Tests ----------

class TestCommandDispatch:
    def test_no_command_returns_none(self):
        assert _run_tool_command("what is a Caesar cipher?") is None

    def test_caesar_encode_dispatches(self):
        result = _run_tool_command("/caesar encode shift=3 HELLO")
        assert result["command"] == "caesar_encode"
        assert result["output"]["encoded"] == "KHOOR"

    def test_caesar_crack_dispatches(self):
        result = _run_tool_command("/caesar crack KHOOR")
        assert result["command"] == "caesar_crack"
        assert "best_guess" in result["output"]

    def test_vigenere_encode_dispatches(self):
        result = _run_tool_command("/vigenere encode key=LEMON ATTACKATDAWN")
        assert result["output"]["encoded"] == "LXFOPVEFRNHR"

    def test_hash_dispatches(self):
        result = _run_tool_command("/hash sha256 abc")
        assert result["output"]["digest"].startswith("ba7816bf")

    def test_hash_case_insensitive_algo(self):
        result = _run_tool_command("/hash SHA256 abc")
        assert result is not None

    def test_rsa_dispatches_with_message(self):
        result = _run_tool_command("/rsa p=61 q=53 e=17 m=65")
        assert result["output"]["roundtrip_ok"] is True

    def test_rsa_missing_params_returns_error(self):
        result = _run_tool_command("/rsa e=17")
        assert "error" in result

    def test_rsa_invalid_prime_returns_error_not_exception(self):
        result = _run_tool_command("/rsa p=60 q=53")
        assert "error" in result
        assert "prime" in result["error"].lower()

    def test_logscan_dispatches(self):
        result = _run_tool_command("/logscan Failed password for root")
        assert len(result["output"]["findings"]) == 1

    def test_command_is_case_insensitive(self):
        assert _run_tool_command("/CAESAR ENCODE shift=1 hi") is not None

    def test_freq_dispatches(self):
        result = _run_tool_command("/freq aaabb")
        assert result["output"]["table"][0]["letter"] == "a"
