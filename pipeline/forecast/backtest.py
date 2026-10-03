"""Rolling-origin backtest (M3 plan protocol guards #1, #3, #7, #10 and #12).

Monthly folds with an expanding window: each fold trains once on everything from `data_start`
up to its test month, then forecasts every hour of that month, day by day, with lag features
that stay >= 24 h. Early stopping uses only the last `es_days` days before the test month.
Hyperparameters are fixed by the protocol and identical for every fold.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Fold:
    name: str  # the test month, 'YYYY-MM'
    fit_start: pd.Timestamp  # first fit hour (inclusive) = data_start, for every fold
    es_start: pd.Timestamp  # fit hours are [fit_start, es_start); early-stopping hours are [es_start, test_start)
    test_start: pd.Timestamp  # 00:00 local on the first day of the test month
    test_end: pd.Timestamp  # 23:00 local on the last day of the test month (inclusive)


def monthly_folds(data_start: pd.Timestamp, first_month: str, last_month: str, es_days: int) -> list[Fold]:
    """One fold per calendar month from `first_month` to `last_month` ('YYYY-MM', both inclusive), in order.

    `es_start` = `test_start` - `es_days` days. Raises ValueError if `last_month` is before
    `first_month`, `es_days` < 1, or any fold's fit window [data_start, es_start) is empty.
    """
    raise NotImplementedError


EARLY_STOPPING_ROUNDS = 100


class Regressor(Protocol):
    def fit(self, X_fit: pd.DataFrame, y_fit: pd.Series, X_es: pd.DataFrame, y_es: pd.Series) -> None: ...

    def predict(self, X: pd.DataFrame) -> np.ndarray: ...


class LgbmRegressor:
    """LightGBM with early stopping on the given early-stopping set, deterministic for a seed.

    `params` are LightGBM training parameters; an optional `early_stopping_rounds` key sets the
    patience (default `EARLY_STOPPING_ROUNDS`) and is not passed to LightGBM. Uses
    `deterministic=True`, the given `seed` and `num_threads`, so the same data, params and seed
    give bit-identical predictions (protocol #10). `best_iteration` is set by `fit`.
    """

    def __init__(self, params: Mapping[str, Any], seed: int, num_threads: int = 1) -> None:
        raise NotImplementedError

    def fit(self, X_fit: pd.DataFrame, y_fit: pd.Series, X_es: pd.DataFrame, y_es: pd.Series) -> None:
        raise NotImplementedError

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError


RESULT_COLUMNS: tuple[str, ...] = ("fold", "actual_mw", "forecast_mw", "baseline_mw", "naive24_mw", "is_scored")


def run_backtest(
    demand: pd.Series,
    holidays: Collection[date],
    folds: list[Fold],
    model_factory: Callable[[], Regressor],
) -> pd.DataFrame:
    """Run every fold and return one row per test hour.

    1. Actuals after the last fold's `test_end` are dropped before anything is built, so later
       data can't influence the run (a development run on 2023 never reads 2024).
    2. Features come from `features.build_features` on the remaining series.
    3. Per fold, a fresh model from `model_factory()` is fitted on the fit hours and early-stopped
       on the early-stopping hours (see `Fold`). Hours with a missing actual are left out of both;
       missing feature values are passed as NaN, never filled. X frames are indexed by `ts_local`
       with columns `features.FEATURE_COLUMNS`; y Series share that index.
    4. Every hour from `test_start` to `test_end` is predicted, gap hours included.

    Returns a DataFrame indexed by `ts_local` (sorted, every hour of every test window) with
    columns `RESULT_COLUMNS`: the fold name, the actual (NaN in a gap), the model forecast, the
    seasonal-naive baseline, the naive t - 24 h value, and `is_scored` (bool: actual, forecast
    and baseline all present).

    Raises ValueError if `folds` is empty, unsorted or overlapping, or if the actuals end before
    the last fold's `test_end` (every test hour must lie inside the series' span).
    """
    raise NotImplementedError
