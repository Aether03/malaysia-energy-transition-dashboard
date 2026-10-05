"""Fetch and verify the Malaysia state boundary file used by the Shape Map (M4 step 3).

Source: geoBoundaries gbOpen MYS ADM1 (boundaryID MYS-ADM1-15666254), licence ODbL 1.0
(OpenStreetMap contributors, via Wambacher). The URL is pinned to a commit, and the download is
checked against a pinned SHA-256 and size BEFORE anything is written. The file must hold the 16
geometries whose shapeISO and shapeName sets equal `seed/dim_state.csv` (iso_3166_2, geo_shape_name).

    .venv/Scripts/python tools/fetch_map.py            # download, verify, write
    .venv/Scripts/python tools/fetch_map.py --check    # verify the local file only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / "report" / "maps" / "mys_adm1.topojson"
DIM_STATE_CSV = ROOT / "seed" / "dim_state.csv"

URL = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/MYS/ADM1/geoBoundaries-MYS-ADM1.topojson"
SHA256 = "b358676a9a2f85e2a713670dcda51564e0d492790cec6b3d7fd359c07dbbb0bd"
SIZE_BYTES = 795_812
OBJECT_NAME = "MYSADM1gbOpen"
GEOMETRY_COUNT = 16
TIMEOUT_SECONDS = 60


class MapError(Exception):
    """The boundary file is not the pinned, expected one."""


def verify_bytes(data: bytes) -> None:
    """Raise MapError unless the bytes match the pinned size and SHA-256."""
    if len(data) != SIZE_BYTES:
        raise MapError(f"size mismatch: expected {SIZE_BYTES:,} bytes, got {len(data):,}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        raise MapError(f"SHA-256 mismatch: expected {SHA256}, got {digest}")


def verify_content(data: bytes) -> None:
    """Raise MapError unless the 16 geometries match dim_state on shapeISO and shapeName."""
    try:
        geometries = json.loads(data)["objects"][OBJECT_NAME]["geometries"]
        props = [g["properties"] for g in geometries]
        iso = {p["shapeISO"] for p in props}
        names = {p["shapeName"] for p in props}
    except (ValueError, KeyError, TypeError) as exc:
        raise MapError(f"unexpected TopoJSON structure: {exc!r}") from exc
    if len(geometries) != GEOMETRY_COUNT:
        raise MapError(f"expected {GEOMETRY_COUNT} geometries, found {len(geometries)}")
    with DIM_STATE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for label, from_map, from_seed in (
        ("shapeISO vs iso_3166_2", iso, {r["iso_3166_2"] for r in rows}),
        ("shapeName vs geo_shape_name", names, {r["geo_shape_name"] for r in rows}),
    ):
        if from_map != from_seed:
            raise MapError(
                f"{label}: only in map {sorted(from_map - from_seed)}, only in dim_state {sorted(from_seed - from_map)}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="verify the existing local file without downloading")
    args = parser.parse_args()

    try:
        if args.check:
            if not MAP_PATH.is_file():
                raise MapError(f"{MAP_PATH} does not exist; run without --check to download it")
            data = MAP_PATH.read_bytes()
            verify_bytes(data)
            verify_content(data)
            print(f"OK: {MAP_PATH.relative_to(ROOT)} matches the pinned SHA-256 and dim_state")
            return 0

        response = requests.get(URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.content
        verify_bytes(data)
        verify_content(data)
    except (MapError, requests.RequestException) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_bytes(data)
    print(f"Wrote {MAP_PATH.relative_to(ROOT)} ({len(data):,} bytes, SHA-256 verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
