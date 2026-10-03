"""Test-first suite for the day-ahead load forecast (M3 step 7).

Every expected value below is derived by hand from the way the input is built (a ramp whose value
is its hour offset, constants, small MAPE sums), never by re-implementing the function under test.
The leakage and "never fill" tests protect the one-shot FINAL backtest (protocol guards #2, #3,
#4, #10, #11 and #12).
"""

import dataclasses
import json
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from pipeline.forecast import backtest, baseline, features, metrics, store
from pipeline.forecast.backtest import Fold
from pipeline.forecast.metrics import Scores

TS = pd.Timestamp
NAN = float("nan")

# --- helpers -----------------------------------------------------------------------------


def _hours(start, n):
    return pd.date_range(start, periods=n, freq="h")


def _ramp(n, start="2024-01-01"):
    """Value = hour offset from `start`: 0, 1, 2, ..."""
    return pd.Series(np.arange(n, dtype=float), index=_hours(start, n))


def _drop(s, *offsets):
    """`s` without the rows at these positions (the result is NOT reindexed)."""
    return s.drop(s.index[list(offsets)])


def _toy(start, n, seed):
    """Daily + weekly shaped load with noise (Monday = 0 ... Sunday = 6)."""
    idx = _hours(start, n)
    rng = np.random.default_rng(seed)
    hour = np.asarray(idx.hour)
    weekday = np.asarray(idx.weekday)
    values = 20000 + 3000 * np.sin(2 * np.pi * hour / 24) + 1000 * weekday + rng.normal(0, 200, n)
    return pd.Series(values, index=idx)


def _ser(values, start="2024-03-01"):
    return pd.Series(np.asarray(values, dtype=float), index=_hours(start, len(values)))


def _lag_expected(n, k, missing=()):
    """Expected `lag_k` of `_ramp(n)` with the given offsets missing: offset - k, else NaN."""
    return np.array([t - k if (t >= k and (t - k) not in missing) else NAN for t in range(n)])


# --- features: complete_hourly -----------------------------------------------------------


def test_complete_hourly_marks_a_missing_hour_nan_and_keeps_the_rest():
    s = _drop(_ramp(10), 4)
    out = features.complete_hourly(s)
    assert len(out) == 10
    assert np.isnan(out.iloc[4])
    assert out.drop(out.index[4]).tolist() == s.tolist()  # nothing filled or interpolated


def test_complete_hourly_sorts_shuffled_input():
    s = _ramp(48)
    shuffled = s.iloc[np.random.default_rng(1).permutation(48)]
    out = features.complete_hourly(shuffled)
    assert out.index.is_monotonic_increasing
    assert out.index.equals(s.index)
    assert out.tolist() == np.arange(48, dtype=float).tolist()


def test_complete_hourly_names_and_frequency():
    s = _ramp(12).rename("whatever")
    out = features.complete_hourly(s)
    assert out.name == "demand_mw"
    assert out.index.name == "ts_local"
    assert out.index.freqstr == "h"


def _empty_series():
    return pd.Series([], index=pd.DatetimeIndex([]), dtype=float)


def _duplicate_timestamp():
    s = _ramp(5)
    return pd.concat([s, s.iloc[[2]]])


def _tz_aware():
    s = _ramp(5)
    s.index = s.index.tz_localize("UTC")
    return s


def _off_the_hour():
    idx = pd.DatetimeIndex(["2024-01-01 00:00", "2024-01-01 00:05", "2024-01-01 02:00"])
    return pd.Series([1.0, 2.0, 3.0], index=idx)


@pytest.mark.parametrize(
    "make_bad", [_empty_series, _duplicate_timestamp, _tz_aware, _off_the_hour],
    ids=["empty", "duplicate", "tz_aware", "off_the_hour"],
)  # fmt: skip
def test_complete_hourly_rejects_bad_input(make_bad):
    with pytest.raises(ValueError):
        features.complete_hourly(make_bad())


# --- features: leakage (guard #2) --------------------------------------------------------

HOLIDAYS = {date(2024, 1, 10), date(2024, 1, 20)}


@pytest.mark.parametrize("cutoff", ["2024-01-08", "2024-01-12", "2024-01-17"])
def test_features_never_use_actuals_from_the_forecast_day_onward(cutoff):
    """A forecast issued at D 00:00 may not see D 00:00 or later: rows up to D 23:00 can't change."""
    s = _toy("2024-01-01", 24 * 28, seed=11)
    d = TS(cutoff)
    next_day = d + pd.Timedelta(days=1)
    base = features.build_features(s, HOLIDAYS)
    keep = base.index < next_day

    replaced = s.copy()
    late = replaced.index >= d
    replaced.loc[late] = np.random.default_rng(5).uniform(1e6, 2e6, int(late.sum()))
    after = features.build_features(replaced, HOLIDAYS)
    pd.testing.assert_frame_equal(base.loc[keep], after.loc[keep])
    # non-vacuous: the first hour of the next day does see D 00:00 through lag_24
    assert after.loc[next_day, "lag_24"] != base.loc[next_day, "lag_24"]
    assert after.loc[next_day, "lag_24"] > 1e6

    # deleting everything from D on (but the last row, which keeps the index spanning the same hours)
    last = s.index[-1]
    thinned = s.drop(s.index[(s.index >= d) & (s.index < last)])
    thinned.loc[last] = 9e6
    after_deleted = features.build_features(thinned, HOLIDAYS)
    assert after_deleted.index.equals(base.index)
    pd.testing.assert_frame_equal(base.loc[keep], after_deleted.loc[keep])
    assert not np.isnan(base.loc[next_day, "lag_24"])
    assert np.isnan(after_deleted.loc[next_day, "lag_24"])


# --- features: lags align by timestamp (guard #11) ---------------------------------------


@pytest.mark.parametrize("k", features.LAGS_H)
def test_every_lag_is_aligned_by_timestamp_when_an_hour_is_missing(k):
    n = 400
    f = features.build_features(_drop(_ramp(n), 100), set())
    # ramp: the value at offset t is t, so lag_k at t is t - k, except where t - k is the missing hour
    np.testing.assert_array_equal(f[f"lag_{k}"].to_numpy(), _lag_expected(n, k, missing={100}))


def test_lag_24_and_lag_168_are_the_same_clock_hour_one_day_and_one_week_earlier():
    s = _toy("2024-01-01 05:00", 24 * 21, seed=3)
    s = _drop(s, 30, 100, 101, 250, 300)
    f = features.build_features(s, set())
    day, week = pd.Timedelta(days=1), pd.Timedelta(days=7)
    np.testing.assert_array_equal(f["lag_24"].to_numpy(), [s.get(t - day, NAN) for t in f.index])
    np.testing.assert_array_equal(f["lag_168"].to_numpy(), [s.get(t - week, NAN) for t in f.index])


def test_a_missing_hour_is_nan_in_lag_24_exactly_24h_later_and_never_filled():
    f = features.build_features(_drop(_ramp(100), 30), set())
    assert f.index[30] == TS("2024-01-02 06:00")  # the row of the missing hour itself still exists
    nan_rows = set(np.flatnonzero(f["lag_24"].isna().to_numpy()))
    assert nan_rows == set(range(24)) | {54}
    assert f["lag_24"].iloc[30] == 6.0
    assert set(np.flatnonzero(f["lag_48"].isna().to_numpy())) == set(range(48)) | {78}


# --- features: rolling mean (guard #11, min periods) -------------------------------------


def test_roll_mean_24_is_the_mean_of_the_24_hours_ending_at_t_minus_24():
    f = features.build_features(_ramp(200), set())
    # ramp: mean(t - 47 ... t - 24) = t - 35.5
    for t in (47, 48, 100, 199):
        assert f["roll_mean_24"].iloc[t] == pytest.approx(t - 35.5)


def test_roll_mean_24_needs_min_periods_hours_at_the_start_of_the_series():
    f = features.build_features(_ramp(200), set())
    first_ok = features.MIN_LAG_H + features.ROLLING_MIN_PERIODS - 1
    assert f["roll_mean_24"].iloc[:first_ok].isna().all()
    # present hours are offsets 0 ... first_ok - 24, whose mean is (first_ok - 24) / 2
    assert f["roll_mean_24"].iloc[first_ok] == pytest.approx((first_ok - 24) / 2)
    assert f["roll_mean_24"].iloc[first_ok + 1] == pytest.approx((first_ok + 1 - 24) / 2)


def test_roll_mean_24_is_nan_below_min_periods_and_a_partial_mean_at_it():
    spread = [54, 57, 60, 63, 66, 69, 72, 75]  # inside the window of t = 100, which is offsets 53 ... 76
    max_missing = features.ROLLING_WINDOW_H - features.ROLLING_MIN_PERIODS
    assert max_missing < len(spread)

    at_threshold = spread[:max_missing]
    f = features.build_features(_drop(_ramp(150), *at_threshold), set())
    expected = (sum(range(53, 77)) - sum(at_threshold)) / (24 - max_missing)
    assert f["roll_mean_24"].iloc[100] == pytest.approx(expected)

    below = spread[: max_missing + 1]
    f = features.build_features(_drop(_ramp(150), *below), set())
    assert np.isnan(f["roll_mean_24"].iloc[100])


# --- features: calendar ------------------------------------------------------------------


@pytest.mark.parametrize("container", [set, frozenset, list])
def test_calendar_features(container):
    # 2024-01-29 is a Monday; the 14 days run to Sunday 2024-02-11. Days 2 (Wed Jan 31) and
    # 5 (Sat Feb 3) are holidays; Saturdays and Sundays are days 5, 6, 12, 13.
    s = _ramp(24 * 14, start="2024-01-29")
    f = features.build_features(s, container([date(2024, 1, 31), date(2024, 2, 3)]))
    offset = np.arange(len(s))
    day = offset // 24
    weekend = np.isin(day % 7, [5, 6]).astype(int)
    holiday = np.isin(day, [2, 5]).astype(int)

    np.testing.assert_array_equal(f["hour"].to_numpy(), offset % 24)
    np.testing.assert_array_equal(f["iso_weekday"].to_numpy(), day % 7 + 1)
    np.testing.assert_array_equal(f["month"].to_numpy(), np.where(day < 3, 1, 2))
    np.testing.assert_array_equal(f["is_weekend"].to_numpy(), weekend)
    np.testing.assert_array_equal(f["is_holiday"].to_numpy(), holiday)
    np.testing.assert_array_equal(f["is_day_off"].to_numpy(), np.maximum(weekend, holiday))
    for column in ("is_weekend", "is_holiday", "is_day_off"):
        assert pd.api.types.is_integer_dtype(f[column])
    # the whole local date is a holiday, all 24 hours
    assert f["is_holiday"].iloc[2 * 24 : 3 * 24].tolist() == [1] * 24
    assert f["is_holiday"].iloc[3 * 24 : 4 * 24].tolist() == [0] * 24


# --- features: shape ---------------------------------------------------------------------


def test_feature_columns_are_exactly_the_declared_ones_in_order():
    s = _toy("2024-01-01", 24 * 20, seed=2)
    f = features.build_features(s, set())
    assert list(f.columns) == list(features.FEATURE_COLUMNS)
    assert f.index.equals(features.complete_hourly(s).index)
    assert f.index.name == "ts_local"


def test_every_lag_is_at_least_the_minimum_lag():
    assert all(k >= features.MIN_LAG_H for k in features.LAGS_H)
    assert [c for c in features.FEATURE_COLUMNS if c.startswith("lag_")] == [f"lag_{k}" for k in features.LAGS_H]


# --- baseline ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("func", "name", "k"),
    [(baseline.seasonal_naive, "baseline_mw", 168), (baseline.naive_24, "naive24_mw", 24)],
    ids=["seasonal_naive", "naive_24"],
)
def test_reference_forecasts_align_by_timestamp_on_an_input_with_a_missing_row(func, name, k):
    n = 400
    s = _drop(_ramp(n), 100)  # 399 rows, deliberately not reindexed
    out = func(s)
    assert out.name == name
    assert out.index.equals(_hours("2024-01-01", n))  # the complete hourly index
    np.testing.assert_array_equal(out.to_numpy(), _lag_expected(n, k, missing={100}))


def test_reference_forecast_constants():
    assert baseline.BASELINE_LAG_H == 168
    assert baseline.NAIVE_LAG_H == 24


def test_lagged_is_the_value_lag_hours_earlier():
    out = baseline.lagged(_ramp(30), 5)
    np.testing.assert_array_equal(out.to_numpy(), _lag_expected(30, 5))
    assert baseline.lagged(_ramp(30), 1000).isna().all()


@pytest.mark.parametrize("lag_h", [0, -1, -24])
def test_lagged_rejects_a_lag_below_one(lag_h):
    with pytest.raises(ValueError):
        baseline.lagged(_ramp(30), lag_h)


# --- metrics: mape, mae ------------------------------------------------------------------


def test_mape_and_mae_hand_values():
    actual = _ser([100, 200, 400])
    forecast = _ser([110, 180, 400])
    # |err| / actual = 0.1, 0.1, 0.0 -> mean 0.2 / 3 -> 6.666...%; |err| = 10, 20, 0 -> 10 MW
    assert metrics.mape(actual, forecast) == pytest.approx(100 * 0.2 / 3)
    assert metrics.mae(actual, forecast) == pytest.approx(10.0)


def test_mape_and_mae_count_over_and_under_forecasts_alike():
    actual = _ser([100, 100])
    assert metrics.mape(actual, _ser([120, 80])) == pytest.approx(20.0)
    assert metrics.mae(actual, _ser([120, 80])) == pytest.approx(20.0)


def test_mae_accepts_non_positive_actuals():
    assert metrics.mae(_ser([0, -5]), _ser([1, -3])) == pytest.approx(1.5)


@pytest.mark.parametrize("func", [metrics.mape, metrics.mae], ids=["mape", "mae"])
def test_error_metrics_reject_nan_empty_and_mismatched_input(func):
    good = _ser([100, 200, 300])
    with pytest.raises(ValueError):
        func(_ser([100, NAN, 300]), good)
    with pytest.raises(ValueError):
        func(good, _ser([100, NAN, 300]))
    with pytest.raises(ValueError):
        func(_empty_series(), _empty_series())
    with pytest.raises(ValueError):
        func(good, _ser([100, 200, 300], start="2024-03-01 01:00"))  # same length, shifted index
    with pytest.raises(ValueError):
        func(good, _ser([100, 200]))  # different length


@pytest.mark.parametrize("bad_actual", [[100, 0, 50], [100, -5, 50]], ids=["zero", "negative"])
def test_mape_rejects_a_non_positive_actual(bad_actual):
    with pytest.raises(ValueError):
        metrics.mape(_ser(bad_actual), _ser([100, 100, 100]))


# --- metrics: scored_mask, score ---------------------------------------------------------

# Hours 0-4 are scored; hour 5 has no baseline (model wildly wrong), hour 6 no actual, hour 7 no model.
ACTUAL = _ser([100, 200, 100, 200, 100, 100, NAN, 100])
MODEL = _ser([110, 180, 100, 200, 90, 1e6, 100, NAN])
BASELINE = _ser([120, 200, 80, 220, 100, NAN, 100, 100])


def test_scored_mask_is_true_where_all_three_are_present():
    mask = metrics.scored_mask(ACTUAL, MODEL, BASELINE)
    assert mask.tolist() == [True] * 5 + [False] * 3
    assert mask.index.equals(ACTUAL.index)


def test_scored_mask_rejects_different_indexes():
    with pytest.raises(ValueError):
        metrics.scored_mask(ACTUAL, MODEL, _ser([1.0] * 8, start="2024-03-02"))


def test_score_uses_only_the_hours_where_actual_model_and_baseline_all_exist():
    s = metrics.score(ACTUAL, MODEL, BASELINE)
    # model: |err| 10, 20, 0, 0, 10 -> 0.1, 0.1, 0, 0, 0.1 -> 6.0 %, MAE 8.0
    # baseline: |err| 20, 0, 20, 20, 0 -> 0.2, 0, 0.2, 0.1, 0 -> 10.0 %, MAE 12.0
    assert s.mape_model == pytest.approx(6.0)
    assert s.mape_baseline == pytest.approx(10.0)
    assert s.mae_model == pytest.approx(8.0)
    assert s.mae_baseline == pytest.approx(12.0)
    assert s.improvement_pct == pytest.approx(40.0)
    assert s.scored_hours == 5
    assert s.excluded_hours == 3


def test_a_wrong_model_value_where_the_baseline_is_missing_does_not_change_the_model_score():
    wild = MODEL.copy()
    wild.iloc[5] = 9e9  # hour 5 has no baseline
    assert metrics.score(ACTUAL, wild, BASELINE).mape_model == pytest.approx(6.0)
    assert metrics.score(ACTUAL, wild, BASELINE).mae_model == pytest.approx(8.0)


def test_score_without_a_scored_hour_raises():
    with pytest.raises(ValueError):
        metrics.score(_ser([100, 100]), _ser([100, 100]), _ser([NAN, NAN]))


# --- metrics: improvement_pct, beats_baseline --------------------------------------------


@pytest.mark.parametrize(
    ("model", "base", "expected"), [(8.0, 10.0, 20.0), (10.0, 10.0, 0.0), (12.0, 10.0, -20.0), (0.0, 5.0, 100.0)]
)  # fmt: skip
def test_improvement_pct_hand_values(model, base, expected):
    assert metrics.improvement_pct(model, base) == pytest.approx(expected)


@pytest.mark.parametrize("base", [0.0, -1.0])
def test_improvement_pct_rejects_a_non_positive_baseline_mape(base):
    with pytest.raises(ValueError):
        metrics.improvement_pct(5.0, base)


@pytest.mark.parametrize(("ci_low", "expected"), [(0.0, False), (-1.0, False), (0.001, True), (25.0, True)])
def test_beats_baseline_needs_a_lower_bound_above_zero(ci_low, expected):
    assert metrics.beats_baseline(ci_low) is expected


# --- metrics: score_groups ---------------------------------------------------------------


def _assert_scores_close(got, want):
    for field in dataclasses.fields(Scores):
        assert getattr(got, field.name) == pytest.approx(getattr(want, field.name)), field.name


def _grouped_toy():
    """Jan 30-31 (48 h), Feb 1-3 (72 h) and six March hours that have no baseline at all."""
    idx = _hours("2024-01-30", 48).append(_hours("2024-02-01", 72)).append(_hours("2024-03-01", 6))
    n = len(idx)
    t = np.arange(n)
    actual = pd.Series(20000 + 1000 * np.sin(t), index=idx)
    model = actual * (1 + 0.01 * (t % 3 - 1))
    base = actual * (1 + 0.02 * (t % 5 - 2))
    base.iloc[[3, 10, 20]] = NAN  # three January hours
    base.iloc[[50, 60, 70, 80, 90]] = NAN  # five February hours (positions 48 + 2, ...)
    base.iloc[120:] = NAN  # all of March
    return actual, model, base, pd.Series(idx.month, index=idx)


def test_score_groups_by_month_matches_score_on_each_slice():
    actual, model, base, month = _grouped_toy()
    groups = metrics.score_groups(actual, model, base, month)
    assert list(groups) == [1, 2]  # March has no scored hour; keys sorted
    for key in (1, 2):
        sel = (month == key).to_numpy()
        _assert_scores_close(groups[key], metrics.score(actual[sel], model[sel], base[sel]))
    assert (groups[1].scored_hours, groups[1].excluded_hours) == (45, 3)
    assert (groups[2].scored_hours, groups[2].excluded_hours) == (67, 5)


def test_score_groups_sorts_keys_not_in_order_of_appearance():
    idx = _hours("2024-03-01", 6)
    flag = pd.Series([1, 1, 1, 0, 0, 0], index=idx)
    actual = _ser([100] * 6)
    groups = metrics.score_groups(actual, _ser([110] * 6), _ser([120] * 6), flag)
    assert list(groups) == [0, 1]
    assert groups[0].mape_model == pytest.approx(10.0)
    assert groups[1].mape_baseline == pytest.approx(20.0)


# --- metrics: day-block bootstrap --------------------------------------------------------


def _noisy_days(n_days, seed):
    actual = _toy("2024-03-01", 24 * n_days, seed=seed)
    rng = np.random.default_rng(seed + 1)
    model = actual * (1 + rng.normal(0, 0.03, len(actual)))
    base = actual * (1 + rng.normal(0, 0.06, len(actual)))
    return actual, model, base


def test_bootstrap_ci_is_exactly_100_when_the_model_is_perfect():
    actual, _, base = _noisy_days(5, seed=1)
    low, high = metrics.day_block_bootstrap_ci(actual, actual.copy(), base, n_boot=50, seed=0)
    assert (low, high) == (pytest.approx(100.0), pytest.approx(100.0))


def test_bootstrap_ci_is_exactly_zero_when_the_model_is_the_baseline():
    actual, _, base = _noisy_days(5, seed=2)
    low, high = metrics.day_block_bootstrap_ci(actual, base.copy(), base, n_boot=50, seed=0)
    assert (low, high) == (pytest.approx(0.0), pytest.approx(0.0))


def test_bootstrap_ci_of_a_single_day_collapses_to_the_point_estimate():
    """One block means every replicate is the same day; hour-level resampling would not collapse."""
    a = 100.0 + np.arange(24)
    model_err = np.tile([0.05, 0.10, 0.15], 8)  # mean 0.10 -> MAPE 10 %
    base_err = np.tile([0.30, 0.10, 0.20], 8)  # mean 0.20 -> MAPE 20 %
    actual = _ser(a)
    low, high = metrics.day_block_bootstrap_ci(
        actual, _ser(a * (1 + model_err)), _ser(a * (1 + base_err)), n_boot=200, seed=3
    )  # fmt: skip
    assert low == high
    assert low == pytest.approx(50.0)  # 100 * (1 - 10 / 20)


def test_bootstrap_ci_resamples_whole_days():
    """Day 1: model 10 %, baseline 20 % (improvement +50). Day 2: model 30 %, baseline 20 % (-50).

    With two whole-day blocks every replicate pools {d1, d1}, {d1, d2}, {d2, d1} or {d2, d2}, so its
    improvement is +50, 0, 0 or -50 and the 95 % CI is exactly (-50, +50) once n_boot is large.
    """
    actual = _ser([100.0] * 48)
    model = _ser([110.0] * 24 + [130.0] * 24)
    base = _ser([120.0] * 48)
    low, high = metrics.day_block_bootstrap_ci(actual, model, base, n_boot=400, seed=1)
    assert low == pytest.approx(-50.0)
    assert high == pytest.approx(50.0)


def test_bootstrap_ci_is_reproducible_for_a_seed_and_depends_on_it():
    actual, model, base = _noisy_days(30, seed=4)
    first = metrics.day_block_bootstrap_ci(actual, model, base, n_boot=100, seed=7)
    again = metrics.day_block_bootstrap_ci(actual, model, base, n_boot=100, seed=7)
    other = metrics.day_block_bootstrap_ci(actual, model, base, n_boot=100, seed=8)
    assert first == again
    assert first != other


def test_bootstrap_ci_brackets_the_point_estimate_and_widens_with_the_level():
    actual, model, base = _noisy_days(40, seed=5)
    point = metrics.score(actual, model, base).improvement_pct
    low95, high95 = metrics.day_block_bootstrap_ci(actual, model, base, n_boot=300, seed=11, level=0.95)
    low80, high80 = metrics.day_block_bootstrap_ci(actual, model, base, n_boot=300, seed=11, level=0.80)
    assert low95 < point < high95
    assert low95 < low80 < high80 < high95  # same replicates, so the quantiles nest, and a wider level reaches further out


def test_bootstrap_ci_ignores_unscored_hours():
    actual, model, base = _noisy_days(10, seed=6)
    wild = model.copy()
    wild.iloc[5] = 9e9
    holey = base.copy()
    holey.iloc[5] = NAN
    holey_clean = metrics.day_block_bootstrap_ci(actual, model, holey, n_boot=50, seed=2)
    holey_wild = metrics.day_block_bootstrap_ci(actual, wild, holey, n_boot=50, seed=2)
    assert holey_wild == holey_clean


@pytest.mark.parametrize(
    "kwargs", [{"n_boot": 0}, {"n_boot": -3}, {"level": 0.0}, {"level": 1.0}, {"level": 1.5}],
    ids=["n_boot_0", "n_boot_negative", "level_0", "level_1", "level_above_1"],
)  # fmt: skip
def test_bootstrap_ci_rejects_bad_settings(kwargs):
    actual, model, base = _noisy_days(3, seed=7)
    settings = {"n_boot": 20, "seed": 0, **kwargs}
    with pytest.raises(ValueError):
        metrics.day_block_bootstrap_ci(actual, model, base, **settings)


def test_bootstrap_ci_rejects_data_without_a_scored_hour():
    actual, model, _ = _noisy_days(3, seed=8)
    with pytest.raises(ValueError):
        metrics.day_block_bootstrap_ci(actual, model, pd.Series(NAN, index=actual.index), n_boot=20, seed=0)


# --- backtest: folds ---------------------------------------------------------------------

LAST_DAY_2024 = {
    "2024-01": 31, "2024-02": 29, "2024-03": 31, "2024-04": 30, "2024-05": 31, "2024-06": 30,
    "2024-07": 31, "2024-08": 31, "2024-09": 30, "2024-10": 31, "2024-11": 30, "2024-12": 31,
}  # fmt: skip


def test_monthly_folds_for_the_final_year():
    data_start = TS("2023-01-08")
    folds = backtest.monthly_folds(data_start, "2024-01", "2024-12", 28)
    assert [f.name for f in folds] == list(LAST_DAY_2024)
    for f in folds:
        assert f.fit_start == TS("2023-01-08 00:00")
        assert f.test_start == TS(f"{f.name}-01 00:00")
        assert f.test_end == TS(f"{f.name}-{LAST_DAY_2024[f.name]} 23:00")
        assert f.es_start == f.test_start - pd.Timedelta(days=28)
    assert folds[1].test_end == TS("2024-02-29 23:00")  # leap year
    assert folds[0].es_start == TS("2023-12-04 00:00")


def test_monthly_folds_for_the_development_months():
    folds = backtest.monthly_folds(TS("2023-01-08"), "2023-10", "2023-12", 28)
    assert [f.name for f in folds] == ["2023-10", "2023-11", "2023-12"]
    assert folds[-1].test_end == TS("2023-12-31 23:00")
    assert folds[0].test_start == TS("2023-10-01 00:00")


def test_monthly_folds_single_month():
    folds = backtest.monthly_folds(TS("2023-01-08"), "2024-02", "2024-02", 7)
    assert len(folds) == 1
    assert folds[0].test_end == TS("2024-02-29 23:00")


def test_monthly_folds_reject_a_last_month_before_the_first():
    with pytest.raises(ValueError):
        backtest.monthly_folds(TS("2023-01-08"), "2024-02", "2024-01", 28)


@pytest.mark.parametrize("es_days", [0, -1])
def test_monthly_folds_reject_an_early_stopping_window_below_one_day(es_days):
    with pytest.raises(ValueError):
        backtest.monthly_folds(TS("2023-01-08"), "2024-01", "2024-03", es_days)


def test_monthly_folds_reject_an_empty_fit_window():
    # first fold: test_start 2024-01-01, es_start 2023-12-04
    with pytest.raises(ValueError):
        backtest.monthly_folds(TS("2024-03-01"), "2024-01", "2024-03", 28)  # data starts after es_start
    with pytest.raises(ValueError):
        backtest.monthly_folds(TS("2023-12-04"), "2024-01", "2024-03", 28)  # data starts AT es_start
    folds = backtest.monthly_folds(TS("2023-12-03 23:00"), "2024-01", "2024-03", 28)  # one fit hour is enough
    assert len(folds) == 3


# --- backtest: run_backtest on fakes -----------------------------------------------------

MAR = Fold("2024-03", TS("2024-01-01"), TS("2024-02-23"), TS("2024-03-01"), TS("2024-03-31 23:00"))
APR = Fold("2024-04", TS("2024-01-01"), TS("2024-03-25"), TS("2024-04-01"), TS("2024-04-30 23:00"))
BT_HOLIDAYS = {date(2024, 1, 1), date(2024, 2, 10), date(2024, 3, 29), date(2024, 4, 10)}


class _SpyRegressor:
    """Records every call; predicts zeros."""

    def __init__(self):
        self.events = []
        self.fit_calls = []
        self.predict_calls = []

    def fit(self, X_fit, y_fit, X_es, y_es):
        self.events.append("fit")
        self.fit_calls.append((X_fit.copy(), y_fit.copy(), X_es.copy(), y_es.copy()))

    def predict(self, X):
        self.events.append("predict")
        self.predict_calls.append(X.copy())
        return np.zeros(len(X))


class _MeanLagModel:
    """Deterministic, and it depends on the training data and on three features."""

    def fit(self, X_fit, y_fit, X_es, y_es):
        self.level = float(y_fit.mean()) + 0.5 * float(y_es.mean())

    def predict(self, X):
        return self.level + X["lag_24"].to_numpy() + 0.1 * X["roll_mean_24"].to_numpy() + 0.01 * X["lag_168"].to_numpy()


class _LagModel:
    """forecast = lag_24 + 1000, NaN wherever lag_24 is NaN."""

    def fit(self, X_fit, y_fit, X_es, y_es):
        pass

    def predict(self, X):
        return X["lag_24"].to_numpy() + 1000.0


def _spy_factory():
    created = []

    def factory():
        model = _SpyRegressor()
        created.append(model)
        return model

    return factory, created


def _bt_series(*, drop=()):
    """2024-01-01 00:00 ... 2024-04-30 23:00 with the given timestamps deleted."""
    s = _toy("2024-01-01", 24 * 121, seed=3)
    return s.drop([TS(t) for t in drop])


def test_run_backtest_gives_each_fold_a_fresh_model_and_only_past_data():
    drop = ["2024-01-20 10:00", "2024-02-25 12:00", "2024-03-10 05:00", "2024-03-10 06:00",
            "2024-03-27 08:00", "2024-04-15 03:00"]  # fmt: skip
    s = _bt_series(drop=drop)
    factory, created = _spy_factory()
    backtest.run_backtest(s, BT_HOLIDAYS, [MAR, APR], factory)

    assert len(created) == 2  # a new model per fold
    for model, fold in zip(created, [MAR, APR], strict=True):
        assert model.events.count("fit") == 1
        assert model.events[0] == "fit"  # fitted before any prediction
        assert model.predict_calls

        X_fit, y_fit, X_es, y_es = model.fit_calls[0]
        present = s.index
        want_fit = present[(present >= fold.fit_start) & (present < fold.es_start)]
        want_es = present[(present >= fold.es_start) & (present < fold.test_start)]
        for X, y, want in ((X_fit, y_fit, want_fit), (X_es, y_es, want_es)):
            assert X.index.equals(want)  # present actuals only, nothing from the test month
            assert y.index.equals(X.index)
            assert X.index.name == "ts_local"
            assert list(X.columns) == list(features.FEATURE_COLUMNS)
            assert y.notna().all()
        assert max(X_fit.index.max(), X_es.index.max()) < fold.test_start  # nothing at or after test_start

    # missing hours are left out of fit and ES, and their consequences stay NaN in X (never filled)
    X_fit, _, X_es, _ = created[0].fit_calls[0]
    assert TS("2024-01-20 10:00") not in X_fit.index
    assert TS("2024-02-25 12:00") not in X_es.index
    assert np.isnan(X_fit.loc["2024-01-21 10:00", "lag_24"])
    assert np.isnan(X_fit.loc["2024-01-22 10:00", "lag_48"])
    assert np.isnan(X_fit.loc["2024-01-27 10:00", "lag_168"])
    assert np.isnan(X_fit.loc["2024-02-03 10:00", "lag_336"])
    assert not np.isnan(X_fit.loc["2024-01-21 11:00", "lag_24"])
    assert not np.isnan(X_fit.loc["2024-01-21 10:00", "roll_mean_24"])  # 23 of 24 hours is enough
    assert np.isnan(X_fit.loc["2024-01-01 05:00", "lag_24"])  # before the series starts
    assert np.isnan(X_es.loc["2024-02-26 12:00", "lag_24"])
    _, _, X_es_apr, _ = created[1].fit_calls[0]
    assert TS("2024-03-27 08:00") not in X_es_apr.index
    assert np.isnan(X_es_apr.loc["2024-03-28 08:00", "lag_24"])


def test_run_backtest_predicts_every_test_hour_gap_hours_included():
    drop = ["2024-03-10 05:00", "2024-03-10 06:00", "2024-04-15 03:00"]
    s = _bt_series(drop=drop)
    factory, created = _spy_factory()
    backtest.run_backtest(s, BT_HOLIDAYS, [MAR, APR], factory)
    for model, fold in zip(created, [MAR, APR], strict=True):
        for X in model.predict_calls:
            assert list(X.columns) == list(features.FEATURE_COLUMNS)
        predicted = pd.concat(model.predict_calls)
        assert predicted.index.is_unique
        assert predicted.index.sort_values().equals(pd.date_range(fold.test_start, fold.test_end, freq="h"))
    march = pd.concat(created[0].predict_calls)
    assert TS("2024-03-10 05:00") in march.index  # the gap hour itself is predicted
    assert np.isnan(march.loc["2024-03-11 05:00", "lag_24"])  # and its successor sees the gap


def test_forecasts_up_to_the_end_of_day_d_do_not_change_when_actuals_from_d_on_change():
    """END-TO-END LEAKAGE (guard #2): D lies inside the second fold's test month."""
    s = _bt_series()
    d = TS("2024-04-12")
    next_day = d + pd.Timedelta(days=1)
    first = backtest.run_backtest(s, BT_HOLIDAYS, [MAR, APR], _MeanLagModel)

    changed = s.copy()
    late = changed.index >= d
    changed.loc[late] = np.random.default_rng(9).uniform(5e4, 9e4, int(late.sum()))
    second = backtest.run_backtest(changed, BT_HOLIDAYS, [MAR, APR], _MeanLagModel)

    cols = ["fold", "forecast_mw", "baseline_mw", "naive24_mw"]
    before = first.index < next_day
    pd.testing.assert_frame_equal(first.loc[before, cols], second.loc[before, cols])
    assert first.loc[before, "forecast_mw"].notna().all()  # non-vacuous: real forecasts were compared
    assert first.loc[next_day, "forecast_mw"] != second.loc[next_day, "forecast_mw"]  # D+1 does see D
    assert not first["actual_mw"].equals(second["actual_mw"])


def test_data_after_the_last_test_end_cannot_influence_the_run():
    full = _toy("2024-01-01", 24 * 131, seed=3)  # ten days beyond April
    ends = APR.test_end
    truncated = full.loc[:ends]
    poisoned = full.copy()
    poisoned.loc[poisoned.index > ends] = 1e9
    assert len(poisoned) > len(truncated)

    expected = backtest.run_backtest(truncated, BT_HOLIDAYS, [MAR, APR], _MeanLagModel)
    actual = backtest.run_backtest(poisoned, BT_HOLIDAYS, [MAR, APR], _MeanLagModel)
    pd.testing.assert_frame_equal(actual, expected)
    assert actual.index.max() == ends

    factory, created = _spy_factory()
    backtest.run_backtest(poisoned, BT_HOLIDAYS, [MAR, APR], factory)
    for model in created:
        indexes = [X.index.max() for X, *_ in model.fit_calls] + [X.index.max() for X in model.predict_calls]
        assert max(indexes) <= ends


def test_result_frame_layout_and_values():
    drop = ["2024-03-03 00:00", "2024-03-15 07:00", "2024-03-15 08:00", "2024-04-02 12:00"]
    s = _bt_series(drop=drop)
    res = backtest.run_backtest(s, BT_HOLIDAYS, [MAR, APR], _LagModel)

    assert list(res.columns) == list(backtest.RESULT_COLUMNS)
    expected_index = pd.date_range(MAR.test_start, MAR.test_end, freq="h").append(
        pd.date_range(APR.test_start, APR.test_end, freq="h")
    )
    assert res.index.equals(expected_index)  # every test hour, gap hours included
    assert res.index.name == "ts_local"
    assert res.index.is_monotonic_increasing
    assert res["fold"].tolist() == ["2024-03"] * (31 * 24) + ["2024-04"] * (30 * 24)

    np.testing.assert_array_equal(res["actual_mw"].to_numpy(), s.reindex(res.index).to_numpy())
    assert np.isnan(res.loc["2024-03-15 07:00", "actual_mw"])
    assert np.isnan(res.loc["2024-04-02 12:00", "actual_mw"])
    # forecast = actual one day earlier + 1000 (NaN where that hour is missing)
    np.testing.assert_array_equal(
        res["forecast_mw"].to_numpy(), s.reindex(res.index - pd.Timedelta(hours=24)).to_numpy() + 1000.0
    )
    np.testing.assert_array_equal(
        res["baseline_mw"].to_numpy(), baseline.seasonal_naive(s).reindex(res.index).to_numpy()
    )
    np.testing.assert_array_equal(
        res["naive24_mw"].to_numpy(), s.reindex(res.index - pd.Timedelta(hours=24)).to_numpy()
    )
    # baseline = actual one week earlier
    np.testing.assert_array_equal(
        res["baseline_mw"].to_numpy(), s.reindex(res.index - pd.Timedelta(days=7)).to_numpy()
    )

    assert res["is_scored"].dtype == bool
    expected_scored = res["actual_mw"].notna() & res["forecast_mw"].notna() & res["baseline_mw"].notna()
    assert res["is_scored"].tolist() == expected_scored.tolist()
    # hand-derived from the deleted hours 03-03 00:00, 03-15 07:00 and 08:00, 04-02 12:00: each one is
    # an unscored gap hour, then 24 h later has no lag_24 forecast, then 168 h later has no baseline
    unscored = [
        "2024-03-03 00:00", "2024-03-04 00:00", "2024-03-10 00:00",
        "2024-03-15 07:00", "2024-03-15 08:00", "2024-03-16 07:00", "2024-03-16 08:00",
        "2024-03-22 07:00", "2024-03-22 08:00",
        "2024-04-02 12:00", "2024-04-03 12:00", "2024-04-09 12:00",
    ]  # fmt: skip
    assert set(res.index[~res["is_scored"]]) == {TS(t) for t in unscored}
    assert res.loc["2024-03-20 12:00", "is_scored"]


LGBM_PARAMS = {
    "objective": "l2", "learning_rate": 0.1, "num_leaves": 7, "n_estimators": 50,
    "min_data_in_leaf": 5, "verbose": -1,
}  # fmt: skip


def test_lgbm_regressor_fits_and_sets_best_iteration():
    s = _toy("2023-12-18", 24 * 40, seed=1)
    f = features.build_features(s, set())
    cut_fit, cut_es = TS("2024-01-15"), TS("2024-01-22")
    fit, es = f.index < cut_fit, (f.index >= cut_fit) & (f.index < cut_es)
    model = backtest.LgbmRegressor(LGBM_PARAMS, seed=7, num_threads=1)
    model.fit(f[fit], s[fit], f[es], s[es])
    assert model.best_iteration >= 1
    pred = model.predict(f[~fit & ~es])
    assert pred.shape == (int((~fit & ~es).sum()),)
    assert np.isfinite(pred).all()


def test_real_lightgbm_backtest_is_bit_identical_for_the_same_seed_and_learns_the_shape():
    s = _toy("2023-12-18", 24 * 74, seed=21)  # ten and a half weeks, ending 2024-02-29 23:00
    s = _drop(s, 30, 200, 205, 700, 1000, 1500)  # missing hours: NaN lags reach the model
    jan = Fold("2024-01", TS("2023-12-18"), TS("2023-12-25"), TS("2024-01-01"), TS("2024-01-31 23:00"))
    feb = Fold("2024-02", TS("2023-12-18"), TS("2024-01-25"), TS("2024-02-01"), TS("2024-02-29 23:00"))

    def run():
        return backtest.run_backtest(
            s, set(), [jan, feb], lambda: backtest.LgbmRegressor(LGBM_PARAMS, seed=7, num_threads=1)
        )

    first, second = run(), run()
    pd.testing.assert_frame_equal(first, second, check_exact=True)
    scored = first[first["is_scored"]]
    assert first["forecast_mw"].notna().all()
    assert first["forecast_mw"].nunique() > 24  # not a constant
    # the toy is a smooth daily + weekly shape: the learner should be comfortably within 10 % on the February fold
    feb_rows = scored[scored["fold"] == "2024-02"]
    assert metrics.mape(feb_rows["actual_mw"], feb_rows["forecast_mw"]) < 10.0


def test_run_backtest_rejects_empty_unsorted_and_overlapping_folds():
    s = _bt_series()
    overlapping = Fold("2024-03b", TS("2024-01-01"), TS("2024-03-08"), TS("2024-03-15"), TS("2024-04-10 23:00"))
    with pytest.raises(ValueError):
        backtest.run_backtest(s, BT_HOLIDAYS, [], _LagModel)
    with pytest.raises(ValueError):
        backtest.run_backtest(s, BT_HOLIDAYS, [APR, MAR], _LagModel)  # unsorted
    with pytest.raises(ValueError):
        backtest.run_backtest(s, BT_HOLIDAYS, [MAR, overlapping], _LagModel)  # test windows overlap
    with pytest.raises(ValueError):
        backtest.run_backtest(s, BT_HOLIDAYS, [MAR, MAR], _LagModel)  # the same window twice


# --- store: fact_rows --------------------------------------------------------------------


def _result_frame():
    idx = pd.DatetimeIndex(pd.date_range("2024-03-01", periods=4, freq="h"), name="ts_local")
    return pd.DataFrame(
        {
            "fold": "2024-03",
            "actual_mw": [100.25, NAN, 100.75, 3.25],
            "forecast_mw": [100.25, 100.5, 3.75, 50.0],
            "baseline_mw": [100.75, 20.0, NAN, 80.0],
            "naive24_mw": [90.0, NAN, 90.0, 90.0],
            "is_scored": [True, False, False, True],
        },
        index=idx,
    )


def _as_dicts(rows):
    return [dict(zip(store.FACT_COLUMNS, row, strict=True)) for row in rows]


def test_fact_columns_are_the_table_columns_in_order():
    assert store.FACT_COLUMNS == (
        "model_run_id", "grid_key", "ts_utc", "ts_local", "actual_mw", "forecast_mw",
        "baseline_mw", "is_scored", "date_key", "hour",
    )  # fmt: skip
    assert store.RUN_KINDS == ("DEV", "FINAL", "POST_HOC")


def test_fact_rows_thailand_offset_values_and_types():
    rows = store.fact_rows(_result_frame(), model_run_id=7, grid_key=2, utc_offset_min=420)
    assert len(rows) == 4
    assert all(isinstance(r, tuple) and len(r) == 10 for r in rows)
    first, second, third, fourth = _as_dicts(rows)

    assert first["model_run_id"] == 7
    assert first["grid_key"] == 2
    assert first["ts_local"] == TS("2024-03-01 00:00")
    assert isinstance(first["ts_local"], datetime)
    assert first["ts_local"].tzinfo is None
    assert first["ts_utc"] == TS("2024-02-29 17:00")  # local - 7 h, across a date boundary
    assert fourth["ts_utc"] == TS("2024-02-29 20:00")
    assert (first["date_key"], first["hour"]) == (20240301, 0)  # local date and hour
    assert (fourth["date_key"], fourth["hour"]) == (20240301, 3)

    # round half up to 0.1; the inputs are binary-exact halves (half-even would give 100.2 and 3.2)
    assert first["actual_mw"] == Decimal("100.3")
    assert first["forecast_mw"] == Decimal("100.3")
    assert first["baseline_mw"] == Decimal("100.8")
    assert third["forecast_mw"] == Decimal("3.8")
    assert fourth["actual_mw"] == Decimal("3.3")
    assert second["forecast_mw"] == Decimal("100.5")
    assert fourth["baseline_mw"] == Decimal("80.0")
    for value in (first["actual_mw"], first["forecast_mw"], fourth["baseline_mw"]):
        assert isinstance(value, Decimal)
        assert value.as_tuple().exponent == -1

    assert second["actual_mw"] is None
    assert third["baseline_mw"] is None
    assert [r["is_scored"] for r in (first, second, third, fourth)] == [1, 0, 0, 1]
    for key in ("model_run_id", "grid_key", "is_scored", "date_key", "hour"):
        assert type(first[key]) is int


def test_fact_rows_singapore_offset():
    rows = _as_dicts(store.fact_rows(_result_frame(), model_run_id=7, grid_key=3, utc_offset_min=480))
    assert rows[0]["ts_utc"] == TS("2024-02-29 16:00")  # local - 8 h
    assert rows[0]["ts_local"] == TS("2024-03-01 00:00")
    assert rows[3]["ts_utc"] == TS("2024-02-29 19:00")


def test_fact_rows_reject_a_nan_forecast():
    frame = _result_frame()
    frame.loc[frame.index[1], "forecast_mw"] = NAN  # the row is correctly unscored, but the column is NOT NULL
    with pytest.raises(ValueError):
        store.fact_rows(frame, model_run_id=1, grid_key=1, utc_offset_min=420)


@pytest.mark.parametrize(
    ("row", "flag"), [(0, False), (1, True), (2, True), (3, False)],
    ids=["scored_row_marked_unscored", "no_actual_marked_scored", "no_baseline_marked_scored", "second_scored_row"],
)  # fmt: skip
def test_fact_rows_reject_an_is_scored_flag_that_disagrees_with_the_data(row, flag):
    frame = _result_frame()
    frame.loc[frame.index[row], "is_scored"] = flag
    with pytest.raises(ValueError):
        store.fact_rows(frame, model_run_id=1, grid_key=1, utc_offset_min=420)


# --- store: run_row ----------------------------------------------------------------------

JAN_FOLD = Fold("2024-01", TS("2023-01-08"), TS("2023-12-04"), TS("2024-01-01"), TS("2024-01-31 23:00"))
DEC_FOLD = Fold("2024-12", TS("2023-01-08"), TS("2024-11-03"), TS("2024-12-01"), TS("2024-12-31 23:00"))
SCORES = Scores(
    mape_model=5.0625, mape_baseline=10.4375, mae_model=3.0625, mae_baseline=4.5625,
    improvement_pct=12.8125, scored_hours=8000, excluded_hours=120,
)  # fmt: skip
COMMIT_A = "0123456789abcdef0123456789abcdef01234567"
COMMIT_B = "89abcdef" * 5
RUN_COLUMNS = {
    "grid_key", "load_run_id", "run_kind", "model_name", "train_start", "train_end", "test_start",
    "test_end", "mape_model", "mape_baseline", "mae_model", "mae_baseline", "improvement_pct",
    "improvement_ci_low", "improvement_ci_high", "scored_hours", "excluded_hours", "params_json",
    "metrics_json", "git_commit", "protocol_commit", "is_current",
}  # fmt: skip


def _run_kwargs(**overrides):
    kwargs = {
        "grid_key": 1, "run_kind": "FINAL", "model_name": "lightgbm", "folds": [JAN_FOLD, DEC_FOLD],
        "scores": SCORES, "ci": (1.0625, 20.5), "params": {"seed": 7, "lightgbm": {"num_leaves": 7, "learning_rate": 0.1}},
        "metrics": {"fold_mape": {"2024-02": 3.0, "2024-01": 2.5}, "a": 1}, "git_commit": COMMIT_A,
        "protocol_commit": COMMIT_B, "load_run_id": 5, "is_current": True,
    }  # fmt: skip
    kwargs.update(overrides)
    return kwargs


def test_run_row_for_a_final_run():
    row = store.run_row(**_run_kwargs())
    assert set(row) == RUN_COLUMNS

    assert row["grid_key"] == 1
    assert row["load_run_id"] == 5
    assert row["run_kind"] == "FINAL"
    assert row["model_name"] == "lightgbm"
    # first fold's fit_start; the day before the last fold's test month; first test_start; last test_end
    assert row["train_start"] == date(2023, 1, 8)
    assert row["train_end"] == date(2024, 11, 30)
    assert row["test_start"] == date(2024, 1, 1)
    assert row["test_end"] == date(2024, 12, 31)
    for key in ("train_start", "train_end", "test_start", "test_end"):
        assert type(row[key]) is date

    # round half up to 3 places; the inputs are binary-exact halves (half-even would end in an even digit)
    expected = {
        "mape_model": "5.063", "mape_baseline": "10.438", "mae_model": "3.063", "mae_baseline": "4.563",
        "improvement_pct": "12.813", "improvement_ci_low": "1.063", "improvement_ci_high": "20.500",
    }  # fmt: skip
    for key, text in expected.items():
        assert isinstance(row[key], Decimal), key
        assert row[key] == Decimal(text), key
        assert row[key].as_tuple().exponent == -3, key
    assert row["scored_hours"] == 8000
    assert row["excluded_hours"] == 120
    assert type(row["scored_hours"]) is int
    assert type(row["excluded_hours"]) is int

    assert row["params_json"] == '{"lightgbm": {"learning_rate": 0.1, "num_leaves": 7}, "seed": 7}'
    assert row["metrics_json"] == '{"a": 1, "fold_mape": {"2024-01": 2.5, "2024-02": 3.0}}'
    assert row["git_commit"] == COMMIT_A
    assert row["protocol_commit"] == COMMIT_B
    assert row["is_current"] == 1
    assert type(row["is_current"]) is int


def test_run_row_for_a_dev_run_without_metrics_or_commits():
    row = store.run_row(
        **_run_kwargs(run_kind="DEV", metrics=None, git_commit=None, protocol_commit=None, load_run_id=None, is_current=False)
    )  # fmt: skip
    assert row["metrics_json"] is None
    assert row["git_commit"] is None
    assert row["protocol_commit"] is None
    assert row["load_run_id"] is None
    assert row["is_current"] == 0
    assert type(row["is_current"]) is int
    assert json.loads(row["params_json"])["seed"] == 7


def test_run_row_accepts_a_post_hoc_run_and_a_collapsed_ci():
    row = store.run_row(**_run_kwargs(run_kind="POST_HOC", is_current=False, ci=(2.0, 2.0)))
    assert row["run_kind"] == "POST_HOC"
    assert row["improvement_ci_low"] == row["improvement_ci_high"] == Decimal("2.000")


_BAD_HASHES = {"uppercase": "A" * 40, "short": "a" * 39, "non_hex": "g" * 40, "long": "a" * 41}


@pytest.mark.parametrize("field", ["git_commit", "protocol_commit"])
@pytest.mark.parametrize("bad", list(_BAD_HASHES.values()), ids=list(_BAD_HASHES))
def test_run_row_rejects_a_commit_that_is_not_40_lowercase_hex(field, bad):
    with pytest.raises(ValueError):
        store.run_row(**_run_kwargs(**{field: bad}))


@pytest.mark.parametrize(
    "overrides",
    [
        {"run_kind": "TEST"},
        {"run_kind": "final"},
        {"protocol_commit": None},
        {"run_kind": "POST_HOC", "protocol_commit": None, "is_current": False},
        {"run_kind": "DEV", "is_current": True},
        {"ci": (5.0, 4.0)},
        {"folds": []},
    ],
    ids=["unknown_kind", "lowercase_kind", "final_without_protocol_commit", "post_hoc_without_protocol_commit",
         "dev_run_current", "ci_low_above_high", "no_folds"],
)  # fmt: skip
def test_run_row_rejects_what_the_table_constraints_reject(overrides):
    with pytest.raises(ValueError):
        store.run_row(**_run_kwargs(**overrides))
