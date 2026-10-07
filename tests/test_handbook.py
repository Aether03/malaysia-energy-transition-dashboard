"""Tests for pipeline/sources/handbook.py (M4 step 5, written BEFORE the parser).

No PDF, no database, no network: the parser is exercised on the committed synthetic page fixtures
(tests/fixtures/handbook/p<page>.json: real word layouts, every number replaced) and on tiny
hand-built tables. Expected values are found in the fixture words by small helpers written here,
independently of the implementation (nearest value line to a label word, then x order).
"""

import copy
import dataclasses
import functools
import hashlib
import json
import pathlib
import random
from dataclasses import replace

import pytest

from pipeline import config
from pipeline.sources import handbook
from pipeline.sources._common import (
    InvalidDownloadError,
    SchemaMismatchError,
    assert_unique_keys,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "handbook"
SPECS = handbook.TABLES[2023]
SPEC_BY_CODE = {s.table_code: s for s in SPECS}
ALL_CODES = [s.table_code for s in SPECS]
PAGES = sorted({s.page for s in SPECS})

# Table -> (data rows, value columns), as pinned in the M4 plan.
SHAPE = {
    "INSTALLED_CAPACITY": (23, 10),
    "AVAILABLE_CAPACITY": (4, 7),
    "KEY_DATA_PEN": (12, 7),
    "KEY_DATA_SAB": (12, 7),
    "KEY_DATA_SAR": (12, 7),
    "SUPPLY_INTERRUPTIONS": (13, 3),
    "PEN_DIST_PERF": (5, 8),
    "SAIDI_BY_STATE": (14, 8),
    "SAIFI_BY_STATE": (14, 8),
    "CAIDI_BY_STATE": (14, 8),
    "SABAH_DIST_PERF": (5, 8),
    "SARAWAK_DIST_PERF": (3, 8),
}
TOTAL_CELLS = 989

# One single-line-labelled row per table, used by the mutation traps: (anchor label word, nth).
# `nth` counts occurrences of that word in the label zone, top to bottom, over the whole page.
TRAP_ROWS = {
    "INSTALLED_CAPACITY": ("IPPs", 0),
    "AVAILABLE_CAPACITY": ("Sabah", 0),
    "KEY_DATA_PEN": ("Population", 0),
    "KEY_DATA_SAB": ("Population", 0),
    "KEY_DATA_SAR": ("Population", 0),
    "SUPPLY_INTERRUPTIONS": ("2013", 0),  # the revenue table above it is unpinned, so its years are scrambled
    "PEN_DIST_PERF": ("Scheduled", 0),
    "SAIDI_BY_STATE": ("Kedah", 0),
    "SAIFI_BY_STATE": ("Kedah", 0),
    "CAIDI_BY_STATE": ("Kedah", 1),  # SAIFI's table is above it on p.84
    "SABAH_DIST_PERF": ("Scheduled", 0),
    "SARAWAK_DIST_PERF": ("SAIDI", 1),  # Sabah's SAIDI row is above it on p.85
}


# --- helpers: fixtures ---------------------------------------------------------------------


@functools.cache
def _fixture(page):
    return json.loads((FIXTURES / f"p{page}.json").read_text(encoding="utf-8"))


def _raw(page):
    """A fresh, mutable copy of a page's fixture words (list of dicts)."""
    return copy.deepcopy(_fixture(page)["words"])


def _words(raw):
    return [handbook.Word(**w) for w in raw]


def _parse(code, raw=None, spec=None, edition=2023):
    spec = spec or SPEC_BY_CODE[code]
    raw = _raw(spec.page) if raw is None else raw
    return handbook.cells_from_words(_words(raw), spec, edition)


def _rows(cells):
    """Cells grouped by row, in order."""
    out = {}
    for c in cells:
        out.setdefault(c.row_pos, []).append(c)
    return [out[k] for k in sorted(out)]


# --- helpers: an independent view of the fixture words -------------------------------------


def _yc(w):
    return (w["top"] + w["bottom"]) / 2


def _lines(raw):
    """Words grouped into lines, simplest possible way: by centre, 3 pt from the line's first word."""
    out = []
    for w in sorted(raw, key=_yc):
        if out and abs(_yc(w) - _yc(out[-1][0])) <= 3.0:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in out]


def _line_text(line):
    return " ".join(w["text"] for w in line)


def _remove(raw, word):
    raw[:] = [w for w in raw if w is not word]


def _label_word(raw, spec, text, nth=0):
    """The nth (top to bottom) word with this text left of the table's label limit."""
    found = sorted((w for w in raw if w["text"] == text and w["x0"] < spec.label_x_max), key=_yc)
    return found[nth]


def _expected_row(raw, spec, anchor, nth=0):
    """The value words of the row an anchor label word belongs to: the numeric words in the value
    zone on the line nearest (vertically) to the anchor, left to right."""
    ay = _yc(_label_word(raw, spec, anchor, nth))
    nums = [w for w in raw if w["x0"] >= spec.label_x_max and handbook.VALUE_TOKEN.match(w["text"])]
    near = min(nums, key=lambda w: abs(_yc(w) - ay))
    return sorted((w for w in nums if abs(_yc(w) - _yc(near)) <= 2.0), key=lambda w: w["x0"])


def _reject(code, raw, spec=None):
    """Parsing must stop with SchemaMismatchError naming the table."""
    spec = spec or SPEC_BY_CODE[code]
    with pytest.raises(SchemaMismatchError, match=spec.table_code):
        handbook.cells_from_words(_words(raw), spec, 2023)


def _drop_first_word_of(raw, anchor):
    """Remove the first word of `anchor` from the first line containing it (breaks that anchor only)."""
    line = next(ln for ln in _lines(raw) if anchor in _line_text(ln))
    first = anchor.split()[0]
    _remove(raw, next(w for w in line if w["text"] == first))


# --- helpers: hand-built words and lines ---------------------------------------------------


def _w(text, x0, yc, width=None, height=7.0):
    width = 6.0 * len(text) if width is None else width
    return handbook.Word(text, x0, x0 + width, yc - height / 2, yc + height / 2)


def _wc(text, xc, yc):
    """A word centred on xc."""
    width = 6.0 * len(text)
    return _w(text, xc - width / 2, yc, width)


def _line(text, y):
    return handbook.Line((_w(text, 10.0, y),), y, text)


def _texts(lines):
    return [ln.text for ln in lines]


COL_A, COL_B = 90.0, 130.0


def _mini_spec(row_labels=("r1", "r2", "r3"), **kw):
    base = {
        "table_code": "MINI", "page": 1, "title": "My Table", "start_after": "My Table",
        "stop_before": "Notes", "label_x_max": 50.0, "col_labels": ("A", "B"), "row_labels": row_labels,
    }  # fmt: skip
    return handbook.TableSpec(**{**base, **kw})


def _mini_words(rows=None, gap=15.0, first_y=40.0, header=None):
    """Title, one header line, the given rows [(label, a, b)] at `gap` spacing, then a notes line."""
    rows = rows or [("r1", "1,500", "2.0"), ("r2", "3", "-"), ("r3", "4.50", "6%")]
    words = [_w("My", 10, 10), _w("Table", 30, 10)]
    words += header or [_wc("A", COL_A, 25), _wc("B", COL_B, 25)]
    y = first_y
    for label, a, b in rows:
        words += [_w(label, 10, y), _wc(a, COL_A, y), _wc(b, COL_B, y)]
        y += gap
    words.append(_w("Notes", 10, y + 15))
    return words


# --- module constants and the pins ---------------------------------------------------------


def test_constants():
    assert handbook.SOURCE == "handbook"
    assert handbook.EDITION == 2023
    assert handbook.LINE_TOLERANCE_PT == 3.0
    assert handbook.COLUMN_TOLERANCE_PT == 10.0
    assert handbook.PAGE_FURNITURE == "ENERGY STATISTICS HANDBOOK"
    assert handbook.RAW_COLUMNS == (
        "edition", "page", "table_code", "row_pos", "col_pos", "row_group", "row_label", "col_label", "value_text",
    )  # fmt: skip
    assert handbook.KEY_COLUMNS == ("edition", "page", "table_code", "row_pos", "col_pos")


def test_key_columns_are_a_prefix_subset_of_raw_columns():
    key, raw = handbook.KEY_COLUMNS, handbook.RAW_COLUMNS
    assert set(key) <= set(raw)
    assert raw[: len(key)] == key  # load() takes the key positions as range(len(KEY_COLUMNS))
    assert len(set(raw)) == len(raw)


def test_cell_fields_follow_raw_columns_and_as_record_is_in_that_order():
    assert [f.name for f in dataclasses.fields(handbook.Cell)] == list(handbook.RAW_COLUMNS)
    cell = handbook.Cell(2023, 13, "T", 4, 5, "Sabah", "IPPs", "Coal", "1,234.5")
    assert cell.as_record() == (2023, 13, "T", 4, 5, "Sabah", "IPPs", "Coal", "1,234.5")
    assert cell.as_record() == tuple(getattr(cell, name) for name in handbook.RAW_COLUMNS)


def test_pinned_tables_are_the_twelve_of_the_2023_edition():
    assert list(handbook.TABLES) == [2023]
    assert ALL_CODES == list(SHAPE)
    assert len(set(ALL_CODES)) == 12
    assert PAGES == [13, 14, 17, 18, 19, 82, 83, 84, 85]


@pytest.mark.parametrize("code", ALL_CODES)
def test_pinned_spec_matches_the_expected_shape(code):
    spec = SPEC_BY_CODE[code]
    assert (len(spec.row_labels), len(spec.col_labels)) == SHAPE[code]


def test_the_expected_cell_total_is_989():
    assert sum(r * c for r, c in SHAPE.values()) == TOTAL_CELLS == 989


# --- VALUE_TOKEN and normalise -------------------------------------------------------------


@pytest.mark.parametrize(
    "token", ["0", "5", "-", "12.5", "-3.2", "1,234", "1,234.56", "123,456,789", "0.714", "60.3%", "855%", "-1,000"]
)
def test_value_token_accepts_printed_numbers(token):
    assert handbook.VALUE_TOKEN.match(token)


@pytest.mark.parametrize(
    "token",
    ["", "n/a", "N/A", "1,23", "1,2345", "1e5", "--", "1.", ".5", "5-", "$5", "(5)", "12 %", "1 234", "1.2.3", "x"],
)
def test_value_token_rejects_everything_else(token):
    assert not handbook.VALUE_TOKEN.match(token)


def test_normalise_collapses_whitespace_and_strips():
    assert handbook.normalise("  a \t b\n\nc  ") == "a b c"
    assert handbook.normalise("") == ""
    assert handbook.normalise("already fine") == "already fine"


# --- fixtures: the licence guard and coverage ----------------------------------------------


def test_every_pinned_page_has_a_fixture_and_no_other_fixture_exists():
    on_disk = sorted(p.name for p in FIXTURES.glob("*.json"))
    assert on_disk == [f"p{page}.json" for page in PAGES]


@pytest.mark.parametrize("page", PAGES)
def test_every_fixture_is_marked_synthetic(page):
    """The licence guard (M4 plan Q1): a fixture must say it holds no Energy Commission data."""
    data = _fixture(page)
    assert data["synthetic"] is True
    assert "SYNTHETIC" in data["note"]
    assert data["edition"] == 2023
    assert data["page"] == page
    assert data["words"]


@pytest.mark.parametrize("page", PAGES)
def test_every_fixture_word_has_text_and_a_box(page):
    for w in _fixture(page)["words"]:
        assert set(w) == {"text", "x0", "x1", "top", "bottom"}
        assert isinstance(w["text"], str)
        assert w["text"] == w["text"].strip()
        assert w["x0"] < w["x1"]
        assert w["top"] < w["bottom"]
    handbook.Word(**_fixture(page)["words"][0])  # constructible


# --- 1. every pinned table parses from its fixture -----------------------------------------


@pytest.mark.parametrize("code", ALL_CODES)
def test_table_has_rows_times_columns_cells_in_row_then_column_order(code):
    n_rows, n_cols = SHAPE[code]
    cells = _parse(code)
    assert len(cells) == n_rows * n_cols
    assert [(c.row_pos, c.col_pos) for c in cells] == [
        (r, c) for r in range(1, n_rows + 1) for c in range(1, n_cols + 1)
    ]


@pytest.mark.parametrize("code", ALL_CODES)
def test_row_labels_equal_the_pin_one_per_row(code):
    spec = SPEC_BY_CODE[code]
    rows = _rows(_parse(code))
    assert [{c.row_label for c in row} for row in rows] == [{label} for label in spec.row_labels]


@pytest.mark.parametrize("code", ALL_CODES)
def test_col_labels_equal_the_pin_by_col_pos_in_every_row(code):
    spec = SPEC_BY_CODE[code]
    for row in _rows(_parse(code)):
        assert [c.col_label for c in row] == list(spec.col_labels)


@pytest.mark.parametrize("code", ALL_CODES)
def test_metadata_and_value_tokens(code):
    spec = SPEC_BY_CODE[code]
    for c in _parse(code):
        assert isinstance(c, handbook.Cell)
        assert (c.edition, c.page, c.table_code) == (2023, spec.page, code)
        assert isinstance(c.row_pos, int)
        assert isinstance(c.col_pos, int)
        assert isinstance(c.value_text, str)
        assert handbook.VALUE_TOKEN.match(c.value_text), c


@pytest.mark.parametrize("code", ALL_CODES)
def test_as_record_order_is_raw_columns(code):
    for c in _parse(code):
        record = c.as_record()
        assert len(record) == len(handbook.RAW_COLUMNS)
        assert record == tuple(getattr(c, name) for name in handbook.RAW_COLUMNS)


@pytest.mark.parametrize("code", ALL_CODES)
def test_every_value_text_is_a_value_zone_word_of_the_fixture(code):
    spec = SPEC_BY_CODE[code]
    zone = {w["text"] for w in _raw(spec.page) if w["x0"] >= spec.label_x_max}
    assert {c.value_text for c in _parse(code)} <= zone


def test_all_tables_together_give_989_cells_with_unique_keys():
    records = [c.as_record() for code in ALL_CODES for c in _parse(code)]
    assert len(records) == TOTAL_CELLS
    assert_unique_keys(records, range(len(handbook.KEY_COLUMNS)))


def test_edition_comes_from_the_argument():
    cells = _parse("AVAILABLE_CAPACITY", edition=1999)
    assert {c.edition for c in cells} == {1999}


def test_word_order_in_the_input_does_not_matter():
    for code in ("INSTALLED_CAPACITY", "SAIDI_BY_STATE", "SARAWAK_DIST_PERF"):
        spec = SPEC_BY_CODE[code]
        shuffled = _raw(spec.page)
        random.Random(7).shuffle(shuffled)
        assert _parse(code, shuffled) == _parse(code)


def test_the_input_word_list_is_not_modified():
    words = _words(_raw(83))
    before = list(words)
    handbook.cells_from_words(words, SPEC_BY_CODE["SAIDI_BY_STATE"], 2023)
    assert words == before


def test_two_tables_on_one_page_do_not_leak_into_each_other():
    saifi = _parse("SAIFI_BY_STATE")
    caidi = _parse("CAIDI_BY_STATE")
    assert {c.table_code for c in saifi} == {"SAIFI_BY_STATE"}
    assert [c.value_text for c in saifi] != [c.value_text for c in caidi]
    assert len({c.value_text for c in saifi} & {c.value_text for c in caidi}) < 10


# --- 2. spot values, found independently in the fixture words ------------------------------

# (table, anchor label word, nth occurrence, row_pos, col_pos): the whole row is compared, and the
# named cell is checked on its own.
SPOTS = [
    ("SAIFI_BY_STATE", "Kedah", 0, 2, 1),  # first year column
    ("SAIFI_BY_STATE", "Kuala", 0, 4, 3),  # a value printed with a trailing zero ("3.00")
    ("SAIDI_BY_STATE", "Putrajaya", 0, 11, 8),  # wrapped label, last column
    ("SAIFI_BY_STATE", "Putrajaya", 0, 11, 8),
    ("CAIDI_BY_STATE", "Putrajaya", 1, 11, 8),
    ("SAIDI_BY_STATE", "PENINSULAR", 0, 14, 1),
    ("SAIDI_BY_STATE", "PENINSULAR", 0, 14, 8),
    ("KEY_DATA_PEN", "(GWh)", 0, 6, 1),
    ("KEY_DATA_PEN", "(toe/GDP", 0, 10, 4),  # Final Energy Intensity (toe/GDP at 2015 prices (RM million))
    ("KEY_DATA_PEN", "(toe/", 0, 11, 7),  # Electricity Intensity (toe/ GDP at 2015 prices (RM million))
    ("KEY_DATA_SAB", "Population", 0, 3, 7),
    ("KEY_DATA_SAR", "Population", 0, 3, 1),
    ("SARAWAK_DIST_PERF", "SAIDI", 1, 1, 8),  # last column: the second "2019"
    ("SARAWAK_DIST_PERF", "SAIDI", 1, 1, 6),  # the first "2019"
    ("SARAWAK_DIST_PERF", "CAIDI", 1, 3, 8),
    ("SABAH_DIST_PERF", "SAIFI", 0, 4, 5),
    ("PEN_DIST_PERF", "Scheduled", 0, 1, 1),
    ("PEN_DIST_PERF", "CAIDI", 0, 5, 8),
    ("INSTALLED_CAPACITY", "Subtotal", 1, 17, 10),  # Sabah's Subtotal x Total
    ("INSTALLED_CAPACITY", "SEB", 0, 18, 1),
    ("INSTALLED_CAPACITY", "RE", 0, 6, 2),  # RE Non-FiT
    ("INSTALLED_CAPACITY", "Share", 0, 23, 10),  # the percent row
    ("AVAILABLE_CAPACITY", "Peninsular", 0, 1, 1),
    ("AVAILABLE_CAPACITY", "Total", 0, 4, 7),
    ("SUPPLY_INTERRUPTIONS", "2010", 0, 1, 1),
    ("SUPPLY_INTERRUPTIONS", "2022", 0, 13, 3),
]


@pytest.mark.parametrize(("code", "anchor", "nth", "row_pos", "col_pos"), SPOTS, ids=lambda v: str(v))
def test_spot_row_values_match_the_fixture_words(code, anchor, nth, row_pos, col_pos):
    spec = SPEC_BY_CODE[code]
    n_cols = len(spec.col_labels)
    expected = _expected_row(_raw(spec.page), spec, anchor, nth)
    assert len(expected) == n_cols  # the finder and the fixture agree on the layout
    cells = _parse(code)
    row = cells[(row_pos - 1) * n_cols : row_pos * n_cols]
    assert row[0].row_pos == row_pos
    assert [c.value_text for c in row] == [w["text"] for w in expected]
    cell = row[col_pos - 1]
    assert (cell.row_pos, cell.col_pos) == (row_pos, col_pos)
    assert cell.value_text == expected[col_pos - 1]["text"]


def test_values_keep_their_printed_form_commas_trailing_zeros_percent():
    saifi = {(c.row_pos, c.col_pos): c.value_text for c in _parse("SAIFI_BY_STATE")}
    assert saifi[(4, 3)] == "3.00"  # not "3.0" or 3.0
    installed = _parse("INSTALLED_CAPACITY")
    texts = [c.value_text for c in installed]
    assert any("," in t for t in texts)  # thousands separators kept
    assert all(t.endswith("%") for t in (c.value_text for c in installed if c.row_label == "Share (%)"))
    per_capita = [c.value_text for c in _rows(_parse("KEY_DATA_PEN"))[7]]  # printed with three decimals
    assert all(len(t.split(".")[1]) == 3 for t in per_capita)


def test_sarawak_repeats_2019_as_columns_6_and_8_with_different_values():
    spec = SPEC_BY_CODE["SARAWAK_DIST_PERF"]
    assert spec.col_labels[5] == spec.col_labels[7] == "2019"
    cells = _parse("SARAWAK_DIST_PERF")
    for row in _rows(cells):
        assert [c.col_pos for c in row if c.col_label == "2019"] == [6, 8]
    assert len({(c.row_pos, c.col_pos) for c in cells}) == 24  # both kept: keyed by position, not by label
    sar = _raw(85)
    row = _expected_row(sar, spec, "SAIDI", 1)
    first, last = (c for c in cells if c.row_pos == 1 and c.col_label == "2019")
    assert (first.value_text, last.value_text) == (row[5]["text"], row[7]["text"])
    assert first.value_text != last.value_text


# --- 3. wrapped labels ---------------------------------------------------------------------


@pytest.mark.parametrize("code", ["SAIDI_BY_STATE", "SAIFI_BY_STATE", "CAIDI_BY_STATE"])
def test_putrajaya_label_above_and_below_its_value_line_belongs_to_one_row(code):
    rows = _rows(_parse(code))
    assert {c.row_label for c in rows[10]} == {"WP Putrajaya (including Cyberjaya)"}
    assert {c.row_label for c in rows[9]} == {"Pulau Pinang"}
    assert {c.row_label for c in rows[11]} == {"Selangor"}


@pytest.mark.parametrize("code", ["SAIDI_BY_STATE", "SAIFI_BY_STATE", "CAIDI_BY_STATE"])
def test_peninsular_malaysia_total_row_label_wraps_around_its_values(code):
    rows = _rows(_parse(code))
    assert len(rows) == 14
    assert {c.row_label for c in rows[13]} == {"PENINSULAR MALAYSIA"}
    assert {c.row_label for c in rows[12]} == {"Terengganu"}


def test_kuala_lumpur_and_negeri_sembilan_two_word_labels_on_the_value_line():
    rows = _rows(_parse("SAIDI_BY_STATE"))
    assert rows[3][0].row_label == "WP Kuala Lumpur"
    assert rows[5][0].row_label == "Negeri Sembilan"


def test_key_data_multi_line_labels_are_joined_top_to_bottom_with_single_spaces():
    rows = _rows(_parse("KEY_DATA_PEN"))
    assert rows[0][0].row_label == "GDP at Current Prices (RM million)*"
    assert rows[2][0].row_label == "Population ('000 people)**"
    assert rows[5][0].row_label == "Electricity Consumption (GWh)"
    assert rows[8][0].row_label == "Electricity Consumption (kWh) per Capita"
    assert rows[9][0].row_label == "Final Energy Intensity (toe/GDP at 2015 prices (RM million))"
    assert rows[10][0].row_label == "Electricity Intensity (toe/ GDP at 2015 prices (RM million))"
    assert rows[11][0].row_label == "Electricity Intensity (GWh/GDP at 2015 prices (RM million))"


def test_key_data_header_words_left_of_the_label_limit_are_not_column_labels():
    # p.17's header line starts with "PENINSULAR MALAYSIA" at x 43 and 93, left of label_x_max 139.
    cells = _parse("KEY_DATA_PEN")
    assert {c.col_label for c in cells} == set(handbook.TABLES[2023][2].col_labels)
    assert not any("PENINSULAR" in c.col_label or "MALAYSIA" in c.col_label for c in cells)
    saidi = _parse("SAIDI_BY_STATE")
    assert not any("State" in c.col_label for c in saidi)  # the "State" header word is a label-zone word


def test_ignored_sub_heading_lines_are_exact_whole_line_matches():
    """'Energy Intensity' is an ignored line, yet it is also inside the row label 'Final Energy Intensity'."""
    spec = SPEC_BY_CODE["KEY_DATA_PEN"]
    assert "Energy Intensity" in spec.ignore_lines
    lines = handbook.group_lines(_words(_raw(17)))
    kept = _texts(handbook.table_region(lines, spec))
    assert "Energy Intensity" not in kept
    assert "Per Capita" not in kept
    assert "Final Energy Intensity" in kept  # a different line, kept
    assert any(t.startswith("Electricity Intensity") for t in kept)
    assert any("per Capita*" in t for t in kept)  # "(RM) per Capita*" survives the "Per Capita" ignore
    row10 = _rows(_parse("KEY_DATA_PEN"))[9]
    assert {c.row_label for c in row10} == {"Final Energy Intensity (toe/GDP at 2015 prices (RM million))"}


@pytest.mark.parametrize("code", ["PEN_DIST_PERF", "SABAH_DIST_PERF"])
def test_distribution_sub_heading_lines_are_ignored_not_rows(code):
    spec = SPEC_BY_CODE[code]
    lines = handbook.group_lines(_words(_raw(spec.page)))
    kept = _texts(handbook.table_region(lines, spec))
    for ignored in spec.ignore_lines:
        assert ignored not in kept
    assert len(_rows(_parse(code))) == 5


# --- 4. row groups -------------------------------------------------------------------------


def test_installed_capacity_row_groups():
    rows = _rows(_parse("INSTALLED_CAPACITY"))
    groups = [{c.row_group for c in row} for row in rows]
    assert all(len(g) == 1 for g in groups)  # one group per row
    flat = [next(iter(g)) for g in groups]
    assert flat[0:9] == ["Peninsular Malaysia"] * 9  # TNB .. Subtotal
    assert flat[9:17] == ["Sabah"] * 8  # SESB .. Subtotal
    assert flat[17:21] == ["Sarawak"] * 4  # SEB .. Subtotal
    assert flat[21:] == [None, None]  # Total, Share (%)
    labels = [rows[i][0].row_label for i in (8, 9, 16, 17, 20, 21, 22)]
    assert labels == ["Subtotal", "SESB", "Subtotal", "SEB", "Subtotal", "Total", "Share (%)"]


@pytest.mark.parametrize("code", [c for c in ALL_CODES if c != "INSTALLED_CAPACITY"])
def test_other_tables_have_no_row_group(code):
    assert SPEC_BY_CODE[code].row_groups == ()
    assert {c.row_group for c in _parse(code)} == {None}


def test_repeated_row_labels_are_distinguished_by_row_position():
    cells = _parse("INSTALLED_CAPACITY")
    ipps = sorted({c.row_pos for c in cells if c.row_label == "IPPs"})
    subtotals = sorted({c.row_pos for c in cells if c.row_label == "Subtotal"})
    assert ipps == [2, 11]
    assert subtotals == [9, 17, 21]


# --- 6. failure traps (each mutates a deep copy of the fixture words) ----------------------


@pytest.mark.parametrize("code", ALL_CODES)
def test_a_deleted_value_word_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    row = _expected_row(raw, spec, *TRAP_ROWS[code])
    _remove(raw, row[2])
    _reject(code, raw)


@pytest.mark.parametrize("code", ALL_CODES)
def test_a_deleted_last_value_word_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    row = _expected_row(raw, spec, *TRAP_ROWS[code])
    _remove(raw, row[-1])
    _reject(code, raw)


@pytest.mark.parametrize("code", ALL_CODES)
def test_a_value_moved_15_pt_right_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    word = _expected_row(raw, spec, *TRAP_ROWS[code])[2]
    word["x0"] += 15.0
    word["x1"] += 15.0
    _reject(code, raw)


@pytest.mark.parametrize("code", ALL_CODES)
def test_a_value_moved_15_pt_left_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    word = _expected_row(raw, spec, *TRAP_ROWS[code])[3 if len(spec.col_labels) > 3 else 1]
    word["x0"] -= 15.0
    word["x1"] -= 15.0
    _reject(code, raw)


@pytest.mark.parametrize("code", ALL_CODES)
def test_a_stray_non_numeric_word_in_the_value_zone_is_rejected_not_skipped(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    row = _expected_row(raw, spec, *TRAP_ROWS[code])
    anchor = row[1]
    raw.append(
        {
            "text": "n/a",
            "x0": anchor["x1"] + 1.0,
            "x1": anchor["x1"] + 12.0,
            "top": anchor["top"],
            "bottom": anchor["bottom"],
        }
    )
    _reject(code, raw)


@pytest.mark.parametrize("code", ALL_CODES)
def test_a_missing_title_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    first = spec.title.split()[0]
    raw[:] = [w for w in raw if w["text"] != first]
    _reject(code, raw)


@pytest.mark.parametrize("code", ["KEY_DATA_SAB", "KEY_DATA_SAR"])
def test_title_alone_missing_is_rejected_when_no_anchor_depends_on_it(code):
    spec = SPEC_BY_CODE[code]
    assert spec.start_after is None
    raw = _raw(spec.page)
    first = spec.title.split()[0]  # SABAH / SARAWAK
    removed = [w for w in raw if w["text"] == first]
    assert removed
    raw[:] = [w for w in raw if w["text"] != first]
    _reject(code, raw)  # everything else on the page is intact


@pytest.mark.parametrize("code", [c for c in ALL_CODES if SPEC_BY_CODE[c].start_after])
def test_a_missing_start_anchor_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    _drop_first_word_of(raw, spec.start_after)
    _reject(code, raw)


@pytest.mark.parametrize("code", ALL_CODES)
def test_a_missing_stop_anchor_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    _drop_first_word_of(raw, spec.stop_before)
    _reject(code, raw)


@pytest.mark.parametrize("code", ["SAIDI_BY_STATE", "SAIFI_BY_STATE", "CAIDI_BY_STATE"])
def test_start_anchor_missing_alone_is_rejected_for_the_by_state_tables(code):
    """Their start anchor ('Unit: ...') differs from the title, so only the anchor is broken."""
    spec = SPEC_BY_CODE[code]
    assert spec.start_after != spec.title
    raw = _raw(spec.page)
    assert spec.title in " ".join(_line_text(ln) for ln in _lines(raw))
    _drop_first_word_of(raw, spec.start_after)
    assert spec.title in " ".join(_line_text(ln) for ln in _lines(raw))
    _reject(code, raw)


# Header year edits: table -> which header word equal to its third column label (top to bottom over the page).
YEAR_HEADERS = {
    "KEY_DATA_PEN": 0, "KEY_DATA_SAB": 0, "KEY_DATA_SAR": 0, "PEN_DIST_PERF": 0, "SAIDI_BY_STATE": 1,
    "SAIFI_BY_STATE": 0, "CAIDI_BY_STATE": 1, "SABAH_DIST_PERF": 0, "SARAWAK_DIST_PERF": 1,
}  # fmt: skip


@pytest.mark.parametrize("code", list(YEAR_HEADERS))
def test_a_changed_header_year_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    year = spec.col_labels[2]
    raw = _raw(spec.page)
    found = sorted((w for w in raw if w["text"] == year and w["x0"] >= spec.label_x_max), key=_yc)
    found[YEAR_HEADERS[code]]["text"] = year[::-1]  # e.g. 2017 -> 7102
    _reject(code, raw)


@pytest.mark.parametrize(
    ("code", "header_word"),
    [("INSTALLED_CAPACITY", "Biogas"), ("AVAILABLE_CAPACITY", "Coal"), ("SUPPLY_INTERRUPTIONS", "Sabah")],
)
def test_a_renamed_header_word_is_rejected(code, header_word):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    word = next(w for w in sorted(raw, key=_yc) if w["text"] == header_word and w["x0"] >= spec.label_x_max)
    word["text"] += "x"
    _reject(code, raw)


def test_reordered_columns_are_rejected():
    spec = SPEC_BY_CODE["AVAILABLE_CAPACITY"]
    raw = _raw(14)
    coal = next(w for w in raw if w["text"] == "Coal")
    solar = next(w for w in raw if w["text"] == "Solar")
    coal["text"], solar["text"] = "Solar", "Coal"
    _reject(spec.table_code, raw)


@pytest.mark.parametrize(
    ("code", "first", "second"),
    [
        ("SAIDI_BY_STATE", "Johor", "Kedah"),
        ("INSTALLED_CAPACITY", "TNB", "SESB"),
        ("AVAILABLE_CAPACITY", "Sabah", "Sarawak"),
        ("PEN_DIST_PERF", "Scheduled", "Unscheduled"),
        ("SAIFI_BY_STATE", "Perak", "Perlis"),
    ],
)
def test_two_swapped_row_label_words_are_rejected(code, first, second):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    a, b = _label_word(raw, spec, first), _label_word(raw, spec, second)
    a["text"], b["text"] = b["text"], a["text"]
    _reject(code, raw)


@pytest.mark.parametrize("code", ALL_CODES)
def test_a_deleted_data_line_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    row = _expected_row(raw, spec, *TRAP_ROWS[code])
    y = _yc(row[0])
    raw[:] = [w for w in raw if abs(_yc(w) - y) > 2.0]
    _reject(code, raw)


@pytest.mark.parametrize("code", ALL_CODES)
def test_an_extra_data_line_is_rejected(code):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    row = _expected_row(raw, spec, *TRAP_ROWS[code])
    # A copy of the row's value line, 5 pt below it: its own line, between this row and the next.
    raw += [{**w, "top": w["top"] + 5.0, "bottom": w["bottom"] + 5.0} for w in row]
    _reject(code, raw)


# Wrapped label part moved to exactly halfway between two data lines.
# (table, part's anchor word, nth, [row above: anchor, nth], [row below: anchor, nth])
AMBIGUOUS = [
    ("SAIDI_BY_STATE", "Putrajaya", 0, ("Pulau", 0), ("Putrajaya", 0)),
    ("SAIFI_BY_STATE", "Putrajaya", 0, ("Pulau", 0), ("Putrajaya", 0)),
    ("CAIDI_BY_STATE", "Putrajaya", 1, ("Pulau", 1), ("Putrajaya", 1)),
    ("AVAILABLE_CAPACITY", "Peninsular", 0, ("Peninsular", 0), ("Sabah", 0)),
]


def _move_label_part_to(raw, spec, part, nth, upper, lower, offset):
    """Move the label line holding `part` to halfway between two data lines (+ offset toward the lower one)."""
    y_upper = _yc(_expected_row(raw, spec, *upper)[0])
    y_lower = _yc(_expected_row(raw, spec, *lower)[0])
    anchor = _label_word(raw, spec, part, nth)
    mates = [w for w in raw if w["x0"] < spec.label_x_max and abs(_yc(w) - _yc(anchor)) <= 1.0]
    delta = (y_upper + y_lower) / 2 + offset - _yc(anchor)
    for w in mates:
        w["top"] += delta
        w["bottom"] += delta


@pytest.mark.parametrize(("code", "part", "nth", "upper", "lower"), AMBIGUOUS, ids=[a[0] for a in AMBIGUOUS])
def test_a_label_part_exactly_between_two_data_lines_is_ambiguous(code, part, nth, upper, lower):
    spec = SPEC_BY_CODE[code]
    raw = _raw(spec.page)
    _move_label_part_to(raw, spec, part, nth, upper, lower, 0.0)
    _reject(code, raw)


def test_a_label_part_within_one_point_of_equally_near_is_still_ambiguous():
    code, part, nth, upper, lower = AMBIGUOUS[0]
    raw = _raw(83)
    _move_label_part_to(raw, SPEC_BY_CODE[code], part, nth, upper, lower, 0.25)  # distances differ by 0.5 pt
    _reject(code, raw)


def test_a_label_part_clearly_nearer_one_data_line_is_assigned_to_it():
    code, part, nth, upper, lower = AMBIGUOUS[0]
    spec = SPEC_BY_CODE[code]
    raw = _raw(83)
    _move_label_part_to(raw, spec, part, nth, upper, lower, 2.0)  # distances differ by 4 pt: toward Putrajaya
    rows = _rows(_parse(code, raw))
    assert {c.row_label for c in rows[10]} == {"WP Putrajaya (including Cyberjaya)"}
    assert {c.row_label for c in rows[9]} == {"Pulau Pinang"}


def test_a_renamed_subtotal_label_is_rejected():
    spec = SPEC_BY_CODE["INSTALLED_CAPACITY"]
    raw = _raw(13)
    _label_word(raw, spec, "Subtotal", 1)["text"] = "Subtotl"
    _reject("INSTALLED_CAPACITY", raw)


@pytest.mark.parametrize(
    "groups", [("Peninsular Malaysia", "Sabah"), ("A", "B", "C", "D"), ("Peninsular Malaysia",), ()]
)
def test_a_wrong_number_of_row_groups_for_the_subtotal_rows_is_rejected_or_ungrouped(groups):
    spec = replace(SPEC_BY_CODE["INSTALLED_CAPACITY"], row_groups=groups)
    if groups == ():
        assert {c.row_group for c in _parse("INSTALLED_CAPACITY", spec=spec)} == {None}  # no groups: nothing to check
    else:
        _reject("INSTALLED_CAPACITY", _raw(13), spec)


def test_a_wrong_header_line_count_is_rejected():
    for header_lines in (2, 4):
        spec = replace(SPEC_BY_CODE["INSTALLED_CAPACITY"], header_lines=header_lines)
        _reject("INSTALLED_CAPACITY", _raw(13), spec)


def test_a_label_limit_that_swallows_the_first_value_column_is_rejected():
    spec = replace(SPEC_BY_CODE["INSTALLED_CAPACITY"], label_x_max=100.0)
    _reject("INSTALLED_CAPACITY", _raw(13), spec)


def test_a_wrong_pinned_label_is_rejected():
    spec = SPEC_BY_CODE["SAIDI_BY_STATE"]
    labels = list(spec.row_labels)
    labels[1] = "Kedah "  # differs by a trailing space: the match is exact
    _reject("SAIDI_BY_STATE", _raw(83), replace(spec, row_labels=tuple(labels)))
    _reject("SAIDI_BY_STATE", _raw(83), replace(spec, row_labels=spec.row_labels[:-1]))
    _reject("SAIDI_BY_STATE", _raw(83), replace(spec, col_labels=spec.col_labels[:-1] + ("2023",)))


def test_a_page_with_no_words_is_rejected():
    for code in ("AVAILABLE_CAPACITY", "KEY_DATA_SAB"):
        _reject(code, [])


def test_records_from_rejects_an_unknown_edition(tmp_path):
    # ASSUMPTION: the edition is checked before the PDF is opened (the file here is not a PDF at all).
    dummy = tmp_path / "not_a_handbook.pdf"
    dummy.write_bytes(b"not a pdf")
    with pytest.raises(SchemaMismatchError):
        handbook.records_from(dummy, edition=1999)


# --- 7. group_lines, page_text, table_region -----------------------------------------------


def test_group_lines_of_no_words_is_an_empty_list():
    assert handbook.group_lines([]) == []


def test_group_lines_returns_line_objects_with_words_text_and_first_word_centre():
    a, b = _w("hello", 10, 100.0), _w("world", 60, 100.5)
    (line,) = handbook.group_lines([b, a])
    assert isinstance(line, handbook.Line)
    assert tuple(line.words) == (a, b)
    assert line.text == "hello world"
    assert line.y_centre == pytest.approx(100.0)  # the FIRST (leftmost-by-centre) word's centre


def test_words_2_9_pt_apart_join_one_line_and_3_1_pt_apart_do_not():
    joined = handbook.group_lines([_w("a", 0, 100.0), _w("b", 20, 102.9)])
    assert _texts(joined) == ["a b"]
    split = handbook.group_lines([_w("a", 0, 100.0), _w("b", 20, 103.1)])
    assert _texts(split) == ["a", "b"]


def test_line_membership_is_anchored_to_the_lines_first_word_not_the_previous_or_a_running_average():
    ws = [_w("a", 0, 100.0), _w("b", 20, 102.5), _w("c", 40, 105.0)]
    assert _texts(handbook.group_lines(ws)) == ["a b", "c"]  # 5.0 from the first word: a new line
    # Running average would join c (3.5 - avg(0, 2.9) = 2.05); first-word anchoring does not (3.5 > 3).
    ws = [_w("a", 0, 100.0), _w("b", 20, 102.9), _w("c", 40, 103.5)]
    assert _texts(handbook.group_lines(ws)) == ["a b", "c"]


def test_a_slow_drift_cannot_chain_rows_together():
    ws = [_w(str(i), 10 * i, 100.0 + 2.0 * i) for i in range(5)]  # centres 100, 102, 104, 106, 108
    assert _texts(handbook.group_lines(ws)) == ["0 1", "2 3", "4"]


def test_lines_come_top_to_bottom_whatever_the_input_order():
    ws = [_w("low", 10, 300.0), _w("high", 10, 100.0), _w("mid", 10, 200.0)]
    lines = handbook.group_lines(ws)
    assert _texts(lines) == ["high", "mid", "low"]
    assert [ln.y_centre for ln in lines] == pytest.approx([100.0, 200.0, 300.0])


def test_words_in_a_line_are_sorted_by_x0():
    ws = [_w("c", 90, 100.0), _w("a", 10, 100.4), _w("b", 50, 99.8)]
    (line,) = handbook.group_lines(ws)
    assert line.text == "a b c"
    assert [w.text for w in line.words] == ["a", "b", "c"]


def test_the_vertical_centre_not_the_top_decides_the_line():
    short = handbook.Word("short", 0, 20, 100.0, 107.0)  # centre 103.5
    tall = handbook.Word("tall", 30, 50, 100.0, 117.0)  # same top, centre 108.5
    assert _texts(handbook.group_lines([short, tall])) == ["short", "tall"]
    taller_but_centred = handbook.Word("big", 30, 50, 98.0, 109.0)  # centre 103.5
    assert _texts(handbook.group_lines([short, taller_but_centred])) == ["short big"]


def test_line_text_is_normalised():
    ws = [handbook.Word("Net  Zero", 0, 40, 100.0, 107.0), handbook.Word(" x\t", 50, 56, 100.0, 107.0)]
    assert _texts(handbook.group_lines(ws)) == ["Net Zero x"]


def test_group_lines_honours_a_custom_tolerance():
    ws = [_w("a", 0, 100.0), _w("b", 20, 102.9)]
    assert _texts(handbook.group_lines(ws, tolerance=1.0)) == ["a", "b"]
    assert _texts(handbook.group_lines(ws, tolerance=5.0)) == ["a b"]


def test_group_lines_on_a_real_page_finds_the_title_and_the_notes_lines():
    texts = _texts(handbook.group_lines(_words(_raw(14))))
    assert texts[0] == "Unit: MW"
    assert "Available Capacity as of 31st December 2021" in texts
    assert any(t.startswith("Note: 1. Available Capacity for Peninsular Malaysia") for t in texts)
    assert texts[-1].startswith("8024 MALAYSIA ENERGY STATISTICS HANDBOOK") or "ENERGY STATISTICS HANDBOOK" in texts[-1]


def test_page_text_joins_the_line_texts_with_single_spaces():
    ws = [_w("first", 10, 100.0), _w("line", 50, 100.0), _w("second", 10, 120.0), _w("line", 60, 120.0)]
    assert handbook.page_text(ws) == "first line second line"
    assert handbook.page_text([]) == ""


def test_page_text_lets_a_title_wrap_over_two_lines():
    assert "System Average Interruption Duration Index (SAIDI) by State in Peninsular Malaysia" in handbook.page_text(
        _words(_raw(83))
    )


def test_table_region_is_the_lines_strictly_between_the_anchors():
    lines = [_line(t, 10.0 * i) for i, t in enumerate(["title", "Title here", "head", "r1", "r2", "Notes: x", "tail"])]
    spec = _mini_spec(start_after="Title here", stop_before="Notes")
    region = handbook.table_region(lines, spec)
    assert _texts(region) == ["head", "r1", "r2"]
    assert region == lines[2:5]  # the very Line objects, in order


def test_table_region_anchors_match_by_substring_and_the_first_occurrence_wins():
    lines = [_line(t, 10.0 * i) for i, t in enumerate(["x Start y", "a", "Start again", "b", "stop 1", "c", "stop 2"])]
    spec = _mini_spec(start_after="Start", stop_before="stop")
    assert _texts(handbook.table_region(lines, spec)) == ["a", "Start again", "b"]


def test_table_region_with_no_start_anchor_begins_at_the_top_of_the_page():
    lines = [_line(t, 10.0 * i) for i, t in enumerate(["head", "r1", "Notes", "tail"])]
    spec = _mini_spec(start_after=None, stop_before="Notes")
    assert _texts(handbook.table_region(lines, spec)) == ["head", "r1"]


def test_table_region_searches_the_stop_anchor_only_below_the_start():
    lines = [_line(t, 10.0 * i) for i, t in enumerate(["Notes above", "Title", "r1", "Notes below", "r2"])]
    spec = _mini_spec(start_after="Title", stop_before="Notes")
    assert _texts(handbook.table_region(lines, spec)) == ["r1"]


def test_table_region_stop_is_searched_strictly_below_the_start_line_itself():
    lines = [_line(t, 10.0 * i) for i, t in enumerate(["Title Notes", "r1", "Notes"])]
    spec = _mini_spec(start_after="Title", stop_before="Notes")
    assert _texts(handbook.table_region(lines, spec)) == ["r1"]


def test_table_region_ignore_lines_match_the_whole_line_exactly():
    texts = [
        "Title",
        "head",
        "Energy Intensity",
        "Final Energy Intensity",
        "Per Capita",
        "GDP per Capita",
        "Per Capita x",
        "Notes",
    ]
    lines = [_line(t, 10.0 * i) for i, t in enumerate(texts)]
    spec = _mini_spec(start_after="Title", ignore_lines=("Energy Intensity", "Per Capita"))
    assert _texts(handbook.table_region(lines, spec)) == [
        "head",
        "Final Energy Intensity",
        "GDP per Capita",
        "Per Capita x",
    ]


def test_table_region_ignore_lines_apply_in_the_header_too():
    lines = [_line(t, 10.0 * i) for i, t in enumerate(["Title", "Sub heading", "head", "r1", "Notes"])]
    spec = _mini_spec(start_after="Title", ignore_lines=("Sub heading",))
    assert _texts(handbook.table_region(lines, spec)) == ["head", "r1"]


@pytest.mark.parametrize(
    "texts",
    [
        ["head", "r1", "Notes"],  # start anchor absent
        ["Title", "head", "r1"],  # stop anchor absent
        ["Notes", "Title", "head"],  # stop anchor only above the start
        ["Title", "Notes", "r1"],  # nothing between the anchors
    ],
    ids=["no-start", "no-stop", "stop-only-above", "empty-region"],
)
def test_table_region_raises_when_an_anchor_is_missing_or_the_region_is_empty(texts):
    lines = [_line(t, 10.0 * i) for i, t in enumerate(texts)]
    with pytest.raises(SchemaMismatchError):
        handbook.table_region(lines, _mini_spec(start_after="Title", stop_before="Notes"))


def test_table_region_raises_on_no_lines():
    with pytest.raises(SchemaMismatchError):
        handbook.table_region([], _mini_spec(start_after=None))


# --- cells_from_words on hand-built tables (rule by rule) ----------------------------------


def test_mini_table_baseline():
    cells = handbook.cells_from_words(_mini_words(), _mini_spec(), 2023)
    assert [(c.row_pos, c.col_pos, c.row_label, c.col_label, c.value_text) for c in cells] == [
        (1, 1, "r1", "A", "1,500"), (1, 2, "r1", "B", "2.0"),
        (2, 1, "r2", "A", "3"), (2, 2, "r2", "B", "-"),
        (3, 1, "r3", "A", "4.50"), (3, 2, "r3", "B", "6%"),
    ]  # fmt: skip
    assert {(c.edition, c.page, c.table_code, c.row_group) for c in cells} == {(2023, 1, "MINI", None)}


def test_a_word_starting_exactly_at_label_x_max_is_a_value_just_left_of_it_is_a_label():
    spec = handbook.TableSpec(
        "ONE", 1, "T", start_after="T", stop_before="Notes", label_x_max=50.0, col_labels=("A",), row_labels=("r1",)
    )
    words = [
        _w("T", 10, 10), _wc("A", 60.0, 25),
        handbook.Word("r1", 49.9, 59.0, 36.5, 43.5), handbook.Word("7", 50.0, 56.0, 36.5, 43.5),
        _w("Notes", 10, 70),
    ]  # fmt: skip
    (cell,) = handbook.cells_from_words(words, spec, 2023)
    assert (cell.row_label, cell.value_text) == ("r1", "7")


@pytest.mark.parametrize("stray", ["n/a", "N/A", "1,23", "1e5", "--", "1.", ".5", "$5", "x"])
def test_an_extra_non_numeric_word_in_the_value_zone_is_an_error(stray):
    words = _mini_words() + [_wc(stray, 170.0, 55.0)]  # on the r2 line, right of both columns
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(words, _mini_spec(), 2023)


def test_a_line_with_one_value_too_many_or_too_few_is_an_error():
    extra = _mini_words() + [_wc("9", 170.0, 55.0)]
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(extra, _mini_spec(), 2023)
    short = [w for w in _mini_words() if w.text != "3"]
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(short, _mini_spec(), 2023)


def _shift(words, text, dx):
    return [replace(w, x0=w.x0 + dx, x1=w.x1 + dx) if w.text == text else w for w in words]


def test_a_value_9_pt_off_its_column_centre_is_accepted_11_pt_is_rejected():
    ok = handbook.cells_from_words(_shift(_mini_words(), "3", 9.0), _mini_spec(), 2023)
    assert [c.value_text for c in ok][2] == "3"
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(_shift(_mini_words(), "3", 11.0), _mini_spec(), 2023)
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(_shift(_mini_words(), "3", -11.0), _mini_spec(), 2023)


def test_columns_are_judged_against_the_median_over_all_data_lines():
    rows = [(f"r{i}", str(i), str(10 + i)) for i in range(1, 6)]
    spec = _mini_spec(row_labels=tuple(r[0] for r in rows))
    words = _shift(_mini_words(rows), "2", 11.0)  # one outlier among five
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(words, spec, 2023)


def test_a_header_over_two_lines_is_joined_top_line_first_then_left_to_right():
    header = [_wc("Alpha", COL_A, 20), _wc("Beta", COL_A, 28), _wc("Gamma", COL_B, 20)]
    spec = _mini_spec(header_lines=2, col_labels=("Alpha Beta", "Gamma"))
    cells = handbook.cells_from_words(_mini_words(header=header, first_y=48.0), spec, 2023)
    assert {c.col_label for c in cells if c.col_pos == 1} == {"Alpha Beta"}
    # The right-hand word on the top line comes first.
    header = [_wc("Beta", COL_A + 12, 20), _wc("Alpha", COL_A - 12, 28), _wc("Gamma", COL_B, 20)]
    spec = _mini_spec(header_lines=2, col_labels=("Beta Alpha", "Gamma"))
    cells = handbook.cells_from_words(_mini_words(header=header, first_y=48.0), spec, 2023)
    assert {c.col_label for c in cells if c.col_pos == 1} == {"Beta Alpha"}
    # Two words on one line: left to right.
    header = [_wc("Alpha", COL_A - 12, 25), _wc("Beta", COL_A + 12, 25), _wc("Gamma", COL_B + 2, 25)]
    spec = _mini_spec(col_labels=("Alpha Beta", "Gamma"))
    cells = handbook.cells_from_words(_mini_words(header=header), spec, 2023)
    assert {c.col_label for c in cells if c.col_pos == 1} == {"Alpha Beta"}


def test_header_words_left_of_label_x_max_are_ignored():
    header = [_w("State", 10, 25), _wc("A", COL_A, 25), _wc("B", COL_B, 25)]
    cells = handbook.cells_from_words(_mini_words(header=header), _mini_spec(), 2023)
    assert [c.col_label for c in cells[:2]] == ["A", "B"]


def test_a_renamed_or_reordered_header_is_an_error():
    swapped = [_wc("B", COL_A, 25), _wc("A", COL_B, 25)]
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(_mini_words(header=swapped), _mini_spec(), 2023)
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(_mini_words(), _mini_spec(col_labels=("A", "C")), 2023)


def _wrapped_words(part_y):
    """r1 data line at y=40, r2 data line at y=60, a wrapped part 'w' at part_y (halfway = 50)."""
    rows = [("r1", "1", "2"), ("r2", "3", "4")]
    return _mini_words(rows, gap=20.0) + [_w("w", 10, part_y)]


def test_a_wrapped_label_part_goes_to_the_nearest_data_line_above_or_below():
    spec = _mini_spec(row_labels=("r1", "w r2"))
    cells = handbook.cells_from_words(_wrapped_words(51.0), spec, 2023)  # 11 from r1, 9 from r2
    assert {c.row_label for c in cells if c.row_pos == 2} == {"w r2"}
    spec = _mini_spec(row_labels=("r1 w", "r2"))
    cells = handbook.cells_from_words(_wrapped_words(49.0), spec, 2023)  # 9 from r1, 11 from r2
    assert {c.row_label for c in cells if c.row_pos == 1} == {"r1 w"}


@pytest.mark.parametrize("part_y", [50.0, 50.25, 49.75, 50.5])
def test_a_wrapped_label_part_equally_near_two_data_lines_within_1_pt_is_ambiguous(part_y):
    # distances differ by 0, 0.5, 0.5, 1.0 pt
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(_wrapped_words(part_y), _mini_spec(row_labels=("r1", "w r2")), 2023)


def test_a_wrapped_label_part_2_pt_off_equal_is_not_ambiguous():
    spec = _mini_spec(row_labels=("r1", "w r2"))
    cells = handbook.cells_from_words(_wrapped_words(51.0), spec, 2023)  # distances 11 vs 9: differ by 2
    assert len(cells) == 4


def test_a_row_label_is_its_parts_top_to_bottom():
    rows = [("r1", "1", "2")]
    words = _mini_words(rows) + [_w("above", 10, 31.0), _w("below", 10, 49.0)]
    # parts: "above" 9 pt above r1's line, "below" 9 pt under it; with one data line there is no ambiguity.
    spec = _mini_spec(row_labels=("above r1 below",))
    (c1, _c2) = handbook.cells_from_words(words, spec, 2023)
    assert c1.row_label == "above r1 below"


def test_label_words_on_the_data_line_are_joined_left_to_right():
    rows = [("Kuala", "1", "2")]
    words = _mini_words(rows) + [_w("Lumpur", 36, 40.0)]
    (c1, _c2) = handbook.cells_from_words(words, _mini_spec(row_labels=("Kuala Lumpur",)), 2023)
    assert c1.row_label == "Kuala Lumpur"


def test_table_with_no_data_line_is_an_error():
    words = [w for w in _mini_words() if w.top < 30 or w.text == "Notes"]
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(words, _mini_spec(), 2023)


def test_a_missing_title_is_an_error_on_a_mini_table():
    words = [w for w in _mini_words() if w.text != "My"]
    with pytest.raises(SchemaMismatchError, match="MINI"):
        handbook.cells_from_words(words, _mini_spec(title="My Table", start_after="Table"), 2023)


def _group_rows(labels):
    return [(label, str(i), str(i + 10)) for i, label in enumerate(labels, start=1)]


def test_row_groups_advance_after_each_group_end_label_and_trailing_rows_get_none():
    labels = ("a", "Subtotal", "b", "Subtotal", "Total")
    spec = _mini_spec(row_labels=labels, row_groups=("G1", "G2"))
    cells = handbook.cells_from_words(_mini_words(_group_rows(labels)), spec, 2023)
    assert [next(c.row_group for c in cells if c.row_pos == r) for r in range(1, 6)] == ["G1", "G1", "G2", "G2", None]


def test_row_groups_use_the_specs_group_end_label():
    labels = ("a", "End", "b", "End", "Subtotal")
    spec = _mini_spec(row_labels=labels, row_groups=("G1", "G2"), group_end_label="End")
    cells = handbook.cells_from_words(_mini_words(_group_rows(labels)), spec, 2023)
    assert [next(c.row_group for c in cells if c.row_pos == r) for r in range(1, 6)] == ["G1", "G1", "G2", "G2", None]


def test_a_group_end_label_row_count_that_differs_from_the_group_count_is_an_error():
    labels = ("a", "Subtotal", "b", "Subtotal", "Total")
    for groups in (("G1",), ("G1", "G2", "G3")):
        spec = _mini_spec(row_labels=labels, row_groups=groups)
        with pytest.raises(SchemaMismatchError, match="MINI"):
            handbook.cells_from_words(_mini_words(_group_rows(labels)), spec, 2023)


def test_without_row_groups_group_end_labels_mean_nothing():
    labels = ("a", "Subtotal", "b", "Subtotal")
    cells = handbook.cells_from_words(_mini_words(_group_rows(labels)), _mini_spec(row_labels=labels), 2023)
    assert {c.row_group for c in cells} == {None}


def test_repeated_labels_are_kept_as_separate_rows():
    labels = ("IPPs", "Subtotal", "IPPs", "Subtotal")
    spec = _mini_spec(row_labels=labels, row_groups=("G1", "G2"))
    cells = handbook.cells_from_words(_mini_words(_group_rows(labels)), spec, 2023)
    assert [(c.row_pos, c.row_label, c.row_group) for c in cells if c.col_pos == 1] == [
        (1, "IPPs", "G1"), (2, "Subtotal", "G1"), (3, "IPPs", "G2"), (4, "Subtotal", "G2"),
    ]  # fmt: skip


# --- 8. implemented helpers ----------------------------------------------------------------


def test_verify_checksum_raises_on_a_file_that_is_not_the_pinned_one(tmp_path):
    other = tmp_path / "Malaysia_Energy_Statistics_Handbook_2023.pdf"
    other.write_bytes(b"a re-issued handbook")
    with pytest.raises(InvalidDownloadError, match="differs from the pinned"):
        handbook.verify_checksum(other)


def test_verify_checksum_returns_the_md5_when_it_matches(tmp_path, monkeypatch):
    body = b"pretend this is the pinned pdf"
    md5 = hashlib.md5(body).hexdigest()
    monkeypatch.setitem(config.HANDBOOK_MD5, handbook.EDITION, md5)
    path = tmp_path / "handbook.pdf"
    path.write_bytes(body)
    assert handbook.verify_checksum(path) == md5


def test_verify_checksum_error_names_both_checksums(tmp_path, monkeypatch):
    body = b"x"
    monkeypatch.setitem(config.HANDBOOK_MD5, handbook.EDITION, "0" * 32)
    path = tmp_path / "h.pdf"
    path.write_bytes(body)
    with pytest.raises(InvalidDownloadError, match=hashlib.md5(body).hexdigest()):
        handbook.verify_checksum(path)


def _rec(row=1, col=1, value="1", table="T", page=13, label="IPPs", col_label="Coal"):
    return (2023, page, table, row, col, None, label, col_label, value)


def test_load_rejects_a_duplicate_key_before_touching_the_database():
    records = [_rec(row=1, col=1, value="1"), _rec(row=2, col=1), _rec(row=1, col=1, value="2")]
    with pytest.raises(ValueError, match="Duplicate natural key"):
        handbook.load(None, records, 1, "handbook.pdf")  # conn=None: the duplicate error must come first


def test_load_judges_duplicates_on_the_key_columns_only(monkeypatch):
    seen = {}

    def fake_merge(conn, table, columns, key_columns, records, run_id, source_file):
        seen.update(
            conn=conn, table=table, columns=columns, key=key_columns, n=len(records), run=run_id, file=source_file
        )
        return 7

    monkeypatch.setattr(handbook._common, "merge_into", fake_merge)
    # Same labels and values, different positions / tables / pages: all distinct keys.
    records = [_rec(row=1, col=1), _rec(row=1, col=2), _rec(row=2, col=1), _rec(table="U"), _rec(page=14), _rec()]
    records[-1] = _rec(row=3, col=3)
    assert handbook.load("CONN", records, 5, "handbook.pdf") == 7
    assert seen == {
        "conn": "CONN", "table": "raw.handbook_cell", "columns": handbook.RAW_COLUMNS, "key": handbook.KEY_COLUMNS,
        "n": 6, "run": 5, "file": "handbook.pdf",
    }  # fmt: skip


@pytest.mark.parametrize("field", range(5))
def test_load_treats_each_of_the_five_key_positions_as_part_of_the_key(field, monkeypatch):
    monkeypatch.setattr(handbook._common, "merge_into", lambda *a, **k: 0)
    base = list(_rec())
    other = list(_rec())
    other[field] = {0: 2022, 1: 14, 2: "U", 3: 2, 4: 2}[field]
    assert handbook.load(None, [tuple(base), tuple(other)], 1, "f") == 0  # differs in the key: no duplicate
    other = list(_rec(label="other", col_label="other", value="9"))
    with pytest.raises(ValueError, match="Duplicate natural key"):
        handbook.load(None, [tuple(base), tuple(other)], 1, "f")  # same key, different payload: duplicate
