"""Singapore half-hourly system demand (source DSG; EMA, Singapore Open Data Licence v1.0) → raw.grid_interval.

The second grid on P4, chosen by the M3 Q4 search (`docs/grid_sources.md`). EMA publishes one
weekly workbook per Monday (`YYYYMMDD.xls`): 7 days × 3 series (System Demand actual, NEM
Demand actual, NEM Demand forecast) × 48 half-hours, labelled by period-ENDING time.

Raw is an exact copy (M3 plan Q1), reshaped to the shared long form:
- `ts_text` = "<date cell as YYYY-MM-DD>|<period label as published>". The day's last label
  `00:00` means midnight at the END of that date; it keeps its own date here and is rolled
  into the next day only in stg (sql/views/R__stg_grid.sql).
- Values keep the source's full precision (V011 widened the raw column).
- `parse_sheet` validates the whole layout (labels, series header, the 48 period labels, 7
  consecutive dates from the Monday in the file name) and stops on any drift.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from pipeline import config
from pipeline.sources import _common
from pipeline.sources._common import SchemaMismatchError, assert_unique_keys

GRID_CODE = "SG_EMA"
SERIES: tuple[str, ...] = ("System Demand (Actual)", "NEM Demand (Actual)", "NEM Demand (Forecast)")
RAW_COLUMNS = ("grid_code", "file_name", "ts_text", "series", "value")
KEY_COLUMNS = ("grid_code", "file_name", "ts_text", "series")

# 1 Jan 2023 is a Sunday, so the first week file is the Monday before it.
FIRST_WEEK = date(2022, 12, 26)
LAST_WEEK = date(2024, 12, 30)

DAYS = 7
DATE_ROW, PERIOD_ROW, SERIES_ROW, FIRST_DATA_ROW = 1, 2, 4, 5
PERIOD_LABELS: tuple[str, ...] = tuple(
    f"{(m // 60) % 24:02d}:{m % 60:02d}" for m in range(30, 24 * 60 + 1, 30)
)  # "00:30" … "23:30", "00:00"


def week_starts(first: date, last: date) -> list[date]:
    """Every Monday from `first` (which must be a Monday) to `last`, inclusive."""
    if first.weekday() != 0:
        raise ValueError(f"{first} is not a Monday")
    weeks = []
    day = first
    while day <= last:
        weeks.append(day)
        day += timedelta(days=7)
    return weeks


def file_names() -> list[str]:
    return [f"{d:%Y%m%d}.xls" for d in week_starts(FIRST_WEEK, LAST_WEEK)]


def _cell(df: pd.DataFrame, row: int, col: int) -> str | None:
    value = df.iat[row, col] if row < df.shape[0] and col < df.shape[1] else None
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value).strip()


def _value(text) -> float | None:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return None
    text = str(text).strip()
    if text == "":
        return None
    return float(text)


def _week_monday(file_name: str) -> date:
    try:
        monday = datetime.strptime(Path(file_name).stem, "%Y%m%d").date()  # noqa: DTZ007 - a calendar date
    except ValueError as exc:
        raise SchemaMismatchError(f"{file_name}: file name is not YYYYMMDD.xls") from exc
    if monday.weekday() != 0:
        raise SchemaMismatchError(f"{file_name}: {monday} is not a Monday")
    return monday


def parse_sheet(df: pd.DataFrame, file_name: str) -> list[tuple]:
    """Validate one weekly sheet (read with header=None, dtype=str) and return its raw records."""
    if _cell(df, DATE_ROW, 0) != "Date" or _cell(df, PERIOD_ROW, 0) != "Period Ending Time":
        raise SchemaMismatchError(f"{file_name}: 'Date' / 'Period Ending Time' labels not found")

    header = [_cell(df, SERIES_ROW, col) for col in range(1, 1 + DAYS * len(SERIES))]
    if header != list(SERIES) * DAYS:
        raise SchemaMismatchError(f"{file_name}: series header changed: {header}")

    labels = tuple(_cell(df, row, 0) for row in range(FIRST_DATA_ROW, FIRST_DATA_ROW + len(PERIOD_LABELS)))
    if labels != PERIOD_LABELS:
        raise SchemaMismatchError(f"{file_name}: period-ending labels changed: {labels}")

    monday = _week_monday(file_name)
    day_cols = [1 + i * len(SERIES) for i in range(DAYS)]
    dates = []
    for i, col in enumerate(day_cols):
        text = _cell(df, DATE_ROW, col)
        try:
            day = date.fromisoformat((text or "")[:10])
        except ValueError as exc:
            raise SchemaMismatchError(f"{file_name}: date cell {text!r} in column {col}") from exc
        if day != monday + timedelta(days=i):
            raise SchemaMismatchError(f"{file_name}: day {i + 1} is {day}, expected {monday + timedelta(days=i)}")
        dates.append(day)

    records: list[tuple] = []
    for day, col in zip(dates, day_cols, strict=True):
        for offset, label in enumerate(PERIOD_LABELS):
            row = FIRST_DATA_ROW + offset
            ts_text = f"{day.isoformat()}|{label}"
            for k, series in enumerate(SERIES):
                records.append((GRID_CODE, file_name, ts_text, series, _value(df.iat[row, col + k])))
    return records


def to_raw_records(path: Path | str) -> list[tuple]:
    path = Path(path)
    return parse_sheet(pd.read_excel(path, header=None, dtype=str), path.name)


def records_from(folder: Path, names: list[str] | None = None) -> list[tuple]:
    """Records for each weekly file in `names` order (default: every week of 2023–24)."""
    folder = Path(folder)
    records: list[tuple] = []
    for name in names if names is not None else file_names():
        path = folder / name
        if not path.exists():
            raise FileNotFoundError(path)
        records.extend(to_raw_records(path))
    return records


def download(refresh: bool = False, retries: int = 3) -> tuple[Path, str]:
    """Download every weekly file into today's folder (or reuse them); returns (folder, source_version)."""
    folder = None
    for name in file_names():
        url = config.EMA_HALF_HOURLY_URL.format(year=name[:4], file_name=name)
        path, _ = _common.download(url, "singapore", name, refresh=refresh, retries=retries)
        folder = path.parent
    assert folder is not None
    return folder, f"EMA half-hourly, {len(file_names())} weekly files {FIRST_WEEK}..{LAST_WEEK}"


def load(conn, records: list[tuple], run_id: int, source_file: str) -> int:
    """MERGE records into raw.grid_interval inside the caller's transaction; returns rows changed."""
    assert_unique_keys(records, range(len(KEY_COLUMNS)))
    return _common.merge_into(conn, "raw.grid_interval", RAW_COLUMNS, KEY_COLUMNS, records, run_id, source_file)
