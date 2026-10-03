"""Forecast scoring (M3 plan protocol guards #5, #6, #7 and #8).

The model and the baseline are always scored on the same hours: those where the actual, the
model forecast and the baseline all exist. Hours left out are counted, never silently dropped.
All Series arguments share one index of naive local timestamps.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Scores:
    mape_model: float  # percent
    mape_baseline: float  # percent
    mae_model: float  # MW
    mae_baseline: float  # MW
    improvement_pct: float  # 100 * (1 - mape_model / mape_baseline)
    scored_hours: int
    excluded_hours: int  # hours of the index that are not scored


def scored_mask(actual: pd.Series, model: pd.Series, baseline: pd.Series) -> pd.Series:
    """Boolean Series on the shared index: True where all three values are present.

    Raises ValueError if the three indexes differ.
    """
    raise NotImplementedError


def mape(actual: pd.Series, forecast: pd.Series) -> float:
    """Mean absolute percentage error in percent: mean(|actual - forecast| / actual) * 100.

    Raises ValueError if the inputs are empty, have different indexes, contain NaN (callers
    apply `scored_mask` first), or any actual is <= 0.
    """
    raise NotImplementedError


def mae(actual: pd.Series, forecast: pd.Series) -> float:
    """Mean absolute error in MW. Same input rules as `mape` (except that actuals may be any value)."""
    raise NotImplementedError


def improvement_pct(mape_model: float, mape_baseline: float) -> float:
    """100 * (1 - mape_model / mape_baseline). Raises ValueError if mape_baseline <= 0."""
    raise NotImplementedError


def score(actual: pd.Series, model: pd.Series, baseline: pd.Series) -> Scores:
    """Every metric on the hours of `scored_mask`; `excluded_hours` = len(index) - scored hours.

    Raises ValueError if no hour is scored.
    """
    raise NotImplementedError


def score_groups(
    actual: pd.Series, model: pd.Series, baseline: pd.Series, keys: pd.Series
) -> dict[Hashable, Scores]:
    """`score` per value of `keys` (same index; for example the month, or a holiday flag).

    Each group is scored on its own scored hours, and its `excluded_hours` counts only that
    group's hours. A group with no scored hour is left out of the result. Keys are sorted.
    """
    raise NotImplementedError


def day_block_bootstrap_ci(
    actual: pd.Series,
    model: pd.Series,
    baseline: pd.Series,
    *,
    n_boot: int,
    seed: int,
    level: float = 0.95,
) -> tuple[float, float]:
    """Percentile CI of `improvement_pct`, resampling whole local days (protocol #8).

    Only scored hours are used. The blocks are the local calendar dates of the index. Each of
    the `n_boot` replicates draws as many dates as there are, with replacement, from
    `numpy.random.default_rng(seed)`, pools all scored hours of the drawn dates, and computes
    `improvement_pct` from the pooled MAPEs. Returns the (1 - level) / 2 and (1 + level) / 2
    quantiles (numpy's default linear method). The same inputs and seed give the same CI.

    Raises ValueError if no hour is scored, `n_boot` < 1, or `level` is not strictly between 0 and 1.
    A replicate whose pooled baseline MAPE is 0 raises (from `improvement_pct`) rather than being skipped.
    """
    raise NotImplementedError


def beats_baseline(ci_low: float) -> bool:
    """The committed decision rule: the model beats the baseline only if the CI's lower bound is above 0."""
    raise NotImplementedError
