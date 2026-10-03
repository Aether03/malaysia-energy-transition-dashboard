"""Rows for `dw.forecast_run` and `dw.fact_load_forecast` (doc 05 §2.4, V010 + V013).

The row builders are pure and enforce the same invariants as the table constraints, so a bad
run fails in Python with a clear message before any INSERT. Writing to the database is added
with the `pipeline forecast` command (M3 step 8).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pandas as pd

from pipeline.forecast.backtest import RESULT_COLUMNS, Fold
from pipeline.forecast.metrics import Scores

_HEX40 = re.compile(r"[0-9a-f]{40}")
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
    rows = []
    for ts, _fold, actual, forecast, base, _naive, is_scored in results[list(RESULT_COLUMNS)].itertuples(name=None):
        if _missing(forecast):
            raise ValueError(f"{ts}: the forecast is missing (dw.fact_load_forecast.forecast_mw is NOT NULL)")
        expected = not (_missing(actual) or _missing(base))
        if bool(is_scored) != expected:
            raise ValueError(f"{ts}: is_scored={is_scored} but actual/forecast/baseline presence says {expected}")
        local = pd.Timestamp(ts).to_pydatetime()
        rows.append(
            (
                int(model_run_id),
                int(grid_key),
                local - timedelta(minutes=utc_offset_min),
                local,
                _round(actual, "0.1"),
                _round(forecast, "0.1"),
                _round(base, "0.1"),
                int(expected),
                local.year * 10000 + local.month * 100 + local.day,
                local.hour,
            )
        )
    return rows


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
    if run_kind not in RUN_KINDS:
        raise ValueError(f"run_kind must be one of {RUN_KINDS}, got {run_kind!r}")
    if run_kind != "DEV" and protocol_commit is None:
        raise ValueError(f"a {run_kind} run needs the protocol commit")
    if run_kind == "DEV" and is_current:
        raise ValueError("a DEV run is never the current run")
    for name, value in (("git_commit", git_commit), ("protocol_commit", protocol_commit)):
        if value is not None and not _HEX40.fullmatch(value):
            raise ValueError(f"{name} must be 40 lowercase hex characters, got {value!r}")
    ci_low, ci_high = ci
    if ci_low > ci_high:
        raise ValueError(f"CI low {ci_low} is above CI high {ci_high}")
    if not folds:
        raise ValueError("no folds")
    return {
        "grid_key": grid_key,
        "load_run_id": load_run_id,
        "run_kind": run_kind,
        "model_name": model_name,
        "train_start": folds[0].fit_start.date(),
        "train_end": (folds[-1].test_start - pd.Timedelta(days=1)).date(),
        "test_start": folds[0].test_start.date(),
        "test_end": folds[-1].test_end.date(),
        "mape_model": _round(scores.mape_model, "0.001"),
        "mape_baseline": _round(scores.mape_baseline, "0.001"),
        "mae_model": _round(scores.mae_model, "0.001"),
        "mae_baseline": _round(scores.mae_baseline, "0.001"),
        "improvement_pct": _round(scores.improvement_pct, "0.001"),
        "improvement_ci_low": _round(ci_low, "0.001"),
        "improvement_ci_high": _round(ci_high, "0.001"),
        "scored_hours": int(scores.scored_hours),
        "excluded_hours": int(scores.excluded_hours),
        "params_json": json.dumps(params, sort_keys=True),
        "metrics_json": None if metrics is None else json.dumps(metrics, sort_keys=True),
        "git_commit": git_commit,
        "protocol_commit": protocol_commit,
        "is_current": int(bool(is_current)),
    }


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _round(value: Any, places: str) -> Decimal | None:
    """Half-up rounding of the float's shortest decimal form (str(), not its binary expansion)."""
    if _missing(value):
        return None
    return Decimal(str(float(value))).quantize(Decimal(places), rounding=ROUND_HALF_UP)
