"""Golden checks on the REAL handbook PDF: local only (M4 plan Q1, Q8, step 6-7).

The PDF is restricted, so it is never in the repo: these tests skip unless the pinned file is on
this PC (env HANDBOOK_PDF, else the git-ignored reference copy or the latest pipeline download).
They hold no handbook values: every expectation is either arithmetic printed in the handbook
itself (subtotals, totals, per-capita ratios) or the independent re-read transcription kept in
git-ignored data/private/ (step 7).
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

from pipeline import config
from pipeline.sources import handbook
from pipeline.sources._common import InvalidDownloadError

ROOT = config.ROOT
FIXTURES = ROOT / "tests" / "fixtures" / "handbook"
REREAD = ROOT / "data" / "private" / "handbook_2023_reread.csv"


def _candidates() -> list[Path]:
    explicit = os.environ.get("HANDBOOK_PDF")
    if explicit:
        return [Path(explicit)]
    found = [ROOT / "docs" / "references" / "data_sources" / "Malaysia_Energy_Statistics_Handbook_2023.pdf"]
    found += sorted((ROOT / "data" / "raw" / "handbook").glob("*/*.pdf"), reverse=True)
    return [p for p in found if p.is_file()]


def _pdf_path() -> tuple[Path | None, list[str]]:
    """The pinned PDF if present; otherwise (None, why each candidate was rejected)."""
    rejected = []
    for candidate in _candidates():
        try:
            handbook.verify_checksum(candidate)
            return candidate, []
        except (OSError, InvalidDownloadError) as exc:
            rejected.append(f"{candidate}: {exc}")
    return None, rejected


PDF, REJECTED = _pdf_path()
# Skip only when no copy is on this PC at all (a fresh clone). A copy that fails its checksum, or
# an explicit HANDBOOK_PDF that does, is an error: a silent skip would make a green run meaningless
# (M4 review H1).
pytestmark = pytest.mark.skipif(PDF is None and not REJECTED, reason="handbook PDF not on this PC (restricted; never committed)")


def test_a_present_pdf_is_the_pinned_file():
    assert not REJECTED or PDF is not None, "handbook PDF present but not the pinned file: " + "; ".join(REJECTED)


@pytest.fixture(scope="module")
def cells() -> dict[str, list[handbook.Cell]]:
    out: dict[str, list[handbook.Cell]] = {}
    for record in handbook.records_from(PDF):
        cell = handbook.Cell(*record)
        out.setdefault(cell.table_code, []).append(cell)
    return out


def _num(text: str) -> float:
    """A printed value as a number; a printed '-' counts as 0 in the handbook's own sums."""
    return 0.0 if text == "-" else float(text.replace(",", "").rstrip("%"))


def _grid(cells: list[handbook.Cell]) -> dict[tuple[int, int], handbook.Cell]:
    return {(c.row_pos, c.col_pos): c for c in cells}


def test_every_pinned_table_parses_with_the_pinned_shape(cells):
    for spec in handbook.TABLES[handbook.EDITION]:
        got = cells[spec.table_code]
        assert len(got) == len(spec.row_labels) * len(spec.col_labels), spec.table_code
    assert sum(len(v) for v in cells.values()) == 989


def test_installed_capacity_rows_and_subtotals_add_up(cells):
    """p.13: each row's fuels sum to its Total column; each block's rows sum to its Subtotal; the
    three Subtotals sum to Total. Printed to 0.1 MW, so allow 0.05 MW per summed cell."""
    g = _grid(cells["INSTALLED_CAPACITY"])
    rows = max(r for r, _ in g)
    for r in range(1, rows):  # the last row is "Share (%)"
        parts = [_num(g[r, c].value_text) for c in range(1, 10)]
        ok = abs(sum(parts) - _num(g[r, 10].value_text)) <= 0.05 * 10
        assert ok, f"row {r} fuels don't sum to its Total"
    subtotals = [r for r in range(1, rows + 1) if g[r, 1].row_label == "Subtotal"]
    start = 1
    for s in subtotals:
        for c in range(1, 11):
            block = sum(_num(g[r, c].value_text) for r in range(start, s))
            ok = abs(block - _num(g[s, c].value_text)) <= 0.05 * (s - start)
            assert ok, f"block ending at row {s} column {c} doesn't sum to its Subtotal"
        start = s + 1
    total = next(r for r in range(1, rows + 1) if g[r, 1].row_label == "Total")
    for c in range(1, 11):
        ok = abs(sum(_num(g[s, c].value_text) for s in subtotals) - _num(g[total, c].value_text)) <= 0.15
        assert ok, f"column {c}: Subtotals don't sum to Total"


def test_available_capacity_rows_and_total_add_up(cells):
    g = _grid(cells["AVAILABLE_CAPACITY"])
    for r in range(1, 5):
        ok = abs(sum(_num(g[r, c].value_text) for c in range(1, 7)) - _num(g[r, 7].value_text)) <= 6 * 0.5
        assert ok, f"row {r} doesn't sum to its Total"
    for c in range(1, 8):
        ok = abs(sum(_num(g[r, c].value_text) for r in range(1, 4)) - _num(g[4, c].value_text)) <= 3 * 0.5
        assert ok, f"column {c}: regions don't sum to Total"


@pytest.mark.parametrize("table", ["KEY_DATA_PEN", "KEY_DATA_SAB", "KEY_DATA_SAR"])
def test_per_capita_rows_equal_totals_over_population(cells, table):
    """Per-capita rows = total / population, within 1% (rounding of the printed inputs)."""
    by_label: dict[str, dict[int, float]] = {}
    for c in cells[table]:
        by_label.setdefault(c.row_label, {})[c.col_pos] = _num(c.value_text)
    pop = by_label["Population ('000 people)**"]
    pairs = (  # (per-capita row, total row, scale): kWh = GWh x 1e3 / thousand people; toe = ktoe / thousand people
        ("Electricity Consumption (kWh) per Capita", "Electricity Consumption (GWh)", 1e3),
        ("Final Energy Consumption (toe) per Capita", "Final Energy Consumption (ktoe)", 1.0),
    )
    for per_capita_row, total_row, scale in pairs:
        for col, total in by_label[total_row].items():
            ok = by_label[per_capita_row][col] == pytest.approx(total * scale / pop[col], rel=0.01)
            assert ok, f"{table} column {col}: {per_capita_row!r} != {total_row!r} / population"


def test_fixtures_hold_no_real_value(cells):
    """No committed fixture keeps a real data value at the same position (licence guard, Q1/Q8)."""
    for spec in handbook.TABLES[handbook.EDITION]:
        data = json.loads((FIXTURES / f"p{spec.page}.json").read_text(encoding="utf-8"))
        words = [handbook.Word(w["text"], w["x0"], w["x1"], w["top"], w["bottom"]) for w in data["words"]]
        synthetic = _grid(handbook.cells_from_words(words, spec, handbook.EDITION))
        for key, real in _grid(cells[spec.table_code]).items():
            if real.value_text != "-":
                assert synthetic[key].value_text != real.value_text, f"{spec.table_code} cell {key} kept its real value"


def test_committed_fixtures_are_the_current_tool_output():
    """The fixtures equal what tools/make_handbook_fixture.py makes from the pinned PDF now, so the
    position-based keep rule (not an older tool) produced them (M4 review M6)."""
    import importlib.util

    import pdfplumber

    spec_ = importlib.util.spec_from_file_location("make_handbook_fixture", ROOT / "tools" / "make_handbook_fixture.py")
    tool = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(tool)
    by_page: dict[int, list[handbook.TableSpec]] = {}
    for spec in handbook.TABLES[handbook.EDITION]:
        by_page.setdefault(spec.page, []).append(spec)
    with pdfplumber.open(PDF) as pdf:
        for page_no, specs in by_page.items():
            committed = json.loads((FIXTURES / f"p{page_no}.json").read_text(encoding="utf-8"))
            assert tool.fixture_for(pdf, page_no, specs) == committed, f"p{page_no} fixture is stale"


@pytest.mark.skipif(not REREAD.is_file(), reason="independent re-read not present (data/private, step 7)")
def test_every_cell_equals_the_independent_re_read(cells):
    """Step 7: two fresh-context agents transcribed every pinned cell from the page images, blind
    to the parser. Any difference is a parse error or a misread, and must be settled by eye."""
    with REREAD.open(encoding="utf-8", newline="") as fh:
        reread = {(r["table_code"], int(r["row_pos"]), int(r["col_pos"])): r["value_text"].strip() for r in csv.DictReader(fh)}
    parsed = {(c.table_code, c.row_pos, c.col_pos): c.value_text for v in cells.values() for c in v}
    assert set(reread) == set(parsed)
    differences = sorted(k for k in parsed if parsed[k] != reread[k])
    assert not differences, f"{len(differences)} cells differ, e.g. {differences[:5]}"  # ids only
