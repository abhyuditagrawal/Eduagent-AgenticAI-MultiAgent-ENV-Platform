import pytest

from app.services.auth import hash_password, verify_password
from app.services.student_state import sm2_update


class TestSM2Algorithm:
    """Test the SM-2 spaced repetition algorithm with known inputs."""

    def test_perfect_answer_increases_interval(self):
        easiness, interval, repetitions = sm2_update(
            quality=5,
            repetitions=1,
            easiness=2.5,
            interval=1,
        )
        assert interval > 1
        assert repetitions == 2
        assert easiness >= 2.5

    def test_poor_answer_resets_repetitions(self):
        easiness, interval, repetitions = sm2_update(
            quality=1,
            repetitions=5,
            easiness=2.5,
            interval=30,
        )
        assert repetitions == 0
        assert interval == 1

    def test_borderline_answer(self):
        easiness, interval, repetitions = sm2_update(
            quality=3,
            repetitions=2,
            easiness=2.5,
            interval=6,
        )
        assert repetitions == 3
        assert interval > 0

    def test_easiness_never_below_minimum(self):
        easiness, interval, repetitions = sm2_update(
            quality=0,
            repetitions=0,
            easiness=1.3,
            interval=1,
        )
        assert easiness >= 1.3

    def test_first_repetition_interval(self):
        easiness, interval, repetitions = sm2_update(
            quality=4,
            repetitions=0,
            easiness=2.5,
            interval=0,
        )
        assert interval == 1
        assert repetitions == 1

    def test_second_repetition_interval(self):
        easiness, interval, repetitions = sm2_update(
            quality=4,
            repetitions=1,
            easiness=2.5,
            interval=1,
        )
        assert interval == 6
        assert repetitions == 2

    def test_sm2_multiple_reviews_increase_intervals(self):
        """Simulate 5 consecutive perfect reviews and verify intervals grow."""
        easiness, interval, reps = 2.5, 0, 0
        intervals = []
        for _ in range(5):
            easiness, interval, reps = sm2_update(
                quality=5, easiness=easiness, interval=interval, repetitions=reps
            )
            intervals.append(interval)
        # Intervals should be strictly increasing after first two
        assert intervals[0] == 1
        assert intervals[1] == 6
        for i in range(2, len(intervals)):
            assert intervals[i] > intervals[i - 1]

    def test_sm2_recovery_after_failure(self):
        """After a failure, verify the student can recover with good answers."""
        # Start with some progress
        easiness, interval, reps = 2.5, 6, 2
        # Fail
        easiness, interval, reps = sm2_update(
            quality=1, easiness=easiness, interval=interval, repetitions=reps
        )
        assert reps == 0
        assert interval == 1
        # Recover with two good answers
        easiness, interval, reps = sm2_update(
            quality=4, easiness=easiness, interval=interval, repetitions=reps
        )
        assert reps == 1
        easiness, interval, reps = sm2_update(
            quality=4, easiness=easiness, interval=interval, repetitions=reps
        )
        assert reps == 2
        assert interval == 6


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
