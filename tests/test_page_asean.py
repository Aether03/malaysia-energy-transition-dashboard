"""The ASEAN page (report page P5 plus the Country Deep Dive drill-through D1 and the T2 country tooltip, M6 step 5):
the takeaway title, the country / metric / year slicers, the trend line, scatter and the two bars, the rank card, the
footnote, the country selector with its deep-dive section and the hover text equal what the report's DAX gives for the
same selection. Expected values are computed here straight from the exported views (or read from exports/expected.json,
the SQL twins' results), never from app/showcase/asean.py or annual.py."""

import itertools
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
PAGE = str(ROOT / "app" / "pages" / "asean.py")
PAGES = ROOT / "report/EnergyTransition.Report/definition/pages"

from showcase import annual, data, metrics

F = data.frames()
EXPECTED = data.expected()
YEARS = list(F["dim_year"]["year"])
FIRST, LAST = YEARS[0], YEARS[-1]
SOURCES = F["dim_source"].sort_values("sort_order")
COUNTRIES = F["dim_country"][F["dim_country"]["area_type"] == "COUNTRY"].sort_values("display_order")
KEY = dict(zip(COUNTRIES["name"], COUNTRIES["country_key"], strict=True))
DEFAULT_PEERS = list(COUNTRIES[COUNTRIES["is_default_peer"]]["name"])
NAVY, MUTED = "#104281", "#8a8984"
SELECTION = ["Malaysia", "Singapore", "Brunei", "Laos"]  # Brunei and Laos report to 2024


def asean():
    from showcase import asean as module  # imported here so a missing module fails these tests, not the whole file

    return module


def fmt(x: float, digits: int = 1) -> str:
    """DAX FORMAT(x, "0.0"): half away from zero."""
    return f"{Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP):.{digits}f}"


def data_as_of() -> str:
    d = pd.to_datetime(F["run_latest"]["finished_at"]).max()
    return f"Data as of {d.day} {d:%b %Y}"


def value(name: str, year: int, col: str) -> float:
    ca = F["country_annual"]
    return ca[(ca["country_key"] == KEY[name]) & (ca["year"] == year)][col].iloc[0]


def compare(names: list[str], last: int) -> dict:
    """The ASEAN measures worked out from the raw views: the latest year every country reports, ranks, values."""
    ca = F["country_annual"]
    sub = ca[ca["country_key"].isin([KEY[n] for n in names]) & (ca["year"] <= last)]

    def latest(col: str) -> int:
        return min(sub[(sub["country_key"] == KEY[n]) & sub[col].notna()]["year"].max() for n in names)

    year, pc_year = latest("re_share_gen_pct"), latest("demand_per_capita_mwh")
    at_year = sub[sub["year"] == year].set_index("country_key")
    share = {n: at_year.at[KEY[n], "re_share_gen_pct"] for n in names}
    intensity = {n: at_year.at[KEY[n], "emissions_intensity_gco2e_kwh"] for n in names}
    mine = "Malaysia"
    out = {"year": year, "per_capita_year": pc_year, "share": share, "intensity": intensity, "n": len(names)}
    if mine in names:
        out["re_rank"] = 1 + sum(v > share[mine] for v in share.values())
        out["int_rank"] = 1 + sum(v < intensity[mine] for v in intensity.values())
    return out


def title_for(names: list[str], last: int) -> str:
    c = compare(names, last)
    return (
        f"Malaysia: {c['re_rank']} of {c['n']} on renewable share, {c['int_rank']} of {c['n']} on carbon intensity "
        f"({c['year']})"
    )


def run(years=None, countries=None, metric=None, country=None, unit=None, sources=None):
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    if years:
        at.select_slider(key="asean_years").set_range(*years).run()
    if countries is not None:
        at.multiselect(key="asean_countries").set_value(countries).run()
    if metric:
        at.radio(key="asean_metric").set_value(metric).run()
    if country:
        at.selectbox(key="asean_country").set_value(country).run()
    if unit:
        at.radio(key="asean_unit").set_value(unit).run()
    if sources:
        at.multiselect(key="asean_sources").set_value(sources).run()
    assert not at.exception
    return at


def chart_specs(at) -> list[dict]:
    return [json.loads(c.proto.spec) for c in at.get("plotly_chart")]


# chart order on the page: P5 trend, intensity bar, scatter, per-capita bar, then the deep dive's four charts
TREND, INTENSITY, SCATTER, PERCAPITA, DEEP_MIX, DEEP_CF, DEEP_DEMAND, DEEP_GROWTH = range(8)


def textbox(page: str, visual: str) -> str:
    d = json.loads((PAGES / page / "visuals" / visual / "visual.json").read_text(encoding="utf-8"))
    runs = d["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"]
    return "".join(r["value"] for r in runs)


def hover_of(trace: dict) -> str:
    """Everything a trace shows on hover, whichever way it was written."""
    return trace.get("hovertemplate", "") + " ".join(map(str, trace.get("hovertext") or []))


def bold_free(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "")


# --- P5 title, subtitle, reset (frame_title, frame_subtitle, frame_reset) ---


def test_the_title_is_the_dax_takeaway_for_the_default_selection():
    at = run()
    assert at.title[0].value == title_for(DEFAULT_PEERS, LAST)
    assert at.title[0].value == "Malaysia: 4 of 6 on renewable share, 5 of 6 on carbon intensity (2025)"
    assert at.caption[0].value == f"ASEAN peers · {FIRST}–{LAST} · {data_as_of()}"  # ASEAN Subtitle


def test_the_title_follows_the_country_selection():
    at = run(countries=SELECTION)
    assert compare(SELECTION, LAST)["year"] == 2024  # Brunei and Laos stop in 2024
    assert at.title[0].value == title_for(SELECTION, LAST)
    assert "of 4 on renewable share" in at.title[0].value and "(2024)" in at.title[0].value


def test_the_title_follows_the_last_year_of_the_range():
    at = run(years=(2000, 2015))
    assert at.title[0].value == title_for(DEFAULT_PEERS, 2015)
    assert at.caption[0].value == f"ASEAN peers · 2000–2015 · {data_as_of()}"


def test_fewer_than_two_countries_say_so():
    at = run(countries=["Malaysia"])
    assert at.title[0].value == "Select at least two countries to compare"
    assert any("Select at least two countries to compare" in m.value for m in at.markdown)  # the rank card


def test_a_selection_without_malaysia_says_so():
    at = run(countries=["Indonesia", "Thailand"])
    assert at.title[0].value == "Malaysia is not in the current selection"


def test_reset_filters_brings_every_default_back():
    at = run(years=(2000, 2010), countries=SELECTION, metric="Emissions (MtCO2e)", country="Vietnam", unit="%")
    next(b for b in at.button if "Reset filters" in b.label).click().run()
    assert at.select_slider(key="asean_years").value == (FIRST, LAST)
    assert at.multiselect(key="asean_countries").value == []
    assert at.radio(key="asean_metric").value == "RE share (%)"
    assert at.selectbox(key="asean_country").value == "Malaysia"
    assert at.radio(key="asean_unit").value == "TWh"
    assert at.multiselect(key="asean_sources").value == []


# --- the slicers (p5_country_slicer, p5_metric_slicer, p5_year_slicer) ---


def test_the_country_slicer_lists_the_ten_asean_countries_and_starts_empty():
    box = run().multiselect(key="asean_countries")
    assert box.label == "Countries (none selected = the 6 default peers)"
    assert box.options == list(COUNTRIES["name"]) and len(box.options) == 10  # never the ASEAN aggregate
    assert box.value == []


def test_with_no_country_selected_the_six_default_peers_are_compared():
    traces = chart_specs(run())[TREND]["data"]
    assert sorted(t["name"] for t in traces) == sorted(DEFAULT_PEERS)
    assert "Brunei" not in {t["name"] for t in traces}


def test_the_selected_countries_are_compared_whatever_their_order():
    traces = chart_specs(run(countries=["Laos", "Brunei", "Malaysia"]))[TREND]["data"]
    assert [t["name"] for t in traces] == ["Brunei", "Laos", "Malaysia"]  # the report's order; Malaysia drawn on top


def test_the_metric_slicer_offers_the_three_metrics_and_starts_on_re_share():
    radio = run().radio(key="asean_metric")
    assert radio.label == "Trend metric"
    assert radio.options == ["RE share (%)", "Carbon intensity (gCO2e/kWh)", "Emissions (MtCO2e)"]
    assert radio.value == "RE share (%)"


def test_the_year_slicer_defaults_to_the_whole_range():
    slider = run().select_slider(key="asean_years")
    assert slider.label == "Years" and slider.value == (FIRST, LAST)


# --- trend line (p5_trend_line) ---

METRIC_COLUMNS = {
    "RE share (%)": "re_share_gen_pct",
    "Carbon intensity (gCO2e/kWh)": "emissions_intensity_gco2e_kwh",
    "Emissions (MtCO2e)": "emissions_mtco2e",
}


def headings(at) -> list[str]:
    return [m.value for m in at.markdown]


@pytest.mark.parametrize("metric", list(METRIC_COLUMNS))
def test_the_metric_selector_switches_the_trend_chart_and_its_title(metric):
    at = run(metric=metric)
    spec = chart_specs(at)[TREND]
    col = METRIC_COLUMNS[metric]
    ca = F["country_annual"]
    for trace in spec["data"]:
        mine = ca[(ca["country_key"] == KEY[trace["name"]]) & ca[col].notna()].sort_values("year")
        assert trace["x"] == list(mine["year"])
        assert trace["y"] == pytest.approx(list(mine[col]))
    assert spec["layout"]["yaxis"]["title"]["text"] == metric
    assert any(h.startswith(f"**Trend by country: {metric}**") for h in headings(at))
    assert metric in at.get("plotly_chart")[TREND].proto.alt  # the text summary names the metric


def test_the_trend_chart_changes_when_the_metric_changes():
    first = chart_specs(run())[TREND]["data"]
    second = chart_specs(run(metric="Carbon intensity (gCO2e/kWh)"))[TREND]["data"]
    assert [t["y"] for t in first] != [t["y"] for t in second]


def test_the_trend_chart_covers_the_selected_years_only():
    traces = chart_specs(run(years=(2005, 2010)))[TREND]["data"]
    assert all(t["x"] == list(range(2005, 2011)) for t in traces)


def test_malaysia_is_navy_and_thick_peers_muted_and_thin_and_every_line_is_labelled():
    spec = chart_specs(run())[TREND]
    lines = {t["name"]: t["line"] for t in spec["data"]}
    assert lines["Malaysia"] == {**lines["Malaysia"], "color": NAVY, "width": 2.5}
    assert all(line["color"] == MUTED and line["width"] == 1.5 for n, line in lines.items() if n != "Malaysia")
    labels = {a["text"] for a in spec["layout"]["annotations"]}  # direct labels at the line ends (doc 04 §3.3)
    assert labels == {"<b>Malaysia</b>" if n == "Malaysia" else n for n in lines}
    assert not spec["layout"].get("showlegend", False)  # the labels replace the legend, as in the report


def test_the_direct_labels_do_not_overlap_and_sit_at_the_line_ends():
    spec = chart_specs(run())[TREND]
    ends = {t["name"]: (t["x"][-1], t["y"][-1]) for t in spec["data"]}
    labels = sorted(spec["layout"]["annotations"], key=lambda a: a["y"])
    span = max(y for _, y in ends.values()) - min(y for _, y in ends.values())
    assert all(b["y"] - a["y"] >= 0.04 * span for a, b in itertools.pairwise(labels))
    for a in labels:
        name = bold_free(a["text"])
        assert a["x"] == ends[name][0]
        assert abs(a["y"] - ends[name][1]) <= 0.15 * span


# --- scatter (p5_scatter) ---


def test_the_scatter_plots_re_share_against_intensity_sized_by_demand():
    at = run()
    c = compare(DEFAULT_PEERS, LAST)
    trace = chart_specs(at)[SCATTER]["data"][0]
    order = trace["text"]
    names = [bold_free(t) for t in order]
    assert sorted(names) == sorted(DEFAULT_PEERS)
    assert trace["x"] == pytest.approx([c["share"][n] for n in names])
    assert trace["y"] == pytest.approx([c["intensity"][n] for n in names])
    assert trace["marker"]["size"] == pytest.approx([value(n, c["year"], "demand_twh") for n in names])
    assert any(b.startswith("**RE share vs carbon intensity (bubble = demand, TWh)") for b in headings(at))


def test_the_scatter_marks_malaysia_by_colour_symbol_and_label():
    trace = chart_specs(run())[SCATTER]["data"][0]
    for name, text, colour, symbol in zip(
        [bold_free(t) for t in trace["text"]],
        trace["text"],
        trace["marker"]["color"],
        trace["marker"]["symbol"],
        strict=True,
    ):
        if name == "Malaysia":
            assert (colour, symbol, text) == (NAVY, "diamond", "<b>Malaysia</b>")
        else:
            assert (colour, symbol, text) == (MUTED, "circle", name)
    assert trace["mode"] == "markers+text"


# --- the two bars (p5_intensity_bar, p5_percapita_bar) ---


def test_the_intensity_bar_lists_the_comparison_year_lowest_first():
    at = run()
    bar = chart_specs(at)[INTENSITY]["data"][0]
    c = compare(DEFAULT_PEERS, LAST)
    assert bar["orientation"] == "h"
    assert bar["y"] == sorted(DEFAULT_PEERS, key=lambda n: c["intensity"][n])
    assert bar["x"] == pytest.approx(sorted(c["intensity"].values()))
    assert any(
        h.startswith("**Carbon intensity at the comparison year (gCO2e/kWh), lowest first") for h in headings(at)
    )


def test_the_per_capita_bar_uses_the_common_per_capita_year_highest_first():
    at = run()
    bar = chart_specs(at)[PERCAPITA]["data"][0]
    c = compare(DEFAULT_PEERS, LAST)
    assert c["per_capita_year"] == 2024 != c["year"]  # Indonesia has no 2025 population yet
    per_capita = {n: value(n, c["per_capita_year"], "demand_per_capita_mwh") for n in DEFAULT_PEERS}
    assert bar["y"] == sorted(DEFAULT_PEERS, key=lambda n: -per_capita[n])
    assert bar["x"] == pytest.approx(sorted(per_capita.values(), reverse=True))
    assert any(h.startswith("**Demand per capita at the common year (MWh)") for h in headings(at))


@pytest.mark.parametrize("chart", [INTENSITY, PERCAPITA])
def test_the_bars_mark_malaysia_by_colour_and_a_bold_label(chart):
    spec = chart_specs(run())[chart]
    bar = spec["data"][0]
    colours = dict(zip(bar["y"], bar["marker"]["color"], strict=True))
    assert colours["Malaysia"] == NAVY and {c for n, c in colours.items() if n != "Malaysia"} == {MUTED}
    ticks = dict(zip(spec["layout"]["yaxis"]["tickvals"], spec["layout"]["yaxis"]["ticktext"], strict=True))
    assert ticks["Malaysia"] == "<b>Malaysia</b>" and ticks["Thailand"] == "Thailand"


def test_the_selection_changes_every_chart_and_the_comparison_year():
    at = run(countries=SELECTION)
    c = compare(SELECTION, LAST)
    bar = chart_specs(at)[INTENSITY]["data"][0]
    assert bar["y"] == sorted(SELECTION, key=lambda n: c["intensity"][n])
    assert bar["x"] == pytest.approx(sorted(c["intensity"].values()))
    assert {bold_free(t) for t in chart_specs(at)[SCATTER]["data"][0]["text"]} == set(SELECTION)
    assert sorted(chart_specs(at)[PERCAPITA]["data"][0]["y"]) == sorted(SELECTION)


# --- rank card (p5_rank_card) ---


def test_the_rank_card_equals_the_sql_twin_and_metrics_ranking():
    at = run()
    ranking = pd.DataFrame(metrics.ranking(F))
    row = ranking[ranking["name"] == "Malaysia"].iloc[0]
    label = f"Malaysia ranks {row['re_share_rank']} of {row['countries_compared']} on renewable share ({row['comparison_year']})"
    twin = next(r for r in EXPECTED["03_ranking"] if r["name"] == "Malaysia")
    assert (row["re_share_rank"], row["comparison_year"]) == (twin["re_share_rank"], twin["comparison_year"])
    cards = [m.value for m in at.markdown if label in m.value]
    assert cards, f"the rank card {label!r} is missing"
    table = next(d for d in at.dataframe if "RE share rank (1 = highest)" in d.value.columns).value
    assert list(table["Country"]) == list(ranking["name"])
    assert list(table["RE share rank (1 = highest)"]) == list(ranking["re_share_rank"])
    assert list(table["Intensity rank (1 = lowest)"]) == list(ranking["intensity_rank"])


def test_the_rank_card_follows_the_selection():
    c = compare(SELECTION, LAST)
    label = f"Malaysia ranks {c['re_rank']} of 4 on renewable share (2024)"
    assert any(label in m.value for m in run(countries=SELECTION).markdown)


# --- T2 country tooltip (t2_title, t2_card_0, t2_card_1, t2_mix_bar) ---


def mix_pct(name: str, year: int) -> dict[str, float]:
    ga = F["generation_annual"].merge(F["dim_source"], on="source_key")
    g = ga[(ga["country_key"] == KEY[name]) & (ga["year"] == year)]
    return {r.display_name: 100 * r.generation_twh / g["generation_twh"].sum() for r in g.itertuples()}


def test_hover_text_carries_the_t2_tooltip_fields():
    specs = chart_specs(run())
    year = compare(DEFAULT_PEERS, LAST)["year"]
    mix = mix_pct("Malaysia", year)
    texts = {
        "trend": next(t for t in specs[TREND]["data"] if t["name"] == "Malaysia"),
        "intensity": specs[INTENSITY]["data"][0],
        "scatter": specs[SCATTER]["data"][0],
        "percapita": specs[PERCAPITA]["data"][0],
    }
    for chart, trace in texts.items():
        hover = hover_of(trace)
        assert f"Malaysia · {year}" in hover, chart  # t2_title: the country and the comparison year
        assert f"RE share: {fmt(value('Malaysia', year, 're_share_gen_pct'))}%" in hover, chart  # t2_card_0
        intensity = f"{value('Malaysia', year, 'emissions_intensity_gco2e_kwh'):,.0f}"
        assert f"Carbon intensity: {intensity} gCO2e/kWh" in hover, chart  # t2_card_1
        for source in ("Coal", "Gas", "Hydro"):  # t2_mix_bar: the mix by source, in %
            assert f"{source} {fmt(mix[source])}%" in hover, chart


def test_hover_text_is_per_country_and_names_the_comparison_year_of_the_selection():
    trace = chart_specs(run(countries=SELECTION))[INTENSITY]["data"][0]
    laos = trace["hovertext"][trace["y"].index("Laos")]
    assert "Laos · 2024" in laos and "Malaysia ·" not in laos


def test_the_hover_also_shows_the_hovered_value():
    specs = chart_specs(run())
    my_trend = next(t for t in specs[TREND]["data"] if t["name"] == "Malaysia")
    assert "%{x}" in my_trend["hovertemplate"] and "%{y" in my_trend["hovertemplate"]
    bar = specs[INTENSITY]["data"][0]
    assert "gCO2e/kWh" in bar["hovertext"][bar["y"].index("Malaysia")]
    pc = specs[PERCAPITA]["data"][0]
    assert "MWh" in pc["hovertext"][pc["y"].index("Malaysia")] and "2024" in pc["hovertext"][pc["y"].index("Malaysia")]
    scatter = specs[SCATTER]["data"][0]
    assert "TWh" in scatter["hovertext"][0]


def test_the_tooltip_fields_are_also_in_show_data():
    at = run()
    tables = [d.value for d in at.dataframe]
    snapshot = next(t for t in tables if "Demand (TWh)" in t.columns)
    assert {"RE share (%)", "Demand (TWh)", *SOURCES["display_name"]} <= set(snapshot.columns)
    mine = snapshot[snapshot["Country"] == "Malaysia"].iloc[0]
    assert mine["Coal"] == pytest.approx(mix_pct("Malaysia", LAST)["Coal"], abs=0.05)


# --- footnote and credits (frame_footnote) ---


def test_the_p5_footnote_is_the_dax_text_for_the_selection():
    def note(year, pc_year):
        return (
            f"Ranking, scatter and intensity bars use {year}, the latest year all selected countries report; per-capita "
            f"demand uses {pc_year} (OWID population). With no country selected, the six default peers are compared. "
            "Sources: Ember (CC BY 4.0), OWID (CC BY 4.0)."
        )

    captions = " ".join(c.value for c in run().caption)
    assert note(2025, 2024) in captions
    narrowed = " ".join(c.value for c in run(countries=SELECTION).caption)
    assert note(2024, 2024) in narrowed and note(2025, 2024) not in narrowed


def test_the_deep_dive_footnote_is_the_reports_text_and_the_credits_follow():
    captions = " ".join(c.value for c in run().caption)
    verbatim = textbox("d1_country", "frame_footnote")
    kept = verbatim.split(" Right-click")[0]  # the report's drill-through sentence has no web equivalent
    assert kept in captions and "Right-click" not in captions
    assert "Ember (2026), Yearly Electricity Data, CC BY 4.0" in captions
    assert "Our World in Data, Energy dataset, CC BY 4.0" in captions
    assert "Grid System Operator" not in captions  # D4 is never credited here: it is not used


# --- the country selector (D1: drill-through landing, d1_back) ---


def test_the_deep_dive_lands_on_malaysia_the_report_focus_as_the_dax_context_does():
    """D1's measures read Context Country Key: the drilled country, else the focus country (Malaysia)."""
    at = run()
    box = at.selectbox(key="asean_country")
    assert box.value == "Malaysia" and box.label == "Country deep dive"
    assert box.options == list(COUNTRIES["name"])
    ca = F["country_annual"]
    fossil = ca[(ca["country_key"] == 1) & (ca["year"] == LAST)]["fossil_share_gen_pct"].iloc[0]
    assert at.subheader[1].value == f"Malaysia: fossil fuels supplied {fmt(fossil)}% of electricity in {LAST}"


def test_changing_the_country_changes_the_deep_dive_title_and_charts():
    before = chart_specs(run())
    at = run(country="Vietnam")
    after = chart_specs(at)
    ca = F["country_annual"]
    fossil = ca[(ca["country_key"] == KEY["Vietnam"]) & (ca["year"] == LAST)]["fossil_share_gen_pct"].iloc[0]
    assert at.subheader[1].value == f"Vietnam: fossil fuels supplied {fmt(fossil)}% of electricity in {LAST}"
    assert f"Vietnam · {FIRST}–{LAST} · {data_as_of()}" in [c.value for c in at.caption]  # Generation Subtitle
    for chart in (DEEP_MIX, DEEP_CF, DEEP_DEMAND, DEEP_GROWTH):
        assert [t.get("y") for t in before[chart]["data"]] != [t.get("y") for t in after[chart]["data"]]
    for chart in (TREND, SCATTER):  # the comparison above it is untouched
        assert before[chart] == after[chart]
    assert at.title[0].value == "Malaysia: 4 of 6 on renewable share, 5 of 6 on carbon intensity (2025)"


def test_the_deep_dive_follows_the_page_year_range():
    at = run(country="Thailand", years=(2000, 2010))
    ca = F["country_annual"]
    fossil = ca[(ca["country_key"] == KEY["Thailand"]) & (ca["year"] == 2010)]["fossil_share_gen_pct"].iloc[0]
    assert at.subheader[1].value == f"Thailand: fossil fuels supplied {fmt(fossil)}% of electricity in 2010"
    assert chart_specs(at)[DEEP_DEMAND]["data"][0]["x"] == list(range(2000, 2011))


def test_the_back_link_returns_to_the_comparison():
    at = run(country="Vietnam")
    assert any("(#compare-countries)" in m.value and "Back" in m.value for m in at.markdown)
    assert at.subheader[0].proto.anchor == "compare-countries"


# --- deep dive: mix area, unit, sources (d1_mix_area, d1_unit_slicer, d1_source_slicer, d1_year_slicer) ---


def gen_of(name: str) -> pd.DataFrame:
    ga = F["generation_annual"].merge(F["dim_source"], on="source_key")
    return ga[ga["country_key"] == KEY[name]]


def test_the_deep_dive_mix_area_stacks_the_countrys_sources_over_the_range():
    at = run(country="Vietnam", years=(2005, 2015))
    mix = {t["name"]: t for t in chart_specs(at)[DEEP_MIX]["data"]}
    assert list(mix) == list(SOURCES["display_name"])
    assert [t["line"]["color"] for t in mix.values()] == list(SOURCES["color_hex"])
    assert all(t["stackgroup"] == "one" for t in mix.values())
    g = gen_of("Vietnam")
    coal = g[(g["display_name"] == "Coal") & g["year"].between(2005, 2015)].sort_values("year")
    assert mix["Coal"]["x"] == list(range(2005, 2016)) and mix["Coal"]["y"] == pytest.approx(
        list(coal["generation_twh"])
    )
    assert any(
        h.startswith("**Generation by source (TWh or % of the year's total, per the Unit toggle)") for h in headings(at)
    )


def test_the_deep_dive_unit_and_source_slicers():
    at = run()
    unit, sources = at.radio(key="asean_unit"), at.multiselect(key="asean_sources")
    assert unit.label == "Unit" and unit.options == ["TWh", "%"] and unit.value == "TWh"
    assert sources.label == "Source" and sources.options == list(SOURCES["display_name"]) and sources.value == []


def test_the_percent_unit_shows_each_sources_share_of_the_countrys_whole_mix():
    at = run(country="Thailand", unit="%")
    mix = {t["name"]: t for t in chart_specs(at)[DEEP_MIX]["data"]}
    g = gen_of("Thailand")
    gas = g[g["display_name"] == "Gas"].sort_values("year")
    total = g.groupby("year")["generation_twh"].sum()
    want = [100 * v / total[y] for v, y in zip(gas["generation_twh"], gas["year"], strict=True)]
    assert mix["Gas"]["y"] == pytest.approx(want, abs=0.001)
    only_gas = chart_specs(run(country="Thailand", unit="%", sources=["Gas"]))[DEEP_MIX]["data"]
    assert [t["name"] for t in only_gas] == ["Gas"] and only_gas[0]["y"] == pytest.approx(mix["Gas"]["y"], abs=1e-9)


# --- deep dive: capacity factor and its note (d1_cf_bar, d1_cf_note) ---


def cf(name: str, year: int, source: str) -> float | None:
    g = gen_of(name)
    r = g[(g["display_name"] == source) & (g["year"] == year)].iloc[0]
    hours = int(F["dim_year"].set_index("year").at[year, "hours_in_year"])
    cap, gen = r["capacity_gw"], r["generation_twh"]
    if pd.isna(cap) or not cap > 0 or 1000 * gen > cap * hours:
        return None
    return 100 * 1000 * gen / (cap * hours)


@pytest.mark.parametrize("country", ["Vietnam", "Thailand", "Indonesia"])
def test_the_deep_dive_capacity_factor_is_the_countrys_at_the_last_year(country):
    at = run(country=country, years=(2000, 2023))
    bar = chart_specs(at)[DEEP_CF]["data"][0]
    want = {s: cf(country, 2023, s) for s in SOURCES["display_name"] if cf(country, 2023, s) is not None}
    assert dict(zip(bar["y"], bar["x"], strict=True)) == pytest.approx(want, abs=0.01)
    assert chart_specs(at)[DEEP_CF]["layout"]["xaxis"]["range"] == [0, 100]
    assert "Capacity factor by source, 2023 (%)" in [m.value.strip("*") for m in at.markdown]


def test_the_deep_dive_capacity_factor_note_names_the_countrys_blank_sources():
    note = "Capacity not reported or inconsistent with generation for "
    at = run(country="Thailand")  # the report's footnote names Thailand as blank in every year
    g = gen_of("Thailand")
    names = [
        s
        for s in SOURCES["display_name"]
        if g[(g["display_name"] == s) & (g["year"] == LAST)].iloc[0]["generation_twh"] > 0
        and cf("Thailand", LAST, s) is None
    ]
    assert names, "the test needs a Thailand source with generation but no usable capacity"
    want = f"{note}{', '.join(names)} in {LAST}, so shown blank, not 0. CF = generation ÷ (capacity × hours in year)."
    assert want in [c.value for c in at.caption]
    assert not any(c.value.startswith(note) for c in run(sources=["Coal", "Gas", "Hydro", "Solar"]).caption)


# --- deep dive: demand and growth (d1_demand_cols, d1_growth_cols) ---


def test_the_deep_dive_demand_and_growth_columns_are_the_countrys():
    at = run(country="Vietnam", years=(2005, 2015))
    demand, growth = chart_specs(at)[DEEP_DEMAND]["data"][0], chart_specs(at)[DEEP_GROWTH]["data"][0]
    ca = F["country_annual"]
    ca = ca[ca["country_key"] == KEY["Vietnam"]].set_index("year")["demand_twh"]
    assert demand["x"] == growth["x"] == list(range(2005, 2016))
    assert demand["y"] == pytest.approx([ca[y] for y in range(2005, 2016)])
    assert growth["y"] == pytest.approx([100 * (ca[y] - ca[y - 1]) / ca[y - 1] for y in range(2005, 2016)], abs=0.001)
    assert demand["marker"]["color"] == NAVY and growth["marker"]["color"] == "#256abf"


def test_a_countrys_first_year_has_no_growth_bar():
    growth = chart_specs(run(country="Indonesia", years=(2000, 2004)))[DEEP_GROWTH]["data"][0]
    assert growth["x"][0] == 2000 and growth["y"][0] is None and None not in growth["y"][1:]


# --- deep dive: empty state (d1_empty_state) ---


def test_a_source_with_no_generation_in_the_countrys_range_says_so():
    """Indonesia is reported from 2000: a Coal filter on 1985-1990 leaves nothing, so the DAX message shows."""
    at = run(country="Indonesia", years=(1985, 1990), sources=["Coal"])
    assert any(i.value == "No Coal generation in this period" for i in at.info)
    assert not any("generation in this period" in i.value for i in run(country="Indonesia", sources=["Coal"]).info)


def test_the_empty_state_names_every_filtered_source(monkeypatch):
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
        at = run(country="Vietnam", sources=["Solar"])
        assert any(i.value == "No Solar generation in this period" for i in at.info)
        assert not any("generation in this period" in i.value for i in run(country="Vietnam", sources=["Coal"]).info)
    finally:
        st.cache_data.clear()


def test_a_country_with_no_data_in_the_range_still_renders_every_chart():
    at = run(country="Indonesia", years=(1985, 1990))
    assert not at.exception and len(at.get("plotly_chart")) == 8


# --- every chart, data-quality badge ---


def test_each_chart_has_a_text_summary_and_show_data():
    at = run()
    charts = at.get("plotly_chart")
    assert len(charts) == 8
    captions = [c.value for c in at.caption]
    for chart in charts:
        assert chart.proto.alt and chart.proto.alt in captions
    assert [e.label for e in at.expander].count("Show data") == 9  # the 8 charts and the rank card


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


# --- asean.py units ---


def test_compared_is_the_selection_or_the_default_peers_in_display_order():
    a = asean()
    assert a.compared(F, []) == DEFAULT_PEERS
    assert a.compared(F, ["Laos", "Brunei"]) == ["Brunei", "Laos"]
    assert a.countries(F) == list(COUNTRIES["name"])


def test_comparison_rows_are_the_sql_twin():
    a = asean()
    c = a.comparison(F, [], FIRST, LAST)
    assert c.rows.to_dict("records") == pd.DataFrame(metrics.ranking(F)).to_dict("records")
    assert (c.year, c.per_capita_year, c.names) == (2025, 2024, DEFAULT_PEERS)
    assert c.title == "Malaysia: 4 of 6 on renewable share, 5 of 6 on carbon intensity (2025)"
    assert c.label == "Malaysia ranks 4 of 6 on renewable share (2025)"


def test_comparison_with_one_country_or_none_of_malaysia():
    a = asean()
    assert a.comparison(F, ["Malaysia"], FIRST, LAST).title == "Select at least two countries to compare"
    assert a.comparison(F, ["Laos", "Brunei"], FIRST, LAST).title == "Malaysia is not in the current selection"


def test_comparison_year_is_capped_by_the_range_end():
    a = asean()
    assert a.comparison(F, [], FIRST, 2015).year == 2015
    assert a.comparison(F, [], FIRST, 1990).year == 1990  # only Malaysia, Thailand and Vietnam report that early
    assert len(a.comparison(F, [], FIRST, 1990).rows) == 3


def test_the_trend_has_one_row_per_country_and_year_with_a_value():
    t = asean().trend(F, ["Malaysia", "Laos"], "Emissions (MtCO2e)", 2020, 2025)
    assert list(t.columns) == ["country", "year", "value"]
    assert set(t["country"]) == {"Malaysia", "Laos"}
    assert t[t["country"] == "Laos"]["year"].max() == 2024  # Laos has no 2025 yet: no row, not a zero
    assert t[(t["country"] == "Malaysia") & (t["year"] == 2025)]["value"].iloc[0] == pytest.approx(
        value("Malaysia", 2025, "emissions_mtco2e")
    )


def test_tooltip_is_the_t2_page_for_a_country_and_year():
    tip = asean().tooltip(F, "Malaysia", 2025)
    assert tip.title == "Malaysia · 2025"
    assert tip.re_share == pytest.approx(value("Malaysia", 2025, "re_share_gen_pct"))
    assert tip.intensity == pytest.approx(value("Malaysia", 2025, "emissions_intensity_gco2e_kwh"))
    mix = dict(tip.mix)
    assert sum(mix.values()) == pytest.approx(100.0, abs=0.01)
    assert mix["Coal"] == pytest.approx(mix_pct("Malaysia", 2025)["Coal"])
    assert "Malaysia · 2025" in tip.html and "Coal" in tip.html and "<br>" in tip.html


def test_tooltip_for_a_country_with_no_data_is_just_its_title():
    tip = asean().tooltip(F, "Indonesia", 1990)
    assert tip.title == "Indonesia · 1990" and tip.mix == [] and tip.re_share is None


def test_spread_keeps_the_order_and_separates_close_labels():
    a = asean()
    out = a.spread([10.0, 10.5, 30.0, 10.2], 2.0)
    order = sorted(range(4), key=lambda i: [10.0, 10.5, 30.0, 10.2][i])
    ranked = [out[i] for i in order]
    assert all(b - a_ >= 2.0 - 1e-9 for a_, b in itertools.pairwise(ranked))
    assert out[2] == 30.0  # a far label stays where it is
    assert sum(out[i] for i in (0, 1, 3)) == pytest.approx(10.0 + 10.5 + 10.2)  # moved apart around their centre
    assert a.spread([1.0, 5.0], 2.0) == [1.0, 5.0] and a.spread([], 2.0) == []


def test_focus_on_makes_the_metric_ports_describe_another_country():
    a = asean()
    t = pd.DataFrame(metrics.trends(a.focus_on(F, "Vietnam")))
    g = gen_of("Vietnam")
    assert t.groupby("year")["generation_twh"].sum().to_dict() == pytest.approx(
        g.groupby("year")["generation_twh"].sum().to_dict()
    )
    assert F["dim_country"]["is_focus"].tolist()[0]  # the original frames are untouched


def test_annual_generation_functions_take_a_country_and_default_to_malaysia():
    ca = F["country_annual"]
    fossil = ca[(ca["country_key"] == KEY["Vietnam"]) & (ca["year"] == 2020)]["fossil_share_gen_pct"].iloc[0]
    assert (
        annual.generation_title(F, 2020, "Vietnam")
        == f"Vietnam: fossil fuels supplied {fmt(fossil)}% of electricity in 2020"
    )
    assert annual.generation_title(F, 2020).startswith("Malaysia: fossil fuels supplied")
    assert (
        annual.generation_subtitle(2000, 2020, "Data as of 1 Jan 2026", "Laos")
        == "Laos · 2000–2020 · Data as of 1 Jan 2026"
    )
    assert annual.generation_subtitle(2000, 2020, "x") == "Malaysia · 2000–2020 · x"
    rows = annual.capacity_factors(F, 2020, [], "Vietnam")
    assert list(rows["source"]) == list(SOURCES["display_name"])
    assert rows["generation_twh"].iloc[0] == pytest.approx(
        gen_of("Vietnam").query("display_name == 'Coal' and year == 2020")["generation_twh"].iloc[0]
    )
    assert annual.capacity_factors(F, 2020, []).equals(annual.capacity_factors(F, 2020, [], "Malaysia"))


def test_the_text_summaries_name_the_extremes_and_where_malaysia_stands():
    a = asean()
    c = a.comparison(F, [], FIRST, LAST)
    snap = a.snapshot(F, c)
    text = a.bar_summary(
        snap, "Carbon intensity (gCO2e/kWh)", c.year, "carbon intensity", "gCO2e/kWh", 0, low_first=True
    )
    assert text == (
        "Carbon intensity in 2025 runs from 459 gCO2e/kWh (Vietnam) to 705 (Indonesia). Malaysia is 5th of 6: 606."
    )
    per_capita = a.bar_summary(snap, "Demand per capita (MWh)", 2024, "demand per capita", "MWh", 2, low_first=False)
    assert per_capita.startswith("Demand per capita in 2024 runs from 10.22 MWh (Singapore) to 1.07 (Philippines).")
    assert "Malaysia is 2nd of 6: 5.91." in per_capita
    assert (
        a.bar_summary(snap.iloc[0:0], "Demand per capita (MWh)", 2024, "x", "u", 1, low_first=True)
        == "No x to show for the selected countries."
    )


def test_the_scatter_summary_does_not_repeat_a_country_that_leads_both_ways():
    a = asean()
    snap = a.snapshot(F, a.comparison(F, [], FIRST, LAST))
    assert a.scatter_summary(snap, 2025).startswith(
        "In 2025, Vietnam has both the highest renewable share (46.0%) and the lowest carbon intensity (459 gCO2e/kWh)."
    )
    other = a.scatter_summary(a.snapshot(F, a.comparison(F, ["Malaysia", "Singapore"], FIRST, LAST)), 2025)
    assert "Malaysia has the highest renewable share (20.4%) and Singapore the lowest carbon intensity" in other


def test_the_footnote_has_no_year_when_nothing_can_be_compared():
    a = asean()
    c = a.comparison(F, ["Indonesia"], FIRST, 1990)  # Indonesia reports from 2000
    assert (c.year, c.per_capita_year) == (None, None)
    assert "use n/a, the latest year" in a.footnote(c) and "per-capita demand uses n/a" in a.footnote(c)


def test_a_country_with_no_demand_in_the_range_gets_one_plain_sentence():
    a = asean()
    empty = annual.demand_series(a.focus_on(F, "Indonesia"), 1985, 1990)
    assert empty.empty
    assert a.demand_summaries(empty, "Indonesia", 1985, 1990) == (
        ("No demand is reported for Indonesia in 1985–1990.",) * 2
    )
    full = annual.demand_series(a.focus_on(F, "Indonesia"), 2000, 2005)
    assert a.demand_summaries(full, "Indonesia", 2000, 2005)[0].startswith("Demand went from")
