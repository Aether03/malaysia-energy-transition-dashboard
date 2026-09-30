"""Ember yearly electricity data (source D1, CC BY 4.0) → raw.ember_yearly.

- `download` saves the global CSV to data/raw/ember/<date>/ (reused the same day unless refresh=True).
- `read_csv` validates the header against the 24 columns verified in doc 05 §1.1.
- `filter_asean` keeps ASEAN members plus Ember's "ASEAN" aggregate.
- `load` MERGEs into raw.ember_yearly on (area, year, electricity_source); unchanged rows
  are left alone, so a repeat load reports zero changes (FR-02).
Download and MERGE mechanics live in `_common`.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from pipeline import config
from pipeline.sources import _common
from pipeline.sources._common import SchemaMismatchError, assert_unique_keys

EXPECTED_COLUMNS: tuple[str, ...] = (
    "Area", "ISO 3 code", "Year", "Area type", "Electricity source", "Is aggregated source",
    "Generation (TWh)", "Generation YoY change (TWh)", "Generation YoY change (%)",
    "Share of generation (%)", "Share of generation YoY change (% points)", "Capacity (GW)",
    "Emissions (MtCO2e)", "Emissions YoY change (MtCO2e)", "Emissions YoY change (%)",
    "Share of emissions (%)", "Emissions intensity (gCO2e/kWh)", "Continent", "Ember region",
    "EU member", "OECD member", "G20 member", "G7 member", "ASEAN member",
)  # fmt: skip

# raw.ember_yearly columns, in the same order as EXPECTED_COLUMNS.
RAW_COLUMNS: tuple[str, ...] = (
    "area", "iso3", "year", "area_type", "electricity_source", "is_aggregated_source",
    "generation_twh", "generation_yoy_twh", "generation_yoy_pct",
    "share_of_generation_pct", "share_of_generation_yoy_pp", "capacity_gw",
    "emissions_mtco2e", "emissions_yoy_mtco2e", "emissions_yoy_pct",
    "share_of_emissions_pct", "emissions_intensity_gco2e_kwh", "continent", "ember_region",
    "eu_member", "oecd_member", "g20_member", "g7_member", "asean_member",
)  # fmt: skip

KEY_COLUMNS = ("area", "year", "electricity_source")
_TEXT = {"Area", "ISO 3 code", "Area type", "Electricity source", "Continent", "Ember region"}
_BOOL = {"Is aggregated source", "EU member", "OECD member", "G20 member", "G7 member", "ASEAN member"}
_INT = {"Year"}

FILE_NAME = "release_generation_yearly_global.csv"

__all__ = ["SchemaMismatchError", "download", "filter_asean", "load", "read_csv", "to_raw_records", "validate_header"]


def validate_header(columns: list[str]) -> None:
    missing = [c for c in EXPECTED_COLUMNS if c not in columns]
    unexpected = [c for c in columns if c not in EXPECTED_COLUMNS]
    if missing or unexpected:
        raise SchemaMismatchError(f"Ember header changed. Missing: {missing}; unexpected: {unexpected}")


def read_csv(path: Path | str) -> pd.DataFrame:
    # Read everything as text; types are converted explicitly in to_raw_records.
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    validate_header(list(df.columns))
    return df


def filter_asean(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["ASEAN member"] == "True") | (df["Area"] == "ASEAN")].reset_index(drop=True)


def _convert(column: str, value: str):
    value = value.strip()
    if value == "":
        return None
    if column in _TEXT:
        return value
    if column in _BOOL:
        if value not in ("True", "False"):
            raise ValueError(f"{column}: expected True/False, got {value!r}")
        return value == "True"
    if column in _INT:
        return int(value)
    number = float(value)
    if math.isnan(number):
        return None
    return number


def to_raw_records(df: pd.DataFrame) -> list[tuple]:
    return [
        tuple(_convert(column, row[column]) for column in EXPECTED_COLUMNS)
        for _, row in df.iterrows()
    ]


def download(refresh: bool = False, retries: int = 3) -> tuple[Path, str]:
    """Download today's file (or reuse it); returns (path, source_version)."""
    return _common.download(config.EMBER_YEARLY_URL, "ember", FILE_NAME, refresh=refresh, retries=retries)


def load(conn, records: list[tuple], run_id: int, source_file: str) -> int:
    """MERGE records into raw.ember_yearly inside the caller's transaction.

    Returns the number of rows inserted or changed (0 on an identical re-load).
    Rows that disappear from Ember are kept, not deleted.
    """
    assert_unique_keys(records, (0, 2, 4))  # area, year, electricity_source
    return _common.merge_into(conn, "raw.ember_yearly", RAW_COLUMNS, KEY_COLUMNS, records, run_id, source_file)
