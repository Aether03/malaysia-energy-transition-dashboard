"""Ember yearly electricity data (source D1, CC BY 4.0) → raw.ember_yearly.

- `download` saves the global CSV to data/raw/ember/<date>/ (reused the same day unless refresh=True).
- `read_csv` validates the header against the 24 columns verified in doc 05 §1.1.
- `filter_asean` keeps ASEAN members plus Ember's "ASEAN" aggregate.
- `load` MERGEs into raw.ember_yearly on (area, year, electricity_source); unchanged rows
  are left alone, so a repeat load reports zero changes (FR-02).
"""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from pipeline import config

log = logging.getLogger(__name__)

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


class SchemaMismatchError(ValueError):
    """The downloaded file's columns differ from the verified header."""


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
    folder = config.RAW_DIR / "ember" / datetime.now(UTC).date().isoformat()
    path = folder / FILE_NAME
    version_file = path.with_suffix(".version")
    if path.exists() and not refresh:
        version = version_file.read_text(encoding="utf-8") if version_file.exists() else "cached"
        log.info("Reusing %s", path)
        return path, version

    folder.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(
                config.EMBER_YEARLY_URL,
                stream=True,
                timeout=60,
                headers={"User-Agent": "malaysia-energy-transition-dashboard (portfolio project)"},
            ) as response:
                response.raise_for_status()
                with partial.open("wb") as fh:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
                version = response.headers.get("Last-Modified") or response.headers.get("ETag") or "unknown"
            partial.replace(path)
            version_file.write_text(version, encoding="utf-8")
            log.info("Downloaded %s (%d bytes, version %s)", path, path.stat().st_size, version)
            return path, version
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            wait = 2**attempt
            log.warning("Download attempt %d failed (%s); retrying in %ds", attempt, exc, wait)
            time.sleep(wait)
    raise AssertionError("unreachable")


def load(conn, records: list[tuple], run_id: int, source_file: str) -> int:
    """MERGE records into raw.ember_yearly inside the caller's transaction.

    Returns the number of rows inserted or changed (0 on an identical re-load).
    Rows that disappear from Ember are kept, not deleted.
    """
    keys = [(r[0], r[2], r[4]) for r in records]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate (area, year, electricity_source) keys in Ember extract")

    cols = ", ".join(RAW_COLUMNS)
    cursor = conn.cursor()
    cursor.execute(f"SELECT TOP (0) {cols} INTO #stage FROM raw.ember_yearly")
    placeholders = ", ".join("?" for _ in RAW_COLUMNS)
    cursor.executemany(f"INSERT INTO #stage ({cols}) VALUES ({placeholders})", records)

    non_keys = [c for c in RAW_COLUMNS if c not in KEY_COLUMNS]
    on = " AND ".join(f"t.{c} = s.{c}" for c in KEY_COLUMNS)
    changed = (
        f"EXISTS (SELECT {', '.join('s.' + c for c in non_keys)} "
        f"EXCEPT SELECT {', '.join('t.' + c for c in non_keys)})"
    )
    updates = ", ".join(f"{c} = s.{c}" for c in non_keys)
    cursor.execute(
        f"""
        SET NOCOUNT ON;  -- otherwise the MERGE row count is returned before the SELECT
        DECLARE @changes TABLE (action NVARCHAR(10));
        MERGE raw.ember_yearly AS t
        USING #stage AS s ON {on}
        WHEN MATCHED AND {changed} THEN
            UPDATE SET {updates}, _run_id = ?, _source_file = ?, _loaded_at = SYSUTCDATETIME()
        WHEN NOT MATCHED BY TARGET THEN
            INSERT ({cols}, _run_id, _source_file) VALUES ({', '.join('s.' + c for c in RAW_COLUMNS)}, ?, ?)
        OUTPUT $action INTO @changes;
        SELECT COUNT(*) FROM @changes;
        """,
        (run_id, source_file, run_id, source_file),
    )
    changes = int(cursor.fetchone()[0])
    cursor.execute("DROP TABLE #stage")
    return changes
