"""Unit tests for the deterministic security-tools engine
(app.services.security_tools) used by the Security Tools agent.

No DB/LLM dependency chain needed here - the module is pure stdlib
(hashlib, re, math), so it's imported directly rather than inlined.
"""

import pytest

from app.services import security_tools as tools


class TestCaesarCipher:
    def test_encode_basic_shift(self):
        assert tools.caesar_encode("HELLO", 3) == "KHOOR"

    def test_decode_reverses_encode(self):
        original = "Attack At Dawn!"
        for shift in range(26):
            assert tools.caesar_decode(tools.caesar_encode(original, shift), shift) == original

    def test_preserves_case_and_non_letters(self):
        assert tools.caesar_encode("Hi, Mom! 123", 1) == "Ij, Npn! 123"

    def test_negative_and_large_shifts_wrap(self):
        assert tools.caesar_encode("A", 26) == "A"
        assert tools.caesar_encode("A", -1) == "Z"

    def test_crack_recovers_known_shift(self):
        plaintext = (
            "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG AND THEN RUNS AWAY "
            "INTO THE FOREST WHERE IT HIDES FROM THE HUNTER ALL NIGHT LONG"
        )
        ciphertext = tools.caesar_encode(plaintext, 7)
        result = tools.caesar_crack(ciphertext)
        assert result["best_guess"]["shift"] == 7
        assert result["best_guess"]["decoded"] == plaintext
        assert len(result["all_candidates"]) == 26


class TestVigenereCipher:
    def test_encode_known_vector(self):
        # Classic textbook example
        assert tools.vigenere_encode("ATTACKATDAWN", "LEMON") == "LXFOPVEFRNHR"

    def test_decode_reverses_encode(self):
        original = "Meet me at the old bridge tonight"
        key = "SECRET"
        assert tools.vigenere_decode(tools.vigenere_encode(original, key), key) == original

    def test_empty_key_raises(self):
        with pytest.raises(ValueError):
            tools.vigenere_encode("test", "123")


class TestFrequencyAnalysis:
    def test_counts_and_percentages(self):
        table = tools.frequency_analysis("aaabb")
        by_letter = {row["letter"]: row for row in table}
        assert by_letter["a"]["count"] == 3
        assert by_letter["b"]["count"] == 2
        assert by_letter["a"]["pct"] == 60.0

    def test_ignores_non_letters(self):
        table = tools.frequency_analysis("a1a2a3!!!")
        assert len(table) == 1
        assert table[0]["count"] == 3


class TestHashing:
    def test_sha256_known_vector(self):
        result = tools.compute_hash("abc", "sha256")
        assert result["digest"] == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )

    def test_md5_flagged_as_broken(self):
        result = tools.compute_hash("abc", "md5")
        assert "broken" in result["note"].lower()

    def test_sha256_not_flagged_as_broken(self):
        result = tools.compute_hash("abc", "sha256")
        assert "no known practical" in result["note"].lower()

    def test_unsupported_algorithm_raises(self):
        with pytest.raises(ValueError):
            tools.compute_hash("abc", "sha3")

    def test_different_inputs_different_digests(self):
        a = tools.compute_hash("password1", "sha256")["digest"]
        b = tools.compute_hash("password2", "sha256")["digest"]
        assert a != b


class TestRSADemo:
    def test_textbook_example(self):
        # The canonical p=61, q=53 textbook RSA example.
        result = tools.rsa_demo(p=61, q=53, e=17)
        assert result["n"] == 3233
        assert result["phi_n"] == 3120
        assert result["d"] == 2753

    def test_encrypt_decrypt_roundtrip(self):
        result = tools.rsa_demo(p=61, q=53, e=17, message=65)
        assert result["roundtrip_ok"] is True
        assert result["decrypted"] == 65

    def test_rejects_non_prime(self):
        with pytest.raises(ValueError):
            tools.rsa_demo(p=60, q=53)

    def test_rejects_equal_primes(self):
        with pytest.raises(ValueError):
            tools.rsa_demo(p=61, q=61)

    def test_rejects_message_too_large(self):
        with pytest.raises(ValueError):
            tools.rsa_demo(p=61, q=53, e=17, message=99999)

    def test_rejects_non_coprime_e(self):
        # phi(3233) = 3120 = 2^4 * 3 * 5 * 13; e=2 shares a factor with phi.
        with pytest.raises(ValueError):
            tools.rsa_demo(p=61, q=53, e=2)

    def test_rejects_oversized_primes(self):
        with pytest.raises(ValueError):
            tools.rsa_demo(p=100003, q=100019)


class TestLogScanner:
    def test_detects_brute_force(self):
        log = "Jan 1 10:00:01 sshd: Failed password for root from 10.0.0.5"
        findings = tools.scan_log(log)
        assert any(f["rule"] == "brute_force" for f in findings)

    def test_detects_sql_injection(self):
        log = "GET /login?user=admin' OR '1'='1 HTTP/1.1"
        findings = tools.scan_log(log)
        assert any(f["rule"] == "sql_injection" for f in findings)

    def test_detects_xss(self):
        log = "GET /comment?text=<script>alert(1)</script> HTTP/1.1"
        findings = tools.scan_log(log)
        assert any(f["rule"] == "xss" for f in findings)

    def test_detects_directory_traversal(self):
        log = "GET /files?path=../../../../etc/passwd HTTP/1.1"
        findings = tools.scan_log(log)
        assert any(f["rule"] == "directory_traversal" for f in findings)

    def test_clean_log_has_no_findings(self):
        log = "GET /dashboard HTTP/1.1 200 OK\nGET /api/subjects HTTP/1.1 200 OK"
        assert tools.scan_log(log) == []

    def test_reports_correct_line_numbers(self):
        log = "line one is clean\nFailed password for admin\nline three is clean"
        findings = tools.scan_log(log)
        assert findings[0]["line"] == 2
