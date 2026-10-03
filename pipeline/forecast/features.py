"""Forecast features (M3 plan protocol guards #2, #4 and #11).

A forecast for local day D is issued at D 00:00 local time, when actuals up to D-1 23:00 are
known. Every feature for target hour t therefore uses actuals from t - 24 h or earlier: for
D 23:00, t - 24 h is D-1 23:00, the last known hour. Features are built in local time on a
complete hourly index. Missing hours stay NaN and are never filled (no imputation, Q1);
LightGBM takes the NaN natively.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import date

import pandas as pd

MIN_LAG_H = 24
LAGS_H: tuple[int, ...] = (24, 48, 168, 336)
ROLLING_WINDOW_H = 24
ROLLING_MIN_PERIODS = 18
CALENDAR_COLUMNS: tuple[str, ...] = ("hour", "iso_weekday", "month", "is_weekend", "is_holiday", "is_day_off")
FEATURE_COLUMNS: tuple[str, ...] = CALENDAR_COLUMNS + tuple(f"lag_{h}" for h in LAGS_H) + ("roll_mean_24",)


def complete_hourly(demand: pd.Series) -> pd.Series:
    """Put `demand` on every hour from its first to its last timestamp.

    Input: a float Series of MW indexed by naive local timestamps on the hour, in any order.
    Output: sorted, index named `ts_local` with freq 'h', Series named `demand_mw`; hours the
    input lacks are NaN. Values are never filled or interpolated.

    Raises ValueError on an empty series, a duplicate timestamp, a timezone-aware index, or a
    timestamp that is not on the hour.
    """
    raise NotImplementedError


def build_features(demand: pd.Series, holidays: Collection[date]) -> pd.DataFrame:
    """One row per hour of `complete_hourly(demand).index`, columns exactly `FEATURE_COLUMNS` in order.

    - `hour` 0-23, `iso_weekday` 1-7 (Monday = 1), `month` 1-12, all of the local timestamp.
    - `is_weekend` 1 on Saturday and Sunday; `is_holiday` 1 when the local date is in `holidays`;
      `is_day_off` 1 when either is 1. These four are integer 0/1.
    - `lag_<k>` is the actual at t - k hours, aligned by timestamp, so a missing hour never
      shifts later values; NaN when that hour is missing or before the series starts.
    - `roll_mean_24` is the mean of the actuals at t - 47 h ... t - 24 h (the 24 hours ending at
      t - 24 h), over the hours present; NaN when fewer than `ROLLING_MIN_PERIODS` are present.

    No feature for hour t may depend on an actual later than t - `MIN_LAG_H` hours.
    """
    raise NotImplementedError
