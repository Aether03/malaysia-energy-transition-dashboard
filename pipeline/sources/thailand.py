"""Thai power system hourly data (source DTH; Zenodo record 17109911, CC BY 4.0) → raw.grid_interval.

EGAT's hourly regional generation and demand plus cross-border flows, 2023 and 2024. It is
the open-data stand-in for Peninsular Malaysia until TNB consents to GSO reuse (doc 02 §11).

Raw is an exact copy of both published files (M3 plan Q1):
- The two files have different headers (2024 reorders the flow columns and renames EDL_* to
  laos_*). `read_file` accepts exactly these two column sets and maps every value by name,
  never by position; anything else stops the run with `SchemaMismatchError`.
- Every row is kept as published: the `0:05` first-hour stamps, the duplicate first hour in
  the 2024 file, and each file's spill-over day into the next year. `file_name` is part of
  the raw key, so the boundary day appears once per file. Normalisation, de-duplication and
  local→UTC happen in `stg` (sql/views/R__stg_thailand.sql).
- Long form: one record per (row, published column), with blanks as NULL.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pandas as pd

from pipeline import config
from pipeline.sources import _common
from pipeline.sources._common import SchemaMismatchError, assert_unique_keys

GRID_CODE = "TH_EGAT"
FILES: tuple[str, ...] = ("system_2023.csv", "system_2024.csv")
DATETIME_COLUMN = "datetime"

_COMMON = (
    "datetime", "north_generation", "north_demand", "south_generation", "south_demand",
    "metropolitan_generation", "metropolitan_demand", "central_generation", "central_demand",
    "northeast_generation", "northeast_demand", "malaysia_IMP", "malaysia_EXP", "hongsa_IMP",
    "cambodia_EXP",
)  # fmt: skip
HEADER_VARIANTS: tuple[frozenset[str], ...] = (
    frozenset(_COMMON) | {"EDL_IMP", "EDL_EXP"},  # system_2023.csv
    frozenset(_COMMON) | {"laos_IMP", "laos_EXP"},  # system_2024.csv
)

RAW_COLUMNS = ("grid_code", "file_name", "ts_text", "series", "value")
KEY_COLUMNS = ("grid_code", "file_name", "ts_text", "series")


def read_file(path: Path | str) -> pd.DataFrame:
    """Read one published file as text; the column set must be one of the known variants."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if frozenset(df.columns) not in HEADER_VARIANTS or len(set(df.columns)) != len(df.columns):
        raise SchemaMismatchError(f"Thailand header changed in {Path(path).name}: {list(df.columns)}")
    return df


def _value(text: str) -> float | None:
    text = text.strip()
    if text == "":
        return None
    number = float(text)
    if math.isnan(number):
        return None
    return number


def to_raw_records(df: pd.DataFrame, file_name: str) -> list[tuple]:
    """Long form in file order: (grid_code, file_name, ts_text, series, value) per cell."""
    series = [c for c in df.columns if c != DATETIME_COLUMN]
    records: list[tuple] = []
    for row in df.to_dict("records"):
        ts_text = row[DATETIME_COLUMN]
        records.extend((GRID_CODE, file_name, ts_text, name, _value(row[name])) for name in series)
    return records


def records_from(folder: Path) -> list[tuple]:
    """Records for every published file in FILES order (2023 first)."""
    folder = Path(folder)
    records: list[tuple] = []
    for name in FILES:
        records.extend(to_raw_records(read_file(folder / name), name))
    return records


def verify_checksum(path: Path) -> str:
    """Return the file's MD5; raise SchemaMismatchError if it differs from Zenodo's published one."""
    md5 = hashlib.md5(path.read_bytes()).hexdigest()  # matches Zenodo's published checksum; not a security use
    expected = config.THAILAND_MD5[path.name]
    if md5 != expected:
        raise SchemaMismatchError(f"{path.name} md5 {md5} differs from Zenodo's {expected}: the record was revised")
    return md5


def download(refresh: bool = False, retries: int = 3) -> tuple[Path, str]:
    """Download both files into today's folder (or reuse them), verify their checksums;
    returns (folder, source_version)."""
    versions = []
    folder = None
    for name in FILES:
        path, _ = _common.download(
            config.THAILAND_FILE_URL.format(file_name=name), "thailand", name, refresh=refresh, retries=retries
        )
        folder = path.parent
        versions.append(f"{name[7:11]} md5 {verify_checksum(path)[:8]}")
    assert folder is not None
    return folder, f"zenodo {config.THAILAND_ZENODO_RECORD} v1.0; " + "; ".join(versions)


def load(conn, records: list[tuple], run_id: int, source_file: str) -> int:
    """MERGE records into raw.grid_interval inside the caller's transaction; returns rows changed."""
    assert_unique_keys(records, range(len(KEY_COLUMNS)))
    return _common.merge_into(conn, "raw.grid_interval", RAW_COLUMNS, KEY_COLUMNS, records, run_id, source_file)


__all__ = [
    "FILES", "GRID_CODE", "HEADER_VARIANTS", "KEY_COLUMNS", "RAW_COLUMNS", "SchemaMismatchError",
    "download", "load", "read_file", "records_from", "to_raw_records",
]  # fmt: skip
