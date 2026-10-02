"""Public holidays for the hourly grids → ref.public_holiday (doc 05 dim_date; M3 plan step 3).

Generated at seed time from the pinned `holidays` package (national holidays only, no
state or regional ones), then corrected by `seed/holiday_override.csv`, where each row
was hand-checked against an official list. The table is fully derived, so it is
rebuilt on every seed: a package upgrade that drops a holiday can't leave a stale row.

Years cover every hourly grid's span plus one year either side (M3 review: Singapore's
first file starts 2022-12-26). An override that no longer matches the package (a REMOVE of
a date the package lacks) or repeats a date stops the seed: the hand check is stale.
Named public_holidays, not calendar, so it can't shadow the standard library module.
"""

from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path

import holidays

log = logging.getLogger(__name__)

# Hourly data spans 2022-12-26 (SG's first week) to 2025-01-05 (SG's last week); one year
# of margin either side. tests/test_public_holidays.py checks this against both sources.
HOLIDAY_YEARS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025, 2026)
COUNTRIES: tuple[str, ...] = ("TH", "MY", "SG")  # names requested in en_US (the TH default is Thai script)
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
        seen: set[tuple[str, date]] = set()
        for row in reader:
            row = {k: (v or "").strip() for k, v in row.items()}
            if row["country_code"] not in COUNTRIES or row["action"] not in ("ADD", "REMOVE") or not row["name"]:
                raise ValueError(f"{OVERRIDE_FILE}: bad row {row}")
            key = (row["country_code"], date.fromisoformat(row["holiday_date"]))
            if key in seen:
                raise ValueError(f"{OVERRIDE_FILE}: duplicate row for {key}")
            seen.add(key)
            rows.append((*key, row["name"], row["action"]))
    return rows


def build_holidays(seed_dir: Path) -> list[tuple[str, date, str, str]]:
    """Package holidays with the overrides applied, as (country, date, name, origin) rows."""
    table = package_holidays()
    for country, day, name, action in read_overrides(seed_dir):
        if action == "REMOVE":
            if (country, day) not in table:
                raise ValueError(f"{OVERRIDE_FILE}: REMOVE {country} {day} matches no package holiday; re-check it")
            del table[(country, day)]
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
