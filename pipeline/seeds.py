"""Seed loader: hand-authored CSVs in `seed/` -> dimension and reference tables.

Each CSV is MERGEd on its natural key, so re-running is idempotent and IDENTITY
surrogate keys stay stable. Rows are updated or inserted, never deleted. All seeds
load in one transaction, in FK-safe order.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from pipeline import config, db

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedSpec:
    csv_name: str
    table: str
    key: str
    columns: tuple[str, ...]  # allowed columns; the only names ever placed in SQL text


# Order matters: parents before children (source_map -> dim_source, kpi/dq_rule -> data_source).
SEEDS: tuple[SeedSpec, ...] = (
    SeedSpec(
        "data_source.csv",
        "dw.dim_data_source",
        "data_source_code",
        ("data_source_code", "name", "licence", "url", "credit_text", "consent_status", "is_publishable"),
    ),
    SeedSpec(
        "dim_source.csv",
        "dw.dim_source",
        "source_code",
        ("source_code", "display_name", "group_name", "sort_order", "color_hex", "color_hex_dark"),
    ),
    SeedSpec(
        "dim_country.csv",
        "dw.dim_country",
        "ember_area",
        ("iso3", "ember_area", "name", "area_type", "is_asean", "is_focus", "is_default_peer", "display_order"),
    ),
    SeedSpec("source_map.csv", "ref.source_map", "ember_source", ("ember_source", "source_code", "include_in_mix")),
    SeedSpec(
        "netr_target.csv",
        "ref.netr_target",
        "target_year",
        ("target_year", "re_capacity_share_pct", "source_name", "source_url"),
    ),
    SeedSpec(
        "re_capacity_official.csv",
        "ref.re_capacity_official",
        "year",
        ("year", "re_capacity_share_pct", "basis", "source_name", "source_url", "as_of"),
    ),
    SeedSpec(
        "kpi.csv",
        "ref.kpi",
        "kpi_code",
        ("kpi_code", "name", "definition", "formula", "unit", "polarity", "data_source_code"),
    ),
    SeedSpec(
        "dq_rule.csv",
        "meta.dq_rule",
        "rule_code",
        ("rule_code", "description", "data_source_code", "severity", "check_sql", "is_active"),
    ),
)


def _read_csv(spec: SeedSpec, seed_dir: Path) -> tuple[list[str], list[tuple[str | None, ...]]]:
    """Return (header, rows) with empty cells as None; the header must fit the spec."""
    path = seed_dir / spec.csv_name
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        unknown = [c for c in header if c not in spec.columns]
        if unknown or spec.key not in header or len(set(header)) != len(header):
            raise ValueError(f"{spec.csv_name}: unexpected header {header} (allowed: {list(spec.columns)})")
        rows = []
        for line_no, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(f"{spec.csv_name} line {line_no}: expected {len(header)} cells, got {len(row)}")
            rows.append(tuple(cell if cell != "" else None for cell in row))
    return header, rows


def _merge_sql(spec: SeedSpec, header: list[str]) -> str:
    """MERGE on the natural key; column names come only from the hard-coded allow-list."""
    cols = [c for c in spec.columns if c in header]  # canonical order, allow-listed names only
    source_cols = ", ".join(f"? AS {c}" for c in cols)
    updates = ", ".join(f"t.{c} = s.{c}" for c in cols if c != spec.key)
    insert_cols = ", ".join(cols)
    insert_vals = ", ".join(f"s.{c}" for c in cols)
    return (
        f"MERGE {spec.table} AS t USING (SELECT {source_cols}) AS s ON t.{spec.key} = s.{spec.key} "
        f"WHEN MATCHED THEN UPDATE SET {updates} "
        f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});"
    )


def seed_all(seed_dir: Path | None = None) -> dict[str, int]:
    """Load every seed CSV in one transaction; returns rows loaded per table."""
    seed_dir = seed_dir or config.SEED_DIR
    counts: dict[str, int] = {}
    conn = db.connect()
    try:
        cursor = conn.cursor()
        for spec in SEEDS:
            header, rows = _read_csv(spec, seed_dir)
            cols = [c for c in spec.columns if c in header]
            sql = _merge_sql(spec, header)
            for row in rows:
                by_name = dict(zip(header, row))
                cursor.execute(sql, tuple(by_name[c] for c in cols))
            counts[spec.table] = len(rows)
            log.info("Seeded %s: %d rows", spec.table, len(rows))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return counts
