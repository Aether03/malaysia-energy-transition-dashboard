"""pipeline export's licence gate (M6 step 1, plan Q3): which mart views and showcase results may leave the PC.
No DB: the gate is pure, and the view list is read from sql/views."""

import json
import re

import pytest

from pipeline import config, export

OPEN = {"D1": True, "D2": True, "D3": True, "D4": False, "D5": False, "D6": True, "DSG": True, "DTH": True, "GEO": True}


def test_every_mart_view_in_sql_views_is_reviewed():
    # A new view must be listed (with its sources) before any export runs: it can't slip out unreviewed.
    created = set()
    for path in (config.ROOT / "sql" / "views").glob("R__mart_*.sql"):
        created |= set(re.findall(r"CREATE OR ALTER VIEW mart\.(\w+)", path.read_text(encoding="utf-8")))
    assert created == set(export.VIEWS)


def test_every_showcase_query_is_reviewed():
    names = {p.stem for p in (config.ROOT / "sql" / "showcase").glob("*.sql")}
    assert names == set(export.SHOWCASE) | set(export.SHOWCASE_NOT_SHOWN)


def test_restricted_views_are_excluded_with_their_reason():
    keep, excluded = export.plan(set(export.VIEWS), OPEN)
    assert "country_annual" in keep and "grid_hourly" in keep and "dq_latest" in keep
    assert excluded["region_annual"] == "D5 not publishable"
    assert not set(keep) & set(excluded)
    assert all(export.VIEWS[v] <= {c for c, ok in OPEN.items() if ok} for v in keep)


def test_consent_for_data_rows_lets_the_restricted_views_through():
    # The designed GRANTED path (M5 lesson): flipping is_publishable is the whole change.
    keep, excluded = export.plan(set(export.VIEWS), {**OPEN, "D5": True})
    assert "region_annual" in keep and "state_reliability" in keep
    assert not any(reason.startswith("D5") for reason in excluded.values())


def test_an_unreviewed_view_refuses_the_whole_export():
    with pytest.raises(export.ExportRefused, match="mart.new_view"):
        export.plan(set(export.VIEWS) | {"new_view"}, OPEN)


def test_an_unknown_source_code_refuses_the_whole_export():
    with pytest.raises(export.ExportRefused, match="D1"):
        export.plan(set(export.VIEWS), {k: v for k, v in OPEN.items() if k != "D1"})


def test_grid_rows_are_kept_only_for_publishable_sources():
    grids = [(1, "TH_EGAT", "DTH"), (2, "MY_PEN_GSO", "D4"), (3, "SG_EMA", "DSG")]
    assert export.publishable_grids(grids, OPEN) == {1: "TH_EGAT", 3: "SG_EMA"}
    assert export.publishable_grids(grids, {**OPEN, "DSG": False}) == {1: "TH_EGAT"}


def test_dq_detail_from_a_restricted_source_refuses_the_export():
    ok = [("R1", "D1", "3 rows"), ("R2", "D5", None), ("R3", None, "run-level")]
    export.check_dq_detail(ok, OPEN)
    with pytest.raises(export.ExportRefused, match="R4"):
        export.check_dq_detail([*ok, ("R4", "D5", "a value")], OPEN)


def test_showcase_results_follow_the_same_gate():
    keep, excluded = export.plan_showcase(OPEN)
    assert "03_ranking" in keep and "09_forecast_metrics" in keep
    assert excluded["13_state_reliability"] == "D5 not publishable"
    assert excluded["00_reconciliation"].startswith("not shown in the app")


def test_grid_keyed_showcase_rows_are_filtered_by_grid_code():
    rows = [{"grid_code": "TH_EGAT", "x": 1}, {"grid_code": "MY_PEN_GSO", "x": 2}]
    assert export.filter_grid_rows(rows, {"TH_EGAT", "SG_EMA"}) == [{"grid_code": "TH_EGAT", "x": 1}]


# ---------------------------------------------------------------- the export run itself, on a fake warehouse (step 6)


def test_a_grid_column_outside_the_filtered_views_refuses_the_export():
    export.check_grid_filtered({"dim_grid": ["grid_key", "grid_code"], "grid_hourly": ["grid_key", "ts"], "kpi": ["a"]})
    with pytest.raises(export.ExportRefused, match="new_view"):
        export.check_grid_filtered({"new_view": ["grid_key", "value"]})
    with pytest.raises(export.ExportRefused, match="other_view"):
        export.check_grid_filtered({"other_view": ["grid_code"]})


class FakeCursor:
    """Answers the export's queries from canned tables: a warehouse with one open and one restricted grid."""

    def __init__(self, tables: dict[str, tuple[list[str], list[tuple]]], grids: list[tuple]):
        self.tables, self.grids, self.description, self._rows = tables, grids, [], []

    def execute(self, sql: str, params: tuple = ()):
        if "dim_data_source" in sql:
            cols, rows = ["data_source_code", "is_publishable"], list(OPEN.items())
        elif "sys.views" in sql:
            cols, rows = ["name"], [(v,) for v in self.tables]
        elif "FROM mart.dim_grid" in sql:
            cols, rows = ["grid_key", "grid_code", "data_source_code"], self.grids
        elif "FROM mart.dq_latest" in sql:
            cols, rows = ["rule_code", "data_source_code", "detail"], []
        elif "FROM mart.run_latest" in sql:
            cols, rows = ["run_id", "started_at", "finished_at", "status"], [(9, "s", "f", "PASS")]
        elif "FROM mart.source_load_latest" in sql:
            cols, rows = ["data_source_code", "rows_in"], [("D1", 5)]
        elif m := re.search(r"FROM mart\.\[(\w+)\]", sql):
            cols, rows = self.tables[m.group(1)]
            if "grid_key IN" in sql:
                rows = [r for r in rows if r[cols.index("grid_key")] in params]
        else:  # a showcase query
            cols, rows = ["grid_code", "value"], [("TH_EGAT", 1.5), ("MY_PEN_GSO", 2.5)]
        self.description, self._rows = [(c,) for c in cols], rows

    def fetchall(self):
        return self._rows


@pytest.fixture
def warehouse(monkeypatch):
    """Point export() at a fake warehouse; returns its tables so a test can change them."""
    from pipeline import db

    grids = [(1, "TH_EGAT", "DTH"), (2, "MY_PEN_GSO", "D4")]
    tables = {
        "country_annual": (["country_key", "year", "value"], [(1, 2024, 1.0)]),
        "dim_grid": (["grid_key", "grid_code", "data_source_code"], grids),
        "grid_hourly": (["grid_key", "demand_mw"], [(1, 100.0), (2, 999.0)]),
        "region_annual": (["region_key", "value"], [(1, 42.0)]),
    }

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def cursor(self):
            return FakeCursor(tables, grids)

    monkeypatch.setattr(db, "connect", lambda *a, **k: Conn())
    return tables


def snapshot(out) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(out.iterdir())}


def test_export_writes_only_open_rows_and_clears_stale_files(warehouse, tmp_path):
    import pandas as pd

    (tmp_path / "README.md").write_text("credits", encoding="utf-8")
    (tmp_path / "region_annual.parquet").write_bytes(b"left over from an earlier export")
    manifest = export.export(tmp_path)
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {
        "README.md",
        "country_annual.parquet",
        "dim_grid.parquet",
        "grid_hourly.parquet",
        "expected.json",
        "manifest.json",
    }
    assert manifest["excluded_views"] == {"region_annual": "D5 not publishable"}
    assert set(pd.read_parquet(tmp_path / "grid_hourly.parquet")["grid_key"]) == {1}  # the GSO grid's rows stay home
    assert set(pd.read_parquet(tmp_path / "dim_grid.parquet")["grid_code"]) == {"TH_EGAT"}
    assert all(
        r["grid_code"] == "TH_EGAT" for r in json.loads((tmp_path / "expected.json").read_text())["08_grid_load"]
    )


def test_a_failure_mid_export_leaves_the_previous_set_untouched(warehouse, tmp_path, monkeypatch):
    export.export(tmp_path)
    before = snapshot(tmp_path)
    warehouse["grid_hourly"] = (["grid_key", "demand_mw"], [(1, 101.0)])  # the next export would change a file
    real = json.dumps

    def manifest_fails(obj, *a, **k):  # the last thing serialised, after every Parquet file
        if isinstance(obj, dict) and "excluded_views" in obj:
            raise OSError("disk full")
        return real(obj, *a, **k)

    monkeypatch.setattr(export.json, "dumps", manifest_fails)
    with pytest.raises(OSError, match="disk full"):
        export.export(tmp_path)
    assert snapshot(tmp_path) == before  # nothing replaced, nothing left behind


def test_an_unfiltered_grid_view_refuses_with_nothing_written(warehouse, tmp_path, monkeypatch):
    monkeypatch.setitem(export.VIEWS, "new_view", frozenset())
    warehouse["new_view"] = (["grid_key", "value"], [(2, 1.0)])
    with pytest.raises(export.ExportRefused, match="new_view"):
        export.export(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_no_publishable_grid_refuses_with_nothing_written(warehouse, tmp_path, monkeypatch):
    monkeypatch.setitem(OPEN, "DTH", False)
    with pytest.raises(export.ExportRefused, match="no publishable grid"):
        export.export(tmp_path)
    assert list(tmp_path.iterdir()) == []
