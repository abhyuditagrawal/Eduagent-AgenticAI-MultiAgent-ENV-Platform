"""Deterministic cryptography/forensics tool engine for the Security Tools agent.

Every function here is pure Python stdlib (hashlib, re, math) with no LLM call -
the agent injects a function's output as a synthetic RAG chunk so the model
narrates/explains a real computed result instead of trying to do arithmetic or
cryptography itself, which LLMs are unreliable at.
"""

import hashlib
import math
import re

# Reference English letter frequencies (%), used to score Caesar-shift candidates
# via chi-squared goodness-of-fit - the standard classical-cryptanalysis technique.
_ENGLISH_FREQ = {
    "a": 8.2, "b": 1.5, "c": 2.8, "d": 4.3, "e": 12.7, "f": 2.2, "g": 2.0,
    "h": 6.1, "i": 7.0, "j": 0.15, "k": 0.77, "l": 4.0, "m": 2.4, "n": 6.7,
    "o": 7.5, "p": 1.9, "q": 0.095, "r": 6.0, "s": 6.3, "t": 9.1, "u": 2.8,
    "v": 0.98, "w": 2.4, "x": 0.15, "y": 2.0, "z": 0.074,
}

_HASH_ALGOS = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}

_BROKEN_HASH_NOTE = {
    "md5": "MD5 is cryptographically broken - practical collision attacks exist, so it must never be used for integrity-critical evidence hashing or password storage.",
    "sha1": "SHA-1 is deprecated - a practical collision attack (SHAttered, 2017) has been demonstrated; treat any SHA-1-only integrity claim as insufficient for forensic evidence.",
    "sha256": "SHA-256 has no known practical collision or preimage attack and is the current standard for forensic evidence hashing.",
    "sha512": "SHA-512 has no known practical collision or preimage attack.",
}


def caesar_encode(text: str, shift: int) -> str:
    shift %= 26
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return "".join(out)


def caesar_decode(text: str, shift: int) -> str:
    return caesar_encode(text, -shift)


def _chi_squared_score(text: str) -> float:
    letters = [c.lower() for c in text if c.isalpha()]
    n = len(letters)
    if n == 0:
        return float("inf")
    counts: dict[str, int] = {}
    for c in letters:
        counts[c] = counts.get(c, 0) + 1
    score = 0.0
    for letter, expected_pct in _ENGLISH_FREQ.items():
        expected = expected_pct / 100 * n
        observed = counts.get(letter, 0)
        if expected > 0:
            score += (observed - expected) ** 2 / expected
    return score


def caesar_crack(ciphertext: str) -> dict:
    """Try all 26 shifts, score each by fit to English letter frequency, return the best."""
    candidates = []
    for shift in range(26):
        decoded = caesar_decode(ciphertext, shift)
        score = _chi_squared_score(decoded)
        candidates.append({"shift": shift, "decoded": decoded, "chi_squared": round(score, 2)})
    candidates.sort(key=lambda c: c["chi_squared"])
    return {"best_guess": candidates[0], "all_candidates": candidates}


def vigenere_encode(text: str, key: str) -> str:
    key = re.sub(r"[^a-zA-Z]", "", key)
    if not key:
        raise ValueError("Vigenere key must contain at least one letter")
    out = []
    ki = 0
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            key_shift = ord(key[ki % len(key)].lower()) - ord("a")
            out.append(chr((ord(ch) - base + key_shift) % 26 + base))
            ki += 1
        else:
            out.append(ch)
    return "".join(out)


def vigenere_decode(text: str, key: str) -> str:
    key = re.sub(r"[^a-zA-Z]", "", key)
    if not key:
        raise ValueError("Vigenere key must contain at least one letter")
    inverted_key = "".join(chr((26 - (ord(k.lower()) - ord("a"))) % 26 + ord("a")) for k in key)
    return vigenere_encode(text, inverted_key)


def frequency_analysis(text: str) -> list[dict]:
    letters = [c.lower() for c in text if c.isalpha()]
    n = len(letters)
    counts: dict[str, int] = {}
    for c in letters:
        counts[c] = counts.get(c, 0) + 1
    table = [
        {"letter": letter, "count": count, "pct": round(count / n * 100, 2) if n else 0.0}
        for letter, count in counts.items()
    ]
    table.sort(key=lambda r: r["count"], reverse=True)
    return table


def compute_hash(text: str, algo: str) -> dict:
    algo = algo.lower()
    if algo not in _HASH_ALGOS:
        raise ValueError(f"Unsupported algorithm '{algo}'. Supported: {', '.join(_HASH_ALGOS)}")
    digest = _HASH_ALGOS[algo](text.encode("utf-8")).hexdigest()
    return {"algorithm": algo, "input": text, "digest": digest, "note": _BROKEN_HASH_NOTE[algo]}


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(math.isqrt(n)) + 1):
        if n % i == 0:
            return False
    return True


def _extended_gcd(a: int, b: int) -> tuple[int, int, int]:
    if a == 0:
        return b, 0, 1
    g, x1, y1 = _extended_gcd(b % a, a)
    return g, y1 - (b // a) * x1, x1


def _mod_inverse(a: int, m: int) -> int:
    g, x, _ = _extended_gcd(a % m, m)
    if g != 1:
        raise ValueError(f"No modular inverse for e={a} mod {m} - choose a different e (must be coprime with phi(n))")
    return x % m


def rsa_demo(p: int, q: int, e: int | None = None, message: int | None = None) -> dict:
    """Textbook (unpadded) RSA key generation + optional encrypt/decrypt walkthrough.

    Deliberately restricted to small, explicit primes - this is a teaching
    demo of the underlying number theory, never a real key (real RSA needs
    512+ bit primes and OAEP padding, which this intentionally does not do).
    """
    if p == q:
        raise ValueError("p and q must be distinct primes")
    if not _is_prime(p) or not _is_prime(q):
        raise ValueError(f"Both p={p} and q={q} must be prime")
    if p > 10_000 or q > 10_000:
        raise ValueError("Keep p, q small (<10,000) - this is a pedagogical demo, not a real key")

    n = p * q
    phi = (p - 1) * (q - 1)

    if e is None:
        e = 65537 if phi > 65537 else 17
        while math.gcd(e, phi) != 1:
            e += 2
    elif math.gcd(e, phi) != 1:
        raise ValueError(f"e={e} is not coprime with phi(n)={phi} - pick another e")

    d = _mod_inverse(e, phi)

    result = {
        "p": p, "q": q, "n": n, "phi_n": phi, "e": e, "d": d,
        "public_key": (e, n), "private_key": (d, n),
    }

    if message is not None:
        if message >= n:
            raise ValueError(f"message={message} must be < n={n} for textbook RSA to work")
        ciphertext = pow(message, e, n)
        recovered = pow(ciphertext, d, n)
        result["message"] = message
        result["ciphertext"] = ciphertext
        result["decrypted"] = recovered
        result["roundtrip_ok"] = recovered == message

    return result


# --- Log / IOC scanner -----------------------------------------------------
# Toy, rule-based indicator-of-compromise detector over a pasted log snippet.
# Deliberately simple regex rules, not a real SIEM - the point is to give
# Network Forensics / Network Security students a concrete "spot the attack"
# exercise grounded in real detection patterns, not a production tool.

_IOC_RULES: list[tuple[str, re.Pattern, str]] = [
    ("brute_force", re.compile(r"failed password", re.I),
     "Repeated authentication failures - possible brute-force login attempt."),
    ("sql_injection", re.compile(r"(\bunion\s+select\b|'\s*or\s*'?1'?\s*=\s*'?1|--\s*$)", re.I),
     "SQL-injection-style payload detected in the request."),
    ("xss", re.compile(r"<script[\s>]|javascript:", re.I),
     "Cross-site-scripting (XSS) style payload detected."),
    ("directory_traversal", re.compile(r"\.\./\.\./|%2e%2e%2f", re.I),
     "Directory-traversal pattern detected (attempt to escape the web root)."),
    ("port_scan_hint", re.compile(r"\bSYN_?SCAN\b|nmap", re.I),
     "Signature associated with port-scanning tools."),
    ("suspicious_useragent", re.compile(r"\b(sqlmap|nikto|curl/\d|python-requests)\b", re.I),
     "Automated-tool user-agent string, atypical for a normal browser session."),
]


def scan_log(log_text: str) -> list[dict]:
    findings = []
    for line_no, line in enumerate(log_text.splitlines(), 1):
        for rule_id, pattern, explanation in _IOC_RULES:
            if pattern.search(line):
                findings.append({
                    "line": line_no,
                    "rule": rule_id,
                    "text": line.strip()[:200],
                    "explanation": explanation,
                })
    return findings
