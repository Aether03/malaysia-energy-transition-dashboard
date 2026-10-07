"""The value scanner's context check (M5 step 10): a row label and an equal number on one line. Synthetic values."""

import re

from tools.scan_handbook_values import context_lines

LABELLED = {re.compile(r"\bJohor\b"): {0.58, 1234.5}}


def test_short_value_with_trailing_zero_beside_its_label_is_flagged():
    assert context_lines(["| state_key=`1` (Johor), year=`2022`, saifi=`0.580` |"], LABELLED) == [1]


def test_thousands_comma_form_is_flagged():
    assert context_lines(["Johor: 1,234.5 GWh"], LABELLED) == [1]


def test_value_without_its_label_is_not_flagged():
    assert context_lines(["saifi=`0.580`"], LABELLED) == []


def test_label_with_other_numbers_or_years_is_not_flagged():
    assert context_lines(["Johor in 2022: 0.59, 12 rows"], LABELLED) == []
