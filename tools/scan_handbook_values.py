"""Scan every committed file for numbers that equal a handbook cell (M4 acceptance, plan Q1).

`tests/test_no_restricted_data.py` guards file types and fixture markers, but it can't see a real
value typed into a doc or comment. This local check reads the landed cells from `raw.handbook_cell`
and looks for each distinctive token (a decimal point or thousands comma and at least 4 digits;
plain integers and years are too common to mean anything) in `git ls-files`. It prints file names,
line numbers and counts only, never the values. Coincidences (package versions, other sources'
figures) are possible, so each hit is reviewed by hand.

    .venv/Scripts/python tools/scan_handbook_values.py      # exit 1 if any file matches
    .venv/Scripts/python tools/scan_handbook_values.py --history   # every blob in every commit (M5 step 10)

`--history` reads each distinct blob reachable from any ref once, under the first path git lists for
it, and names the commits that added a matching blob, so a leak can be traced and rewritten.

Short values (fewer than 4 digits) are too common to match on their own, and that is how one leak got
past this scan: a 3-digit cell written with an extra trailing zero (M5 step 10). So each line is also
checked in context: a line that names a handbook row label (a state, a region, ...) and holds a number
numerically equal to one of that row's cells (a decimal, or at least 3 digits; not a year) is flagged.

`docs/report.pdf` is scanned page by page: the Regions and State reliability pages are skipped only while the
Energy Commission's consent (D5) is GRANTED in `seed/data_source.csv` (`scannable_pages`).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.db import connect
from tools.export_pages import RESTRICTED_MARKERS, RESTRICTED_PAGES, consent

SKIP_SUFFIXES = (".topojson", ".png", ".pbix", ".abf", ".xls", ".xlsx")
# Reviewed coincidences: file -> number of matching tokens that are not from the handbook.
KNOWN = {
    "Documents/plans/M2_plan.md": 1,  # OWID/UN population figure
    "Documents/plans/M3_plan.md": 1,  # package version
    "docs/forecast_final.json": 1,  # package version
    # Open showcase results (D1/D2/grids only; no D5 query is exported): rounded Ember capacity factors, GW and TWh
    # that equal a handbook cell by chance. Reviewed 2026-10-11 by query and field; re-review after each export.
    "exports/expected.json": 34,
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


NUMBER = re.compile(r"(?<![\d.])\d[\d,]*(?:\.\d+)?(?!\d)")


def row_values() -> dict[str, set[float]]:
    """Row label -> the numeric cells of that row (decimals, or at least 3 digits); labels under 4 characters skipped."""
    with connect() as conn:
        rows = conn.cursor().execute("SELECT row_label, value_text FROM raw.handbook_cell").fetchall()
    out: dict[str, set[float]] = {}
    for label, text in rows:
        v = (text or "").strip().replace(",", "").rstrip("%")
        if len(label.strip()) >= 4 and re.fullmatch(r"-?\d+(\.\d+)?", v) and ("." in v or len(v.lstrip("-")) >= 3):
            out.setdefault(label.strip(), set()).add(round(float(v), 6))
    return out


def context_lines(lines: list[str], labelled: dict[re.Pattern[str], set[float]]) -> list[int]:
    """Line numbers where a row label and a number equal to one of that row's cells appear together."""
    hits = []
    for n, line in enumerate(lines, 1):
        for rx, values in labelled.items():
            if rx.search(line) and any(
                ("." in s or len(s) >= 3) and not re.fullmatch(r"(19|20)\d\d", s) and round(float(s), 6) in values
                for s in (m.replace(",", "") for m in NUMBER.findall(line))
            ):
                hits.append(n)
                break
    return hits


def scannable_pages(texts: list[str], consent_by_source: dict[str, str]) -> list[str]:
    """PDF page texts to scan. A page with a restricted marker (a Regions/State reliability page) is skipped only
    while its source's consent is GRANTED: those are the consented charts (DATA_LICENSES.md, D5). Every other page
    is scanned, so a handbook value anywhere else in the PDF is still caught."""
    granted = all(consent_by_source.get(code) == "GRANTED" for code in set(RESTRICTED_PAGES.values()))
    return [t for t in texts if not (granted and any(m in t for m in RESTRICTED_MARKERS))]


def _pdf_lines(source: Path | bytes) -> list[str]:
    """The text layer of a PDF (docs/report.pdf, M5 step 5): PNGs can't be scanned, the PDF of the same pages can."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(source)
    texts = scannable_pages([doc[i].get_textpage().get_text_range() for i in range(len(doc))], consent())
    return [line for text in texts for line in text.splitlines()]


def _cell(value) -> str:
    """A cell as text; a number in plain and thousands-comma form, so either way a handbook token was written matches."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return str(value)
    number = int(value) if float(value).is_integer() else value
    return f"{number} {number:,}"


def _parquet_lines(source: Path | bytes) -> list[str]:
    """A Parquet snapshot (exports/, M6 plan Q5) as text: a header line, then one line per row."""
    import io

    import pandas as pd

    frame = pd.read_parquet(io.BytesIO(source) if isinstance(source, bytes) else source)
    return [" | ".join(map(str, frame.columns))] + [
        " | ".join(map(_cell, row)) for row in frame.itertuples(index=False)
    ]


def token_checked(name: str) -> bool:
    """Parquet snapshots get the label-plus-value check only: their tens of thousands of open-data numbers (hourly
    MW, TWh) equal some handbook token by chance, while a handbook table landing there would carry its row labels."""
    return not name.lower().endswith(".parquet")


def _lines(name: str, source: Path | bytes) -> list[str]:
    if name.lower().endswith(".pdf"):
        return _pdf_lines(source)
    if name.lower().endswith(".parquet"):
        return _parquet_lines(source)
    return (source if isinstance(source, bytes) else source.read_bytes()).decode("utf-8").splitlines()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def _history_blobs():
    """(path, blob id, lines) for each distinct blob reachable from any ref."""
    seen: dict[str, str] = {}
    for row in _git("rev-list", "--all", "--objects").splitlines():
        oid, _, path = row.partition(" ")
        if path and oid not in seen:
            seen[oid] = path
    check = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        cwd=ROOT,
        input="\n".join(seen),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    for oid in (r.split()[0] for r in check if r.endswith(" blob")):
        path = seen[oid]
        if path.endswith(SKIP_SUFFIXES) or path.startswith("tests/fixtures/"):
            continue
        data = subprocess.run(["git", "cat-file", "blob", oid], cwd=ROOT, capture_output=True, check=True).stdout
        try:
            lines = _lines(path, data)
        except UnicodeDecodeError:
            continue
        yield path, oid, lines


def _worktree_files():
    for name in filter(None, _git("ls-files").split("\n")):
        if name.endswith(SKIP_SUFFIXES) or name.startswith("tests/fixtures/"):
            continue  # fixtures are synthetic by construction and tested for it
        try:
            lines = _lines(name, ROOT / name)
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        yield name, None, lines


def main() -> int:
    history = "--history" in sys.argv[1:]
    toks = tokens()
    if not toks:
        print("raw.handbook_cell is empty: run the pipeline first")
        return 1
    regexes = [re.compile(r"(?<![\d.,])" + re.escape(t) + r"(?!\d)") for t in toks]
    labelled = {re.compile(r"\b" + re.escape(label) + r"\b"): v for label, v in row_values().items()}
    problems = checked = 0
    for name, oid, lines in _history_blobs() if history else _worktree_files():
        checked += 1
        matched = (
            {i for i, rx in enumerate(regexes) if any(rx.search(line) for line in lines)}
            if token_checked(name)
            else set()
        )
        in_context = context_lines(lines, labelled)
        if not matched and not in_context:
            continue
        line_nos = sorted({n for n, line in enumerate(lines, 1) if any(regexes[i].search(line) for i in matched)})
        # A blob in history may be an older version of a reviewed file, with fewer of its coincidences.
        known = KNOWN.get(name, 0)
        status = "known coincidence" if (len(matched) <= known if history else len(matched) == known) else "CHECK"
        if in_context:
            status = "CHECK"
        problems += status == "CHECK"
        where = ""
        if oid and status == "CHECK":
            added = _git("log", "--all", "--format=%h", f"--find-object={oid}").split()
            where = f", blob {oid[:10]}, in commit(s) {' '.join(added)}"
        context = f"; label + value on lines {in_context}" if in_context else ""
        print(f"{status}: {name}: {len(matched)} token(s), lines {line_nos}{context}{where}")
    unit = "blobs in all history" if history else "files"
    print(f"{len(toks)} tokens checked against {checked} {unit}; {problems} file(s) to check")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
