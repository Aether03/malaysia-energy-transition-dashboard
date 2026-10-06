"""DOSM monthly electricity supply and consumption (source D3, CC BY 4.0) → raw.dosm_electricity.

A WARN-level cross-check on Ember generation totals only (doc 05 S1); the series ends Jun 2024.
- `read_csv` validates the header matches the expected columns (date, sector, measure).
- `to_raw_records` converts DataFrame rows to tuples in raw column order
  (month: datetime.date, sector: str, measure: str, value_gwh: float).
- Blank values raise ValueError (no NULL allowed in raw.dosm_electricity.value_gwh).
- `load` MERGEs into raw.dosm_electricity on (month, sector, measure).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline import config
from pipeline.sources import _common
from pipeline.sources._common import SchemaMismatchError, assert_unique_keys

FILES = {"supply": "electricity_supply.csv", "consumption": "electricity_consumption.csv"}

RAW_COLUMNS = ("month", "sector", "measure", "value_gwh")
KEY_COLUMNS = ("month", "sector", "measure")


def read_csv(path: Path | str, measure: str) -> pd.DataFrame:
    """Read and validate a DOSM CSV file.

    Args:
        path: Path to the CSV file
        measure: Either 'supply' or 'consumption' (used to validate header)

    Returns:
        DataFrame with columns [date, sector, measure]

    Raises:
        ValueError: if measure is not 'supply' or 'consumption'
        SchemaMismatchError: if header doesn't match expected columns
    """
    if measure not in ("supply", "consumption"):
        raise ValueError(f"measure must be 'supply' or 'consumption', got {measure}")

    expected_columns = ["date", "sector", measure]

    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    if len(df.columns) != 3 or list(df.columns) != expected_columns:
        missing = [c for c in expected_columns if c not in df.columns]
        extra = [c for c in df.columns if c not in expected_columns]
        msg = f"DOSM header mismatch. Expected {expected_columns}"
        if missing:
            msg += f", missing {missing}"
        if extra:
            msg += f", extra {extra}"
        raise SchemaMismatchError(msg)

    return df


def to_raw_records(df: pd.DataFrame, measure: str) -> list[tuple]:
    """Convert DataFrame rows to raw record tuples.

    Args:
        df: DataFrame with columns [date, sector, measure_name]
        measure: 'supply' or 'consumption' (used as the measure value in output)

    Returns:
        List of tuples (month: datetime.date, sector: str, measure: str, value_gwh: float)

    Raises:
        ValueError: if a value field is blank
    """
    records = []
    for _, row in df.iterrows():
        date_str = row["date"].strip()
        sector = row["sector"].strip()
        value_str = row[measure].strip()

        if value_str == "":
            raise ValueError(f"Blank value for {date_str} and {sector}")

        try:
            month = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007 - a calendar date, no zone
        except ValueError as e:
            raise ValueError(f"Invalid date format: {date_str}") from e

        value_gwh = float(value_str)

        records.append((month, sector, measure, value_gwh))

    return records


def download(refresh: bool = False, retries: int = 3) -> tuple[Path, str]:
    """Download both supply and consumption files; returns (folder_path, version_string).

    Both files are downloaded into the same dated folder. Returns (folder, version) where
    version is a string like "supply=<v1>; consumption=<v2>".
    """
    supply_path, supply_version = _common.download(
        config.DOSM_SUPPLY_URL, "dosm", FILES["supply"], refresh=refresh, retries=retries
    )
    _consumption_path, consumption_version = _common.download(
        config.DOSM_CONSUMPTION_URL, "dosm", FILES["consumption"], refresh=refresh, retries=retries
    )

    folder = supply_path.parent
    version = f"supply={supply_version}; consumption={consumption_version}"
    return folder, version


def records_from(folder: Path) -> list[tuple]:
    """Read both supply and consumption files from folder and return all records.

    Supply records are returned first, then consumption records.
    """
    supply_path = folder / FILES["supply"]
    consumption_path = folder / FILES["consumption"]

    df_supply = read_csv(supply_path, "supply")
    df_consumption = read_csv(consumption_path, "consumption")

    records_supply = to_raw_records(df_supply, "supply")
    records_consumption = to_raw_records(df_consumption, "consumption")

    return records_supply + records_consumption


def load(conn, records: list[tuple], run_id: int, source_file: str) -> int:
    """MERGE records into raw.dosm_electricity inside the caller's transaction; returns rows changed."""
    assert_unique_keys(records, (0, 1, 2))  # month, sector, measure
    return _common.merge_into(conn, "raw.dosm_electricity", RAW_COLUMNS, KEY_COLUMNS, records, run_id, source_file)


__all__ = ["FILES", "KEY_COLUMNS", "RAW_COLUMNS", "SchemaMismatchError", "download", "load", "read_csv", "records_from", "to_raw_records"]
