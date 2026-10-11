"""The Overview page (report page P1, M6 step 4): the takeaway title, the five KPI cards with their YoY deltas, the
generation-mix area, the NETR panel, the rank card, the findings, the footnote and the credits equal what the report's
DAX gives for the same selection. Expected values are computed here straight from the exported views (or read from
exports/expected.json, the SQL twins' results), never from app/showcase/annual.py."""

import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
PAGE = str(ROOT / "app" / "pages" / "overview.py")
P1 = ROOT / "report/EnergyTransition.Report/definition/pages/59dacfc5089b163e62a0/visuals"

from showcase import annual, data

F = data.frames()
EXPECTED = data.expected()
LATEST = int(F["dim_year"].loc[F["dim_year"]["is_complete"], "year"].max())


def data_as_of() -> str:
    d = pd.to_datetime(F["run_latest"]["finished_at"]).max()
    return f"Data as of {d.day} {d:%b %Y}"


def fmt(x: float, digits: int = 1) -> str:
    """DAX FORMAT(x, "0.0"): half away from zero."""
    return f"{Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP):.{digits}f}"


def malaysia(year: int) -> pd.Series:
    ca = F["country_annual"]
    return ca[(ca["country_key"] == 1) & (ca["year"] == year)].iloc[0]


def run(year: int | None = None):
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    if year is not None:
        at.selectbox(key="overview_year").set_value(year).run()
    assert not at.exception
    return at


def chart_specs(at) -> list[dict]:
    return [json.loads(c.proto.spec) for c in at.get("plotly_chart")]


def strip_colour(text: str) -> str:
    m = re.fullmatch(r":\w+\[(.*)\]", text, flags=re.DOTALL)
    return m.group(1) if m else text


def delta_lines(at) -> list[str]:
    return [strip_colour(m.value) for m in at.markdown if " vs " in m.value or m.value.strip("*: ") == "—"]


# --- the title, subtitle and year slicer (frame_title, frame_subtitle, p1_year_slicer) ---


def test_the_title_is_the_dax_takeaway_for_the_default_year():
    at = run()
    re_share = malaysia(LATEST)["re_share_gen_pct"]
    assert at.title[0].value == f"Renewables supplied {fmt(re_share)}% of Malaysia's electricity in {LATEST}"
    assert at.caption[0].value == f"Malaysia · {LATEST} · {data_as_of()}"  # Overview Subtitle


def test_the_title_follows_the_year_slicer():
    at = run(2015)
    assert malaysia(2015)["re_share_gen_pct"] == pytest.approx(9.957, abs=1e-3)
    assert at.title[0].value == "Renewables supplied 10.0% of Malaysia's electricity in 2015"  # 9.957 rounds up
    assert at.caption[0].value == f"Malaysia · 2015 · {data_as_of()}"


def test_the_year_slicer_defaults_to_the_latest_complete_year_and_lists_every_year():
    at = run()
    box = at.selectbox(key="overview_year")
    assert box.value == LATEST
    assert box.label == "Year"
    assert sorted(box.options, key=int) == [str(y) for y in F["dim_year"]["year"]]


def test_reset_filters_brings_the_default_year_back():
    at = run(2010)
    assert at.selectbox(key="overview_year").value == 2010
    next(b for b in at.button if "Reset filters" in b.label).click().run()
    assert at.selectbox(key="overview_year").value == LATEST
    assert at.title[0].value.endswith(f"in {LATEST}")


# --- the KPI cards and deltas (p1_kpi_0..4, p1_kpi_delta_0..4) ---

CARDS = [  # label as the report's card shows it, column, digits, grouping
    ("Total Generation (TWh)", "total_generation_twh", 1, True),
    ("RE Share (%)", "re_share_gen_pct", 1, False),
    ("Fossil Share (%)", "fossil_share_gen_pct", 1, False),
    ("Carbon Intensity (gCO2e/kWh)", "emissions_intensity_gco2e_kwh", 0, True),
    ("Demand per Capita (MWh)", "demand_per_capita_mwh", 2, False),
]


@pytest.mark.parametrize("year", [LATEST, 2015])
def test_the_kpi_cards_show_the_reports_measures(year):
    at = run(year)
    row = malaysia(year)
    assert [m.label for m in at.metric] == [c[0] for c in CARDS]
    for metric, (_, col, digits, grouping) in zip(at.metric, CARDS, strict=True):
        shown = fmt(row[col], digits)
        if grouping:
            shown = f"{float(shown):,.{digits}f}"
        assert metric.value == shown


def test_the_kpi_cards_carry_the_t1_tooltip_text():
    at = run()
    k = F["kpi"].set_index("kpi_code")
    ds = F["data_source"].set_index("data_source_code")
    codes = ["TOTAL_GENERATION", "RE_SHARE_GEN", "FOSSIL_SHARE_GEN", "CARBON_INTENSITY", "DEMAND_PER_CAPITA"]
    for metric, code in zip(at.metric, codes, strict=True):
        r = k.loc[code]
        assert metric.help.startswith(f"{r['name']} ({r['unit']}). {r['definition']} Formula: {r['formula']}. Source: ")
        assert ds.at[r["data_source_code"], "credit_text"] in metric.help
    # the report's own tooltip text on p1_kpi_go_0 is the same sentence
    go = json.loads((P1 / "p1_kpi_go_0" / "visual.json").read_text(encoding="utf-8"))
    tip = re.search(r"'(Total generation \(TWh\)\..*?)'\"", json.dumps(go, ensure_ascii=False)).group(1)
    assert at.metric[0].help.startswith(tip.split(" Click for")[0].replace("''", "'"))


def expected_delta(code: str, year: int, judged: bool) -> str:
    row = next(r for r in EXPECTED["02_yoy_lag"] if r["kpi_code"] == code and r["year"] == year)
    if row["change"] is None:
        return "—"
    change = row["change"]
    unit = " pp" if row["change_unit"] == "pp" else "%"
    text = f"{'▲' if change >= 0 else '▼'} {fmt(abs(change))}{unit} vs {year - 1}"
    word = "up" if change >= 0 else "down"
    if judged and row["direction"] != "NEUTRAL":
        word += ", " + row["direction"].lower()
    return f"{text} · {word}"


CODES = [
    ("TOTAL_GENERATION", False),
    ("RE_SHARE_GEN", True),
    ("FOSSIL_SHARE_GEN", True),
    ("CARBON_INTENSITY", True),
    ("DEMAND_PER_CAPITA", False),
]


@pytest.mark.parametrize("year", [LATEST, 2020, 2016])
def test_the_deltas_equal_the_sql_twin_with_an_arrow_and_a_word(year):
    at = run(year)
    assert delta_lines(at) == [expected_delta(code, year, judged) for code, judged in CODES]


def test_the_deltas_judge_only_the_three_kpis_the_report_colours():
    lines = delta_lines(run(LATEST))
    assert lines[1].endswith("up, good")  # RE share rose in 2025 (+0.63 pp)
    assert lines[2].endswith("down, good")  # fossil share fell
    assert lines[0].endswith(("up", "down"))  # total generation and demand per capita carry no verdict
    assert lines[4].endswith(("up", "down"))


def test_the_first_year_has_no_delta():
    at = run(int(F["dim_year"]["year"].min()))
    assert delta_lines(at) == ["—"] * 5  # "YoY for the first year in range → —, not 0%"


# --- no data for the year (p1 'No Data Message', doc 03 P1 empty state) ---


def test_a_year_without_data_says_so_and_no_card_is_blank(monkeypatch):
    real = data.frames

    def blanked():
        f = real()
        ca = f["country_annual"].copy()
        mine = (ca["country_key"] == 1) & (ca["year"] == LATEST)
        ca.loc[mine, ["total_generation_twh", "re_share_gen_pct", "fossil_share_gen_pct"]] = float("nan")
        return {**f, "country_annual": ca}

    monkeypatch.setattr(data, "frames", blanked)
    st.cache_data.clear()
    try:
        at = run()
        assert any(f"No data for {LATEST}" in i.value for i in at.info)
        assert all(m.value for m in at.metric)  # a card says "—", never an empty string
    finally:
        st.cache_data.clear()


# --- charts: mix area, NETR bars (p1_mix_area, p1_netr_bars, p1_netr_label) ---


def test_the_mix_area_stacks_every_source_over_all_years_in_the_source_colours():
    at = run()
    mix = chart_specs(at)[0]["data"]
    src = F["dim_source"].sort_values("sort_order")
    assert [t["name"] for t in mix] == list(src["display_name"])
    assert [t["line"]["color"] for t in mix] == list(src["color_hex"])
    assert all(t["stackgroup"] == "one" for t in mix)
    years = list(F["dim_year"]["year"])
    assert mix[0]["x"] == years  # the year slicer does not filter it (the report's NoFilter interaction)
    ga = F["generation_annual"]
    coal = ga[(ga["country_key"] == 1) & (ga["source_key"] == 1)].sort_values("year")
    assert mix[0]["y"] == pytest.approx(list(coal["generation_twh"]))


def test_the_mix_area_does_not_change_with_the_year_slicer():
    assert chart_specs(run())[0]["data"] == chart_specs(run(2005))[0]["data"]


def netr_expected(year: int) -> str:
    ember = malaysia(year)["re_share_capacity_pct"]
    off = F["re_capacity_official"]
    off = off[off["year"] <= year]
    tg = F["netr_target"]
    tg = tg[tg["target_year"] >= year].sort_values("target_year").iloc[0]
    text = "Ember grid basis " + (f"{fmt(ember)}%" if pd.notna(ember) else "not reported")
    if len(off):
        o = off.sort_values("year").iloc[-1]
        text += f" · official {fmt(o['re_capacity_share_pct'], 0)}% (incl. off-grid and rooftop, {o['year']})"
    return text + f" · target {fmt(tg['re_capacity_share_pct'], 0)}% by {tg['target_year']}"


@pytest.mark.parametrize("year", [LATEST, 2015, 1990])
def test_the_netr_label_is_the_dax_progress_label(year):
    at = run(year)
    assert netr_expected(year) in [c.value for c in at.caption]


def test_the_netr_bars_show_both_bases_beside_the_target():
    at = run()
    bars = {t["name"]: t["x"] for t in chart_specs(at)[1]["data"]}
    assert bars == {
        "RE Capacity Share (%)": [pytest.approx(malaysia(LATEST)["re_share_capacity_pct"])],
        "Official RE Capacity Share (%)": [31.0],
        "NETR Target (%)": [31.0],
    }
    spec = chart_specs(at)[1]
    assert spec["layout"]["xaxis"]["range"] == [0, 100]
    hover = " ".join(str(t.get("hovertext", "")) + str(t.get("hovertemplate", "")) for t in spec["data"])
    assert "12th Malaysia Plan" in hover  # the target cites its source (doc 03)
    assert "gap" in hover.lower()


def test_the_netr_bars_leave_out_what_the_year_does_not_have():
    at = run(2010)  # before the first official point; the next target is 2025's 31%
    assert {t["name"] for t in chart_specs(at)[1]["data"]} == {"RE Capacity Share (%)", "NETR Target (%)"}


# --- rank card (p1_rank_card, p1_rank_arrow) ---


def test_the_rank_card_says_where_malaysia_ranks_among_the_peers():
    at = run()
    row = next(r for r in EXPECTED["03_ranking"] if r["name"] == "Malaysia")
    label = f"Malaysia ranks {row['re_share_rank']} of {row['countries_compared']} on renewable share ({LATEST})"
    texts = [m.value for m in at.markdown]
    assert any(label in t for t in texts)
    assert any("→" in t for t in texts)  # the card's arrow to the ASEAN page


def test_the_rank_card_uses_the_latest_year_up_to_the_selected_one():
    at = run(2015)
    ca, dc = F["country_annual"], F["dim_country"]
    peers = dc[dc["is_default_peer"]]["country_key"]
    shares = ca[ca["country_key"].isin(peers) & (ca["year"] == 2015)].set_index("country_key")["re_share_gen_pct"]
    rank = int((shares > shares[1]).sum()) + 1
    assert any(
        f"Malaysia ranks {rank} of {shares.notna().sum()} on renewable share (2015)" in m.value for m in at.markdown
    )


# --- findings, footnote, credits, "Show data" (p1_findings, frame_footnote) ---


def textbox(visual: str) -> list[str]:
    d = json.loads((P1 / visual / "visual.json").read_text(encoding="utf-8"))
    paragraphs = d["visual"]["objects"]["general"][0]["properties"]["paragraphs"]
    return ["".join(r["value"] for r in p["textRuns"]) for p in paragraphs]


def test_the_findings_are_the_reports_text():
    at = run()
    shown = " ".join(m.value for m in at.markdown)
    for line in textbox("p1_findings"):
        assert line.removeprefix("1. ").removeprefix("2. ").removeprefix("3. ") in shown


def test_the_findings_numbers_still_match_the_data():
    """The report's three findings are typed text: this fails when a refresh makes one stale."""
    e = EXPECTED["07_emissions_vs_demand"][0]
    assert round(e["intensity_change_pct"], 1) == -9.5
    assert round(e["emissions_change_pct"]) == 27
    assert round(e["generation_change_pct"]) == 40
    avg = {r["year"]: r["re_share_3yr_avg_pct"] for r in EXPECTED["04_rolling_avg"] if r["name"] == "Malaysia"}
    assert (round(avg[2015], 1), round(avg[2025], 1)) == (9.6, 19.7)
    my = next(r for r in EXPECTED["03_ranking"] if r["name"] == "Malaysia")
    assert (my["re_share_rank"], my["intensity_rank"], my["countries_compared"]) == (4, 5, 6)
    assert round(my["emissions_intensity_gco2e_kwh"]) == 606


def test_the_footnote_and_the_credits():
    at = run()
    captions = " ".join(c.value for c in at.caption)
    assert textbox("frame_footnote")[0] in captions
    assert "Ember (2026), Yearly Electricity Data, CC BY 4.0" in captions
    assert "Our World in Data, Energy dataset, CC BY 4.0" in captions
    assert "Grid System Operator" not in captions  # D4 is never credited here: it is not used


def test_each_chart_has_a_text_summary_and_show_data():
    at = run()
    specs = at.get("plotly_chart")
    assert len(specs) == 2
    captions = [c.value for c in at.caption]
    for chart in specs:
        alt = chart.proto.alt
        assert alt and alt in captions  # the one-sentence summary under the chart
    labels = [e.label for e in at.expander]
    assert labels.count("Show data") == 3  # mix, NETR, rank table


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


def test_fmt_rounds_half_away_from_zero_like_dax_format():
    assert annual.fmt(0.25, 1) == "0.3"  # Python's round-half-even would give 0.2
    assert annual.fmt(2.675, 2) == "2.68"
    assert annual.fmt(-0.05, 1) == "-0.1"
    assert annual.fmt(1234.5, 0, grouping=True) == "1,235"
    assert annual.fmt(None) == "" and annual.fmt(float("nan")) == ""


def test_netr_progress_picks_the_next_target_and_the_latest_official_point():
    n = annual.netr_progress(F, 2015)
    assert (n.target_year, n.target, n.official, n.official_year) == (2025, 31.0, None, None)
    assert n.gap == pytest.approx(n.ember - 31.0)
    n = annual.netr_progress(F, 2025)
    assert (n.official, n.official_year) == (31.0, 2025)
    assert annual.netr_progress(F, 1990).ember is None  # Ember reports no capacity share before 2000


def test_rank_label_needs_two_countries_and_malaysia_in_the_set():
    solo = {**F, "dim_country": F["dim_country"].assign(is_default_peer=lambda d: d["is_focus"])}
    assert annual.rank_summary(solo, LATEST)[0] == "Select at least two countries to compare"
    no_my = {
        **F,
        "country_annual": F["country_annual"].assign(
            re_share_gen_pct=lambda d: d["re_share_gen_pct"].where(d["country_key"] != 1)
        ),
    }
    assert annual.rank_summary(no_my, LATEST)[0] == "Malaysia is not in the current selection"


def test_the_latest_complete_year_ignores_a_partial_one():
    dy = F["dim_year"].copy()
    dy.loc[dy["year"] == LATEST, "is_complete"] = False
    assert annual.latest_complete_year({**F, "dim_year": dy}) == LATEST - 1
