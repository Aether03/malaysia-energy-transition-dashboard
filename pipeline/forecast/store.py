"""Rows for `dw.forecast_run` and `dw.fact_load_forecast` (doc 05 §2.4, V010 + V013).

The row builders are pure and enforce the same invariants as the table constraints, so a bad
run fails in Python with a clear message before any INSERT. Writing to the database is added
with the `pipeline forecast` command (M3 step 8).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from pipeline.forecast.backtest import Fold
from pipeline.forecast.metrics import Scores

RUN_KINDS: tuple[str, ...] = ("DEV", "FINAL", "POST_HOC")
FACT_COLUMNS: tuple[str, ...] = (
    "model_run_id", "grid_key", "ts_utc", "ts_local", "actual_mw", "forecast_mw",
    "baseline_mw", "is_scored", "date_key", "hour",
)  # fmt: skip


def fact_rows(results: pd.DataFrame, model_run_id: int, grid_key: int, utc_offset_min: int) -> list[tuple]:
    """One tuple per row of a `backtest.run_backtest` result, in `FACT_COLUMNS` order.

    - `ts_local` is the index as a naive `datetime`; `ts_utc` = `ts_local` - `utc_offset_min` minutes.
    - `actual_mw`, `forecast_mw` and `baseline_mw` are `Decimal`s rounded half-up to 0.1 MW;
      NaN becomes None.
    - `is_scored` is int 0/1; `date_key` is yyyymmdd of `ts_local` as int; `hour` is its hour.

    Raises ValueError if any forecast is NaN (the column is NOT NULL), or if a row's
    `is_scored` disagrees with "actual, forecast and baseline all present".
    """
    raise NotImplementedError


def run_row(
    *,
    grid_key: int,
    run_kind: str,
    model_name: str,
    folds: Sequence[Fold],
    scores: Scores,
    ci: tuple[float, float],
    params: Mapping[str, Any],
    metrics: Mapping[str, Any] | None,
    git_commit: str | None,
    protocol_commit: str | None,
    load_run_id: int | None,
    is_current: bool,
) -> dict[str, Any]:
    """A `dw.forecast_run` row as a dict keyed by column name (all columns except the identity
    `model_run_id` and the defaulted `trained_at`).

    - `train_start` = the first fold's `fit_start` date; `train_end` = the day before the last
      fold's test month (so `train_end` > `test_start` for a multi-fold run; V014 relaxes the
      V010 date check to `train_end` < `test_end`); `test_start` / `test_end` = the first fold's
      `test_start` date and the last fold's `test_end` date.
    - The metric columns come from `scores`, and the CI columns from `ci`, as `Decimal`s rounded
      half-up to 3 places; `scored_hours` / `excluded_hours` as int.
    - `params_json` / `metrics_json` are `json.dumps(..., sort_keys=True)`; `metrics_json` is
      None when `metrics` is None.
    - `is_current` is int 0/1.

    Raises ValueError, mirroring the V010/V013 constraints, if: `run_kind` is not in `RUN_KINDS`;
    a non-DEV run has no `protocol_commit`; a DEV run is current; a commit hash is not 40
    lowercase hex characters; the CI's low bound is above its high bound; or `folds` is empty.
    """
    raise NotImplementedError
