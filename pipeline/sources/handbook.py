"""Energy Commission, Malaysia Energy Statistics Handbook (source D5) → raw.handbook_cell.

LICENCE (M4 plan Q1). The handbook is "All rights reserved"; reproduction needs the Energy
Commission's prior written consent, and any excerpt must be credited "Source: Energy
Commission" (handbook p.5). So:
- the PDF is downloaded at runtime into git-ignored `data/raw/handbook/<date>/` and never
  committed; the cells live only in the local database;
- this module, the page pins and the printed headings below are code and metadata, not data;
- committed test fixtures are page word layouts with every number replaced (see
  `tools/make_handbook_fixture.py`), never real values.

WHAT IS LANDED. Whole tables from pinned pages, exactly as printed (M4 plan Q3): one record per
(table, data row, value column), keyed by position, because labels repeat (p.13's utility rows
recur per region block; Sarawak's p.85 header prints "2019" twice). Casting, aliasing and the
Q4 inconsistency rules happen in `stg` (sql/views/R__stg_handbook.sql), never here.

HOW A PAGE IS READ (two layers, M4 plan Q8):
1. `words_from_page` (thin, needs pdfplumber): the page's words with their boxes, built from
   upright characters only. The margin section markers and p.13's region labels are printed
   rotated; they come out reversed ("AISYALAM RALUSNINEP") and are dropped by this filter.
2. `cells_from_words` (pure, no PDF): turns one table's words into cells, failing loudly on
   anything that differs from the pinned spec. Every rule is in its docstring.

Silent number errors are the task's main risk (doc 06 task 4.1, High): every structural surprise
raises `SchemaMismatchError`; nothing is skipped, guessed or padded.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from pipeline import config
from pipeline.sources import _common
from pipeline.sources._common import (
    InvalidDownloadError,
    SchemaMismatchError,
    assert_unique_keys,
)

SOURCE = "handbook"
EDITION = 2023  # the latest edition (M4 plan Q2); the 2022 edition is a check-only input, never parsed

# One line = words whose vertical centres lie within this distance (pt) of the line's first word.
# Values and their label sit up to ~1 pt apart; separate rows are >= 10 pt apart (profiled).
LINE_TOLERANCE_PT = 3.0
# A value must lie within this distance (pt) of its column's median centre; columns are >= 31 pt
# apart and values within a column spread <= ~6 pt (profiled), so a shifted cell fails loudly.
COLUMN_TOLERANCE_PT = 10.0
# A value token: a number with optional thousands commas, decimals and percent sign, or a lone
# dash (printed for "none"/"not applicable"; kept as printed and turned into NULL in stg).
VALUE_TOKEN = re.compile(r"^-?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?%?$|^-$")
# The running header/footer on every page ("84 MALAYSIA ENERGY STATISTICS HANDBOOK 2023").
PAGE_FURNITURE = "ENERGY STATISTICS HANDBOOK"

RAW_COLUMNS = (
    "edition", "page", "table_code", "row_pos", "col_pos", "row_group", "row_label", "col_label", "value_text",
)  # fmt: skip
KEY_COLUMNS = ("edition", "page", "table_code", "row_pos", "col_pos")


@dataclass(frozen=True)
class Word:
    """One word as pdfplumber boxes it (PDF points, origin top-left)."""

    text: str
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass(frozen=True)
class Line:
    """Words sharing a line, sorted left to right; `text` is their texts joined by single spaces."""

    words: tuple[Word, ...]
    y_centre: float
    text: str


@dataclass(frozen=True)
class TableSpec:
    """A pinned table: where it is, and exactly what its headings say (printed text, not data).

    Region: the lines strictly below the first line containing `start_after` (or from the top of
    the page when it is None) and strictly above the first later line containing `stop_before`.
    Lines whose whole text equals one of `ignore_lines` are dropped (sub-headings such as
    "Per Capita"); the match is exact, never a substring, because "Energy Intensity" is also
    part of the row label "Final Energy Intensity" (prototype finding).
    The first `header_lines` remaining lines are the column header; the rest is the body.
    Words starting left of `label_x_max` are row-label words; the rest are values or headers.
    """

    table_code: str
    page: int
    title: str  # must appear in the page text (lines joined by spaces), else SchemaMismatchError
    start_after: str | None
    stop_before: str
    label_x_max: float
    col_labels: tuple[str, ...]
    row_labels: tuple[str, ...]
    header_lines: int = 1
    ignore_lines: tuple[str, ...] = ()
    row_groups: tuple[str, ...] = ()  # block names in order; each block ends after a `group_end_label` row
    group_end_label: str = "Subtotal"


@dataclass(frozen=True)
class Cell:
    edition: int
    page: int
    table_code: str
    row_pos: int  # 1-based, top to bottom
    col_pos: int  # 1-based, left to right
    row_group: str | None
    row_label: str
    col_label: str
    value_text: str

    def as_record(self) -> tuple:
        return (
            self.edition, self.page, self.table_code, self.row_pos, self.col_pos,
            self.row_group, self.row_label, self.col_label, self.value_text,
        )  # fmt: skip


# --- pins for the 2023 edition (profiled 2026-10-05; label_x_max = midpoint of the measured gap
# between the widest label and the first value column, per table) -----------------------------
_YEARS_2015_2021 = tuple(str(y) for y in range(2015, 2022))
_YEARS_2015_2022 = tuple(str(y) for y in range(2015, 2023))
_STATES = (
    "Johor", "Kedah", "Kelantan", "WP Kuala Lumpur", "Melaka", "Negeri Sembilan", "Pahang", "Perak",
    "Perlis", "Pulau Pinang", "WP Putrajaya (including Cyberjaya)", "Selangor", "Terengganu", "PENINSULAR MALAYSIA",
)  # fmt: skip
_KEY_DATA_ROWS = (
    "GDP at Current Prices (RM million)*",
    "GDP at 2015 {p}rices (RM million)*",
    "Population ('000 people)**",
    "Final Energy Consumption (ktoe)",
    "Electricity Consumption (ktoe)",
    "Electricity Consumption (GWh)",
    "GDP at Current Prices (RM) per Capita*",
    "Final Energy Consumption (toe) per Capita",
    "Electricity Consumption (kWh) per Capita",
    "Final Energy Intensity (toe/GDP at 2015 prices (RM million))",
    "Electricity Intensity (toe/ GDP at 2015 prices (RM million))",
    "Electricity Intensity (GWh/GDP at 2015 prices (RM million))",
)
_PERF_IGNORE = ("Electricity Supply Interruptions per 1,000 Customers", "SAIDI, SAIFI & CAIDI")
_KEY_DATA_IGNORE = ("Per Capita", "Energy Intensity")

TABLES: dict[int, tuple[TableSpec, ...]] = {
    2023: (
        TableSpec(
            "INSTALLED_CAPACITY", 13, "Installed Capacity as of 31st December 2021",
            start_after="Installed Capacity as of 31st December 2021", stop_before="Notes: Data exclude",
            label_x_max=82.5, header_lines=3,
            col_labels=("Major Hydro", "Mini Hydro", "Natural Gas", "Coal", "Diesel / MFO", "Biomass", "Solar",
                        "Biogas", "Others", "Total"),
            row_labels=("TNB", "IPPs", "Co-Generation", "Self-Generation", "FiT", "RE Non-FiT", "LSS", "NEM",
                        "Subtotal", "SESB", "IPPs", "Co-Generation", "Self-Generation", "FiT", "LSS", "NEM",
                        "Subtotal", "SEB", "Co-Generation", "Self-Generation", "Subtotal", "Total", "Share (%)"),
            row_groups=("Peninsular Malaysia", "Sabah", "Sarawak"),
        ),
        TableSpec(
            "AVAILABLE_CAPACITY", 14, "Available Capacity as of 31st December 2021",
            start_after="Available Capacity as of 31st December 2021", stop_before="Note: 1. Available Capacity",
            label_x_max=87.0, header_lines=3,
            col_labels=("Hydro", "Natural Gas", "Coal", "Diesel / MFO", "Biomass / Biogas", "Solar", "Total"),
            row_labels=("Peninsular Malaysia", "Sabah", "Sarawak", "Total"),
        ),
        TableSpec(
            "KEY_DATA_PEN", 17, "Key Economic and Energy Data by Region",
            start_after="Key Economic and Energy Data by Region", stop_before="Notes (*)",
            label_x_max=139.0, col_labels=_YEARS_2015_2021, ignore_lines=_KEY_DATA_IGNORE,
            row_labels=tuple(r.format(p="P") for r in _KEY_DATA_ROWS),
        ),
        TableSpec(
            "KEY_DATA_SAB", 18, "SABAH 2015 2016 2017 2018 2019 2020 2021",
            start_after=None, stop_before="Notes (*)",  # nothing above the header (furniture is at the foot)
            label_x_max=132.0, col_labels=_YEARS_2015_2021, ignore_lines=_KEY_DATA_IGNORE,
            row_labels=tuple(r.format(p="p") for r in _KEY_DATA_ROWS),
        ),
        TableSpec(
            "KEY_DATA_SAR", 19, "SARAWAK 2015 2016 2017 2018 2019 2020 2021",
            start_after=None, stop_before="Notes (*)",  # nothing above the header (furniture is at the foot)
            label_x_max=132.0, col_labels=_YEARS_2015_2021, ignore_lines=_KEY_DATA_IGNORE,
            row_labels=tuple(r.format(p="p") for r in _KEY_DATA_ROWS),
        ),
        TableSpec(
            "SUPPLY_INTERRUPTIONS", 82, "Number of Electricity Supply Interruptions",
            start_after="Number of Electricity Supply Interruptions", stop_before=PAGE_FURNITURE,
            label_x_max=85.0,  # the row labels are years; "Peninsular" in the header starts at 88
            col_labels=("Peninsular Malaysia", "Sabah", "Sarawak"),
            row_labels=tuple(str(y) for y in range(2010, 2023)),
        ),
        TableSpec(
            "PEN_DIST_PERF", 83, "Performance of Distribution System in Peninsular Malaysia",
            start_after="Performance of Distribution System in Peninsular Malaysia",
            stop_before="System Average Interruption Duration Index (SAIDI) by",
            label_x_max=105.0, col_labels=_YEARS_2015_2022, ignore_lines=_PERF_IGNORE,
            row_labels=("Scheduled Interruptions", "Unscheduled Interruptions",
                        "SAIDI (Minutes/ Customer/Year) by Voltage Level",
                        "SAIFI (Number of Interruptions/ Customer/Year) by Voltage Level",
                        "CAIDI (Minutes/ Interrupted Customer/Year) by Voltage Level"),
        ),
        TableSpec(
            "SAIDI_BY_STATE", 83,
            "System Average Interruption Duration Index (SAIDI) by State in Peninsular Malaysia",
            start_after="Unit: Minutes/Customer/Year", stop_before=PAGE_FURNITURE,
            label_x_max=121.0, col_labels=_YEARS_2015_2022, row_labels=_STATES,
        ),
        TableSpec(
            "SAIFI_BY_STATE", 84,
            "System Average Interruption Frequency Index (SAIFI) by State in Peninsular Malaysia",
            start_after="Unit: Number of Interruptions/Customer/Year",
            stop_before="Customer Average Interruption Duration Index (CAIDI) by",
            label_x_max=120.0, col_labels=_YEARS_2015_2022, row_labels=_STATES,
        ),
        TableSpec(
            "CAIDI_BY_STATE", 84,
            "Customer Average Interruption Duration Index (CAIDI) by State in Peninsular Malaysia",
            start_after="Unit: Minutes/Interrupted Customer/Year", stop_before=PAGE_FURNITURE,
            label_x_max=120.0, col_labels=_YEARS_2015_2022, row_labels=_STATES,
        ),
        TableSpec(
            "SABAH_DIST_PERF", 85, "Performance of Distribution System in Sabah",
            start_after="Performance of Distribution System in Sabah",
            stop_before="Performance of Distribution System in Sarawak",
            label_x_max=104.0, col_labels=_YEARS_2015_2022, ignore_lines=_PERF_IGNORE,
            row_labels=("Scheduled Interruptions", "Unscheduled Interruptions", "SAIDI (Minutes/ Customer/Year)",
                        "SAIFI (Number of Interruption/ Customer/Year)", "CAIDI (Minutes/ Interrupted Customer/Year)"),
        ),
        TableSpec(
            "SARAWAK_DIST_PERF", 85, "Performance of Distribution System in Sarawak",
            start_after="Performance of Distribution System in Sarawak", stop_before=PAGE_FURNITURE,
            label_x_max=134.0,
            # As printed: the last column repeats "2019" (M4 plan Q4.2). Kept verbatim; stg decides.
            col_labels=("2014", "2015", "2016", "2017", "2018", "2019", "2020", "2019"),
            row_labels=("SAIDI (Minutes/Customer/ Year)", "SAIFI (Number of Interruptions/Customer/ Year)",
                        "CAIDI (Minutes/ Interrupted Customer/ Year)"),
        ),
    ),
}  # fmt: skip


def normalise(text: str) -> str:
    """Collapse every run of whitespace to one space and strip the ends."""
    return " ".join(text.split())


def group_lines(words: list[Word], tolerance: float = LINE_TOLERANCE_PT) -> list[Line]:
    """Group words into lines, top to bottom.

    Words are taken in order of vertical centre ((top + bottom) / 2). A word joins the current
    line when its centre is within `tolerance` of the centre of the line's FIRST word (not a
    running average, so a slow drift can't chain two rows together); otherwise it starts a new
    line. Within a line words are sorted by x0. `y_centre` is the first word's centre; `text` is
    the normalised join of the word texts. Returns [] for no words.
    """
    raise NotImplementedError


def page_text(words: list[Word]) -> str:
    """The page as one normalised string: `group_lines` texts joined by single spaces."""
    raise NotImplementedError


def table_region(lines: list[Line], spec: TableSpec) -> list[Line]:
    """The spec's lines: below the first line containing `spec.start_after` (top of page when
    None), above the first LATER line containing `spec.stop_before`, minus lines whose whole
    text equals an `ignore_lines` entry.

    Raises SchemaMismatchError when `start_after` or `stop_before` isn't found (the layout moved),
    or when the region is empty.
    """
    raise NotImplementedError


def cells_from_words(words: list[Word], spec: TableSpec, edition: int) -> list[Cell]:
    """One table's cells, in row then column order. Pure: no PDF, no database.

    Rules (each failure raises SchemaMismatchError naming the table and the line):
    1. Title: `spec.title` must occur in `page_text(words)`.
    2. Region: `table_region(group_lines(words), spec)`; its first `spec.header_lines` lines are
       the header, the rest the body.
    3. Data lines: body lines with at least one word whose x0 >= `label_x_max`. Every such word
       must match VALUE_TOKEN (a stray word in the value zone is an error, never skipped), and
       every data line must hold exactly len(col_labels) values.
    4. Columns: values are assigned left to right in x order. Each column's centre is the median
       of its values' x-centres over all data lines; every value must lie within
       COLUMN_TOLERANCE_PT of its column's centre (catches a missing cell that shifted the rest).
    5. Column labels: every header-line word with x0 >= `label_x_max` goes to the column with the
       nearest centre; a column's label is its words joined top line first, then left to right.
       The result must equal `spec.col_labels` exactly (so a re-ordered or renamed column fails).
       Header-line words left of `label_x_max` (e.g. "State", "PENINSULAR MALAYSIA") are ignored.
    6. Row labels: label words (x0 < `label_x_max`) on a data line belong to it. A body line with
       label words and no values (a wrapped label part) belongs to the data line with the nearest
       y_centre; if the two nearest are within 1 pt of equally near, that's an error (ambiguous).
       A row's label is its parts joined top to bottom with single spaces. The sequence of row
       labels must equal `spec.row_labels` exactly.
    7. Row groups: when `spec.row_groups` is set, rows are assigned to the groups in order; a
       group ends after a row whose label is `spec.group_end_label`. Rows after the last group
       get None. The number of `group_end_label` rows must equal len(row_groups).
    8. Output: one Cell per (data row, column); value_text exactly as printed (no casting).
    """
    raise NotImplementedError


def words_from_page(page) -> list[Word]:
    """Words of a pdfplumber page built from upright characters only (rotated text dropped)."""
    upright = page.filter(lambda obj: obj.get("object_type") != "char" or obj.get("upright", True))
    return [Word(w["text"], w["x0"], w["x1"], w["top"], w["bottom"]) for w in upright.extract_words()]


def records_from(path: Path, edition: int = EDITION) -> list[tuple]:
    """Raw records for every pinned table of the edition, in TABLES order.

    Opens the PDF with pdfplumber, reads each pinned page once (`words_from_page`), and calls
    `cells_from_words` per table. Raises SchemaMismatchError for an unknown edition or a page
    number beyond the document.
    """
    raise NotImplementedError


def verify_checksum(path: Path) -> str:
    """Return the file's MD5; raise InvalidDownloadError if it differs from the pinned one.

    The pin ties the page numbers above to one exact file: a re-issued PDF stops the run.
    """
    md5 = hashlib.md5(path.read_bytes()).hexdigest()  # identifies the pinned file; not a security use
    expected = config.HANDBOOK_MD5[EDITION]
    if md5 != expected:
        raise InvalidDownloadError(f"{path.name} md5 {md5} differs from the pinned {expected}")
    return md5


def download(refresh: bool = False, retries: int = 3) -> tuple[Path, str]:
    """Download the pinned edition into today's git-ignored folder (or reuse it).
    Returns (path, source_version)."""
    url = config.HANDBOOK_URL[EDITION]
    path, version = _common.download(
        url, SOURCE, Path(url).name, refresh=refresh, retries=retries, validate=verify_checksum
    )
    return path, f"edition {EDITION} md5 {config.HANDBOOK_MD5[EDITION][:8]}; {version}"


def load(conn, records: list[tuple], run_id: int, source_file: str) -> int:
    """MERGE records into raw.handbook_cell inside the caller's transaction; returns rows changed."""
    assert_unique_keys(records, range(len(KEY_COLUMNS)))
    return _common.merge_into(conn, "raw.handbook_cell", RAW_COLUMNS, KEY_COLUMNS, records, run_id, source_file)


__all__ = [
    "EDITION", "KEY_COLUMNS", "RAW_COLUMNS", "TABLES", "Cell", "Line", "SchemaMismatchError", "TableSpec", "Word",
    "cells_from_words", "download", "group_lines", "load", "normalise", "page_text", "records_from",
    "table_region", "verify_checksum", "words_from_page",
]  # fmt: skip
