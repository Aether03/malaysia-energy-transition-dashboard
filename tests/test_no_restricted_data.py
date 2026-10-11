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


def test_exports_hold_only_publishable_sources():
    # M6 plan Q3: every exported file's sources are publishable in the seed, and no excluded view has a file.
    import csv

    manifest_path = ROOT / "exports" / "manifest.json"
    if not manifest_path.exists():
        pytest.skip("exports/ has not been written yet")
    with (ROOT / "seed" / "data_source.csv").open(encoding="utf-8", newline="") as f:
        publishable = {r["data_source_code"] for r in csv.DictReader(f) if r["is_publishable"] == "1"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        assert set(entry["sources"]) <= publishable, f"{entry['file']}: {entry['sources']}"
    on_disk = {p.stem for p in (ROOT / "exports").glob("*.parquet")}
    assert on_disk == {e["file"].removesuffix(".parquet") for e in manifest["files"]}
    assert not on_disk & set(manifest["excluded_views"])


def restricted_rows(exports: pathlib.Path, publishable: set[str]) -> list[str]:
    """What the Parquet files themselves hold, not what the manifest says (M6 review M4): every grid row belongs to a
    grid in dim_grid whose source is publishable, no handbook view (read from sql/views, not from pipeline/export.py)
    has a file, and a restricted source's DQ rule carries no detail."""
    import re

    import pandas as pd

    problems = []
    frames = {p.stem: pd.read_parquet(p) for p in exports.glob("*.parquet")}
    grid = frames.get("dim_grid", pd.DataFrame(columns=["grid_key", "grid_code", "data_source_code"]))
    problems += [f"dim_grid: {c} not publishable" for c in set(grid["data_source_code"]) - publishable]
    for name, frame in frames.items():
        if "grid_key" in frame and not set(frame["grid_key"]) <= set(grid["grid_key"]):
            problems.append(f"{name}: grid rows outside dim_grid")
    m4 = (ROOT / "sql" / "views" / "R__mart_m4.sql").read_text(encoding="utf-8")
    handbook = set(re.findall(r"CREATE OR ALTER VIEW mart\.(\w+)", m4))
    problems += [f"{name}: a handbook view" for name in handbook & set(frames)]
    dq = frames.get("dq_latest")
    if dq is not None:
        leaks = dq[~dq["data_source_code"].isin(publishable) & dq["data_source_code"].notna() & dq["detail"].notna()]
        problems += [f"dq_latest {r}: restricted detail" for r in leaks["rule_code"]]
    return problems


def publishable_in_seed() -> set[str]:
    import csv

    with (ROOT / "seed" / "data_source.csv").open(encoding="utf-8", newline="") as f:
        return {r["data_source_code"] for r in csv.DictReader(f) if r["is_publishable"] == "1"}


def test_the_exported_files_hold_no_restricted_rows():
    if not (ROOT / "exports" / "manifest.json").exists():
        pytest.skip("exports/ has not been written yet")
    assert restricted_rows(ROOT / "exports", publishable_in_seed()) == []


def test_the_content_check_catches_restricted_rows(tmp_path):
    """Positive control: a GSO grid, its rows, a handbook view and a restricted DQ detail are each flagged."""
    import pandas as pd

    pd.DataFrame(
        {"grid_key": [1, 2], "grid_code": ["TH_EGAT", "MY_PEN_GSO"], "data_source_code": ["DTH", "D4"]}
    ).to_parquet(tmp_path / "dim_grid.parquet")
    pd.DataFrame({"grid_key": [1, 3]}).to_parquet(tmp_path / "grid_hourly.parquet")
    pd.DataFrame({"x": [1]}).to_parquet(tmp_path / "region_annual.parquet")
    pd.DataFrame({"rule_code": ["R"], "data_source_code": ["D5"], "detail": ["a value"]}).to_parquet(
        tmp_path / "dq_latest.parquet"
    )
    problems = restricted_rows(tmp_path, publishable_in_seed())
    assert problems == [
        "dim_grid: D4 not publishable",
        "grid_hourly: grid rows outside dim_grid",
        "region_annual: a handbook view",
        "dq_latest R: restricted detail",
    ]
