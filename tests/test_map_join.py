"""State boundary file joins cleanly to dim_state and the alias seed (M4 step 3): no database, no network."""

import csv
import hashlib
import importlib.util
import json
from collections import Counter

import pytest

from pipeline import config

ROOT = config.SEED_DIR.parent

_spec = importlib.util.spec_from_file_location("fetch_map", ROOT / "tools" / "fetch_map.py")
fetch_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_map)

# Row labels exactly as printed in the handbook tables (the alias seed must resolve all of them).
HANDBOOK_LABELS = [
    "Johor",
    "Kedah",
    "Kelantan",
    "WP Kuala Lumpur",
    "Melaka",
    "Negeri Sembilan",
    "Pahang",
    "Perak",
    "Perlis",
    "Pulau Pinang",
    "WP Putrajaya (including Cyberjaya)",
    "Selangor",
    "Terengganu",
]


def _rows(name):
    with (config.SEED_DIR / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def properties():
    topo = json.loads(fetch_map.MAP_PATH.read_bytes())
    return [g["properties"] for g in topo["objects"][fetch_map.OBJECT_NAME]["geometries"]]


@pytest.fixture(scope="module")
def states():
    return _rows("dim_state.csv")


def test_topojson_has_16_geometries(properties):
    assert len(properties) == 16


def test_every_shape_iso_joins_to_exactly_one_state(properties, states):
    iso_counts = Counter(r["iso_3166_2"] for r in states)
    for p in properties:
        assert iso_counts[p["shapeISO"]] == 1, p["shapeISO"]
    assert {p["shapeISO"] for p in properties} == set(iso_counts)


def test_every_shape_name_joins_to_exactly_one_state(properties, states):
    name_counts = Counter(r["geo_shape_name"] for r in states)
    for p in properties:
        assert name_counts[p["shapeName"]] == 1, p["shapeName"]
    assert {p["shapeName"] for p in properties} == set(name_counts)


def test_every_alias_points_at_a_real_state(states):
    codes = {r["state_code"] for r in states}
    aliases = _rows("state_alias.csv")
    assert len({r["alias"] for r in aliases}) == len(aliases)  # alias is the primary key
    assert {r["state_code"] for r in aliases} <= codes


def test_handbook_labels_are_all_aliased():
    aliases = {r["alias"] for r in _rows("state_alias.csv")}
    assert set(HANDBOOK_LABELS) <= aliases
    assert "PENINSULAR MALAYSIA" not in {a.upper() for a in aliases}  # a total row, not a state


def test_every_state_region_exists(states):
    regions = {r["region_code"] for r in _rows("dim_region.csv")}
    assert {r["region_code"] for r in states} <= regions


def test_local_file_matches_the_pinned_sha256():
    data = fetch_map.MAP_PATH.read_bytes()
    assert len(data) == fetch_map.SIZE_BYTES
    assert hashlib.sha256(data).hexdigest() == fetch_map.SHA256
