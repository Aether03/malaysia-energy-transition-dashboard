"""Reference forecasts: seasonal naive (the doc 02 §4 baseline) and naive t - 24 h (protocol #9)."""

from __future__ import annotations

import pandas as pd

BASELINE_LAG_H = 168
NAIVE_LAG_H = 24


def lagged(demand: pd.Series, lag_h: int) -> pd.Series:
    """The actual at t - `lag_h` hours, for every t of `features.complete_hourly(demand).index`.

    Aligned by timestamp, never by position: with a missing hour in the input, the value for t
    is still the reading taken exactly `lag_h` hours before t, and NaN where that hour is missing
    or before the series starts. Raises ValueError if `lag_h` < 1.
    """
    raise NotImplementedError


def seasonal_naive(demand: pd.Series) -> pd.Series:
    """`lagged(demand, BASELINE_LAG_H)` named `baseline_mw`: the same hour one week earlier."""
    raise NotImplementedError


def naive_24(demand: pd.Series) -> pd.Series:
    """`lagged(demand, NAIVE_LAG_H)` named `naive24_mw`: the same hour one day earlier."""
    raise NotImplementedError
