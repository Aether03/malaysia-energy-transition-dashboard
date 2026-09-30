"""Our World in Data energy dataset (source D2, CC BY 4.0) → raw.owid_energy.

Used for population (demand per capita) and as a WARN-level cross-check on Ember.
- `read_csv` keeps only the 18 columns this project uses (doc 05 §1.1). OWID adds columns
  over time, so extra columns are allowed; a missing required column stops the run.
- `filter_asean` keeps the 10 ASEAN members by ISO code (OWID aggregates such as
  OWID_WRL or blank-coded regions are dropped).
- `load` MERGEs into raw.owid_energy on (iso_code, year).
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from pipeline import config
from pipeline.sources import _common
from pipeline.sources._common import SchemaMismatchError, assert_unique_keys

# raw.owid_energy keeps OWID's own column names (already snake_case).
REQUIRED_COLUMNS: tuple[str, ...] = (
    "country", "year", "iso_code", "population", "per_capita_electricity",
    "electricity_demand", "electricity_generation", "carbon_intensity_elec",
    "renewables_share_elec", "coal_electricity", "gas_electricity", "oil_electricity",
    "hydro_electricity", "solar_electricity", "wind_electricity", "biofuel_electricity",
    "other_renewable_electricity", "greenhouse_gas_emissions",
)  # fmt: skip

KEY_COLUMNS = ("iso_code", "year")
_TEXT = {"country", "iso_code"}
_INT = {"year", "population"}

FILE_NAME = "owid-energy-data.csv"


def read_csv(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaMismatchError(f"OWID header changed. Missing: {missing}")
    return df.loc[:, list(REQUIRED_COLUMNS)]


def filter_asean(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["iso_code"].isin(config.ASEAN_ISO3)].reset_index(drop=True)


def _convert(column: str, value: str):
    value = value.strip()
    if value == "":
        return None
    if column in _TEXT:
        return value
    number = float(value)
    if math.isnan(number):
        return None
    if column in _INT:
        return int(number)  # population arrives as "35977834" or "35977834.0"
    return number


def to_raw_records(df: pd.DataFrame) -> list[tuple]:
    return [tuple(_convert(column, row[column]) for column in REQUIRED_COLUMNS) for _, row in df.iterrows()]


def download(refresh: bool = False, retries: int = 3) -> tuple[Path, str]:
    """Download today's file (or reuse it); returns (path, source_version)."""
    return _common.download(config.OWID_ENERGY_URL, "owid", FILE_NAME, refresh=refresh, retries=retries)


def load(conn, records: list[tuple], run_id: int, source_file: str) -> int:
    """MERGE records into raw.owid_energy inside the caller's transaction; returns rows changed."""
    assert_unique_keys(records, (2, 1))  # iso_code, year
    return _common.merge_into(conn, "raw.owid_energy", REQUIRED_COLUMNS, KEY_COLUMNS, records, run_id, source_file)


__all__ = ["REQUIRED_COLUMNS", "SchemaMismatchError", "download", "filter_asean", "load", "read_csv", "to_raw_records"]
