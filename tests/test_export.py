"""pipeline export's licence gate (M6 step 1, plan Q3): which mart views and showcase results may leave the PC.
No DB: the gate is pure, and the view list is read from sql/views."""

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
