"""`pipeline forecast`: the locked backtest per grid, stored in SQL Server (M3 plan Q2 and Q6).

Three modes:
- DEV (`--dev`): the protocol's development months, never later than `DEV_LIMIT` (2023). Settings
  come from the working-tree protocol, and demand is read from SQL only up to the last
  development hour, so 2024 is never loaded. Stored as a DEV run, which is never current.
- FINAL (`--final --grid X`): the single 2024 backtest of one grid. Refused unless every guarded
  file is committed and clean (`protocol.committed_protocol`, which covers the record too),
  refused for a grid that already has a FINAL run in the database or the record, and refused if
  the settings or any guarded file differ from an earlier grid's recorded run. The record
  entry, `docs/forecast_final.json`, is written BEFORE the database commit; commit the record
  before running the next grid (the gate enforces it).
- Replay (no flag; also the FORECAST step of `pipeline run`): for every grid in the record, check
  the record's settings against the protocol committed at its `protocol_commit`, check the
  input fingerprint (demand, holidays, library versions), re-run the FINAL backtest and require
  an identical forecast and metrics. If the database lacks that FINAL run (an empty-DB rebuild,
  or a crash between the record and the commit), the replayed run is stored with the record's
  commits. A replay repeats the same deterministic computation on the same inputs, so it is not
  a second look at the test (protocol #1, #10). A mismatch is an environment failure, and its
  message names the fields that differ, never the new values.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import config, db
from pipeline.forecast import metrics, store
from pipeline.forecast.backtest import Fold, LgbmRegressor, monthly_folds, run_backtest
from pipeline.forecast.protocol import (
    RECORD_REL,
    Protocol,
    changed_since,
    committed_protocol,
    load_protocol,
    protocol_at_commit,
    protocol_from_dict,
)

log = logging.getLogger(__name__)

RECORD_PATH = config.ROOT / RECORD_REL
MODEL_NAME = "lightgbm"
# A DEV run may never reach the test year, whatever the working-tree protocol says (MLE review M1).
DEV_LIMIT = pd.Timestamp("2023-12-31 23:00")
# Pre-declared sanity bound: a run that can't score at least 98% of its test hours stops.
MAX_EXCLUDED_SHARE = 0.02
# dim_country.iso3 -> ref.public_holiday.country_code
HOLIDAY_COUNTRY = {"THA": "TH", "SGP": "SG", "MYS": "MY"}
# The run-level numbers a replay must reproduce exactly (as stored, 3 decimals).
COMPARED = (
    "mape_model", "mape_baseline", "mae_model", "mae_baseline", "improvement_pct",
    "improvement_ci_low", "improvement_ci_high", "scored_hours", "excluded_hours",
)  # fmt: skip
VERSIONED_PACKAGES = ("lightgbm", "numpy", "pandas", "holidays")


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
    demand = pd.Series(
        [float(r[1]) for r in rows], index=pd.DatetimeIndex([r[0] for r in rows], name="ts_local"), name="demand_mw"
    )
    if demand.index.max() > until:  # belt and braces: the query must never return a later hour
        raise ForecastError(f"grid {grid.grid_code}: demand after {until} was returned")
    return demand


def load_holidays(conn, grid: Grid) -> set[date]:
    cursor = conn.cursor()
    cursor.execute("SELECT holiday_date FROM ref.public_holiday WHERE country_code = ?", (grid.holiday_country,))
    return {r[0] for r in cursor.fetchall()}


def input_fingerprint(demand: pd.Series, holidays: set[date]) -> dict[str, Any]:
    """SHA-256 of the demand series and holiday set the run used, plus library versions (MLE review H2)."""
    demand_lines = "\n".join(f"{ts.isoformat()} {value!r}" for ts, value in demand.sort_index().items())
    holiday_lines = "\n".join(d.isoformat() for d in sorted(holidays))
    return {
        "demand_sha256": hashlib.sha256(demand_lines.encode()).hexdigest(),
        "demand_hours": len(demand),
        "holidays_sha256": hashlib.sha256(holiday_lines.encode()).hexdigest(),
        # Python major.minor only: a patch upgrade must not break every later replay (item 2).
        "versions": {
            "python": ".".join(platform.python_version_tuple()[:2]),
            **{p: version(p) for p in VERSIONED_PACKAGES},
        },
    }


def forecast_sha256(results: pd.DataFrame) -> str:
    """SHA-256 of every forecast at full float precision, so a replay must be bit-identical."""
    lines = "\n".join(f"{ts.isoformat()} {value!r}" for ts, value in results["forecast_mw"].items())
    return hashlib.sha256(lines.encode()).hexdigest()


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
    if scores.excluded_hours > MAX_EXCLUDED_SHARE * len(results):
        raise ForecastError(
            f"{scores.excluded_hours} of {len(results)} test hours can't be scored (limit {MAX_EXCLUDED_SHARE:.0%})"
        )

    def ci(reference: pd.Series) -> tuple[float, float]:
        return metrics.day_block_bootstrap_ci(
            actual, forecast, reference, n_boot=protocol.n_boot, seed=protocol.seed,
            level=protocol.level, block_days=protocol.block_days,
        )  # fmt: skip

    primary_ci = ci(base)
    holiday_days = pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in holidays))
    on_holiday = pd.Series(results.index.normalize().isin(holiday_days), index=results.index)
    day_type = on_holiday.map({True: "holiday", False: "other"})
    scored = results["is_scored"]
    details = {
        "beats_baseline": metrics.beats_baseline(primary_ci[0]),
        "ci_level": protocol.level,
        "ci_block_days": protocol.block_days,
        "n_boot": protocol.n_boot,
        "bias_mw": {  # mean(forecast - actual) on the scored hours
            "model": round(float((forecast - actual)[scored].mean()), 4),
            "baseline": round(float((base - actual)[scored].mean()), 4),
        },
        "per_month": {k: _scores_dict(v) for k, v in metrics.score_groups(actual, forecast, base, results["fold"]).items()},
        "by_day_type": {k: _scores_dict(v) for k, v in metrics.score_groups(actual, forecast, base, day_type).items()},
        # Secondary references (protocol #9, MLE review H3): reported with their own CI, each on the
        # hours where the actual, the model and that reference all exist. They don't set the banner.
        "secondary": {
            name: {**_scores_dict(metrics.score(actual, forecast, results[column])), "ci": list(ci(results[column]))}
            for name, column in (("naive24", "naive24_mw"), ("weekday_naive", "weekday_naive_mw"))
        },
        "best_iteration": {f.name: m.best_iteration for f, m in zip(folds, models, strict=True)},
    }
    return Outcome(folds, results, scores, primary_ci, details)


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


def final_run_metrics(conn, grid: Grid) -> dict[str, Any] | None:
    """The stored FINAL run of a grid as {model_run_id, COMPARED columns as text}, or None."""
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT model_run_id, {', '.join(COMPARED)} FROM dw.forecast_run WHERE grid_key = ? AND run_kind = 'FINAL'",
        (grid.grid_key,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {"model_run_id": int(row[0]), **{c: str(v) for c, v in zip(COMPARED, row[1:], strict=True)}}


def read_record(path: Path | None = None) -> dict[str, Any]:
    path = path or RECORD_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_record(record: dict[str, Any], path: Path | None = None) -> None:
    """Write atomically (temp file, then rename), so a crash never leaves half a record (item 3)."""
    path = path or RECORD_PATH
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _head_commit() -> str | None:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=config.ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return done.stdout.strip() or None


def _month_end(month: str) -> pd.Timestamp:
    return pd.Period(month, freq="M").end_time.floor("h")


def _final_row(grid: Grid, outcome: Outcome, protocol: Protocol, git_commit: str, protocol_commit: str,
               load_run_id: int | None) -> dict[str, Any]:  # fmt: skip
    return store.run_row(
        grid_key=grid.grid_key, run_kind="FINAL", model_name=MODEL_NAME, folds=outcome.folds,
        scores=outcome.scores, ci=outcome.ci, params=protocol.raw, metrics=outcome.details,
        git_commit=git_commit, protocol_commit=protocol_commit, load_run_id=load_run_id, is_current=True,
    )  # fmt: skip


# --- the three modes -----------------------------------------------------------------------


def run_dev(grid_code: str, load_run_id: int | None) -> Outcome:
    protocol = load_protocol()
    until = _month_end(protocol.dev_last_month)
    if until > DEV_LIMIT:
        raise ForecastError(f"a DEV run may not go past {DEV_LIMIT} (the protocol's dev months end {until})")
    conn = db.connect()
    try:
        grid = load_grid(conn, grid_code)
        demand = load_demand(conn, grid, until)
        holidays = load_holidays(conn, grid)
        outcome = backtest_grid(demand, holidays, protocol, "DEV")
        outcome.details["fingerprint"] = input_fingerprint(demand, holidays)
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
        raise ForecastError(f"{grid_code} already has a recorded FINAL run ({RECORD_REL}); runs are once only")
    for other, entry in record.items():
        # Every grid runs the same locked settings and code: no edit after seeing a result.
        if entry["protocol"] != protocol.raw:
            raise ForecastError(f"the protocol settings differ from {other}'s recorded FINAL run")
        changed = changed_since(entry["git_commit"])
        if changed:
            raise ForecastError(f"guarded files changed since {other}'s FINAL run: {changed}")
    conn = db.connect()
    try:
        grid = load_grid(conn, grid_code)
        if final_run_metrics(conn, grid) is not None:
            raise ForecastError(f"{grid_code} already has a FINAL run in dw.forecast_run; runs are once only")
        demand = load_demand(conn, grid, _month_end(protocol.final_last_month))
        holidays = load_holidays(conn, grid)
        fingerprint = input_fingerprint(demand, holidays)
        outcome = backtest_grid(demand, holidays, protocol, "FINAL")
        outcome.details["fingerprint"] = fingerprint
        row = _final_row(grid, outcome, protocol, head_commit, protocol_commit, load_run_id)
        # The record goes first: if the database commit then fails, the next replay stores the run.
        record[grid_code] = {
            "protocol_commit": protocol_commit,
            "git_commit": head_commit,
            "protocol": protocol.raw,
            "fingerprint": fingerprint,
            "forecast_sha256": forecast_sha256(outcome.results),
            "metrics": {c: str(row[c]) for c in COMPARED},
            "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        write_record(record)
        model_run_id = save_run(conn, grid, row, outcome.results)
    finally:
        conn.close()
    log.info("FINAL run %d for %s: %s", model_run_id, grid_code, _summary(row))
    log.warning("Commit %s now; the gate refuses the next FINAL run until it is committed.", RECORD_REL)
    return outcome


def replay(grid_code: str, entry: dict[str, Any], load_run_id: int | None) -> str:
    """Re-run a recorded FINAL backtest; store it if the database lacks it. Returns a status message."""
    committed = protocol_at_commit(entry["protocol_commit"])
    if committed.raw != entry["protocol"]:
        raise ForecastError(f"{grid_code}: the record's settings differ from the protocol committed at its protocol_commit")
    protocol = protocol_from_dict(entry["protocol"])
    conn = db.connect()
    try:
        grid = load_grid(conn, grid_code)
        demand = load_demand(conn, grid, _month_end(protocol.final_last_month))
        holidays = load_holidays(conn, grid)
        fingerprint = input_fingerprint(demand, holidays)
        changed = sorted(k for k in fingerprint if fingerprint[k] != entry["fingerprint"].get(k))
        if changed:
            raise ForecastError(f"{grid_code}: replay inputs differ from the recorded run in {changed}; not replayed")
        outcome = backtest_grid(demand, holidays, protocol, "FINAL")
        outcome.details["fingerprint"] = fingerprint
        row = _final_row(grid, outcome, protocol, entry["git_commit"], entry["protocol_commit"], load_run_id)
        replayed = {c: str(row[c]) for c in COMPARED}
        differ = [c for c in COMPARED if replayed[c] != entry["metrics"].get(c)]
        if forecast_sha256(outcome.results) != entry["forecast_sha256"]:
            differ.insert(0, "forecast_sha256")
        if differ:
            # Names only: printing the new values would be an unlabelled second look at the test.
            raise ForecastError(f"{grid_code}: the replay does not reproduce the recorded FINAL run ({differ})")
        stored = final_run_metrics(conn, grid)
        if stored is None:
            model_run_id = save_run(conn, grid, row, outcome.results)
            return f"replayed and stored as FINAL run {model_run_id} (identical to the record)"
        if any(stored[c] != replayed[c] for c in COMPARED):
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
