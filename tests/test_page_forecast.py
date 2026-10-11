"""The Forecast page (P4b, M6 step 4): each report item has an app element, and its numbers are the report's.

Expected numbers come from `exports/expected.json` (the SQL twins), from `docs/forecast.md` (the locked protocol's
results table, which the report page also shows) or from plain pandas, never from the code under test. Unit tests
cover the pure functions in `app/showcase/grid.py` (the DAX blank states and branches)."""

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
PAGE = str(APP / "pages" / "forecast.py")
REPORT = ROOT / "report/EnergyTransition.Report/definition/pages"
TH = "Thailand national grid (EGAT)"
SG = "Singapore national grid (EMA)"
# docs/forecast.md "Results (2024 backtest)": improvement over seasonal naive and over the weekday-aware naive.
DOCS = {
    "TH_EGAT": {"main": "46.9% lower MAPE (95% CI 39.3 to 52.8)", "second": "33.9% lower MAPE (95% CI 26.0 to 40.1)"},
    "SG_EMA": {"main": "34.5% lower MAPE (95% CI 26.2 to 41.7)", "second": "24.4% lower MAPE (95% CI 15.7 to 32.4)"},
}


# ---------------------------------------------------------------- helpers
def arr(x) -> np.ndarray:
    """A figure field as numpy: plotly 6+ writes numpy input as {"dtype", "bdata"[, "shape"]}."""
    if isinstance(x, dict) and "bdata" in x:
        a = np.frombuffer(base64.b64decode(x["bdata"]), dtype=np.dtype(x["dtype"]))
        return a.reshape([int(s) for s in x["shape"].split(",")]) if "shape" in x else a
    return np.array(x, dtype=float)


def figure(at) -> dict:
    (chart,) = at.get("plotly_chart")
    return json.loads(chart.proto.spec)


def captions(at) -> list[str]:
    return [c.value for c in at.caption]


def markdown(at) -> list[str]:
    return [m.value for m in at.markdown]


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


def metrics(at) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


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


def whole_run(expected, code) -> dict:
    return next(r for r in expected["09_forecast_metrics"] if r["grid_code"] == code and r["month"] is None)


def as_of(frames) -> str:
    d = pd.to_datetime(frames["run_latest"]["finished_at"]).max()
    return f"Data as of {d.day} {d:%b %Y}"


# ---------------------------------------------------------------- the page: frame items
def test_renders_without_exception(th, sg):
    assert not th.exception and not sg.exception


@pytest.mark.parametrize(("code", "country", "grid"), [("TH_EGAT", "Thailand", None), ("SG_EMA", "Singapore", SG)])
def test_title_is_the_dax_takeaway(expected, code, country, grid):
    """frame_title = [P4 Title]: the improvement over the baseline, rounded to a whole percent."""
    pct = whole_run(expected, code)["improvement_pct"]
    assert run(grid).title[0].value == f"{country}: day-ahead forecast cuts hourly error by {pct:.0f}%"


def test_the_grid_widget_switches_the_whole_page(expected):
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert widget(at, "selectbox", "Grid").value == TH
    widget(at, "selectbox", "Grid").select(SG).run()
    assert at.title[0].value == "Singapore: day-ahead forecast cuts hourly error by 35%"
    assert at.session_state["grid_name"] == SG  # remembered for the Grid load page
    assert "Showing: Singapore national grid (EMA)" in at.info[0].value
    assert metrics(at)["Model MAPE (%)"] == "1.64"  # docs/forecast.md: Singapore 1.64%


def test_subtitle_banner_and_footer(th, sg, frames):
    """frame_subtitle = [P4 Forecast Subtitle], p4b_banner = [Grid Banner], frame_footnote verbatim then credits."""
    assert captions(th)[0] == f"Sum of regional demand (EGAT) · day-ahead backtest, 2024 · local time · {as_of(frames)}"
    assert captions(sg)[0] == f"System demand (EMA) · day-ahead backtest, 2024 · local time · {as_of(frames)}"
    assert th.info[0].value.startswith("Showing: Thailand national grid (EGAT) · Open-data stand-in")
    caps = captions(th)
    assert caps[-2] == report_text("p4b_forecast", "frame_footnote")
    ds = frames["data_source"].set_index("data_source_code")["credit_text"]
    assert caps[-1].startswith("Credits: ") and ds["DTH"] in caps[-1] and ds["DSG"] in caps[-1]


def test_no_reset_button(th):
    assert not th.button


def test_the_grid_choice_made_on_the_other_page_is_kept(sg):
    assert widget(sg, "selectbox", "Grid").value == SG


# ---------------------------------------------------------------- the page: cards, verdict, window
@pytest.mark.parametrize(("code", "grid"), [("TH_EGAT", None), ("SG_EMA", SG)])
def test_the_five_cards_are_the_backtest_measures(expected, code, grid):
    """p4b_card_*: [Backtest MAPE Model/Baseline (%)] 0.00, [Improvement (%)] 0.0, [MAE Model/Baseline (MW)] #,0."""
    r = whole_run(expected, code)
    assert metrics(run(grid)) == {
        "Model MAPE (%)": f"{r['mape_model']:.2f}",
        "Baseline MAPE (%)": f"{r['mape_baseline']:.2f}",
        "Improvement (%)": f"{r['improvement_pct']:.1f}",
        "Model MAE (MW)": f"{r['mae_model']:,.0f}",
        "Baseline MAE (MW)": f"{r['mae_baseline']:,.0f}",
    }


def test_the_thailand_cards_match_the_published_results(th):
    assert metrics(th) == {
        "Model MAPE (%)": "3.31",
        "Baseline MAPE (%)": "6.23",
        "Improvement (%)": "46.9",
        "Model MAE (MW)": "810",
        "Baseline MAE (MW)": "1,485",
    }


def test_card_tooltips_list_the_other_backtest_measures(th):
    """The cards' Tooltips field well: the window, the CI and the MAE pair, each card leaving out its own measure."""
    tips = {m.label: m.help for m in th.metric}
    mape = tips["Model MAPE (%)"]
    assert "Backtest Window: Backtest 1 Jan 2024 – 31 Dec 2024 · 8,778 hours scored, 6 excluded" in mape
    assert "Backtest Improvement CI: 95% CI 39.3 to 52.8" in mape
    assert "Backtest MAE Model (MW): 810" in mape and "Backtest MAE Baseline (MW): 1,485" in mape
    assert (
        "Backtest MAE Model (MW)" not in tips["Model MAE (MW)"]
        and "Backtest MAE Baseline (MW): 1,485" in tips["Model MAE (MW)"]
    )
    assert "Backtest MAE Baseline (MW)" not in tips["Baseline MAE (MW)"]


@pytest.mark.parametrize(("code", "grid"), [("TH_EGAT", None), ("SG_EMA", SG)])
def test_verdict_secondary_and_window_are_the_reports_sentences(expected, code, grid):
    """p4b_verdict = [Forecast Verdict], p4b_secondary = [Forecast Secondary], p4b_window = [Backtest Window]."""
    at = run(grid)
    assert [s.value for s in at.success] == [f"Beats the seasonal-naive baseline: {DOCS[code]['main']}"]
    assert not at.warning
    assert f"Also beats a weekday-aware naive rule: {DOCS[code]['second']}" in markdown(at)
    scored = whole_run(expected, code)["scored_hours"]
    excluded = 6 if code == "TH_EGAT" else 0  # docs/forecast.md results table
    assert f"Backtest 1 Jan 2024 – 31 Dec 2024 · {scored:,} hours scored, {excluded} excluded" in markdown(at)


# ---------------------------------------------------------------- the page: date slicer and chart
def test_nothing_picked_shows_the_grids_2024_peak_day(th, sg, expected):
    """p4b_date_slicer default + [Forecast Default Day]: the day of the highest actual hour."""
    day = widget(th, "selectbox", "Backtest day")
    assert day.value is None and len(day.options) == 366
    assert figure(th)["layout"]["title"]["text"] == "Forecast vs actual, Mon 29 Apr 2024 (2024 peak day)"
    peak = pd.Timestamp(
        next(
            r for r in expected["08_grid_load"] if r["grid_code"] == "SG_EMA" and r["year"] == 2024 and not r["month"]
        )["peak_at"]
    )
    assert (
        figure(sg)["layout"]["title"]["text"]
        == f"Forecast vs actual, {peak:%a} {peak.day} {peak:%b %Y} (2024 peak day)"
    )


def test_the_default_day_chart_is_actual_model_baseline_by_hour(th, frames):
    """p4b_fc_line = [Day Actual/Model/Baseline (MW)] over the 24 hours; baseline dashed, nothing by colour alone."""
    fig = figure(th)
    traces = {t["name"]: t for t in fig["data"]}
    assert list(traces) == ["Day Actual (MW)", "Day Model (MW)", "Day Baseline (MW)"]
    day = frames["load_forecast_current"].query("grid_key == 1 and date_key == 20240429").sort_values("hour")
    for name, col in (
        ("Day Actual (MW)", "actual_mw"),
        ("Day Model (MW)", "forecast_mw"),
        ("Day Baseline (MW)", "baseline_mw"),
    ):
        np.testing.assert_allclose(arr(traces[name]["y"]), day[col].to_numpy())
        assert list(arr(traces[name]["x"])) == list(range(24))
    assert traces["Day Baseline (MW)"]["line"]["dash"] != traces["Day Actual (MW)"]["line"]["dash"]
    assert [t["line"]["color"] for t in fig["data"]] == ["#0b0b0b", "#104281", "#52514e"]  # the report's lines
    assert "MW" in traces["Day Model (MW)"]["hovertemplate"]


def test_picking_another_day_changes_the_line(frames):
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    before = figure(at)
    widget(at, "selectbox", "Backtest day").select(date(2024, 1, 15)).run()
    fig = figure(at)
    assert fig["layout"]["title"]["text"] == "Forecast vs actual, Mon 15 Jan 2024"  # no peak-day suffix when picked
    day = frames["load_forecast_current"].query("grid_key == 1 and date_key == 20240115").sort_values("hour")
    np.testing.assert_allclose(arr(fig["data"][0]["y"]), day["actual_mw"].to_numpy())
    assert fig["data"][0]["y"] != before["data"][0]["y"]
    widget(at, "selectbox", "Backtest day").set_value(None).run()  # clearing the pick returns to the peak day
    assert figure(at)["layout"]["title"]["text"].endswith("(2024 peak day)")


def test_the_chart_has_a_summary_and_a_data_table(th):
    (chart,) = th.get("plotly_chart")
    assert chart.proto.alt and chart.proto.alt in captions(th)
    assert [e.label for e in th.expander] == ["Show data"]
    table = th.dataframe[0].value
    assert len(table) == 24 and {"Day Actual (MW)", "Day Model (MW)", "Day Baseline (MW)"} <= set(table.columns)


# ---------------------------------------------------------------- the page: empty and error states
def patched(monkeypatch, **edits):
    """Run the page on frames altered by `edits` {frame name: function}, then restore the cache."""
    import streamlit as st
    from showcase import data

    real = data.frames

    def altered():
        f = real()
        for name, edit in edits.items():
            f[name] = edit(f[name])
        return f

    monkeypatch.setattr(data, "frames", altered)
    st.cache_data.clear()
    return st


def test_a_day_outside_the_window_shows_the_empty_state(monkeypatch):
    """p4b_fc_empty = [Forecast Empty State]; the line has nothing to draw."""
    st = patched(monkeypatch, forecast_run_current=lambda d: d.assign(test_start="2024-02-01", test_end="2024-02-29"))
    try:
        at = run()  # the peak day (29 Apr) is outside the shortened window
        assert "Forecast available for 1 Feb 2024 – 29 Feb 2024" in [i.value for i in at.info]
        assert not at.get("plotly_chart")
        widget(at, "selectbox", "Backtest day").select(date(2024, 2, 10)).run()
        assert len(at.get("plotly_chart")) == 1 and not any(i.value.startswith("Forecast available") for i in at.info)
    finally:
        st.cache_data.clear()


def test_a_failed_forecast_step_shows_the_error_state(monkeypatch):
    """p4b_fc_error = [Forecast Error State]."""
    st = patched(monkeypatch, forecast_status=lambda d: d.assign(status="FAILED"))
    try:
        at = run()
        assert "Forecast not generated in latest run — see About page" in [w.value for w in at.warning]
    finally:
        st.cache_data.clear()


def test_no_state_message_when_everything_is_fine(th):
    assert [i.value for i in th.info] == [th.info[0].value]  # only the banner
    assert not th.warning


# ---------------------------------------------------------------- grid.py: the pure functions
@pytest.fixture(scope="module")
def grid():
    from showcase import grid

    return grid


RUN = {
    "model_run_id": 7,
    "grid_key": 1,
    "test_start": "2024-01-01",
    "test_end": "2024-12-31",
    "scored_hours": 8778,
    "excluded_hours": 6,
    "mape_model": 3.309,
    "mape_baseline": 6.227,
    "mae_model": 809.989,
    "mae_baseline": 1485.304,
    "improvement_pct": 46.864,
    "improvement_ci_low": 39.324,
    "improvement_ci_high": 52.849,
    "beats_baseline": True,
    "improvement_weekday_pct": 33.932,
    "improvement_weekday_ci_low": 26.007,
    "improvement_weekday_ci_high": 40.064,
}
GRID = {"grid_key": 1, "country_name": "Thailand", "demand_label": "Sum of regional demand (EGAT)"}


def test_title_branches(grid):
    assert grid.forecast_title(GRID, RUN) == "Thailand: day-ahead forecast cuts hourly error by 47%"
    assert (
        grid.forecast_title(GRID, {**RUN, "improvement_pct": -3.2})
        == "Thailand: day-ahead forecast does not beat the baseline"
    )
    assert (
        grid.forecast_title(GRID, {**RUN, "improvement_pct": 0.0})
        == "Thailand: day-ahead forecast does not beat the baseline"
    )
    assert grid.forecast_title(GRID, None) == "Thailand: hourly grid load"


def test_verdict_branches_and_blank(grid):
    assert grid.verdict(RUN) == (True, "Beats the seasonal-naive baseline: 46.9% lower MAPE (95% CI 39.3 to 52.8)")
    ok, text = grid.verdict({**RUN, "beats_baseline": False})
    assert not ok and text.startswith("WARN: does not beat the seasonal-naive baseline (the 95% CI includes 0)")
    assert grid.verdict(None) is None


def test_secondary_branches_and_blank(grid):
    assert grid.secondary(RUN) == "Also beats a weekday-aware naive rule: 33.9% lower MAPE (95% CI 26.0 to 40.1)"
    weak = {**RUN, "improvement_weekday_ci_low": -15.3, "improvement_weekday_ci_high": 24.6}
    assert (
        grid.secondary(weak)
        == "Its edge over a simple weekday-aware naive rule is not established (95% CI -15.3 to 24.6 includes 0)"
    )
    assert grid.secondary({**RUN, "improvement_weekday_ci_low": None}) is None and grid.secondary(None) is None


def test_window_and_ci_text(grid):
    assert grid.backtest_window(RUN) == "Backtest 1 Jan 2024 – 31 Dec 2024 · 8,778 hours scored, 6 excluded"
    assert grid.improvement_ci(RUN) == "95% CI 39.3 to 52.8"
    assert grid.backtest_window(None) is None and grid.improvement_ci(None) is None


def test_card_values_use_the_reports_formats(grid):
    cards = {label: value for label, value, _ in grid.cards(RUN)}
    assert cards == {
        "Model MAPE (%)": "3.31",
        "Baseline MAPE (%)": "6.23",
        "Improvement (%)": "46.9",
        "Model MAE (MW)": "810",
        "Baseline MAE (MW)": "1,485",
    }
    assert [label for label, _, _ in grid.cards(None)] and all(v == "" for _, v, _ in grid.cards(None))


def frames_for_days():
    rows = []
    for key, hours, peak in ((20240301, range(24), 100.0), (20240302, range(24), 100.0), (20240303, range(3), 50.0)):
        for h in hours:
            actual = peak if h == 5 else 10.0
            rows.append(
                {
                    "grid_key": 1,
                    "ts_local": f"{str(key)[:4]}-{str(key)[4:6]}-{str(key)[6:]}T{h:02d}:00:00",
                    "date_key": key,
                    "hour": h,
                    "actual_mw": actual,
                    "forecast_mw": actual - 1,
                    "baseline_mw": actual + 1,
                    "is_scored": True,
                }
            )
    return {"load_forecast_current": pd.DataFrame(rows)}


def test_default_day_is_the_earliest_of_tied_peak_hours(grid):
    assert grid.default_day(frames_for_days(), 1) == date(2024, 3, 1)
    assert grid.default_day(frames_for_days(), 9) is None  # blank when the grid has no forecast rows


def test_day_series_is_24_hours_with_blanks_for_missing_hours(grid):
    s = grid.day_series(frames_for_days(), 1, date(2024, 3, 3))
    assert list(s["hour"]) == list(range(24))
    assert s["actual_mw"].notna().sum() == 3 and s["model_mw"].iloc[0] == 9.0 and s["baseline_mw"].iloc[1] == 11.0
    assert grid.day_series(frames_for_days(), 1, date(2024, 4, 1))["actual_mw"].isna().all()


def test_empty_and_error_states(grid):
    assert grid.empty_state(RUN, date(2023, 12, 31)) == "Forecast available for 1 Jan 2024 – 31 Dec 2024"
    assert grid.empty_state(RUN, date(2025, 1, 1)) == "Forecast available for 1 Jan 2024 – 31 Dec 2024"
    assert grid.empty_state(RUN, date(2024, 6, 1)) is None and grid.empty_state(None, date(2024, 6, 1)) is None
    ok = {"forecast_status": pd.DataFrame({"grid_key": [1], "status": ["SUCCESS"]})}
    bad = {"forecast_status": pd.DataFrame({"grid_key": [1], "status": ["FAILED"]})}
    msg = "Forecast not generated in latest run — see About page"
    assert grid.error_state(ok, 1) is None and grid.error_state(bad, 1) == msg
    assert grid.error_state(ok, 3) == msg  # DAX: a blank status is <> "SUCCESS"


def test_run_row_is_blank_unless_exactly_one_run(grid):
    f = {"forecast_run_current": pd.DataFrame([RUN, {**RUN, "grid_key": 3}, {**RUN, "grid_key": 3}])}
    assert grid.run_row(f, 1)["improvement_pct"] == 46.864
    assert grid.run_row(f, 3) is None and grid.run_row(f, 9) is None  # SELECTEDVALUE over 0 or 2+ rows


def test_day_title(grid):
    assert grid.day_title(date(2024, 4, 29), picked=False) == "Forecast vs actual, Mon 29 Apr 2024 (2024 peak day)"
    assert grid.day_title(date(2024, 1, 15), picked=True) == "Forecast vs actual, Mon 15 Jan 2024"
