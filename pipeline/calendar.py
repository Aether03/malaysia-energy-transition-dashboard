"""Public holidays for the hourly grids → ref.public_holiday (doc 05 dim_date; M3 plan step 3).

Generated at seed time from the pinned `holidays` package (national holidays only, no
state or regional ones), then corrected by `seed/holiday_override.csv`, where each row
was hand-checked against an official list. The table is fully derived, so it is
rebuilt on every seed: a package upgrade that drops a holiday can't leave a stale row.
"""

from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path

import holidays

log = logging.getLogger(__name__)

# The Thailand files span 2023-01-01 to 2025-01-01 local time; MY is ready for GSO.
HOLIDAY_YEARS: tuple[int, ...] = (2023, 2024, 2025)
COUNTRIES: tuple[str, ...] = ("TH", "MY")  # names requested in en_US (the TH default is Thai script)
OVERRIDE_FILE = "holiday_override.csv"
OVERRIDE_COLUMNS = ("country_code", "holiday_date", "name", "action")  # action: ADD or REMOVE


def package_holidays(years: tuple[int, ...] = HOLIDAY_YEARS) -> dict[tuple[str, date], tuple[str, str]]:
    """{(country, date): (name, origin)} from the holidays package."""
    origin = f"holidays {holidays.__version__}"
    out: dict[tuple[str, date], tuple[str, str]] = {}
    for country in COUNTRIES:
        for day, name in holidays.country_holidays(country, years=years, language="en_US").items():
            out[(country, day)] = (name, origin)
    return out


def read_overrides(seed_dir: Path) -> list[tuple[str, date, str, str]]:
    path = seed_dir / OVERRIDE_FILE
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != OVERRIDE_COLUMNS:
            raise ValueError(f"{OVERRIDE_FILE}: header must be {list(OVERRIDE_COLUMNS)}, got {reader.fieldnames}")
        rows = []
        for row in reader:
            if row["country_code"] not in COUNTRIES or row["action"] not in ("ADD", "REMOVE"):
                raise ValueError(f"{OVERRIDE_FILE}: bad row {row}")
            rows.append((row["country_code"], date.fromisoformat(row["holiday_date"]), row["name"], row["action"]))
    return rows


def build_holidays(seed_dir: Path) -> list[tuple[str, date, str, str]]:
    """Package holidays with the overrides applied, as (country, date, name, origin) rows."""
    table = package_holidays()
    for country, day, name, action in read_overrides(seed_dir):
        if action == "REMOVE":
            table.pop((country, day), None)
        else:
            table[(country, day)] = (name, "override")
    return [(c, d, name, origin) for (c, d), (name, origin) in sorted(table.items())]


def load_public_holidays(cursor, seed_dir: Path) -> int:
    """Rebuild ref.public_holiday inside the caller's (seed) transaction; returns the row count."""
    rows = build_holidays(seed_dir)
    cursor.execute("DELETE FROM ref.public_holiday")
    cursor.executemany(
        "INSERT INTO ref.public_holiday (country_code, holiday_date, name, origin) VALUES (?, ?, ?, ?)",
        rows,
    )
    log.info("Seeded ref.public_holiday: %d rows", len(rows))
    return len(rows)
