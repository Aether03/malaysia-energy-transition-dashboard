"""tools/export_pages.py: which pages reach the public export (M5 plan Q2). No PDF needed."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import export_pages as ep

PAGES = [
    ("59dacfc5089b163e62a0", "Overview"),
    ("p3_regions", "Regions"),
    ("p3b_state_reliability", "State reliability"),
    ("p6b_data_quality", "Data quality"),
]


def test_restricted_pages_are_dropped_until_consent_is_granted():
    for status in ("NOT_REQUESTED", "REQUESTED", "REFUSED"):
        assert ep.keep_flags(PAGES, {"D5": status}) == [True, False, False, True]
    assert ep.keep_flags(PAGES, {"D5": "GRANTED"}) == [True, True, True, True]


def test_a_missing_consent_row_does_not_publish_a_restricted_page():
    # Absent from the seed means not GRANTED: the page stays out.
    assert ep.keep_flags([("p3_regions", "Regions")], {"D1": "OPEN"}) == [False]


def test_marker_check_passes_when_mapping_and_content_agree():
    texts = [
        "Renewables supplied",
        "SAIFI by region: Sabah",
        "SAIDI by state, 2022 (darker = less reliable)",
        "34 rules",
    ]
    assert ep.check_markers(texts, [True, False, False, True], PAGES) == []


def test_marker_check_passes_when_consent_keeps_the_restricted_pages():
    texts = ["Renewables supplied", "SAIFI by region: Sabah", "(darker = less reliable)", "34 rules"]
    assert ep.check_markers(texts, [True, True, True, True], PAGES) == []


def test_marker_check_refuses_restricted_text_on_a_kept_page():
    texts = ["Renewables supplied", "SAIFI by region", "darker = less reliable", "SAIFI by region leaked"]
    problems = ep.check_markers(texts, [True, False, False, True], PAGES)
    assert len(problems) == 1 and problems[0].startswith("p6b_data_quality: kept page")


def test_marker_check_refuses_a_shifted_page_order():
    texts = ["SAIFI by region", "Renewables supplied", "darker = less reliable", "34 rules"]
    problems = ep.check_markers(texts, [True, False, False, True], PAGES)
    assert any(p.startswith("59dacfc5089b163e62a0: kept page") for p in problems)
    assert any(p.startswith("p3_regions: dropped page has no restricted marker") for p in problems)


def test_visible_pages_skip_hidden_ones_and_keep_report_order(tmp_path):
    (tmp_path / "pages.json").write_text(json.dumps({"pageOrder": ["b", "a", "t"]}), encoding="utf-8")
    for name, extra in (("a", {}), ("b", {}), ("t", {"visibility": "HiddenInViewMode"})):
        (tmp_path / name).mkdir()
        (tmp_path / name / "page.json").write_text(json.dumps({"displayName": name.upper(), **extra}), encoding="utf-8")
    assert ep.visible_pages(tmp_path) == [("b", "B"), ("a", "A")]


def test_slug():
    assert ep.slug(3, "Grid load") == "03_grid_load"
    assert ep.slug(7, "Data quality") == "07_data_quality"
