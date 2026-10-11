"""The Generation page (report page P2, M6 step 4): the takeaway title, the TWh / % mix area, the target line, the
capacity-factor bar with its note, the demand and growth columns, the three slicers, the empty state, the footnote and
the credits equal what the report's DAX gives for the same selection. Expected values are computed here straight from
the exported views, never from app/showcase/annual.py."""

import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
PAGE = str(ROOT / "app" / "pages" / "generation.py")
P2 = ROOT / "report/EnergyTransition.Report/definition/pages/p2_generation/visuals"

from showcase import annual, data

F = data.frames()
YEARS = list(F["dim_year"]["year"])
FIRST, LAST = YEARS[0], YEARS[-1]
SOURCES = F["dim_source"].sort_values("sort_order")
COLOURS = dict(zip(SOURCES["display_name"], SOURCES["color_hex"], strict=True))
ND = "Capacity not reported or inconsistent with generation for "


def fmt(x: float, digits: int = 1) -> str:
    """DAX FORMAT(x, "0.0"): half away from zero."""
    return f"{Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP):.{digits}f}"


def data_as_of() -> str:
    d = pd.to_datetime(F["run_latest"]["finished_at"]).max()
    return f"Data as of {d.day} {d:%b %Y}"


def my_gen() -> pd.DataFrame:
    ga = F["generation_annual"].merge(F["dim_source"], on="source_key")
    return ga[ga["country_key"] == 1]


def run(years=None, unit=None, sources=None):
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    if years:
        at.select_slider(key="generation_years").set_range(*years).run()
    if unit:
        at.radio(key="generation_unit").set_value(unit).run()
    if sources:
        at.multiselect(key="generation_sources").set_value(sources).run()
    assert not at.exception
    return at


def chart_specs(at) -> list[dict]:
    return [json.loads(c.proto.spec) for c in at.get("plotly_chart")]


def trace_by_name(spec: dict) -> dict:
    return {t["name"]: t for t in spec["data"]}


def textbox(visual: str) -> list[str]:
    d = json.loads((P2 / visual / "visual.json").read_text(encoding="utf-8"))
    paragraphs = d["visual"]["objects"]["general"][0]["properties"]["paragraphs"]
    return ["".join(r["value"] for r in p["textRuns"]) for p in paragraphs]


def fossil(year: int) -> float:
    ca = F["country_annual"]
    return ca[(ca["country_key"] == 1) & (ca["year"] == year)]["fossil_share_gen_pct"].iloc[0]


# --- title, subtitle and the year-range slicer (frame_title, frame_subtitle, p2_year_slicer) ---


def test_the_title_is_the_dax_takeaway_for_the_default_range():
    at = run()
    assert at.title[0].value == f"Malaysia: fossil fuels supplied {fmt(fossil(LAST))}% of electricity in {LAST}"
    assert at.caption[0].value == f"Malaysia · {FIRST}–{LAST} · {data_as_of()}"  # Generation Subtitle


def test_the_title_follows_the_last_year_of_the_range():
    at = run(years=(1990, 2010))
    assert at.title[0].value == f"Malaysia: fossil fuels supplied {fmt(fossil(2010))}% of electricity in 2010"
    assert at.caption[0].value == f"Malaysia · 1990–2010 · {data_as_of()}"


def test_the_range_slicer_defaults_to_every_year():
    slider = run().select_slider(key="generation_years")
    assert slider.value == (FIRST, LAST)
    assert slider.label == "Years"


def test_reset_filters_brings_the_defaults_back():
    at = run(years=(2000, 2005), unit="%", sources=["Coal"])
    next(b for b in at.button if "Reset filters" in b.label).click().run()
    assert at.select_slider(key="generation_years").value == (FIRST, LAST)
    assert at.radio(key="generation_unit").value == "TWh"
    assert at.multiselect(key="generation_sources").value == []


# --- mix area and the Unit / Source slicers (p2_mix_area, p2_unit_slicer, p2_source_slicer) ---


def test_the_unit_slicer_offers_twh_and_percent_and_starts_on_twh():
    radio = run().radio(key="generation_unit")
    assert radio.label == "Unit" and radio.options == ["TWh", "%"] and radio.value == "TWh"


def test_the_source_slicer_lists_the_seven_sources_and_starts_empty():
    box = run().multiselect(key="generation_sources")
    assert box.label == "Source" and box.options == list(SOURCES["display_name"]) and box.value == []


def test_the_mix_area_stacks_the_sources_in_twh_over_the_range():
    at = run(years=(2000, 2010))
    mix = chart_specs(at)[0]["data"]
    assert [t["name"] for t in mix] == list(SOURCES["display_name"])
    assert [t["line"]["color"] for t in mix] == list(SOURCES["color_hex"])
    assert all(t["stackgroup"] == "one" for t in mix)
    g = my_gen()
    hydro = g[(g["display_name"] == "Hydro") & g["year"].between(2000, 2010)].sort_values("year")
    by_name = trace_by_name(chart_specs(at)[0])
    assert by_name["Hydro"]["x"] == list(range(2000, 2011))
    assert by_name["Hydro"]["y"] == pytest.approx(list(hydro["generation_twh"]))


def test_the_percent_unit_shows_each_sources_share_of_the_years_whole_mix():
    at = run(unit="%")
    mix = trace_by_name(chart_specs(at)[0])
    g = my_gen()
    coal = g[g["display_name"] == "Coal"].sort_values("year")
    total = g.groupby("year")["generation_twh"].sum()
    want = [100 * v / total[y] for v, y in zip(coal["generation_twh"], coal["year"], strict=True)]
    assert mix["Coal"]["y"] == pytest.approx(want, abs=0.001)
    stacked = [sum(t["y"][i] for t in mix.values()) for i in range(len(YEARS))]
    assert stacked == pytest.approx([100.0] * len(YEARS), abs=0.01)


def test_a_source_selection_keeps_the_share_of_the_whole_mix():
    """Ctx Generation Share is divided by the whole mix, so a source slicer never inflates the shares."""
    all_sources = trace_by_name(chart_specs(run(unit="%"))[0])["Solar"]["y"]
    only_solar = chart_specs(run(unit="%", sources=["Solar"]))[0]["data"]
    assert [t["name"] for t in only_solar] == ["Solar"]
    assert only_solar[0]["y"] == pytest.approx(all_sources, abs=1e-9)


def test_the_source_slicer_narrows_the_capacity_factor_bar_too():
    at = run(sources=["Coal", "Gas"])
    bar = chart_specs(at)[2]["data"][0]
    assert sorted(bar["y"]) == ["Coal", "Gas"]


# --- capacity factor bar and note (p2_cf_bar, p2_cf_note) ---


def cf(year: int, source: str) -> float | None:
    g = my_gen()
    r = g[(g["display_name"] == source) & (g["year"] == year)].iloc[0]
    hours = int(F["dim_year"].set_index("year").at[year, "hours_in_year"])
    cap, gen = r["capacity_gw"], r["generation_twh"]
    if pd.isna(cap) or not cap > 0 or 1000 * gen > cap * hours:
        return None
    return 100 * 1000 * gen / (cap * hours)


@pytest.mark.parametrize("year", [2025, 2024, 2012])  # 2024 is a leap year: 8,784 hours
def test_the_capacity_factor_bar_is_generation_over_capacity_times_hours(year):
    at = run(years=(2000, year))
    bar = chart_specs(at)[2]["data"][0]
    want = {s: cf(year, s) for s in SOURCES["display_name"] if cf(year, s) is not None}
    assert dict(zip(bar["y"], bar["x"], strict=True)) == pytest.approx(want, abs=0.01)
    assert bar["orientation"] == "h"
    assert all(COLOURS[s] == c for s, c in zip(bar["y"], bar["marker"]["color"], strict=True))
    assert chart_specs(at)[2]["layout"]["xaxis"]["range"] == [0, 100]
    assert f"Capacity factor by source, {year} (%)" in [m.value.strip("*") for m in at.markdown]


def test_the_capacity_factor_hover_shows_its_inputs():
    bar = chart_specs(run())[2]["data"][0]
    hover = bar.get("hovertemplate", "") + " ".join(map(str, bar.get("hovertext", [])))
    assert "capacity" in hover.lower() and "generation" in hover.lower() and "hours" in hover.lower()


def test_the_capacity_factor_note_names_sources_with_no_usable_capacity():
    at = run(years=(FIRST, 1990))  # Ember has no capacity before 2000
    g = my_gen()
    names = [
        s
        for s in SOURCES["display_name"]
        if g[(g["display_name"] == s) & (g["year"] == 1990)].iloc[0]["generation_twh"] > 0
    ]
    assert names, "the test needs sources that generated in 1990"
    note = f"{ND}{', '.join(names)} in 1990, so shown blank, not 0. CF = generation ÷ (capacity × hours in year)."
    assert note in [c.value for c in at.caption]
    assert chart_specs(at)[2]["data"][0]["x"] == []  # nothing to draw, and the note says why


def test_the_capacity_factor_note_is_absent_when_every_factor_can_be_shown():
    at = run(sources=["Coal", "Gas", "Hydro", "Solar"])
    assert not any(c.value.startswith(ND) for c in at.caption)


# --- demand columns and growth (p2_demand_cols, p2_growth_cols) ---


def test_demand_and_growth_columns_cover_the_range():
    at = run(years=(2000, 2010))
    demand, growth = chart_specs(at)[3]["data"][0], chart_specs(at)[4]["data"][0]
    ca = F["country_annual"]
    ca = ca[ca["country_key"] == 1].set_index("year")["demand_twh"]
    assert demand["x"] == growth["x"] == list(range(2000, 2011))
    assert demand["y"] == pytest.approx([ca[y] for y in range(2000, 2011)])
    # growth looks one year back even beyond the range's first year (Ctx Demand Growth uses y - 1)
    assert growth["y"] == pytest.approx([100 * (ca[y] - ca[y - 1]) / ca[y - 1] for y in range(2000, 2011)], abs=0.001)
    assert demand["marker"]["color"] == "#104281" and growth["marker"]["color"] == "#256abf"


def test_the_first_year_of_the_data_has_no_growth_bar():
    growth = chart_specs(run(years=(FIRST, FIRST + 3)))[4]["data"][0]
    assert growth["x"][0] == FIRST and growth["y"][0] is None
    assert None not in growth["y"][1:]


# --- target line (p2_target_line) ---


def test_the_target_line_spans_2000_to_2050_and_ignores_the_range():
    wide = chart_specs(run())[1]
    narrow = chart_specs(run(years=(2005, 2008)))[1]
    assert wide["data"] == narrow["data"]  # the report's NoFilter interaction on this chart
    lines = {t["name"]: t for t in wide["data"]}
    ember, official, target = lines["Ember grid basis (%)"], lines["Official (%)"], lines["Target (%)"]
    ca = F["country_annual"]
    ca = ca[(ca["country_key"] == 1) & (ca["year"] >= 2000)].dropna(subset=["re_share_capacity_pct"])
    assert ember["x"] == list(ca["year"]) and ember["y"] == pytest.approx(list(ca["re_share_capacity_pct"]))
    assert (official["x"], official["y"]) == ([2025], [31.0])
    assert (target["x"], target["y"]) == ([2025, 2030, 2035, 2050], [31.0, 35.0, 40.0, 70.0])
    assert target["line"]["dash"] == "dash"
    assert wide["layout"]["yaxis"]["range"] == [0, 100]
    hover = " ".join(map(str, target.get("hovertext", []))) + target.get("hovertemplate", "")
    assert "12th Malaysia Plan" in hover and "National Energy Transition Roadmap" in hover  # cites its sources


# --- empty state (p2_empty_state) ---


def test_a_source_with_no_generation_in_the_range_says_so(monkeypatch):
    real = data.frames

    def no_solar():
        f = real()
        ga = f["generation_annual"].copy()
        solar = f["dim_source"].set_index("source_code").at["SOLAR", "source_key"]
        ga.loc[ga["source_key"] == solar, "generation_twh"] = float("nan")
        return {**f, "generation_annual": ga}

    monkeypatch.setattr(data, "frames", no_solar)
    st.cache_data.clear()
    try:
        assert not any("generation in this period" in i.value for i in run().info)  # nothing filtered
        assert any(i.value == "No Solar generation in this period" for i in run(sources=["Solar"]).info)
        assert not any("generation in this period" in i.value for i in run(sources=["Coal"]).info)
    finally:
        st.cache_data.clear()


def test_a_source_that_generated_nothing_is_not_an_empty_state():
    """No Source Generation Message tests ISBLANK, and a sum of zeros is 0, not blank: wind & other RE is all zeros."""
    at = run(sources=["Wind & other renewables"])
    assert not any("generation in this period" in i.value for i in at.info)


# --- footnote, credits, summaries, "Show data" (frame_footnote) ---


def test_the_footnote_and_the_credits():
    at = run()
    captions = " ".join(c.value for c in at.caption)
    assert textbox("frame_footnote")[0] in captions
    assert "Ember (2026), Yearly Electricity Data, CC BY 4.0" in captions
    assert "Our World in Data" not in captions  # P2 draws on D1 only


def test_each_chart_has_a_text_summary_and_show_data():
    at = run()
    charts = at.get("plotly_chart")
    assert len(charts) == 5
    captions = [c.value for c in at.caption]
    for chart in charts:
        assert chart.proto.alt and chart.proto.alt in captions
    assert [e.label for e in at.expander].count("Show data") == 5


def test_the_charts_carry_the_reports_titles():
    titles = [m.value.strip("*") for m in run().markdown]
    for t in (
        "Generation by source (TWh or % of the year's total, per the Unit toggle)",
        "National RE capacity targets: share of installed capacity (%)",
        "Electricity demand (TWh)",
        "Demand growth, year on year (%)",
    ):
        assert t in titles


def test_the_data_quality_badge_shows_in_the_sidebar_when_a_rule_fails(monkeypatch):
    real = data.frames

    def one_failing():
        f = real()
        return {**f, "dq_latest": f["dq_latest"].assign(status=["FAIL"] + ["PASS"] * (len(f["dq_latest"]) - 1))}

    assert not run().sidebar.error  # the exported run has no FAIL
    monkeypatch.setattr(data, "frames", one_failing)
    st.cache_data.clear()
    try:
        assert "1 data-quality rule failing" in run().sidebar.error[0].value  # frame_nav_badge
    finally:
        st.cache_data.clear()


# --- annual.py units ---


def test_the_capacity_factor_table_names_why_a_factor_is_blank():
    rows = annual.capacity_factors(F, 1990, [])
    assert set(rows["reason"].dropna()) <= {
        "CAPACITY_NOT_REPORTED",
        "GENERATION_NOT_REPORTED",
        "NO_CAPACITY",
        "CF_ABOVE_100",
    }
    assert rows["capacity_factor_pct"].isna().all()  # no capacity before 2000
    assert list(rows["source"]) == list(SOURCES["display_name"])


def test_capacity_factor_note_lists_only_sources_that_generated():
    rows = pd.DataFrame(
        {
            "source": ["Coal", "Gas", "Solar"],
            "generation_twh": [1.0, 0.0, 2.0],
            "capacity_factor_pct": [None, None, 50.0],
            "reason": ["CAPACITY_NOT_REPORTED", "CAPACITY_NOT_REPORTED", None],
        }
    )
    assert (
        annual.capacity_factor_note(rows, 2001)
        == f"{ND}Coal in 2001, so shown blank, not 0. CF = generation ÷ (capacity × hours in year)."
    )
    assert annual.capacity_factor_note(rows.iloc[2:], 2001) is None


def test_no_source_message_needs_a_selection():
    assert annual.no_source_message(F, FIRST, LAST, []) is None
    assert annual.no_source_message(F, FIRST, LAST, ["Solar"]) is None  # Solar has generation in the range


def test_target_axis_years():
    axis = annual.target_axis(F)
    assert list(axis["year"]) == [*range(2000, 2026), 2030, 2035, 2050]
