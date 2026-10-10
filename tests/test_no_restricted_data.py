"""The M4 plan Q1 licence guard: nothing restricted may be tracked by git.

The Malaysia Energy Statistics Handbook is "All rights reserved", so its PDF and any numbers read
from it must never be committed. This test asks git what IS tracked (so it also catches a file that
was force-added past .gitignore) and fails if a PDF, a data/ or docs/references/ path, or a handbook
fixture that is not marked synthetic is among them.
"""

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HANDBOOK_FIXTURES = "tests/fixtures/handbook/"
# The one PDF that may be tracked: the report export without the restricted pages (M5 plan Q2, written by
# tools/export_pages.py). Its text is checked below and value-scanned by tools/scan_handbook_values.py.
PUBLIC_PDFS = {"docs/report.pdf"}


@pytest.fixture(scope="module")
def tracked():
    """Every tracked path (forward slashes, relative to the repo root)."""
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, timeout=60).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pytest.skip("not inside a git work tree")
    paths = [p for p in out.decode("utf-8").split("\0") if p]
    assert paths, "git ls-files returned nothing: the guard would pass vacuously"
    return paths


def test_no_tracked_file_is_a_pdf_except_the_public_report(tracked):
    pdfs = [p for p in tracked if p.lower().endswith(".pdf") and p not in PUBLIC_PDFS]
    assert pdfs == []


def test_the_public_report_pdf_holds_no_restricted_page():
    path = ROOT / "docs" / "report.pdf"
    if not path.exists():
        pytest.skip("docs/report.pdf has not been exported yet")
    pdfium = pytest.importorskip("pypdfium2")
    sys.path.insert(0, str(ROOT / "tools"))
    from export_pages import RESTRICTED_MARKERS, consent

    doc = pdfium.PdfDocument(path)
    texts = [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    marked = [i + 1 for i, text in enumerate(texts) if any(m in text for m in RESTRICTED_MARKERS)]
    if consent().get("D5") == "GRANTED":
        assert len(marked) == 2  # P3 and P3b, consented 2026-10-09 (DATA_LICENSES.md, D5)
    else:
        assert marked == [], f"pages {marked} carry restricted page text"


def test_nothing_under_data_or_docs_references_is_tracked(tracked):
    restricted = [p for p in tracked if p.lower().startswith(("data/", "docs/references/"))]
    assert restricted == []


def test_every_tracked_handbook_fixture_is_json_marked_synthetic(tracked):
    fixtures = [p for p in tracked if p.lower().startswith(HANDBOOK_FIXTURES)]
    for rel in fixtures:
        assert rel.endswith(".json"), f"{rel}: only synthetic .json fixtures may live here"
        path = ROOT / rel
        if not path.exists():  # tracked but deleted from the work tree: nothing to read
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("synthetic") is True, f"{rel} is not marked synthetic"
