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

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HANDBOOK_FIXTURES = "tests/fixtures/handbook/"


@pytest.fixture(scope="module")
def tracked():
    """Every tracked path (forward slashes, relative to the repo root)."""
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, timeout=60
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pytest.skip("not inside a git work tree")
    paths = [p for p in out.decode("utf-8").split("\0") if p]
    assert paths, "git ls-files returned nothing: the guard would pass vacuously"
    return paths


def test_no_tracked_file_is_a_pdf(tracked):
    pdfs = [p for p in tracked if p.lower().endswith(".pdf")]
    assert pdfs == []


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
