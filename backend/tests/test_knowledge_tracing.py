"""Unit tests for the Bayesian Knowledge Tracing + forgetting engine.

Inlines the pure functions from app.services.knowledge_tracing so the test
file can run without the full backend dependency chain (asyncpg, etc.).
"""

import math

# ---------- Inlined from app.services.knowledge_tracing ----------

BKT_P_L0 = 0.10
BKT_P_TRANSIT = 0.15
BKT_P_SLIP = 0.10
BKT_P_GUESS = 0.20
RETENTION_THRESHOLD = 0.5


def _difficulty_transit(difficulty_tier: int) -> float:
    return {1: 0.20, 2: 0.15, 3: 0.10}.get(difficulty_tier, 0.15)


def bkt_posterior(prior: float, correct: bool,
                  p_slip: float = BKT_P_SLIP,
                  p_guess: float = BKT_P_GUESS) -> float:
    if correct:
        numerator = prior * (1 - p_slip)
        denom = prior * (1 - p_slip) + (1 - prior) * p_guess
    else:
        numerator = prior * p_slip
        denom = prior * p_slip + (1 - prior) * (1 - p_guess)
    if denom <= 0:
        return prior
    return numerator / denom


def bkt_update(prior: float, correct: bool, difficulty_tier: int = 1) -> float:
    posterior = bkt_posterior(prior, correct)
    p_t = _difficulty_transit(difficulty_tier)
    updated = posterior + (1 - posterior) * p_t
    return max(0.0, min(1.0, updated))


def update_memory_stability(current_stability: float, mastery: float,
                            correct: bool) -> float:
    if correct:
        growth = 1.4 + mastery
        return min(365.0, max(1.0, current_stability * growth))
    else:
        return max(0.5, current_stability * 0.5)


def retrievability(stability: float, days_elapsed: float) -> float:
    if stability <= 0:
        return 0.0
    return math.exp(-days_elapsed / stability)


def days_until_forgetting(stability: float,
                          threshold: float = RETENTION_THRESHOLD) -> float:
    if stability <= 0:
        return 0.0
    return -stability * math.log(threshold)

# ---------- End inlined ----------


class TestBKTPosterior:
    def test_correct_answer_increases_belief(self):
        prior = 0.3
        posterior = bkt_posterior(prior, correct=True)
        assert posterior > prior

    def test_incorrect_answer_decreases_belief(self):
        prior = 0.6
        posterior = bkt_posterior(prior, correct=False)
        assert posterior < prior

    def test_posterior_bounded_0_1(self):
        for prior in (0.0, 0.01, 0.5, 0.99, 1.0):
            for correct in (True, False):
                p = bkt_posterior(prior, correct)
                assert 0.0 <= p <= 1.0


class TestBKTUpdate:
    def test_repeated_correct_converges_to_mastery(self):
        mastery = 0.1
        for _ in range(8):
            mastery = bkt_update(mastery, correct=True, difficulty_tier=1)
        assert mastery > 0.9

    def test_harder_concepts_learn_slower(self):
        easy = bkt_update(0.1, correct=True, difficulty_tier=1)
        hard = bkt_update(0.1, correct=True, difficulty_tier=3)
        assert easy > hard

    def test_update_bounded(self):
        m = bkt_update(0.999, correct=True, difficulty_tier=1)
        assert 0.0 <= m <= 1.0


class TestMemoryStability:
    def test_success_grows_stability(self):
        s = update_memory_stability(2.0, mastery=0.8, correct=True)
        assert s > 2.0

    def test_failure_shrinks_stability(self):
        s = update_memory_stability(10.0, mastery=0.8, correct=False)
        assert s < 10.0

    def test_stability_capped(self):
        s = update_memory_stability(300.0, mastery=1.0, correct=True)
        assert s <= 365.0

    def test_higher_mastery_grows_faster(self):
        low = update_memory_stability(5.0, mastery=0.2, correct=True)
        high = update_memory_stability(5.0, mastery=0.9, correct=True)
        assert high > low


class TestForgettingCurve:
    def test_retrievability_decreases_over_time(self):
        s = 5.0
        r0 = retrievability(s, 0)
        r5 = retrievability(s, 5)
        r10 = retrievability(s, 10)
        assert r0 == 1.0
        assert r0 > r5 > r10

    def test_retrievability_at_stability_is_1_over_e(self):
        s = 7.0
        r = retrievability(s, s)
        assert abs(r - math.exp(-1)) < 1e-9

    def test_days_until_forgetting_matches_threshold(self):
        s = 10.0
        t = days_until_forgetting(s, threshold=RETENTION_THRESHOLD)
        # Recall at predicted time should equal the threshold
        assert abs(retrievability(s, t) - RETENTION_THRESHOLD) < 1e-9

    def test_more_stable_memory_lasts_longer(self):
        t_low = days_until_forgetting(2.0)
        t_high = days_until_forgetting(20.0)
        assert t_high > t_low
