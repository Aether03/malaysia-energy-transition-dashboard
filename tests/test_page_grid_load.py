"""The Grid load page (P4, M6 step 4): each report item has an app element, and its numbers are the report's.

Page tests run `app/pages/grid_load.py` headless (`AppTest`) and compare with `exports/expected.json` (the SQL
twins' results) or with a plain-pandas recomputation, never with the code under test. Unit tests cover the pure
functions in `app/showcase/grid.py`, including the DAX edge cases (blank states, rounding, TREATAS)."""

import base64
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
PAGE = str(APP / "pages" / "grid_load.py")
REPORT = ROOT / "report/EnergyTransition.Report/definition/pages"
TH = "Thailand national grid (EGAT)"
SG = "Singapore national grid (EMA)"


# ---------------------------------------------------------------- helpers
def arr(x) -> np.ndarray:
    """A figure field as numpy: plotly 6+ writes numpy input as {"dtype", "bdata"[, "shape"]}."""
    if isinstance(x, dict) and "bdata" in x:
        a = np.frombuffer(base64.b64decode(x["bdata"]), dtype=np.dtype(x["dtype"]))
        return a.reshape([int(s) for s in x["shape"].split(",")]) if "shape" in x else a
    return np.array(x, dtype=float)


def figures(at) -> dict[str, dict]:
    figs = {}
    for c in at.get("plotly_chart"):
        fig = json.loads(c.proto.spec)
        figs[fig["layout"]["title"]["text"]] = fig
    return figs


def captions(at) -> list[str]:
    return [c.value for c in at.caption]


def report_text(page: str, visual: str) -> str:
    v = json.loads((REPORT / page / "visuals" / visual / "visual.json").read_text(encoding="utf-8"))
    runs = v["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"]
    return "".join(r["value"] for r in runs)


def widget(at, kind: str, label: str):
    return next(w for w in getattr(at, kind) if w.label == label)


def run(grid: str | None = None):
    at = AppTest.from_file(PAGE, default_timeout=60)
    if grid:
        at.session_state["grid_name"] = grid  # the selection both grid pages share (the report's slicer sync)
    return at.run()


@pytest.fixture(scope="module")
def frames():
    from showcase import data

    return data.frames()


@pytest.fixture(scope="module")
def expected():
    from showcase import data

    return data.expected()


@pytest.fixture(scope="module")
def th():
    return run()


@pytest.fixture(scope="module")
def sg():
    return run(SG)


def peak_row(expected, code, year):
    return next(
        r for r in expected["08_grid_load"] if r["grid_code"] == code and r["year"] == year and r["month"] is None
    )


def as_of(frames) -> str:
    d = pd.to_datetime(frames["run_latest"]["finished_at"]).max()
    return f"Data as of {d.day} {d:%b %Y}"


# ---------------------------------------------------------------- the page: frame items
def test_renders_without_exception(th, sg):
    assert not th.exception and not sg.exception


@pytest.mark.parametrize(("code", "country", "grid"), [("TH_EGAT", "Thailand", None), ("SG_EMA", "Singapore", SG)])
def test_title_is_the_dax_takeaway(expected, code, country, grid):
    """frame_title = [P4 Load Title]: 2024 peak and load factor of the chosen grid."""
    r = peak_row(expected, code, 2024)
    want = f"{country}: demand peaked at {r['peak_mw']:,.0f} MW in 2024; load factor {r['load_factor_pct']:.0f}%"
    assert run(grid).title[0].value == want


def test_the_grid_widget_switches_the_whole_page(th, expected):
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert widget(at, "selectbox", "Grid").value == TH
    assert widget(at, "selectbox", "Grid").options == [TH, SG]
    widget(at, "selectbox", "Grid").select(SG).run()
    assert at.title[0].value.startswith("Singapore: demand peaked at 8,023 MW in 2024; load factor 85%")
    assert at.session_state["grid_name"] == SG  # remembered for the Forecast page
    assert "Showing: Singapore national grid (EMA)" in at.info[0].value


def test_subtitle_banner_and_credits(th, sg, frames):
    """frame_subtitle = [P4 Subtitle], p4_banner = [Grid Banner] (the label doc reconciliation.md recommends)."""
    assert captions(th)[0] == f"Sum of regional demand (EGAT) · hourly, 2023–24 · local time · {as_of(frames)}"
    assert captions(sg)[0] == f"System demand (EMA) · hourly, 2023–24 · local time · {as_of(frames)}"
    assert th.info[0].value == (
        "Showing: Thailand national grid (EGAT) · Open-data stand-in for Peninsular Malaysia until TNB consents to GSO data use"
    )
    assert sg.info[0].value == "Showing: Singapore national grid (EMA) · ASEAN peer grid (open data)"


def test_the_footer_is_the_reports_footnote_then_the_credits(th, frames):
    caps = captions(th)
    assert caps[-2] == report_text("p4_grid_load", "frame_footnote")
    ds = frames["data_source"].set_index("data_source_code")["credit_text"]
    assert caps[-1].startswith("Credits: ") and ds["DTH"] in caps[-1] and ds["DSG"] in caps[-1]


def test_no_reset_button(th):
    assert not th.button  # these two report pages have none


def test_the_grid_choice_made_on_the_other_page_is_kept(sg):
    assert widget(sg, "selectbox", "Grid").value == SG


# ---------------------------------------------------------------- the page: texts that sit with charts
def test_peak_text_names_the_peak_hour(th, sg, expected):
    """p4_peak_text = [Peak Text]: "Peak 35,560 MW on 29 Apr 2024, 21:00" (the max over 2023-24, as the report)."""
    assert "Peak 35,560 MW on 29 Apr 2024, 21:00" in captions(th)
    assert "Peak 8,023 MW on 29 Oct 2024, 16:00" in captions(sg)
    assert peak_row(expected, "TH_EGAT", 2024)["peak_at"] == "2024-04-29T21:00:00"


def test_flow_note_gives_the_annual_totals(th, expected):
    """p4_flow_note = [Flow Subtitle]."""
    fl = {r["year"]: r for r in expected["11_interconnector_flows"]}
    want = (
        f"Exported {fl[2023]['export_gwh']:,.1f} GWh to Malaysia and imported {fl[2023]['import_gwh']:,.1f} GWh in 2023; "
        f"{fl[2024]['export_gwh']:,.1f} and {fl[2024]['import_gwh']:,.1f} GWh in 2024. Above 0 = Thailand exports"
    )
    assert want in captions(th)


def test_singapore_has_no_flow_chart_but_says_why(sg):
    assert "No Malaysia interconnector flows are published for this grid" in captions(sg)
    assert not any("net flow" in t for t in figures(sg))


# ---------------------------------------------------------------- the page: charts
def test_every_chart_has_a_text_summary_and_a_data_table(th, sg):
    for at, n in ((th, 5), (sg, 4)):
        charts = at.get("plotly_chart")
        assert len(charts) == n
        assert [e.label for e in at.expander] == ["Show data"] * n
        assert len(at.dataframe) == n
        caps = captions(at)
        assert all(c.proto.alt and c.proto.alt in caps for c in charts)


def test_the_chart_titles_are_the_reports(th):
    assert list(figures(th)) == [
        "Average load by month and hour (GW)",
        "Typical day (MW)",
        "Monthly peak (MW)",
        "Load factor (%)",
        "Thailand ↔ Malaysia daily net flow (MW)",
    ]


def test_heatmap_cells_are_mean_load_in_gw_with_values_shown(th, frames):
    """p4_heatmap = [Avg Load (GW)] by month x hour over 2023-24; values in the cells and in the hover."""
    h = frames["grid_hourly"].query("grid_key == 1 and year in (2023, 2024)")
    want = h.groupby(["month", "hour"])["demand_mw"].mean().unstack() / 1000
    trace = figures(th)["Average load by month and hour (GW)"]["data"][0]
    assert trace["type"] == "heatmap"
    np.testing.assert_allclose(arr(trace["z"]), want.to_numpy(), rtol=1e-9)
    assert list(trace["y"])[:3] == ["Jan", "Feb", "Mar"] and list(arr(trace["x"])) == list(range(24))
    assert "GW" in trace["hovertemplate"] and trace["texttemplate"]  # nothing by colour alone
    table = th.dataframe[0].value  # "Show data": the same grid as a table
    assert table.shape[0] == 12 and round(table.iloc[0, 1], 1) == round(want.iloc[0, 0], 1)


def test_typical_day_has_two_day_types_over_24_hours(th, expected):
    traces = {t["name"]: t for t in figures(th)["Typical day (MW)"]["data"]}
    assert set(traces) == {"Weekday", "Weekend & holiday"}
    rows = [r for r in expected["10_load_curves"] if r["grid_code"] == "TH_EGAT"]
    for day_type, tr in traces.items():
        pts = [r for r in rows if r["day_type"] == day_type]
        want = sum(r["mean_mw"] * r["hours"] for r in pts if r["hour"] == 21) / sum(
            r["hours"] for r in pts if r["hour"] == 21
        )
        assert arr(tr["y"])[21] == pytest.approx(want, abs=0.1)  # twin values are rounded to 0.1 MW
        assert len(arr(tr["y"])) == 24
    assert traces["Weekend & holiday"]["line"]["dash"] != traces["Weekday"]["line"]["dash"]  # not by colour alone


def test_the_season_slicer_narrows_only_the_typical_day(th, expected):
    """p4_season_slicer: nothing picked = every season; picking narrows [Avg Load Curve (MW)] (TREATAS)."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    season = widget(at, "multiselect", "Season")
    assert season.options == ["Hot (Mar–May)", "Rainy (Jun–Oct)", "Cool (Nov–Feb)"]  # season_order
    assert season.value == []
    before = {k: v for k, v in figures(at).items() if k != "Typical day (MW)"}
    season.select("Hot (Mar–May)").run()
    after = figures(at)
    rows = [
        r
        for r in expected["10_load_curves"]
        if r["grid_code"] == "TH_EGAT" and r["season"] == "Hot (Mar–May)" and r["day_type"] == "Weekday"
    ]
    got = next(t for t in after["Typical day (MW)"]["data"] if t["name"] == "Weekday")
    np.testing.assert_allclose(arr(got["y"]), [r["mean_mw"] for r in sorted(rows, key=lambda r: r["hour"])], atol=0.06)
    assert {k: v for k, v in after.items() if k != "Typical day (MW)"} == before  # heatmap and peaks stay whole-year


def test_monthly_peak_and_load_factor_match_the_twin(th, expected):
    """p4_peak_cols = [Peak Load (MW)], p4_lf_line = [Load Factor (%)], one series per year."""
    figs = figures(th)
    for title, field, tol in (("Monthly peak (MW)", "peak_mw", 0.06), ("Load factor (%)", "load_factor_pct", 0.006)):
        series = {t["name"]: t for t in figs[title]["data"]}
        assert set(series) == {"2023", "2024"}
        for year in (2023, 2024):
            rows = sorted(
                (
                    r
                    for r in expected["08_grid_load"]
                    if r["grid_code"] == "TH_EGAT" and r["year"] == year and r["month"]
                ),
                key=lambda r: r["month"],
            )
            np.testing.assert_allclose(arr(series[str(year)]["y"]), [r[field] for r in rows], atol=tol)
            assert list(series[str(year)]["x"]) == [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]


def test_flow_line_is_the_daily_mean_net_flow_with_gaps_left_open(th, frames, expected):
    """p4_flow_line = [Daily Net Flow (MW)] (counterparty MY, 2023-24); missing days stay gaps."""
    tr = figures(th)["Thailand ↔ Malaysia daily net flow (MW)"]["data"][0]
    y, x = arr(tr["y"]), pd.to_datetime(tr["x"])
    fd = frames["grid_flow_daily"].query("grid_key == 1 and counterparty == 'MY' and year in (2023, 2024)")
    assert np.count_nonzero(~np.isnan(y)) == len(fd) == 724
    assert len(y) == (x.max() - x.min()).days + 1 and np.isnan(y).sum() == len(y) - len(fd)
    for year in (2023, 2024):
        want = next(r for r in expected["11_interconnector_flows"] if r["year"] == year)["mean_daily_net_mw"]
        assert np.nanmean(y[x.year == year]) == pytest.approx(want, abs=0.06)


def test_a_failing_data_quality_rule_shows_the_sidebar_badge(monkeypatch):
    """frame_nav_badge = [DQ Fail Badge Text], through ui.header."""
    import streamlit as st
    from showcase import data

    real = data.frames

    def one_failing():
        f = real()
        f["dq_latest"] = f["dq_latest"].assign(status=["FAIL"] + ["PASS"] * (len(f["dq_latest"]) - 1))
        return f

    monkeypatch.setattr(data, "frames", one_failing)
    st.cache_data.clear()
    try:
        at = run()
        assert "1 data-quality rule failing" in at.sidebar.error[0].value
    finally:
        st.cache_data.clear()


# ---------------------------------------------------------------- grid.py: the pure functions
@pytest.fixture(scope="module")
def grid():
    from showcase import grid

    return grid


def test_num_rounds_half_away_from_zero_like_dax_format(grid):
    assert grid.num(0.5) == "1" and grid.num(2.5) == "3" and grid.num(-2.5) == "-3"
    assert grid.num(35559.8, 0, thousands=True) == "35,560"
    assert grid.num(0.25, 1) == "0.3" and grid.num(46.864, 1) == "46.9" and grid.num(3.309, 2) == "3.31"


def test_date_text_matches_dax_formats(grid):
    assert grid.date_text(date(2024, 4, 29)) == "29 Apr 2024"
    assert grid.date_text(date(2024, 4, 29), weekday=True) == "Mon 29 Apr 2024"


def synthetic():
    """One grid, 2 seasons in season_pick but a third in the hours; 2023 Jan-Feb weekdays and weekends."""
    ts = pd.date_range("2023-01-01", periods=24 * 59, freq="h")
    h = pd.DataFrame({"ts_local": ts.strftime("%Y-%m-%dT%H:%M:%S"), "grid_key": 1})
    h["date_key"] = ts.strftime("%Y%m%d").astype(int)
    h["hour"], h["year"], h["month"] = ts.hour, ts.year, ts.month
    h["demand_mw"] = 100.0 + ts.hour + 10 * (ts.month - 1)
    h["season"] = np.where(ts.month == 1, "A", "B")
    h.loc[h["date_key"] == 20230115, "season"] = "Orphan"  # in the hours, not in season_pick
    h["season_order"] = 1
    h["day_type"] = np.where(ts.dayofweek >= 5, "Weekend & holiday", "Weekday")
    dim_date = pd.DataFrame({"date_key": h["date_key"].unique()})
    dim_date["month"] = dim_date["date_key"] // 100 % 100
    dim_date["month_name"] = dim_date["month"].map({1: "Jan", 2: "Feb"})
    pick = pd.DataFrame({"grid_key": [1, 1, 3], "season": ["A", "B", "Z"], "season_order": [2, 1, 1]})
    return {"grid_hourly": h, "dim_date": dim_date, "season_pick": pick}


def test_season_options_follow_season_order_for_the_grid(grid):
    assert grid.season_options(synthetic(), 1) == ["B", "A"]
    assert grid.season_options(synthetic(), 3) == ["Z"]


def test_load_curve_uses_only_the_seasons_season_pick_lists(grid):
    """[Avg Load Curve (MW)] = TREATAS(VALUES(season_pick[season]), grid_hourly[season]): no pick = the grid's
    listed seasons, so hours of a season missing from season_pick drop out; a pick narrows to that season."""
    f = synthetic()
    h = f["grid_hourly"]
    for picked, seasons in (([], ["A", "B"]), (["A"], ["A"])):
        got = grid.load_curve(f, 1, picked).set_index(["day_type", "hour"])["mean_mw"].sort_index()
        want = h[h["season"].isin(seasons)].groupby(["day_type", "hour"])["demand_mw"].mean().sort_index()
        pd.testing.assert_series_equal(got, want, check_names=False)


def test_heatmap_is_gw_by_month_row_and_hour_column(grid):
    z = grid.heatmap(synthetic(), 1)
    assert list(z.index) == ["Jan", "Feb"] and list(z.columns) == list(range(24))
    assert z.loc["Jan", 3] == pytest.approx((100 + 3) / 1000) and z.loc["Feb", 0] == pytest.approx(0.110)


def test_load_factor_is_not_double_rounded(grid):
    """The twin rounds to 2 places; the report formats the unrounded value to 1, so 52.4496 shows 52.4, not 52.5."""
    f = {"grid_hourly": pd.DataFrame({"grid_key": 1, "year": 2024, "month": 1, "demand_mw": [4.8992, 100.0]})}
    assert grid.load_factor(f, 1, 2024) == pytest.approx(52.4496)
    assert grid.num(grid.load_factor(f, 1, 2024), 1) == "52.4"


def test_load_title_falls_back_when_the_grid_has_no_peak(grid):
    g = {"country_name": "Thailand", "grid_key": 1, "grid_code": "TH_EGAT"}
    f = {"grid_hourly": pd.DataFrame({"grid_key": [1], "year": [2024], "month": [1], "demand_mw": [10.0]})}
    assert grid.load_title(g, f, []) == "Grid load"
    rows = [{"grid_code": "TH_EGAT", "year": 2024, "month": None, "peak_mw": 35559.8, "peak_at": "2024-04-29T21:00:00"}]
    f["grid_hourly"] = pd.DataFrame(
        {"grid_key": [1, 1], "year": [2024, 2024], "month": [1, 1], "demand_mw": [69.25, 100.0]}
    )
    assert grid.load_title(g, f, rows) == "Thailand: demand peaked at 35,560 MW in 2024; load factor 85%"


def test_peak_text_takes_the_earliest_of_tied_peaks_over_both_years(grid):
    rows = [
        {"grid_code": "X", "year": 2023, "month": None, "peak_mw": 9.0, "peak_at": "2023-05-06T09:00:00"},
        {"grid_code": "X", "year": 2024, "month": None, "peak_mw": 9.0, "peak_at": "2024-01-02T14:00:00"},
        {"grid_code": "X", "year": 2024, "month": 1, "peak_mw": 9.0, "peak_at": "2024-01-02T14:00:00"},
    ]
    assert grid.peak_text(rows, "X") == "Peak 9 MW on 6 May 2023, 9:00"
    assert grid.peak_text(rows, "nope") is None


def test_flow_note_and_blank_state(grid):
    rows = [
        {"grid_code": "TH_EGAT", "year": 2023, "export_gwh": 235.3, "import_gwh": 65.5},
        {"grid_code": "TH_EGAT", "year": 2024, "export_gwh": 149.6, "import_gwh": 150.9},
    ]
    assert grid.flow_note(rows, "TH_EGAT") == (
        "Exported 235.3 GWh to Malaysia and imported 65.5 GWh in 2023; 149.6 and 150.9 GWh in 2024. Above 0 = Thailand exports"
    )
    assert grid.flow_note(rows, "SG_EMA") == "No Malaysia interconnector flows are published for this grid"


def test_flow_daily_keeps_malaysia_2023_24_only_with_gaps_as_nan(grid):
    fd = pd.DataFrame(
        {
            "grid_key": 1,
            "counterparty": ["MY", "MY", "KH", "MY"],
            "date": ["2023-01-01", "2023-01-03", "2023-01-02", "2025-01-01"],
            "year": [2023, 2023, 2023, 2025],
            "net_flow_mw": [5.0, 7.0, 99.0, 1.0],
        }
    )
    out = grid.flow_daily({"grid_flow_daily": fd}, 1)
    assert list(out["date"].dt.strftime("%Y-%m-%d")) == ["2023-01-01", "2023-01-02", "2023-01-03"]
    assert out["net_flow_mw"].isna().tolist() == [False, True, False]


def test_monthly_takes_peaks_from_the_port_rows_and_the_load_factor_unrounded(grid):
    f = synthetic()
    g = {"grid_code": "X", "grid_key": 1}
    rows = [
        {"grid_code": "X", "year": 2023, "month": 1, "peak_mw": 123.0},
        {"grid_code": "X", "year": 2023, "month": 2, "peak_mw": 133.0},
        {"grid_code": "X", "year": 2023, "month": None, "peak_mw": 133.0},  # the whole-year row is not a month
        {"grid_code": "Y", "year": 2023, "month": 1, "peak_mw": 999.0},  # another grid
    ]
    m = grid.monthly(f, g, rows)
    assert list(m["month_name"]) == ["Jan", "Feb"] and list(m["peak_mw"]) == [123.0, 133.0]
    assert list(m["load_factor_pct"]) == pytest.approx([100 * 111.5 / 123, 100 * 121.5 / 133])
    table = grid.by_month(m, "peak_mw", 0)
    assert list(table.columns) == ["Month", "2023"] and list(table["Month"]) == ["Jan", "Feb"]
    assert grid.monthly(f, g, []).empty


def test_summaries_say_the_unit_and_survive_empty_data(grid):
    m = pd.DataFrame(
        {"year": [2023, 2024], "month_name": ["Jan", "Feb"], "peak_mw": [10.0, 20.0], "load_factor_pct": [70.04, 80.06]}
    )
    assert grid.monthly_summary(m, "load_factor_pct", "%") == (
        "The highest load factor is 80.1% (Feb 2024) and the lowest 70.0% (Jan 2023)."
    )
    assert grid.monthly_summary(m, "peak_mw", "MW").startswith("The highest monthly peak is 20 MW (Feb 2024)")
    assert grid.monthly_summary(m.iloc[0:0], "peak_mw", "MW") == "No monthly values are published for this grid."
    assert grid.heatmap_summary(pd.DataFrame()) == "No hourly load is published for this grid."
