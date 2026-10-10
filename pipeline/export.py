"""`pipeline export`: Parquet snapshots of the open-data mart views for the Streamlit showcase (FR-21, M6 plan Q3-Q4).

Licence gate, fail closed:
- Every `mart` view is listed in VIEWS with the data sources it draws from (an empty set is this project's own
  reference or run metadata). A view with a source that is not `is_publishable` is left out, and the reason is
  printed and recorded in the manifest. So a source that gains consent for its data rows needs only its flag.
- The export refuses outright on an unlisted view or showcase query, an unknown source code, or a data-quality
  detail from a non-publishable source (DQ details can hold values; the handbook's are NULL by design).
- Views keyed by grid keep only the rows of grids whose source is publishable.

`exports/expected.json` holds the open showcase queries' result sets (the SQL twins), gated the same way: the
app's pandas calculations are tested against them (plan Q4).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from pipeline import config

log = logging.getLogger(__name__)

EXPORT_DIR = config.ROOT / "exports"
SHOWCASE_DIR = config.SQL_DIR / "showcase"

_GRIDS = frozenset({"DTH", "DSG"})  # dim_grid's sources; grid-keyed views are filtered row by row (GRID_KEYED)

# Every mart view (sql/views/R__mart_*.sql) and the sources its rows come from.
VIEWS: dict[str, frozenset[str]] = {
    # Annual country and generation data: Ember, with OWID population for per-capita demand.
    "country_annual": frozenset({"D1", "D2"}),
    "generation_annual": frozenset({"D1"}),
    "netr_target": frozenset({"D6"}),
    "re_capacity_official": frozenset({"D6"}),
    # Hourly grids: row-filtered by grid source.
    "dim_grid": frozenset(),
    "grid_hourly": frozenset(),
    "grid_flow_daily": frozenset(),
    "load_forecast_current": frozenset(),
    "forecast_run_current": frozenset(),
    "forecast_status": frozenset(),
    "season_pick": frozenset(),
    "forecast_date": _GRIDS,
    # This project's reference data and run metadata (names, definitions, statuses; no source values).
    "dim_country": frozenset(),
    "dim_source": frozenset(),
    "dim_year": frozenset(),
    "dim_date": frozenset(),
    "dim_hour": frozenset(),
    "kpi": frozenset(),
    "data_source": frozenset(),
    "dq_latest": frozenset(),
    "run_latest": frozenset(),
    "source_load_latest": frozenset(),
    # The Energy Commission handbook (M4): consent covers the charts, not these rows (DATA_LICENSES.md, D5).
    "dim_region": frozenset({"D5"}),
    "region_annual": frozenset({"D5"}),
    "region_capacity": frozenset({"D5"}),
    "dim_state": frozenset({"D5"}),
    "state_reliability": frozenset({"D5"}),
    "reliability_metric": frozenset({"D5"}),
    "reliability_year": frozenset({"D5"}),
}
GRID_KEYED = frozenset(
    {
        "grid_hourly",
        "grid_flow_daily",
        "load_forecast_current",
        "forecast_run_current",
        "forecast_status",
        "season_pick",
    }
)

# sql/showcase queries the app is checked against, with their sources; grid-keyed ones by grid_code.
SHOWCASE: dict[str, frozenset[str]] = {
    "01_trends": frozenset({"D1"}),
    "02_yoy_lag": frozenset({"D1", "D2"}),
    "03_ranking": frozenset({"D1", "D2"}),
    "04_rolling_avg": frozenset({"D1"}),
    "05_capacity_factor": frozenset({"D1"}),
    "06_re_growth_decomposition": frozenset({"D1"}),
    "07_emissions_vs_demand": frozenset({"D1", "D2"}),
    "08_grid_load": frozenset(),
    "09_forecast_metrics": frozenset(),
    "10_load_curves": frozenset(),
    "11_interconnector_flows": frozenset(),
    "12_regions": frozenset({"D5"}),
    "13_state_reliability": frozenset({"D5"}),
}
SHOWCASE_GRID_KEYED = frozenset({"08_grid_load", "09_forecast_metrics", "10_load_curves", "11_interconnector_flows"})
SHOWCASE_NOT_SHOWN = {"00_reconciliation": "not shown in the app (a warehouse check against raw Ember)"}


class ExportRefused(RuntimeError):
    """The export would publish something unreviewed or restricted; nothing is written."""


def _gate(names: set[str], sources: dict[str, frozenset[str]], publishable: dict[str, bool], kind: str):
    unknown = sorted(names - set(sources))
    if unknown:
        raise ExportRefused(f"unreviewed {kind}: {', '.join(unknown)}; list it with its sources in pipeline/export.py")
    missing = sorted({code for n in names for code in sources[n]} - set(publishable))
    if missing:
        raise ExportRefused(f"source code(s) not in dim_data_source: {', '.join(missing)}")
    keep, excluded = [], {}
    for name in sorted(names):
        closed = sorted(code for code in sources[name] if not publishable[code])
        if closed:
            excluded[name] = f"{', '.join(closed)} not publishable"
        else:
            keep.append(name)
    return keep, excluded


def plan(views: set[str], publishable: dict[str, bool]) -> tuple[list[str], dict[str, str]]:
    """(views to export, {excluded view: reason}). Raises ExportRefused on an unlisted view or unknown source."""
    keep, excluded = _gate(
        {f"mart.{v}" for v in views}, {f"mart.{k}": s for k, s in VIEWS.items()}, publishable, "view"
    )
    return [k.removeprefix("mart.") for k in keep], {k.removeprefix("mart."): r for k, r in excluded.items()}


def plan_showcase(publishable: dict[str, bool]) -> tuple[list[str], dict[str, str]]:
    names = {p.stem for p in SHOWCASE_DIR.glob("*.sql")} - set(SHOWCASE_NOT_SHOWN)
    keep, excluded = _gate(names, SHOWCASE, publishable, "showcase query")
    return keep, {**excluded, **SHOWCASE_NOT_SHOWN}


def publishable_grids(grids: list[tuple[int, str, str]], publishable: dict[str, bool]) -> dict[int, str]:
    """{grid_key: grid_code} for (grid_key, grid_code, data_source_code) rows whose source is publishable."""
    return {key: code for key, code, source in grids if publishable.get(source, False)}


def filter_grid_rows(rows: list[dict], grid_codes: set[str]) -> list[dict]:
    return [r for r in rows if r["grid_code"] in grid_codes]


def check_dq_detail(rows: list[tuple[str, str | None, str | None]], publishable: dict[str, bool]) -> None:
    """(rule_code, data_source_code, detail): a detail may quote values, so a restricted source's must be NULL."""
    leaks = [rule for rule, source, detail in rows if source and not publishable.get(source, False) and detail]
    if leaks:
        raise ExportRefused(f"dq_latest detail from a non-publishable source: {', '.join(leaks)}")


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def _query(cursor, sql: str, params: tuple = ()) -> tuple[list[str], list[tuple]]:
    cursor.execute(sql, params)
    return [d[0] for d in cursor.description], cursor.fetchall()


def export(out_dir: Path = EXPORT_DIR) -> dict:
    """Write exports/<view>.parquet, expected.json and manifest.json; returns the manifest."""
    import pandas as pd

    from pipeline import db

    with db.connect() as conn:
        cur = conn.cursor()
        _, rows = _query(cur, "SELECT data_source_code, is_publishable FROM dw.dim_data_source")
        publishable = {code: bool(flag) for code, flag in rows}
        _, rows = _query(
            cur, "SELECT v.name FROM sys.views v JOIN sys.schemas s ON s.schema_id = v.schema_id WHERE s.name = 'mart'"
        )
        keep, excluded = plan({r[0] for r in rows}, publishable)
        _, rows = _query(cur, "SELECT grid_key, grid_code, data_source_code FROM mart.dim_grid")
        grids = publishable_grids([tuple(r) for r in rows], publishable)
        _, rows = _query(cur, "SELECT rule_code, data_source_code, detail FROM mart.dq_latest")
        check_dq_detail([tuple(r) for r in rows], publishable)
        if not grids:
            raise ExportRefused("no publishable grid in mart.dim_grid")

        frames = {}
        for view in keep:
            where, params = "", ()
            if view in GRID_KEYED or view == "dim_grid":
                where = f" WHERE grid_key IN ({', '.join('?' * len(grids))})"
                params = tuple(grids)
            cols, data = _query(cur, f"SELECT * FROM mart.[{view}]{where}", params)
            frame = pd.DataFrame([[_plain(v) for v in row] for row in data], columns=cols)
            frames[view] = frame.sort_values(cols, kind="stable", na_position="first").reset_index(drop=True)

        show_keep, show_excluded = plan_showcase(publishable)
        expected = {}
        for name in show_keep:
            cols, data = _query(cur, (SHOWCASE_DIR / f"{name}.sql").read_text(encoding="utf-8"))
            result = [dict(zip(cols, (_plain(v) for v in row), strict=True)) for row in data]
            expected[name] = filter_grid_rows(result, set(grids.values())) if name in SHOWCASE_GRID_KEYED else result

        _, run = _query(cur, "SELECT run_id, started_at, finished_at, status FROM mart.run_latest")
        cols, loads = _query(cur, "SELECT * FROM mart.source_load_latest ORDER BY data_source_code")

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.parquet"):
        old.unlink()  # a view excluded since the last export must not linger
    files = []
    for view, frame in frames.items():
        frame.to_parquet(out_dir / f"{view}.parquet", index=False)
        files.append({"file": f"{view}.parquet", "rows": len(frame), "sources": sorted(VIEWS[view])})
    (out_dir / "expected.json").write_text(json.dumps(expected, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = {
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "run": dict(zip(("run_id", "started_at", "finished_at", "status"), map(_plain, run[0]), strict=True))
        if run
        else None,
        "data_vintage": [dict(zip(cols, map(_plain, r), strict=True)) for r in loads],
        "grids": sorted(grids.values()),
        "files": files,
        "excluded_views": excluded,
        "expected": sorted(expected),
        "excluded_showcase": show_excluded,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, reason in {**excluded, **show_excluded}.items():
        log.info("Left out %s: %s", name, reason)
    return manifest
