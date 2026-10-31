import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.multitest import multipletests

from strategy_workflows import Statistics as st
from strategy_workflows import WalkForward as wf


def test_holm_matches_hand_values_and_statsmodels_and_keeps_the_input_order():
    p = [0.01, 0.04, 0.03, 0.005]
    assert st.holm_adjust(p) == pytest.approx([0.03, 0.06, 0.06, 0.02])
    rng = np.random.default_rng(0)
    for _ in range(20):
        values = list(rng.uniform(0, 0.2, 4))
        assert st.holm_adjust(values) == pytest.approx(multipletests(values, method="holm")[1])
    assert st.holm_adjust([0.6, 0.7]) == pytest.approx([1.0, 1.0]) and st.holm_adjust([]) == []


def test_bootstrap_blocks_have_the_requested_mean_length_and_wrap_around():
    n, size = 3000, 40
    idx = st.stationary_bootstrap_indices(n, size, 10, np.random.default_rng(1))
    assert idx.shape == (size, n) and idx.min() >= 0 and idx.max() < n
    breaks = (idx[:, 1:] != (idx[:, :-1] + 1) % n).sum(axis=1)       # a new block starts at every break
    mean_block = n / (breaks.mean() + 1)
    assert mean_block == pytest.approx(10, rel=0.05)
    longer = st.stationary_bootstrap_indices(n, size, 40, np.random.default_rng(1))
    assert n / (((longer[:, 1:] != (longer[:, :-1] + 1) % n).sum(axis=1)).mean() + 1) == pytest.approx(40, rel=0.1)
    ends = st.stationary_bootstrap_indices(5, 200, 1e9, np.random.default_rng(2))   # one block: runs through the end
    assert (ends[:, 1:] == (ends[:, :-1] + 1) % 5).all()


def test_sharpe_rows_is_the_annualised_ddof0_ratio_and_nan_when_constant():
    x = np.array([[0.01, -0.01, 0.02, 0.0], [0.5, 0.5, 0.5, 0.5]])
    out = st.sharpe_rows(x)
    assert out[0] == pytest.approx(x[0].mean() / x[0].std() * np.sqrt(252)) and np.isnan(out[1])


def test_point_difference_and_rho_are_the_plain_statistics():
    rng = np.random.default_rng(3)
    a = rng.normal(0.001, 0.01, 500)
    b = 0.5 * a + rng.normal(0.0, 0.01, 500)
    out = st.paired_sharpe_bootstrap(a, b, n_resamples=200)
    sharpe = lambda v: v.mean() / v.std() * np.sqrt(252)
    assert out["difference"] == pytest.approx(sharpe(a) - sharpe(b))
    assert out["rho"] == pytest.approx(np.corrcoef(a, b)[0, 1]) and out["n_days"] == 500
    assert out["ci_low"] < out["difference"] < out["ci_high"]


def test_resampling_is_paired_so_a_scaled_copy_has_no_difference_in_any_resample():
    a = np.random.default_rng(4).normal(0.001, 0.01, 400)
    out = st.paired_sharpe_bootstrap(a, 3.0 * a, n_resamples=300)
    assert out["difference"] == pytest.approx(0.0, abs=1e-9)
    assert out["ci_low"] == pytest.approx(0.0, abs=1e-9) and out["ci_high"] == pytest.approx(0.0, abs=1e-9)
    assert out["rho"] == pytest.approx(1.0)


def test_interval_width_of_independent_iid_series_matches_the_analytic_standard_error():
    rng = np.random.default_rng(5)
    n = 2000
    a, b = rng.normal(0, 0.01, n), rng.normal(0, 0.01, n)
    out = st.paired_sharpe_bootstrap(a, b, mean_block=1.0001, n_resamples=4000, seed=1)
    se = np.sqrt(2 * 252 / n)                                    # sd of a difference of two annualised Sharpes
    assert (out["ci_high"] - out["ci_low"]) == pytest.approx(2 * 1.96 * se, rel=0.08)
    assert (out["difference"] - out["ci_low"]) / (out["ci_high"] - out["difference"]) == pytest.approx(1.0, abs=0.08)


def test_bootstrap_is_reproducible_for_a_fixed_seed_and_changes_with_it():
    rng = np.random.default_rng(6)
    a, b = rng.normal(0.001, 0.01, 300), rng.normal(0.0, 0.01, 300)
    one = st.paired_sharpe_bootstrap(a, b, n_resamples=300, seed=9)
    assert one == st.paired_sharpe_bootstrap(a, b, n_resamples=300, seed=9)
    assert one["ci_low"] != st.paired_sharpe_bootstrap(a, b, n_resamples=300, seed=10)["ci_low"]
    assert (st.BOOTSTRAP_MEAN_BLOCK, st.BOOTSTRAP_RESAMPLES) == (10, 10_000)


def test_bootstrap_rejects_mismatched_input():
    with pytest.raises(ValueError):
        st.paired_sharpe_bootstrap(np.zeros(5), np.zeros(4))


# --- comparison of configurations in the walk-forward summary ------------------

def returns_frame(values, start="2024-01-01"):
    days = pd.date_range(start, periods=len(values)).strftime("%Y-%m-%d")
    return pd.DataFrame({"date": days, "window": 1, "seed": 1, "mode": "real", "placebo_set": 0, "return": values})


def test_compare_configs_joins_days_reports_reference_minus_config_and_the_correlation():
    rng = np.random.default_rng(7)
    ref = rng.normal(0.001, 0.01, 300)
    other = 0.4 * ref + rng.normal(0.0, 0.01, 300)
    series = {"llm_mcts": wf.real_daily_series(returns_frame(ref)),
              "random": wf.real_daily_series(returns_frame(other[10:], "2024-01-11")),
              "buy_hold": wf.real_daily_series(returns_frame(ref))}
    table = wf.compare_configs(series)
    assert list(table["config"]) == ["random", "buy_hold"] and list(table.columns) == wf.COMPARISON_FIELDS
    row = table.iloc[0]
    assert row["n_days"] == 290                                    # only the common days
    sharpe = lambda v: v.mean() / v.std() * np.sqrt(252)
    assert row["sharpe_reference"] == pytest.approx(sharpe(ref[10:])) and row["sharpe_config"] == pytest.approx(sharpe(other[10:]))
    assert row["difference"] == pytest.approx(sharpe(ref[10:]) - sharpe(other[10:]))
    assert row["rho"] == pytest.approx(np.corrcoef(ref[10:], other[10:])[0, 1])
    assert row["ci_low"] < row["difference"] < row["ci_high"]
    assert table.iloc[1]["difference"] == pytest.approx(0.0, abs=1e-9)   # the reference against itself


def test_real_daily_series_averages_seeds_per_day_and_ignores_placebo_and_repeats():
    days = ["2024-01-01", "2024-01-02"]
    frames = [pd.DataFrame({"date": days, "window": 1, "seed": s, "mode": "real", "placebo_set": 0, "return": r})
              for s, r in ((1, [0.01, 0.03]), (2, [0.03, 0.05]), (2, [0.03, 0.07]))]      # last one repeats seed 2
    frames.append(pd.DataFrame({"date": days, "window": 1, "seed": 1, "mode": "placebo", "placebo_set": 1,
                                "return": [9.0, 9.0]}))
    series = wf.real_daily_series(pd.concat(frames))
    assert series.tolist() == pytest.approx([0.02, 0.05])


def test_compare_step_writes_comparison_csv_for_every_folder_with_real_returns(tmp_path, capsys):
    rng = np.random.default_rng(8)
    ref = rng.normal(0.001, 0.01, 120)
    for name, values in (("llm_mcts", ref), ("tsmom", ref * 0.5 + rng.normal(0, 0.01, 120))):
        (tmp_path / name).mkdir()
        returns_frame(values).to_csv(tmp_path / name / "returns.csv", index=False)
    (tmp_path / "empty").mkdir()
    wf.step_compare(type("A", (), {"results_root": str(tmp_path)})())
    table = pd.read_csv(tmp_path / "comparison.csv")
    assert list(table["config"]) == ["tsmom"]
    (tmp_path / "comparison.csv").unlink()
    (tmp_path / "llm_mcts" / "returns.csv").unlink()
    wf.step_compare(type("A", (), {"results_root": str(tmp_path)})())
    assert not (tmp_path / "comparison.csv").exists() and "no comparison" in capsys.readouterr().out


def test_wilson_interval_known_values():
    low, high = st.wilson_interval(6, 10)
    assert low == pytest.approx(0.3127, abs=1e-3) and high == pytest.approx(0.8318, abs=1e-3)
    low, high = st.wilson_interval(0, 5)
    assert low == 0.0 and high == pytest.approx(0.4345, abs=1e-3)
    assert all(np.isnan(v) for v in st.wilson_interval(0, 0))


def test_fisher_p_greater_is_one_sided_and_nan_for_an_empty_group():
    assert st.fisher_p_greater(2, 10, 0, 10) == pytest.approx(0.2368, abs=1e-4)
    assert st.fisher_p_greater(6, 10, 0, 10) == pytest.approx(0.0054, abs=1e-4)
    assert st.fisher_p_greater(0, 10, 6, 10) > 0.99               # fewer than the base: not "greater"
    assert np.isnan(st.fisher_p_greater(1, 0, 0, 10)) and np.isnan(st.fisher_p_greater(1, 10, 0, 0))


def test_detection_threshold_is_the_lowest_level_below_alpha():
    def rows(*pairs):
        return [{'strength': s, 'p_fisher': p} for s, p in pairs]
    assert st.detection_threshold(rows((0.0, None), (0.05, 0.24), (0.1, 0.005)))['strength'] == 0.1
    assert st.detection_threshold(rows((0.0, None), (0.05, 0.03), (0.1, 0.001)))['strength'] == 0.05
    assert st.detection_threshold(rows((0.0, None), (0.05, 0.24), (0.1, 0.2))) is None
    assert st.detection_threshold(rows((0.0, None), (0.05, float('nan')), (0.1, 0.05))) is None   # p must be below alpha
    assert st.detection_threshold(rows((0.1, 0.001))) ['strength'] == 0.1
    assert st.detection_threshold([]) is None
