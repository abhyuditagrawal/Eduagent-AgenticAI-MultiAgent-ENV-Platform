import pytest

from app.services.auth import hash_password, verify_password
from app.services.student_state import sm2_update


class TestSM2Algorithm:
    """Test the SM-2 spaced repetition algorithm with known inputs."""

    def test_perfect_answer_increases_interval(self):
        result = sm2_update(
            quality=5,
            repetitions=1,
            easiness=2.5,
            interval=1,
        )
        assert result["interval"] > 1
        assert result["repetitions"] == 2
        assert result["easiness"] >= 2.5

    def test_poor_answer_resets_repetitions(self):
        result = sm2_update(
            quality=1,
            repetitions=5,
            easiness=2.5,
            interval=30,
        )
        assert result["repetitions"] == 0
        assert result["interval"] == 1

    def test_borderline_answer(self):
        result = sm2_update(
            quality=3,
            repetitions=2,
            easiness=2.5,
            interval=6,
        )
        assert result["repetitions"] == 3
        assert result["interval"] > 0

    def test_easiness_never_below_minimum(self):
        result = sm2_update(
            quality=0,
            repetitions=0,
            easiness=1.3,
            interval=1,
        )
        assert result["easiness"] >= 1.3

    def test_first_repetition_interval(self):
        result = sm2_update(
            quality=4,
            repetitions=0,
            easiness=2.5,
            interval=0,
        )
        assert result["interval"] == 1
        assert result["repetitions"] == 1

    def test_second_repetition_interval(self):
        result = sm2_update(
            quality=4,
            repetitions=1,
            easiness=2.5,
            interval=1,
        )
        assert result["interval"] == 6
        assert result["repetitions"] == 2


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_and_verify(self):
        password = "secure_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("incorrect", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        # bcrypt salts should make these different
        assert h1 != h2
