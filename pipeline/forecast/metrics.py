"""Forecast scoring (M3 plan protocol guards #5, #6, #7 and #8).

The model and the baseline are always scored on the same hours: those where the actual, the
model forecast and the baseline all exist. Hours left out are counted, never silently dropped.
All Series arguments share one index of naive local timestamps.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

import numpy as np
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


def _same_index(*series: pd.Series) -> None:
    first = series[0].index
    if any(not s.index.equals(first) for s in series[1:]):
        raise ValueError("the series must share one index")


def _clean_pair(actual: pd.Series, forecast: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    _same_index(actual, forecast)
    if actual.empty:
        raise ValueError("no values to score")
    if actual.isna().any() or forecast.isna().any():
        raise ValueError("NaN in the scored values: apply scored_mask first")
    return actual.to_numpy(dtype=float), forecast.to_numpy(dtype=float)


def scored_mask(actual: pd.Series, model: pd.Series, baseline: pd.Series) -> pd.Series:
    """Boolean Series on the shared index: True where all three values are present.

    Raises ValueError if the three indexes differ.
    """
    _same_index(actual, model, baseline)
    return actual.notna() & model.notna() & baseline.notna()


def mape(actual: pd.Series, forecast: pd.Series) -> float:
    """Mean absolute percentage error in percent: mean(|actual - forecast| / actual) * 100.

    Raises ValueError if the inputs are empty, have different indexes, contain NaN (callers
    apply `scored_mask` first), or any actual is <= 0.
    """
    a, f = _clean_pair(actual, forecast)
    if (a <= 0).any():
        raise ValueError("MAPE needs every actual above 0")
    return float(np.mean(np.abs(a - f) / a) * 100)


def mae(actual: pd.Series, forecast: pd.Series) -> float:
    """Mean absolute error in MW. Same input rules as `mape` (except that actuals may be any value)."""
    a, f = _clean_pair(actual, forecast)
    return float(np.mean(np.abs(a - f)))


def improvement_pct(mape_model: float, mape_baseline: float) -> float:
    """100 * (1 - mape_model / mape_baseline). Raises ValueError if mape_baseline <= 0."""
    if mape_baseline <= 0:
        raise ValueError(f"the baseline MAPE must be above 0, got {mape_baseline}")
    return 100 * (1 - mape_model / mape_baseline)


def score(actual: pd.Series, model: pd.Series, baseline: pd.Series) -> Scores:
    """Every metric on the hours of `scored_mask`; `excluded_hours` = len(index) - scored hours.

    Raises ValueError if no hour is scored.
    """
    mask = scored_mask(actual, model, baseline)
    scored = int(mask.sum())
    if scored == 0:
        raise ValueError("no hour has an actual, a model forecast and a baseline")
    a, m, b = actual[mask], model[mask], baseline[mask]
    mape_model, mape_baseline = mape(a, m), mape(a, b)
    return Scores(
        mape_model=mape_model,
        mape_baseline=mape_baseline,
        mae_model=mae(a, m),
        mae_baseline=mae(a, b),
        improvement_pct=improvement_pct(mape_model, mape_baseline),
        scored_hours=scored,
        excluded_hours=len(mask) - scored,
    )


def score_groups(
    actual: pd.Series, model: pd.Series, baseline: pd.Series, keys: pd.Series
) -> dict[Hashable, Scores]:
    """`score` per value of `keys` (same index; for example the month, or a holiday flag).

    Each group is scored on its own scored hours, and its `excluded_hours` counts only that
    group's hours. A group with no scored hour is left out of the result. Keys are sorted.
    """
    _same_index(actual, model, baseline, keys)
    mask = scored_mask(actual, model, baseline)
    groups: dict[Hashable, Scores] = {}
    for key in sorted(pd.unique(keys)):
        in_group = (keys == key).to_numpy()
        if mask[in_group].any():
            label = key.item() if isinstance(key, np.generic) else key
            groups[label] = score(actual[in_group], model[in_group], baseline[in_group])
    return groups


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
    if n_boot < 1:
        raise ValueError(f"n_boot must be at least 1, got {n_boot}")
    if not 0 < level < 1:
        raise ValueError(f"level must be strictly between 0 and 1, got {level}")
    mask = scored_mask(actual, model, baseline)
    if not mask.any():
        raise ValueError("no hour has an actual, a model forecast and a baseline")
    a = actual[mask].to_numpy(dtype=float)
    if (a <= 0).any():
        raise ValueError("MAPE needs every actual above 0")
    ape_model = np.abs(a - model[mask].to_numpy(dtype=float)) / a
    ape_baseline = np.abs(a - baseline[mask].to_numpy(dtype=float)) / a
    # Per-day sums, so a replicate's pooled MAPE is (sum of its days' APE) / (its hours).
    day_codes, days = pd.factorize(actual.index[mask].normalize())
    n_days = len(days)
    sum_model = np.bincount(day_codes, weights=ape_model, minlength=n_days)
    sum_baseline = np.bincount(day_codes, weights=ape_baseline, minlength=n_days)
    hours = np.bincount(day_codes, minlength=n_days)
    draws = np.random.default_rng(seed).integers(0, n_days, size=(n_boot, n_days))
    pooled_hours = hours[draws].sum(axis=1)
    mape_model = sum_model[draws].sum(axis=1) / pooled_hours * 100
    mape_baseline = sum_baseline[draws].sum(axis=1) / pooled_hours * 100
    improvements = np.array([improvement_pct(m, b) for m, b in zip(mape_model, mape_baseline, strict=True)])
    low, high = np.quantile(improvements, [(1 - level) / 2, (1 + level) / 2])
    return float(low), float(high)


def beats_baseline(ci_low: float) -> bool:
    """The committed decision rule: the model beats the baseline only if the CI's lower bound is above 0."""
    return bool(ci_low > 0)
