"""The value scanner's context check (M5 step 10): a row label and an equal number on one line. Synthetic values."""

import re

from tools.scan_handbook_values import context_lines, scannable_pages

LABELLED = {re.compile(r"\bJohor\b"): {0.58, 1234.5}}


def test_short_value_with_trailing_zero_beside_its_label_is_flagged():
    assert context_lines(["| state_key=`1` (Johor), year=`2022`, saifi=`0.580` |"], LABELLED) == [1]


def test_thousands_comma_form_is_flagged():
    assert context_lines(["Johor: 1,234.5 GWh"], LABELLED) == [1]


def test_value_without_its_label_is_not_flagged():
    assert context_lines(["saifi=`0.580`"], LABELLED) == []


def test_label_with_other_numbers_or_years_is_not_flagged():
    assert context_lines(["Johor in 2022: 0.59, 12 rows"], LABELLED) == []


# PDF pages (M5, D5 consent 2026-10-09): the consented Regions/State reliability pages are skipped only while
# D5 is GRANTED; markers are the export tool's (tools/export_pages.py). Synthetic values.
PAGES = ["Renewables supplied 20.4%", "SAIFI by region: Johor 1,234.5", "34 rules"]


def test_restricted_pdf_page_is_scanned_until_consent_is_granted():
    for status in ("NOT_REQUESTED", "REQUESTED", "REFUSED"):
        assert scannable_pages(PAGES, {"D5": status}) == PAGES


def test_consented_pdf_page_is_skipped_and_the_others_are_still_scanned():
    assert scannable_pages(PAGES, {"D5": "GRANTED"}) == [PAGES[0], PAGES[2]]


def test_values_on_an_unmarked_page_are_scanned_even_with_consent():
    assert scannable_pages(["Johor 1,234.5"], {"D5": "GRANTED"}) == ["Johor 1,234.5"]


def test_a_missing_consent_row_keeps_the_page_in_the_scan():
    assert scannable_pages(PAGES, {"D1": "OPEN"}) == PAGES
