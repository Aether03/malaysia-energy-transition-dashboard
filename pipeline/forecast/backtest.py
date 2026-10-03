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
from itertools import pairwise
from typing import Any, Protocol

import lightgbm as lgb
import numpy as np
import pandas as pd

from pipeline.forecast.baseline import naive_24, seasonal_naive
from pipeline.forecast.features import build_features, complete_hourly


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
    if es_days < 1:
        raise ValueError(f"es_days must be at least 1, got {es_days}")
    first, last = pd.Period(first_month, freq="M"), pd.Period(last_month, freq="M")
    if last < first:
        raise ValueError(f"last month {last_month} is before first month {first_month}")
    start = pd.Timestamp(data_start)
    folds = []
    for month in pd.period_range(first, last, freq="M"):
        test_start = month.start_time
        es_start = test_start - pd.Timedelta(days=es_days)
        if not start < es_start:
            raise ValueError(f"fold {month}: no fit hours between {start} and {es_start}")
        folds.append(Fold(str(month), start, es_start, test_start, month.end_time.floor("h")))
    return folds


EARLY_STOPPING_ROUNDS = 100
DEFAULT_BOOST_ROUNDS = 2000
_ROUND_ALIASES = ("num_iterations", "num_iteration", "n_iter", "num_tree", "num_trees", "num_round",
                  "num_rounds", "nrounds", "num_boost_round", "n_estimators", "max_iter")  # fmt: skip


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
        training = dict(params)
        self.early_stopping_rounds = int(training.pop("early_stopping_rounds", EARLY_STOPPING_ROUNDS))
        self.num_boost_round = DEFAULT_BOOST_ROUNDS
        for alias in _ROUND_ALIASES:
            if alias in training:
                self.num_boost_round = int(training.pop(alias))
        if not any(key in training for key in ("verbose", "verbosity")):
            training["verbosity"] = -1
        # Determinism (protocol #10): fixed seed and thread count, deterministic histogram building.
        training.update(seed=seed, num_threads=num_threads, deterministic=True, force_row_wise=True)
        self.params = training
        self.booster: lgb.Booster | None = None
        self.best_iteration: int | None = None

    def fit(self, X_fit: pd.DataFrame, y_fit: pd.Series, X_es: pd.DataFrame, y_es: pd.Series) -> None:
        fit_set = lgb.Dataset(X_fit, label=y_fit, free_raw_data=False)
        es_set = lgb.Dataset(X_es, label=y_es, reference=fit_set, free_raw_data=False)
        self.booster = lgb.train(
            self.params,
            fit_set,
            num_boost_round=self.num_boost_round,
            valid_sets=[es_set],
            callbacks=[lgb.early_stopping(self.early_stopping_rounds, verbose=False)],
        )
        self.best_iteration = self.booster.best_iteration or self.num_boost_round

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.booster is None:
            raise RuntimeError("predict called before fit")
        return self.booster.predict(X, num_iteration=self.best_iteration)


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
    if not folds:
        raise ValueError("no folds")
    for fold in folds:
        if not fold.fit_start < fold.es_start < fold.test_start <= fold.test_end:
            raise ValueError(f"fold {fold.name}: windows out of order")
    for earlier, later in pairwise(folds):
        if later.test_start <= earlier.test_end:
            raise ValueError(f"folds {earlier.name} and {later.name} are unsorted or overlap")

    actual = complete_hourly(demand)
    last_end = folds[-1].test_end
    if actual.index[-1] < last_end:
        raise ValueError(f"the actuals end at {actual.index[-1]}, before the last test hour {last_end}")
    actual = actual.loc[:last_end]
    features = build_features(actual, holidays)
    reference = pd.concat([seasonal_naive(actual), naive_24(actual)], axis=1)
    index = actual.index
    present = actual.notna().to_numpy()

    parts = []
    for fold in folds:
        fit = present & (index >= fold.fit_start) & (index < fold.es_start)
        es = present & (index >= fold.es_start) & (index < fold.test_start)
        test = (index >= fold.test_start) & (index <= fold.test_end)
        model = model_factory()
        model.fit(features[fit], actual[fit], features[es], actual[es])
        # Every feature is >= 24 h old at its hour, so predicting the whole month at once gives
        # the same values as issuing each day's forecast at its own local midnight.
        part = pd.DataFrame(
            {
                "fold": fold.name,
                "actual_mw": actual[test],
                "forecast_mw": np.asarray(model.predict(features[test]), dtype=float),
                "baseline_mw": reference.loc[test, "baseline_mw"],
                "naive24_mw": reference.loc[test, "naive24_mw"],
            },
            index=index[test],
        )
        parts.append(part)
    result = pd.concat(parts)
    result["is_scored"] = (
        result["actual_mw"].notna() & result["forecast_mw"].notna() & result["baseline_mw"].notna()
    )
    return result[list(RESULT_COLUMNS)]
