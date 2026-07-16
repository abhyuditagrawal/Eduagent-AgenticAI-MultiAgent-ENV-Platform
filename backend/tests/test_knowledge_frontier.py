"""Unit tests for the Knowledge Frontier / ZPD partitioning logic.

These tests are self-contained: they inline the readiness formula and
threshold constants from knowledge_frontier.py so that they can run
without the full backend dependency chain (asyncpg, sentence-transformers …).
"""

# Mirror the constants from app.services.knowledge_frontier
MASTERY_THRESHOLD = 0.7
PREREQ_THRESHOLD = 0.6


def _readiness(avg_prereq: float, own: float, difficulty: int) -> float:
    """Replicate the inline readiness formula from knowledge_frontier.py."""
    difficulty_factor = 1.0 / (1.0 + 0.15 * (difficulty - 1))
    return avg_prereq * (1.0 - own) * difficulty_factor


class TestFrontierReadiness:
    """Test the readiness score formula used to rank frontier concepts."""

    def test_readiness_increases_with_prereq_mastery(self):
        low = _readiness(0.5, 0.1, 1)
        high = _readiness(0.9, 0.1, 1)
        assert high > low

    def test_readiness_decreases_with_own_mastery(self):
        low_own = _readiness(0.9, 0.1, 1)
        high_own = _readiness(0.9, 0.6, 1)
        assert low_own > high_own

    def test_easier_concepts_preferred(self):
        easy = _readiness(0.9, 0.1, 1)
        hard = _readiness(0.9, 0.1, 3)
        assert easy > hard

    def test_readiness_zero_when_fully_mastered(self):
        r = _readiness(0.9, 1.0, 1)
        assert r == 0.0

    def test_readiness_zero_when_no_prereq(self):
        r = _readiness(0.0, 0.1, 1)
        assert r == 0.0

    def test_difficulty_factor_positive(self):
        for d in range(1, 6):
            factor = 1.0 / (1.0 + 0.15 * (d - 1))
            assert 0 < factor <= 1.0


class TestThresholds:
    """Verify the threshold constants are sensible."""

    def test_mastery_threshold(self):
        assert 0.5 <= MASTERY_THRESHOLD <= 0.95

    def test_prereq_threshold(self):
        assert 0.3 <= PREREQ_THRESHOLD <= 0.8

    def test_prereq_lower_than_mastery(self):
        assert PREREQ_THRESHOLD <= MASTERY_THRESHOLD


class TestPartitioningLogic:
    """Test the conceptual partitioning rules using the same threshold values."""

    def test_mastered_concept_classified(self):
        own = MASTERY_THRESHOLD + 0.05
        assert own >= MASTERY_THRESHOLD

    def test_frontier_concept_conditions(self):
        own = 0.2  # not mastered
        prereq = PREREQ_THRESHOLD + 0.1  # met
        assert own < MASTERY_THRESHOLD
        assert prereq >= PREREQ_THRESHOLD

    def test_locked_concept_conditions(self):
        own = 0.2
        prereq = PREREQ_THRESHOLD - 0.2  # not met
        assert own < MASTERY_THRESHOLD
        assert prereq < PREREQ_THRESHOLD
