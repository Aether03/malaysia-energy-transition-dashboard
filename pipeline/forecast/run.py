"""`pipeline forecast`: the locked backtest per grid, stored in SQL Server (M3 plan Q2 and Q6).

Three modes:
- DEV (`--dev`): the protocol's development months (2023 only). Settings come from the
  working-tree protocol, and demand is read from SQL only up to the last development hour, so
  2024 is never loaded. Stored as a DEV run, which is never current.
- FINAL (`--final`): the single 2024 backtest per grid. Refused unless the protocol and the
  forecast code are committed and clean (`protocol.committed_protocol`), and refused for a grid
  that already has a FINAL run in the database or in the committed record. Stores the run as
  current and writes the record, `docs/forecast_final.json`.
- Replay (no flag; also the FORECAST step of `pipeline run`): for every grid in the record,
  re-run the FINAL backtest from the settings stored with it and require identical metrics. If
  the database has no FINAL run for that grid (an empty-DB rebuild), the replayed run is stored
  with the record's commits. A replay repeats the same deterministic computation, so it is not
  a second look at the test (protocol #1, #10).
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import config, db
from pipeline.forecast import metrics, store
from pipeline.forecast.backtest import Fold, LgbmRegressor, monthly_folds, run_backtest
from pipeline.forecast.protocol import (
    Protocol,
    committed_protocol,
    load_protocol,
    protocol_from_dict,
)

log = logging.getLogger(__name__)

RECORD_PATH = config.ROOT / "docs" / "forecast_final.json"
MODEL_NAME = "lightgbm"
# dim_country.iso3 -> ref.public_holiday.country_code
HOLIDAY_COUNTRY = {"THA": "TH", "SGP": "SG", "MYS": "MY"}
# The run-level numbers a replay must reproduce exactly (as stored, 3 decimals).
COMPARED = (
    "mape_model", "mape_baseline", "mae_model", "mae_baseline", "improvement_pct",
    "improvement_ci_low", "improvement_ci_high", "scored_hours", "excluded_hours",
)  # fmt: skip


class ForecastError(RuntimeError):
    """A forecast run was refused or could not be reproduced."""


@dataclass(frozen=True)
class Grid:
    grid_key: int
    grid_code: str
    utc_offset_min: int
    data_source_code: str
    holiday_country: str


@dataclass
class Outcome:
    folds: list[Fold]
    results: pd.DataFrame
    scores: metrics.Scores
    ci: tuple[float, float]
    details: dict[str, Any]  # forecast_run.metrics_json


# --- data ----------------------------------------------------------------------------------


def forecast_grids(conn) -> list[str]:
    """Published grids that have hourly demand, in code order."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT g.grid_code FROM dw.dim_grid AS g WHERE g.is_published = 1 "
        "AND EXISTS (SELECT 1 FROM dw.fact_grid_hourly AS f WHERE f.grid_key = g.grid_key) ORDER BY g.grid_code"
    )
    return [row[0] for row in cursor.fetchall()]


def load_grid(conn, grid_code: str) -> Grid:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT g.grid_key, g.utc_offset_min, g.data_source_code, c.iso3 FROM dw.dim_grid AS g "
        "JOIN dw.dim_country AS c ON c.country_key = g.country_key WHERE g.grid_code = ?",
        (grid_code,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ForecastError(f"unknown grid {grid_code}")
    grid_key, offset, source, iso3 = row
    if iso3 not in HOLIDAY_COUNTRY:
        raise ForecastError(f"grid {grid_code}: no holiday calendar for country {iso3}")
    return Grid(int(grid_key), grid_code, int(offset), source, HOLIDAY_COUNTRY[iso3])


def load_demand(conn, grid: Grid, until: pd.Timestamp) -> pd.Series:
    """Hourly demand up to `until` (inclusive). Later hours are never read (protocol #1)."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ts_local, CAST(demand_mw AS FLOAT) FROM dw.fact_grid_hourly "
        "WHERE grid_key = ? AND ts_local <= ? ORDER BY ts_local",
        (grid.grid_key, until.to_pydatetime()),
    )
    rows = cursor.fetchall()
    if not rows:
        raise ForecastError(f"grid {grid.grid_code}: no hourly demand up to {until}")
    return pd.Series(
        [float(r[1]) for r in rows], index=pd.DatetimeIndex([r[0] for r in rows], name="ts_local"), name="demand_mw"
    )


def load_holidays(conn, grid: Grid) -> set[date]:
    cursor = conn.cursor()
    cursor.execute("SELECT holiday_date FROM ref.public_holiday WHERE country_code = ?", (grid.holiday_country,))
    return {r[0] for r in cursor.fetchall()}


# --- the backtest --------------------------------------------------------------------------


def backtest_grid(demand: pd.Series, holidays: set[date], protocol: Protocol, kind: str) -> Outcome:
    """Run the protocol's DEV or FINAL folds and score them."""
    first, last = (
        (protocol.dev_first_month, protocol.dev_last_month)
        if kind == "DEV"
        else (protocol.final_first_month, protocol.final_last_month)
    )
    folds = monthly_folds(protocol.data_start, first, last, protocol.es_days)
    models: list[LgbmRegressor] = []

    def factory() -> LgbmRegressor:
        model = LgbmRegressor(protocol.lightgbm, protocol.seed, protocol.num_threads)
        models.append(model)
        return model

    results = run_backtest(demand, holidays, folds, factory)
    actual, forecast, base = results["actual_mw"], results["forecast_mw"], results["baseline_mw"]
    scores = metrics.score(actual, forecast, base)
    ci = metrics.day_block_bootstrap_ci(actual, forecast, base, n_boot=protocol.n_boot, seed=protocol.seed,
                                        level=protocol.level)  # fmt: skip

    holiday_days = pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in holidays))
    on_holiday = pd.Series(results.index.normalize().isin(holiday_days), index=results.index)
    day_type = on_holiday.map({True: "holiday", False: "other"})
    # protocol #9: naive t - 24 h on the scored hours where it also exists
    naive_hours = results["is_scored"] & results["naive24_mw"].notna()
    details = {
        "beats_baseline": metrics.beats_baseline(ci[0]),
        "ci_level": protocol.level,
        "n_boot": protocol.n_boot,
        "per_month": {k: _scores_dict(v) for k, v in metrics.score_groups(actual, forecast, base, results["fold"]).items()},
        "by_day_type": {k: _scores_dict(v) for k, v in metrics.score_groups(actual, forecast, base, day_type).items()},
        "naive24": {
            "hours": int(naive_hours.sum()),
            "mape": round(metrics.mape(actual[naive_hours], results.loc[naive_hours, "naive24_mw"]), 4),
            "mae": round(metrics.mae(actual[naive_hours], results.loc[naive_hours, "naive24_mw"]), 4),
            "mape_model_same_hours": round(metrics.mape(actual[naive_hours], forecast[naive_hours]), 4),
        },
        "best_iteration": {f.name: m.best_iteration for f, m in zip(folds, models, strict=True)},
    }
    return Outcome(folds, results, scores, ci, details)


def _scores_dict(s: metrics.Scores) -> dict[str, Any]:
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(s).items()}


# --- storing -------------------------------------------------------------------------------


def save_run(conn, grid: Grid, row: dict[str, Any], results: pd.DataFrame) -> int:
    """Insert the run and its hourly rows in one transaction; returns model_run_id."""
    cursor = conn.cursor()
    try:
        if row["is_current"]:
            cursor.execute(
                "UPDATE dw.forecast_run SET is_current = 0 WHERE grid_key = ? AND is_current = 1", (grid.grid_key,)
            )
        columns = list(row)
        cursor.execute(
            f"INSERT INTO dw.forecast_run ({', '.join(columns)}) OUTPUT inserted.model_run_id "
            f"VALUES ({', '.join('?' for _ in columns)})",
            tuple(row[c] for c in columns),
        )
        model_run_id = int(cursor.fetchone()[0])
        facts = store.fact_rows(results, model_run_id, grid.grid_key, grid.utc_offset_min)
        cursor.executemany(
            f"INSERT INTO dw.fact_load_forecast ({', '.join(store.FACT_COLUMNS)}) "
            f"VALUES ({', '.join('?' for _ in store.FACT_COLUMNS)})",
            facts,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return model_run_id


def _final_run(conn, grid: Grid) -> dict[str, Any] | None:
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT model_run_id, {', '.join(COMPARED)} FROM dw.forecast_run WHERE grid_key = ? AND run_kind = 'FINAL'",
        (grid.grid_key,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {"model_run_id": int(row[0]), **{c: _text(v) for c, v in zip(COMPARED, row[1:], strict=True)}}


def _text(value: Any) -> str:
    return str(value)


def read_record(path: Path = RECORD_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_record(record: dict[str, Any], path: Path = RECORD_PATH) -> None:
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _head_commit() -> str | None:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=config.ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return done.stdout.strip() or None


# --- the three modes -----------------------------------------------------------------------


def _month_end(month: str) -> pd.Timestamp:
    return pd.Period(month, freq="M").end_time.floor("h")


def run_dev(grid_code: str, load_run_id: int | None) -> Outcome:
    protocol = load_protocol()
    conn = db.connect()
    try:
        grid = load_grid(conn, grid_code)
        demand = load_demand(conn, grid, _month_end(protocol.dev_last_month))
        outcome = backtest_grid(demand, load_holidays(conn, grid), protocol, "DEV")
        row = store.run_row(
            grid_key=grid.grid_key, run_kind="DEV", model_name=MODEL_NAME, folds=outcome.folds,
            scores=outcome.scores, ci=outcome.ci, params=protocol.raw, metrics=outcome.details,
            git_commit=_head_commit(), protocol_commit=None, load_run_id=load_run_id, is_current=False,
        )  # fmt: skip
        model_run_id = save_run(conn, grid, row, outcome.results)
    finally:
        conn.close()
    log.info("DEV run %d for %s: %s", model_run_id, grid_code, _summary(row))
    return outcome


def run_final(grid_code: str, load_run_id: int | None) -> Outcome:
    protocol_commit, head_commit = committed_protocol()
    protocol = load_protocol()
    record = read_record()
    if grid_code in record:
        raise ForecastError(f"{grid_code} already has a recorded FINAL run ({RECORD_PATH.name}); runs are once only")
    conn = db.connect()
    try:
        grid = load_grid(conn, grid_code)
        if _final_run(conn, grid) is not None:
            raise ForecastError(f"{grid_code} already has a FINAL run in dw.forecast_run; runs are once only")
        demand = load_demand(conn, grid, _month_end(protocol.final_last_month))
        outcome = backtest_grid(demand, load_holidays(conn, grid), protocol, "FINAL")
        row = store.run_row(
            grid_key=grid.grid_key, run_kind="FINAL", model_name=MODEL_NAME, folds=outcome.folds,
            scores=outcome.scores, ci=outcome.ci, params=protocol.raw, metrics=outcome.details,
            git_commit=head_commit, protocol_commit=protocol_commit, load_run_id=load_run_id, is_current=True,
        )  # fmt: skip
        model_run_id = save_run(conn, grid, row, outcome.results)
    finally:
        conn.close()
    record[grid_code] = {
        "protocol_commit": protocol_commit,
        "git_commit": head_commit,
        "protocol": protocol.raw,
        "metrics": {c: _text(row[c]) for c in COMPARED},
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _write_record(record)
    log.info("FINAL run %d for %s: %s", model_run_id, grid_code, _summary(row))
    return outcome


def replay(grid_code: str, entry: dict[str, Any], load_run_id: int | None) -> str:
    """Re-run a recorded FINAL backtest; store it if the database lacks it. Returns a status message."""
    protocol = protocol_from_dict(entry["protocol"])
    conn = db.connect()
    try:
        grid = load_grid(conn, grid_code)
        demand = load_demand(conn, grid, _month_end(protocol.final_last_month))
        outcome = backtest_grid(demand, load_holidays(conn, grid), protocol, "FINAL")
        row = store.run_row(
            grid_key=grid.grid_key, run_kind="FINAL", model_name=MODEL_NAME, folds=outcome.folds,
            scores=outcome.scores, ci=outcome.ci, params=protocol.raw, metrics=outcome.details,
            git_commit=entry["git_commit"], protocol_commit=entry["protocol_commit"],
            load_run_id=load_run_id, is_current=True,
        )  # fmt: skip
        replayed = {c: _text(row[c]) for c in COMPARED}
        if replayed != entry["metrics"]:
            diff = {c: (entry["metrics"].get(c), replayed[c]) for c in COMPARED if entry["metrics"].get(c) != replayed[c]}
            raise ForecastError(f"{grid_code}: the replay does not reproduce the recorded FINAL run: {diff}")
        stored = _final_run(conn, grid)
        if stored is None:
            model_run_id = save_run(conn, grid, row, outcome.results)
            return f"replayed and stored as FINAL run {model_run_id} (identical to the record)"
        stored_metrics = {c: stored[c] for c in COMPARED}
        if stored_metrics != replayed:
            raise ForecastError(f"{grid_code}: FINAL run {stored['model_run_id']} differs from the record")
        return f"replay identical to FINAL run {stored['model_run_id']}"
    finally:
        conn.close()


def _summary(row: dict[str, Any]) -> str:
    return (
        f"MAPE model {row['mape_model']}% vs baseline {row['mape_baseline']}%, improvement "
        f"{row['improvement_pct']}% (CI {row['improvement_ci_low']} to {row['improvement_ci_high']}), "
        f"{row['scored_hours']} scored / {row['excluded_hours']} excluded hours"
    )
