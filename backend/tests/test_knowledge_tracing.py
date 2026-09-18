"""Unit tests for the Bayesian Knowledge Tracing + forgetting engine.

Inlines the pure functions from app.services.knowledge_tracing so the test
file can run without the full backend dependency chain (asyncpg, etc.).
"""

import math
from collections import defaultdict

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


def _forward_backward(obs, p_l0, p_t, p_s, p_g):
    n = len(obs)
    if n == 0:
        return []

    def emit(learned, correct):
        if learned:
            return (1 - p_s) if correct else p_s
        return p_g if correct else (1 - p_g)

    alpha = [[0.0, 0.0] for _ in range(n)]
    scales = [0.0] * n
    alpha[0][0] = (1 - p_l0) * emit(False, obs[0])
    alpha[0][1] = p_l0 * emit(True, obs[0])
    scales[0] = alpha[0][0] + alpha[0][1] or 1.0
    alpha[0][0] /= scales[0]
    alpha[0][1] /= scales[0]

    for t in range(1, n):
        pred_unlearned = alpha[t - 1][0] * (1 - p_t)
        pred_learned = alpha[t - 1][0] * p_t + alpha[t - 1][1]
        alpha[t][0] = pred_unlearned * emit(False, obs[t])
        alpha[t][1] = pred_learned * emit(True, obs[t])
        scales[t] = alpha[t][0] + alpha[t][1] or 1.0
        alpha[t][0] /= scales[t]
        alpha[t][1] /= scales[t]

    beta = [[1.0, 1.0] for _ in range(n)]
    for t in range(n - 2, -1, -1):
        e0 = emit(False, obs[t + 1])
        e1 = emit(True, obs[t + 1])
        beta[t][0] = ((1 - p_t) * e0 * beta[t + 1][0] + p_t * e1 * beta[t + 1][1]) / scales[t + 1]
        beta[t][1] = (e1 * beta[t + 1][1]) / scales[t + 1]

    gamma = []
    for t in range(n):
        u = alpha[t][0] * beta[t][0]
        l = alpha[t][1] * beta[t][1]
        total = (u + l) or 1.0
        gamma.append(l / total)
    return gamma


def _em_fit(sequences, difficulty_tiers, iterations=8):
    p_l0, p_t_default, p_s, p_g = BKT_P_L0, BKT_P_TRANSIT, BKT_P_SLIP, BKT_P_GUESS
    p_transit_by_tier = {1: 0.20, 2: 0.15, 3: 0.10}

    for _ in range(iterations):
        l0_sum = 0.0
        n_seqs = 0
        learned_correct = 0.0
        learned_total = 0.0
        unlearned_correct = 0.0
        unlearned_total = 0.0
        transit_num = defaultdict(float)
        transit_den = defaultdict(float)

        for obs, tiers in zip(sequences, difficulty_tiers):
            if not obs:
                continue
            gamma = _forward_backward(obs, p_l0, p_t_default, p_s, p_g)
            l0_sum += gamma[0]
            n_seqs += 1

            for t, (correct, tier) in enumerate(zip(obs, tiers)):
                p_learned = gamma[t]
                p_unlearned = 1 - p_learned
                if correct:
                    learned_correct += p_learned
                    unlearned_correct += p_unlearned
                learned_total += p_learned
                unlearned_total += p_unlearned
                if t > 0:
                    prev_unlearned = 1 - gamma[t - 1]
                    transit_num[tier] += prev_unlearned * p_learned
                    transit_den[tier] += prev_unlearned

        if n_seqs == 0:
            break

        p_l0 = min(0.95, max(0.02, l0_sum / n_seqs))
        p_s = min(0.45, max(0.01, 1 - (learned_correct / learned_total))) if learned_total > 0 else p_s
        p_g = min(0.45, max(0.01, unlearned_correct / unlearned_total)) if unlearned_total > 0 else p_g
        for tier in (1, 2, 3):
            if transit_den.get(tier, 0) > 0:
                p_transit_by_tier[tier] = min(0.6, max(0.02, transit_num[tier] / transit_den[tier]))
        p_t_default = p_transit_by_tier[1]

    return {
        "p_l0": round(p_l0, 4),
        "p_slip": round(p_s, 4),
        "p_guess": round(p_g, 4),
        "p_transit": {k: round(v, 4) for k, v in p_transit_by_tier.items()},
    }

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


class TestForwardBackward:
    def test_output_length_matches_input(self):
        gamma = _forward_backward([True, True, False, True], 0.1, 0.15, 0.1, 0.2)
        assert len(gamma) == 4

    def test_all_correct_pushes_belief_up(self):
        gamma = _forward_backward([True] * 6, 0.1, 0.15, 0.1, 0.2)
        assert gamma[-1] > gamma[0]

    def test_all_incorrect_keeps_belief_low(self):
        gamma = _forward_backward([False] * 6, 0.1, 0.15, 0.1, 0.2)
        assert gamma[-1] < 0.3

    def test_probabilities_bounded(self):
        gamma = _forward_backward([True, False, True, False, True], 0.3, 0.2, 0.15, 0.25)
        assert all(0.0 <= g <= 1.0 for g in gamma)

    def test_empty_sequence_returns_empty(self):
        assert _forward_backward([], 0.1, 0.15, 0.1, 0.2) == []


class TestEMFit:
    def test_fits_all_expected_keys(self):
        sequences = [[True, True, True, True, True, True], [False, True, True, True, True]]
        tiers = [[1] * 6, [1] * 5]
        result = _em_fit(sequences, tiers, iterations=3)
        assert set(result.keys()) == {"p_l0", "p_slip", "p_guess", "p_transit"}
        assert set(result["p_transit"].keys()) == {1, 2, 3}

    def test_fitted_probabilities_are_valid(self):
        sequences = [[True, False, True, True, False, True, True, True]]
        tiers = [[1] * 8]
        result = _em_fit(sequences, tiers, iterations=5)
        assert 0.0 <= result["p_l0"] <= 1.0
        assert 0.0 <= result["p_slip"] <= 1.0
        assert 0.0 <= result["p_guess"] <= 1.0
        for v in result["p_transit"].values():
            assert 0.0 <= v <= 1.0

    def test_consistently_correct_student_fits_low_slip(self):
        # A student who is essentially always right once past the first
        # couple of attempts should fit a low slip probability.
        sequences = [[False, True, True, True, True, True, True, True, True, True]] * 3
        tiers = [[1] * 10] * 3
        result = _em_fit(sequences, tiers, iterations=8)
        assert result["p_slip"] < 0.3

    def test_empty_sequences_returns_defaults_without_crashing(self):
        result = _em_fit([[]], [[]], iterations=3)
        assert result["p_l0"] == BKT_P_L0
