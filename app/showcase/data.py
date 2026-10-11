"""Read the export snapshots that `python -m pipeline export` writes to exports/ (M6 plan Q3)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

EXPORTS = Path(__file__).resolve().parents[2] / "exports"


def manifest(exports: Path = EXPORTS) -> dict:
    return json.loads((exports / "manifest.json").read_text(encoding="utf-8"))


def expected(exports: Path = EXPORTS) -> dict[str, list[dict]]:
    """The open sql/showcase results at export time: what the metric ports must reproduce (plan Q4)."""
    return json.loads((exports / "expected.json").read_text(encoding="utf-8"))


def frames(exports: Path = EXPORTS) -> dict[str, pd.DataFrame]:
    """Every exported view, by view name. Only the files the manifest lists, so a stray file is never read."""
    return {
        f["file"].removesuffix(".parquet"): pd.read_parquet(exports / f["file"]) for f in manifest(exports)["files"]
    }
