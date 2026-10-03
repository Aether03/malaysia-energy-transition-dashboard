"""Reference forecasts: seasonal naive (the doc 02 §4 baseline), and two secondary references:
naive t - 24 h (protocol #9) and the weekday-aware naive (MLE review H3)."""

from __future__ import annotations

import pandas as pd

from pipeline.forecast.features import complete_hourly

BASELINE_LAG_H = 168
NAIVE_LAG_H = 24


def lagged(demand: pd.Series, lag_h: int) -> pd.Series:
    """The actual at t - `lag_h` hours, for every t of `features.complete_hourly(demand).index`.

    Aligned by timestamp, never by position: with a missing hour in the input, the value for t
    is still the reading taken exactly `lag_h` hours before t, and NaN where that hour is missing
    or before the series starts. Raises ValueError if `lag_h` < 1.
    """
    if lag_h < 1:
        raise ValueError(f"lag_h must be at least 1, got {lag_h}")
    actual = complete_hourly(demand)
    return actual.shift(lag_h, freq="h").reindex(actual.index)


def seasonal_naive(demand: pd.Series) -> pd.Series:
    """`lagged(demand, BASELINE_LAG_H)` named `baseline_mw`: the same hour one week earlier."""
    return lagged(demand, BASELINE_LAG_H).rename("baseline_mw")


def weekday_naive(demand: pd.Series) -> pd.Series:
    """The weekday-aware naive, named `weekday_naive_mw`: the actual at t - 24 h when t falls on
    Tuesday to Friday (yesterday was a weekday too), otherwise at t - 168 h (Saturday, Sunday and
    Monday look back one week). Holidays are not special-cased. Aligned by timestamp like `lagged`.
    """
    day = lagged(demand, NAIVE_LAG_H)
    week = lagged(demand, BASELINE_LAG_H)
    tue_to_fri = (day.index.dayofweek >= 1) & (day.index.dayofweek <= 4)
    return day.where(tue_to_fri, week).rename("weekday_naive_mw")


def naive_24(demand: pd.Series) -> pd.Series:
    """`lagged(demand, NAIVE_LAG_H)` named `naive24_mw`: the same hour one day earlier."""
    return lagged(demand, NAIVE_LAG_H).rename("naive24_mw")
