"""Scan every committed file for numbers that equal a handbook cell (M4 acceptance, plan Q1).

`tests/test_no_restricted_data.py` guards file types and fixture markers, but it can't see a real
value typed into a doc or comment. This local check reads the landed cells from `raw.handbook_cell`
and looks for each distinctive token (a decimal point or thousands comma and at least 4 digits;
plain integers and years are too common to mean anything) in `git ls-files`. It prints file names,
line numbers and counts only, never the values. Coincidences (package versions, other sources'
figures) are possible, so each hit is reviewed by hand.

    .venv/Scripts/python tools/scan_handbook_values.py      # exit 1 if any file matches
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.db import connect

SKIP_SUFFIXES = (".topojson", ".png", ".pbix", ".abf", ".xls", ".xlsx", ".parquet")
# Reviewed coincidences: file -> number of matching tokens that are not from the handbook.
KNOWN = {
    "Documents/plans/M2_plan.md": 1,  # OWID/UN population figure
    "Documents/plans/M3_plan.md": 1,  # package version
    "docs/forecast_final.json": 1,  # package version
    "requirements.txt": 1,  # package version
    "sql/migrations/V010__grid_and_forecast.sql": 1,  # package version in a comment
    "tests/test_forecast_run.py": 1,  # synthetic test load
}


def tokens() -> set[str]:
    with connect() as conn:
        rows = conn.cursor().execute("SELECT DISTINCT value_text FROM raw.handbook_cell").fetchall()
    values = {r[0].strip() for r in rows}
    pattern = re.compile(r"[\d,]*\.\d+|\d{1,3}(,\d{3})+(\.\d+)?")
    return {v for v in values if pattern.fullmatch(v) and sum(c.isdigit() for c in v) >= 4}


def _pdf_lines(path: Path) -> list[str]:
    """The text layer of a PDF (docs/report.pdf, M5 step 5): PNGs can't be scanned, the PDF of the same pages can."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(path)
    return [line for i in range(len(doc)) for line in doc[i].get_textpage().get_text_range().splitlines()]


def main() -> int:
    toks = tokens()
    if not toks:
        print("raw.handbook_cell is empty: run the pipeline first")
        return 1
    regexes = [re.compile(r"(?<![\d.,])" + re.escape(t) + r"(?!\d)") for t in toks]
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    problems = 0
    for name in filter(None, files):
        if name.endswith(SKIP_SUFFIXES) or name.startswith("tests/fixtures/"):
            continue  # fixtures are synthetic by construction and tested for it
        try:
            lines = _pdf_lines(ROOT / name) if name.lower().endswith(".pdf") else (ROOT / name).read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        matched = {i for i, rx in enumerate(regexes) if any(rx.search(line) for line in lines)}
        if not matched:
            continue
        line_nos = sorted({n for n, line in enumerate(lines, 1) if any(regexes[i].search(line) for i in matched)})
        status = "known coincidence" if KNOWN.get(name) == len(matched) else "CHECK"
        problems += status == "CHECK"
        print(f"{status}: {name}: {len(matched)} token(s), lines {line_nos}")
    print(f"{len(toks)} tokens checked against {len(files)} files; {problems} file(s) to check")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
