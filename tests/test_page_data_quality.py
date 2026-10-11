"""The Data quality page (report page P6b, M6 step 5): every rule of the latest run with an icon-and-word result, the
Pass/Warn/Fail slicer, the per-source rows table that filters the rules, the summaries, the warn note and the empty
state. Expected values come straight from the exported views (or the report's own visual.json), never from
app/showcase/meta.py, whose pure functions get their own unit tests at the end."""

import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
PAGE = str(ROOT / "app" / "pages" / "data_quality.py")
P6B = ROOT / "report/EnergyTransition.Report/definition/pages/p6b_data_quality/visuals"

from showcase import cache, data, meta

F = data.frames()
DQ = F["dq_latest"]
LABEL = {"PASS": "✓ Pass", "WARN": "! Warn", "FAIL": "✕ Fail"}  # [DQ Status Label]
SLICER, PICK = "dq_status", "dq_source_pick"  # the widget keys
COLUMNS = ["Rule", "Source", "Severity", "Result", "Rows affected", "What it checks", "Detail"]
METADATA_FRAMES = {"data_source", "kpi", "run_latest", "source_load_latest", "dq_latest"}


# ---------------------------------------------------------------- helpers
def visual(name: str) -> dict:
    return json.loads((P6B / name / "visual.json").read_text(encoding="utf-8"))


def textbox(name: str) -> list[str]:
    paragraphs = visual(name)["visual"]["objects"]["general"][0]["properties"]["paragraphs"]
    return ["".join(r["value"] for r in p["textRuns"]) for p in paragraphs]


def shape_literal(name: str) -> str:
    text = visual(name)["visual"]["objects"]["text"][1]["properties"]["text"]["expr"]["Literal"]["Value"]
    return text[1:-1].replace("''", "'")


def stamp(iso: str) -> str:
    return iso[:16].replace("T", " ")


def conditional_colours(prop: str) -> dict[str, str]:
    """The report's conditional format of the Result column: status -> colour, for backColor or fontColor."""
    values = visual("p6b_dq_table")["visual"]["objects"]["values"]
    item = next(v for v in values if prop in v["properties"])
    cases = item["properties"][prop]["solid"]["color"]["expr"]["Conditional"]["Cases"]
    return {
        c["Condition"]["Comparison"]["Right"]["Literal"]["Value"].strip("'"): c["Value"]["Literal"]["Value"].strip("'")
        for c in cases
    }


@contextmanager
def patched(frames: dict):
    """The page reads `frames` instead of the exported snapshots (the cache is cleared on the way in and out)."""
    patch = pytest.MonkeyPatch()
    patch.setattr(data, "frames", lambda: frames)
    st.cache_data.clear()
    try:
        yield
    finally:
        patch.undo()
        st.cache_data.clear()


def run():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    return at


@pytest.fixture(scope="module")
def at():
    return run()


def captions(at) -> list[str]:
    return [c.value for c in at.caption]


def page_text(at) -> str:
    parts = [e.value for e in (*at.markdown, *at.caption, *at.info, *at.warning, *at.error)]
    return "\n".join(parts)


def tables(at) -> list[pd.DataFrame]:
    """Every table on the page (static or interactive), a named index turned back into a column."""
    return [e.value if e.value.index.name is None else e.value.reset_index() for e in (*at.table, *at.dataframe)]


def has_table(at, column: str) -> bool:
    return any(column in d.columns for d in tables(at))


def table(at, column: str) -> pd.DataFrame:
    """The first table on the page that has a `column`."""
    return next(d for d in tables(at) if column in d.columns)


def rules(at) -> pd.DataFrame:
    return table(at, "Rows affected")


def sources(at) -> pd.DataFrame:
    return table(at, "Rows read")


def select(at, code: str | None):
    """Pick a row of the sources table, as a click would (None clears it)."""
    rows = [] if code is None else [list(sources(at)["Code"]).index(code)]
    at.session_state[PICK] = {"selection": {"rows": rows, "columns": [], "cells": []}}
    return at.run()


def expected_rules(statuses=(), code=None) -> pd.DataFrame:
    d = DQ
    if statuses:
        d = d[d["status"].isin(statuses)]
    if code:
        d = d[d["data_source_code"] == code]
    return d.sort_values(["rows_affected", "rule_code"], ascending=[False, True])


def failing(n: int = 1) -> dict:
    status = ["FAIL"] * n + ["PASS"] * (len(DQ) - n)
    return {**F, "dq_latest": DQ.assign(status=status)}


# ---------------------------------------------------------------- frame items
def test_title_and_subtitle_are_the_reports_text(at):
    """frame_title is typed text in the report; frame_subtitle says 'select' where Power BI says 'click'."""
    assert at.title[0].value == shape_literal("frame_title") == "Every data-quality rule, checked on each pipeline run"
    report = shape_literal("frame_subtitle")
    assert "click a source" in report
    assert captions(at)[0] == report.replace("click a source", "select a source")


def test_the_footnote_is_the_reports_text_adapted_to_the_web(at):
    """frame_footnote: the button becomes the sidebar notice, 'click' becomes 'select'; nothing else changes."""
    report = textbox("frame_footnote")[0]
    web = report.replace("the number on the Data quality button counts", "the notice in the sidebar counts").replace(
        "Click a source on the left to see only its rules; click it again to clear.",
        "Select a source in the table to see only its rules; select it again to clear.",
    )
    assert web != report
    assert captions(at)[-2] == web


def test_the_footer_credits_the_sources_in_the_rows_table(at):
    credits = captions(at)[-1]
    ds = F["data_source"].set_index("data_source_code")["credit_text"]
    assert credits.startswith("Credits: ")
    for code in ("D1", "D2", "D3", "D5", "DSG", "DTH"):  # the six sources with a recorded load
        assert ds[code] in credits
    assert ds["D4"] not in credits


def test_no_fail_badge_when_no_rule_fails(at):
    assert not at.sidebar.error


def test_the_fail_badge_is_unchanged_and_the_chip_says_fail():
    """frame_nav_badge: the sidebar notice appears with a failing rule; the table says ✕ Fail; the slicer finds it."""
    with patched(failing()):
        at = run()
        assert "1 data-quality rule failing" in at.sidebar.error[0].value
        assert (rules(at)["Result"] == "✕ Fail").sum() == 1
        assert "33 pass · 0 warn · 1 fail, of 34 rules" in page_text(at)
        at.button_group(key=SLICER).set_value(["FAIL"]).run()
        assert list(rules(at)["Result"]) == ["✕ Fail"]


# ---------------------------------------------------------------- p6b_dq_table, p6b_dq_summary
def test_all_34_rules_show_by_default_with_the_reports_columns_and_order(at):
    shown = rules(at)
    want = expected_rules()
    assert list(shown.columns) == COLUMNS
    assert len(shown) == len(DQ) == 34
    assert list(shown["Rule"]) == list(want["rule_code"])  # rows affected descending, then rule code
    assert list(shown["Severity"]) == list(want["severity"])
    assert list(shown["Rows affected"]) == list(want["rows_affected"])
    assert list(shown["What it checks"]) == list(want["description"])


def test_every_result_cell_is_an_icon_and_a_word(at):
    shown = rules(at)
    want = expected_rules()
    assert list(shown["Result"]) == [LABEL[s] for s in want["status"]]
    assert set(shown["Result"]) <= set(LABEL.values())
    for cell in shown["Result"]:
        icon, word = cell.split(" ")
        assert icon in "✓!✕" and word in {"Pass", "Warn", "Fail"}


def test_the_source_column_is_the_code_and_blank_for_grid_rules(at):
    shown = rules(at)
    want = expected_rules()
    assert [None if pd.isna(s) else s for s in shown["Source"]] == [
        None if pd.isna(s) else s for s in want["data_source_code"]
    ]
    assert shown["Source"].isna().sum() == DQ["data_source_code"].isna().sum() > 0


def test_detail_is_shown_where_the_rule_has_one_and_blank_for_d5(at):
    shown = rules(at).set_index("Rule")
    d5 = DQ[DQ["data_source_code"] == "D5"]
    assert len(d5) == 12 and d5["detail"].isna().all()  # by design: names and statuses only
    for rule in d5["rule_code"]:
        assert pd.isna(shown.loc[rule, "Detail"]) or shown.loc[rule, "Detail"] == ""
    for _, r in DQ[DQ["detail"].notna()].iterrows():
        # verbatim apart from the Decimal('...') wrapper around numbers; nothing invented
        assert shown.loc[r["rule_code"], "Detail"] == re.sub(r"Decimal\('([^']*)'\)", r"\1", r["detail"])
    assert "Decimal(" not in " ".join(shown["Detail"].dropna())
    assert "202.7540" in shown.loc["OWID_GEN_WITHIN_5PCT", "Detail"]  # the number itself stays


def test_the_summary_counts_the_whole_run(at):
    """p6b_dq_summary = [DQ Summary]."""
    counts = DQ["status"].value_counts()
    want = f"{counts.get('PASS', 0)} pass · {counts.get('WARN', 0)} warn · {counts.get('FAIL', 0)} fail, of {len(DQ)} rules"
    assert want == "30 pass · 4 warn · 0 fail, of 34 rules"
    assert want in page_text(at)


def test_the_run_summary_is_the_dax_text(at):
    """p6b_run_summary = [Run Summary]."""
    r = F["run_latest"].iloc[0]
    want = (
        f"Run {r['run_id']} · {r['status']} · started {stamp(r['started_at'])}, finished {stamp(r['finished_at'])} UTC"
    )
    assert want in page_text(at)


# ---------------------------------------------------------------- p6b_status_slicer
def test_the_status_slicer_offers_the_three_results_in_icon_and_word_and_picks_none(at):
    pills = at.button_group(key=SLICER)
    assert pills.options == ["✓ Pass", "! Warn", "✕ Fail"]
    assert pills.value == []  # none picked shows all, as the report's tile slicer


def test_picking_warn_shows_only_the_four_warnings():
    at = run()
    at.button_group(key=SLICER).set_value(["WARN"]).run()
    shown = rules(at)
    want = expected_rules(["WARN"])
    assert len(shown) == 4
    assert set(shown["Result"]) == {"! Warn"}
    assert list(shown["Rule"]) == list(want["rule_code"])


def test_two_results_can_be_picked_together():
    at = run()
    at.button_group(key=SLICER).set_value(["PASS", "WARN"]).run()
    assert len(rules(at)) == 34
    at.button_group(key=SLICER).set_value(["PASS"]).run()
    assert len(rules(at)) == 30


def test_the_summary_ignores_the_slicer():
    """[DQ Summary] removes the page's filters: the counts are page-wide."""
    at = run()
    at.button_group(key=SLICER).set_value(["WARN"]).run()
    assert "30 pass · 4 warn · 0 fail, of 34 rules" in page_text(at)


def test_picking_a_result_nothing_has_says_so_instead_of_showing_a_blank_table():
    """Nothing fails today, so the Fail pill leaves no rule."""
    at = run()
    at.button_group(key=SLICER).set_value(["FAIL"]).run()
    assert not has_table(at, "Rows affected")
    assert any("No rules match" in i.value for i in at.info)


# ---------------------------------------------------------------- p6b_sources
def test_the_sources_table_lists_each_loaded_source_by_name(at):
    shown = sources(at)
    load = F["source_load_latest"].merge(F["data_source"][["data_source_code", "name"]], on="data_source_code")
    load = load.sort_values("name", key=lambda s: s.str.casefold())
    assert list(shown.columns) == ["Code", "Source", "Rows read", "Rows changed", "Last loaded"]
    assert list(shown["Source"]) == list(load["name"])
    assert list(shown["Code"]) == list(load["data_source_code"])
    assert list(shown["Rows read"]) == list(load["rows_in"])  # [Source Rows Read]
    assert list(shown["Rows changed"]) == list(load["rows_merged"])  # [Source Rows Changed]
    assert list(shown["Last loaded"]) == [t[:10] for t in load["loaded_at"]]  # [Source Last Loaded], yyyy-mm-dd
    assert len(shown) == 6  # sources with no load (D4, D6, GEO) drop out, as the DAX leaves them blank


def test_the_sources_table_selects_one_row_at_a_time(at):
    """'Click a source to filter the rules; click it again to clear' (p6b_sources)."""
    proto = next(d.proto for d in at.dataframe if "Rows read" in d.value.columns)
    assert list(proto.selection_mode) == [proto.SINGLE_ROW]


def test_selecting_a_source_filters_the_rules_to_it():
    at = run()
    select(at, "D1")
    want = expected_rules(code="D1")
    assert len(want) > 0
    assert list(rules(at)["Rule"]) == list(want["rule_code"])
    assert set(rules(at)["Source"]) == {"D1"}


def test_the_source_and_result_filters_combine():
    at = run()
    at.button_group(key=SLICER).set_value(["WARN"]).run()
    select(at, "D1")
    assert list(rules(at)["Rule"]) == list(expected_rules(["WARN"], "D1")["rule_code"])
    assert len(rules(at)) == 2  # CF_AT_MOST_1, STALE_COUNTRY_YEARS


def test_clearing_the_selection_brings_every_rule_back():
    at = run()
    select(at, "D3")
    assert len(rules(at)) < 34
    select(at, None)
    assert len(rules(at)) == 34


def test_a_source_with_no_rules_says_so():
    """The grid sources carry no rule of their own (their checks are the untagged grid rules)."""
    at = run()
    select(at, "DSG")
    assert any("No rules match" in i.value for i in at.info)


# ---------------------------------------------------------------- p6b_warn_note, p6b_dq_empty
def test_the_warn_note_is_the_reports_text(at):
    shown = page_text(at)
    lines = textbox("p6b_warn_note")
    assert lines[0] == "Expected WARNs (docs/reconciliation.md)"
    assert len(lines) == 5
    for line in lines:
        assert line in shown


def test_the_warn_note_still_explains_every_warning_in_the_run():
    """The note is typed text in the report: this fails when a refresh makes it stale."""
    note = "\n".join(textbox("p6b_warn_note"))
    warns = set(DQ.loc[DQ["status"] == "WARN", "rule_code"])
    assert warns == {"OWID_GEN_WITHIN_5PCT", "DOSM_SUPPLY_WITHIN_10PCT", "CF_AT_MOST_1", "STALE_COUNTRY_YEARS"}
    assert all(code in note for code in warns)


def test_with_no_run_recorded_the_page_says_so_and_shows_no_table():
    """p6b_dq_empty = [DQ Empty Message]; [DQ Summary] and [Run Summary] say the same."""
    nothing = {**F, "dq_latest": DQ.iloc[0:0], "run_latest": F["run_latest"].iloc[0:0]}
    with patched(nothing):
        at = run()
    assert any(i.value == "No pipeline run recorded" for i in at.info)
    assert not has_table(at, "Rows affected")
    assert page_text(at).count("No pipeline run recorded") >= 3
    assert not at.sidebar.error


def test_with_a_run_there_is_no_empty_message(at):
    assert "No pipeline run recorded" not in page_text(at)
    assert not any("No rules match" in i.value for i in at.info)


# ---------------------------------------------------------------- no restricted data
def test_the_page_reads_only_metadata_frames(monkeypatch):
    seen = set()

    class Spy(dict):
        def __getitem__(self, key):
            seen.add(key)
            return super().__getitem__(key)

    monkeypatch.setattr(cache, "frames", lambda: Spy(F))
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert seen and seen <= METADATA_FRAMES


# ---------------------------------------------------------------- meta.py units
def synthetic_dq(statuses, codes=None, rows=None) -> pd.DataFrame:
    n = len(statuses)
    return pd.DataFrame(
        {
            "run_id": 1,
            "rule_code": [f"R{i}" for i in range(n)],
            "description": [f"checks {i}" for i in range(n)],
            "severity": "WARN",
            "data_source_code": codes or ["D1"] * n,
            "status": statuses,
            "rows_affected": rows or [0] * n,
            "detail": [None] * n,
            "checked_at": "2026-01-01T00:00:00",
        }
    )


def test_status_label_is_icon_and_word_from_the_theme():
    from showcase import theme

    for status, (_, label) in theme.STATUS.items():
        assert meta.status_label(status) == label == LABEL[status]


def test_dq_summary_and_empty_message():
    f = {"dq_latest": synthetic_dq(["PASS", "PASS", "WARN", "FAIL"])}
    assert meta.dq_summary(f) == "2 pass · 1 warn · 1 fail, of 4 rules"
    assert meta.dq_empty_message(f) == ""
    none = {"dq_latest": synthetic_dq([])}
    assert meta.dq_summary(none) == "No pipeline run recorded" == meta.dq_empty_message(none)


def test_dq_rules_filter_by_result_and_source_and_sort_worst_first():
    dq = synthetic_dq(["PASS", "WARN", "WARN", "FAIL"], codes=["D1", "D1", "D2", None], rows=[0, 5, 5, 9])
    f = {"dq_latest": dq}
    assert list(meta.dq_rules(f)["Rule"]) == ["R3", "R1", "R2", "R0"]  # rows desc, then rule code
    assert list(meta.dq_rules(f, ["WARN"])["Rule"]) == ["R1", "R2"]
    assert list(meta.dq_rules(f, ["WARN", "FAIL"], "D2")["Rule"]) == ["R2"]
    assert list(meta.dq_rules(f, source="D1")["Rule"]) == ["R1", "R0"]  # a rule with no source never matches one
    assert meta.dq_rules(f, ["PASS"], "D2").empty


def test_dq_rules_leave_a_missing_detail_blank():
    dq = synthetic_dq(["WARN", "WARN"]).assign(detail=[None, "(1, 2)"])
    shown = meta.dq_rules({"dq_latest": dq})
    assert shown["Detail"].isna().sum() == 1
    assert shown.set_index("Rule").loc["R1", "Detail"] == "(1, 2)"


def test_source_loads_drop_sources_without_a_load_and_sort_by_name():
    ds = pd.DataFrame({"data_source_code": ["A", "B", "C"], "name": ["zeta", "Alpha", "unloaded"]})
    load = pd.DataFrame(
        {
            "data_source_code": ["A", "B"],
            "rows_in": [10, 20],
            "rows_merged": [1, 2],
            "loaded_at": ["2026-03-04T05:06:07", "2026-03-05T05:06:07"],
        }
    )
    shown = meta.source_loads({"data_source": ds, "source_load_latest": load})
    assert list(shown["Source"]) == ["Alpha", "zeta"]
    assert list(shown["Rows read"]) == [20, 10]
    assert list(shown["Last loaded"]) == ["2026-03-05", "2026-03-04"]


def test_the_chips_use_the_reports_conditional_colours():
    back, font = conditional_colours("backColor"), conditional_colours("fontColor")
    assert back == {"PASS": "#0ca30c", "WARN": "#fab219", "FAIL": "#d03b3b"}
    for status, label in LABEL.items():
        css = meta.chip_css(label)
        assert f"background-color: {back[status]}" in css and f"color: {font[status]}" in css
    assert meta.chip_css("anything else") == ""
