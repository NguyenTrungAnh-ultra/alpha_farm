import numpy as np
from scipy import stats

from deflated_sharpe import (EULER_GAMMA, daily_sharpe, deflated_sharpe, expected_max_sharpe,
                             probabilistic_sharpe)


def test_psr_matches_hand_computation():
    r = np.array([0.01, -0.005, 0.02, 0.0, 0.01])
    sr = 0.007 / np.sqrt(np.mean((r - 0.007) ** 2))
    d = r - r.mean()
    skew = np.mean(d ** 3) / np.mean(d ** 2) ** 1.5
    kurt = np.mean(d ** 4) / np.mean(d ** 2) ** 2
    expected = stats.norm.cdf(sr * 2.0 / np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    assert np.isclose(daily_sharpe(r), sr)
    assert np.isclose(probabilistic_sharpe(r, 0.0), expected)
    assert np.isclose(probabilistic_sharpe(r, 0.0), 0.9385, atol=1e-3)  # worked by hand: z ~ 1.54


def test_single_trial_has_zero_sr0_so_dsr_equals_psr():
    r = np.random.default_rng(0).normal(0.001, 0.01, 300)
    assert expected_max_sharpe([daily_sharpe(r)]) == 0.0
    assert deflated_sharpe(r, [daily_sharpe(r)]) == probabilistic_sharpe(r, 0.0)


def test_zero_variance_across_trials_gives_zero_sr0():
    assert np.isclose(expected_max_sharpe([0.05, 0.05, 0.05]), 0.0, atol=1e-12)


def test_more_trials_raise_sr0_and_lower_dsr():
    r = np.random.default_rng(1).normal(0.002, 0.01, 500)
    few = [0.01, 0.03, 0.05, 0.07]
    many = few * 5  # same mean, variance of the same order, five times the trials
    assert expected_max_sharpe(many) > expected_max_sharpe(few)
    assert deflated_sharpe(r, many) < deflated_sharpe(r, few)


def test_sr0_formula():
    s = np.array([0.0, 0.02, 0.04])
    expected = s.std(ddof=1) * ((1 - EULER_GAMMA) * stats.norm.ppf(1 - 1 / 3)
                                + EULER_GAMMA * stats.norm.ppf(1 - 1 / (3 * np.e)))
    assert np.isclose(expected_max_sharpe(s), expected)


def test_normal_series_has_normal_moments():
    r = np.random.default_rng(2).normal(0, 1, 200000)
    assert abs(stats.skew(r)) < 0.03
    assert abs(stats.kurtosis(r, fisher=False) - 3) < 0.05
