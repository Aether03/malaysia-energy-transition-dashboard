"""The About page (report page P6, M6 step 5): every source with its credit, licence and consent, the KPI definitions,
the method notes, the data vintage, and what the web version leaves out and why. Expected values are computed here
straight from the exported views and the manifest (or read from the report's own visual.json), never from
app/showcase/meta.py, whose pure functions get their own unit tests at the end."""

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
PAGE = str(ROOT / "app" / "pages" / "about.py")
P6 = ROOT / "report/EnergyTransition.Report/definition/pages/p6_about/visuals"

from showcase import cache, data, meta

F = data.frames()
MANIFEST = data.manifest()
REPO = "https://github.com/Aether03/malaysia-energy-transition-dashboard"
IMAGES = [f"{REPO}/blob/main/docs/img/03_regions.png", f"{REPO}/blob/main/docs/img/04_state_reliability.png"]
METADATA_FRAMES = {"data_source", "kpi", "run_latest", "source_load_latest", "dq_latest"}


# ---------------------------------------------------------------- helpers
def visual(name: str) -> dict:
    return json.loads((P6 / name / "visual.json").read_text(encoding="utf-8"))


def textbox(name: str) -> list[str]:
    paragraphs = visual(name)["visual"]["objects"]["general"][0]["properties"]["paragraphs"]
    return ["".join(r["value"] for r in p["textRuns"]) for p in paragraphs]


def shape_literal(name: str) -> str:
    text = visual(name)["visual"]["objects"]["text"][1]["properties"]["text"]["expr"]["Literal"]["Value"]
    return text[1:-1].replace("''", "'")


def stamp(iso: str) -> str:
    """DAX FORMAT(x, "yyyy-mm-dd hh:nn") of an ISO timestamp."""
    return iso[:16].replace("T", " ")


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


# ---------------------------------------------------------------- frame items: title, subtitle, footnote, badge
def test_renders_without_exception(at):
    assert at.title[0].value


def test_the_title_is_the_reports_fixed_sentence(at):
    """frame_title: typed text in the report, not a measure."""
    assert at.title[0].value == shape_literal("frame_title") == "Where the data comes from, and on what terms"


def test_the_subtitle_is_the_dax_run_summary(at):
    """frame_subtitle = [Run Summary]: the latest run, its status and its start and finish."""
    r = F["run_latest"].iloc[0]
    want = (
        f"Run {r['run_id']} · {r['status']} · started {stamp(r['started_at'])}, finished {stamp(r['finished_at'])} UTC"
    )
    assert captions(at)[0] == want


def test_the_footnote_is_the_reports_text_without_the_power_bi_sentence(at):
    """frame_footnote: verbatim, minus 'Links open in your browser (Ctrl+click in Power BI Desktop).'"""
    report = textbox("frame_footnote")[0]
    power_bi = " Links open in your browser (Ctrl+click in Power BI Desktop)."
    assert power_bi in report
    assert captions(at)[-2] == report.replace(power_bi, "")


def test_the_footer_credits_the_sources_the_page_draws_on(at):
    credits = captions(at)[-1]
    ds = F["data_source"].set_index("data_source_code")["credit_text"]
    assert credits.startswith("Credits: ")
    for code in ("D1", "D2", "D3", "D5", "D6", "DSG", "DTH"):
        assert ds[code] in credits
    assert ds["D4"] not in credits  # GSO is not used: only the table below lists it, as the report does


def test_the_fail_badge_follows_the_dq_run():
    """frame_nav_badge: nothing when no rule fails, a sidebar notice when one does."""
    assert not run().sidebar.error
    failing = {**F, "dq_latest": F["dq_latest"].assign(status=["FAIL"] + ["PASS"] * (len(F["dq_latest"]) - 1))}
    with patched(failing):
        assert "1 data-quality rule failing" in run().sidebar.error[0].value


# ---------------------------------------------------------------- p6_sources, p6_consent, p6_github
def test_the_sources_table_lists_every_data_source_row_in_the_reports_order_and_columns(at):
    shown = table(at, "Credit")
    ds = F["data_source"].sort_values("name", key=lambda s: s.str.casefold())
    assert list(shown.columns) == ["Source", "What it provides", "Licence", "Credit", "Consent", "Link"]
    assert len(shown) == len(ds) == 9
    assert list(shown["Source"]) == list(ds["name"])
    assert list(shown["What it provides"]) == list(ds["provides"])
    assert list(shown["Licence"]) == list(ds["licence"])
    assert list(shown["Credit"]) == list(ds["credit_text"])  # worded as each licence asks
    assert list(shown["Consent"]) == list(ds["consent_status"])  # the word, not just a colour
    assert list(shown["Link"]) == list(ds["url"])


def test_the_sources_table_keeps_the_requested_and_granted_sources(at):
    shown = table(at, "Credit").set_index("Source")
    assert shown.loc["Grid System Operator (GSO) System Demand", "Consent"] == "REQUESTED"
    assert shown.loc["Energy Commission Malaysia Energy Statistics Handbook", "Consent"] == "GRANTED"


def test_the_consent_summary_names_each_source_that_needs_permission(at):
    """p6_consent = [Consent Summary]: sources whose consent is not OPEN, by name, with the status in words."""
    words = {"REQUESTED": "permission requested", "GRANTED": "permission granted", "REFUSED": "permission refused"}
    ds = F["data_source"]
    ds = ds[ds["consent_status"] != "OPEN"].sort_values("name")
    want = "; ".join(f"{r['name']}: {words[r['consent_status']]}" for _, r in ds.iterrows())
    assert want  # the exported data has two such sources
    assert want in page_text(at)


def test_the_github_button_opens_the_reports_repository(at):
    """p6_github: the action button 'Source code on GitHub'."""
    link = visual("p6_github")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]["webUrl"]
    url = link["expr"]["Literal"]["Value"].strip("'")
    assert url == REPO
    label = visual("p6_github")["visual"]["objects"]["text"][1]["properties"]["text"]["expr"]["Literal"]["Value"]
    buttons = [(b.proto.label, b.proto.url) for b in at.get("link_button")]
    assert (label.strip("'"), url) in buttons


# ---------------------------------------------------------------- p6_kpis, p6_notes
def test_the_kpi_table_defines_every_kpi_in_the_reports_columns(at):
    shown = table(at, "Definition")
    kpi = F["kpi"].sort_values("name", key=lambda s: s.str.casefold())
    assert list(shown.columns) == ["KPI", "Definition", "Formula", "Unit"]
    assert list(shown["KPI"]) == list(kpi["name"])
    assert list(shown["Definition"]) == list(kpi["definition"])
    assert list(shown["Formula"]) == list(kpi["formula"])
    assert list(shown["Unit"]) == list(kpi["unit"])
    assert len(shown) == 11


def test_the_method_notes_are_the_reports_text(at):
    shown = page_text(at)
    notes = textbox("p6_notes")
    assert notes[0] == "Method notes"
    assert len(notes) == 6
    for line in notes:
        assert line in shown


def test_the_notes_about_pages_the_web_leaves_out_say_so(at):
    shown = page_text(at)
    for key in ("States: handbook labels", "Sarawak: the 2023 handbook"):
        assert next(line for line in textbox("p6_notes") if line.startswith(key)) in shown
    assert "The States and Sarawak notes describe the report's Regions and State reliability pages" in shown
    assert "not in this web version" in shown


# ---------------------------------------------------------------- the data vintage
def test_the_vintage_shows_the_export_time_and_the_run(at):
    shown = page_text(at)
    assert f"{stamp(MANIFEST['exported_at'])} UTC" in shown
    assert f"run {MANIFEST['run']['run_id']}" in shown.lower()


def test_the_vintage_table_has_one_row_per_source_with_its_version(at):
    shown = table(at, "Source version")
    vintage = MANIFEST["data_vintage"]
    names = F["data_source"].set_index("data_source_code")["name"]
    assert list(shown["Source"]) == [names[v["data_source_code"]] for v in vintage]
    assert list(shown["Source version"]) == [v["source_version"] for v in vintage]
    assert list(shown["Loaded"]) == [stamp(v["loaded_at"]) for v in vintage]
    assert list(shown["Run"]) == [v["run_id"] for v in vintage]
    assert len(shown) == len(vintage) == 6


# ---------------------------------------------------------------- what the web version leaves out
def test_every_excluded_view_and_query_is_listed_with_its_reason(at):
    shown = table(at, "Why")
    pairs = {(r["Left out"], r["Why"]) for _, r in shown.iterrows()}
    want = {(k, v) for k, v in {**MANIFEST["excluded_views"], **MANIFEST["excluded_showcase"]}.items()}
    assert pairs == want
    assert ("region_annual", "D5 not publishable") in pairs
    assert len(shown) == 10


def test_the_page_explains_why_regions_and_state_reliability_are_not_here(at):
    shown = page_text(at)
    assert "Regions" in shown and "State reliability" in shown
    assert "charts as images" in shown  # the consent covers charts as images, not the data rows
    assert "data rows" in shown
    assert "Not endorsed by the Energy Commission" in shown  # consent condition 4 (DATA_LICENSES.md)


def test_the_two_consented_images_are_linked_not_embedded(at):
    shown = page_text(at)
    for url in IMAGES:
        assert f"]({url})" in shown
    assert not at.get("imgs") and not at.get("image")
    assert "![" not in shown


def test_the_page_reads_only_metadata_frames_and_shows_no_handbook_table(monkeypatch):
    """No D4/D5 data beyond the data_source, kpi, dq_latest and load metadata the export already holds."""
    seen = set()

    class Spy(dict):
        def __getitem__(self, key):
            seen.add(key)
            return super().__getitem__(key)

    monkeypatch.setattr(cache, "frames", lambda: Spy(F))
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert seen and seen <= METADATA_FRAMES
    assert not any(name in F for name in MANIFEST["excluded_views"])  # none of the D5 views was ever exported


# ---------------------------------------------------------------- meta.py units
def frames_with(**overrides):
    return {**F, **overrides}


def test_run_summary_says_when_no_run_is_recorded():
    empty = F["run_latest"].iloc[0:0]
    assert meta.run_summary(frames_with(run_latest=empty)) == "No pipeline run recorded"


def test_run_summary_formats_the_two_times_without_seconds():
    run_latest = pd.DataFrame(
        {"run_id": [9], "started_at": ["2026-01-02T03:04:59"], "finished_at": ["2026-01-02T05:06:07"], "status": ["OK"]}
    )
    assert meta.run_summary(frames_with(run_latest=run_latest)) == (
        "Run 9 · OK · started 2026-01-02 03:04, finished 2026-01-02 05:06 UTC"
    )


def test_consent_summary_is_empty_when_every_source_is_open():
    ds = F["data_source"].assign(consent_status="OPEN")
    assert meta.consent_summary(frames_with(data_source=ds)) == ""


def test_consent_summary_passes_an_unknown_status_through_and_sorts_by_name():
    ds = pd.DataFrame(
        {
            "name": ["Zed", "Alpha", "Mid"],
            "consent_status": ["REFUSED", "MAYBE", "OPEN"],
            "data_source_code": list("ZAM"),
        }
    )
    assert meta.consent_summary(frames_with(data_source=ds)) == "Alpha: MAYBE; Zed: permission refused"


def test_sources_table_sorts_names_ignoring_case():
    ds = F["data_source"].iloc[:3].assign(name=["b source", "A source", "C source"])
    assert list(meta.sources_table(frames_with(data_source=ds))["Source"]) == ["A source", "b source", "C source"]


def test_exported_at_reads_the_manifest_time_as_utc():
    assert meta.exported_at({"exported_at": "2026-10-10T18:55:20+00:00"}) == "2026-10-10 18:55 UTC"


def test_left_out_lists_views_then_queries_each_with_its_reason():
    m = {"excluded_views": {"b_view": "why b", "a_view": "why a"}, "excluded_showcase": {"q": "why q"}}
    shown = meta.left_out(m)
    assert list(shown.columns) == ["Left out", "Kind", "Why"]
    assert list(shown["Left out"]) == ["a_view", "b_view", "q"]
    assert list(shown["Why"]) == ["why a", "why b", "why q"]


def test_left_out_is_empty_when_nothing_is_excluded():
    assert meta.left_out({"excluded_views": {}, "excluded_showcase": {}}).empty
