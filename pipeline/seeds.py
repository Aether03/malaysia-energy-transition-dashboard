"""Seed loader: hand-authored CSVs in `seed/` -> dimension and reference tables.

Each CSV is MERGEd on its natural key, so re-running is idempotent and IDENTITY
surrogate keys stay stable. Seed rows are updated or inserted, never deleted. All seeds
load in one transaction, in FK-safe order. A seed can carry a natural value (e.g. an ISO3
code) that a lookup resolves to a surrogate key in Python, with a clear error if it is
unknown.

The one exception to "never deleted" is `ref.public_holiday`: it is generated from
`pipeline.public_holidays` (not hand-authored) and rebuilt on every seed.

Every CSV must carry every column of its spec (a missing column would leave the old value
in place silently), and a DQ rule's `check_sql` must be a query (SELECT/WITH), since it runs
inside the rebuild transaction (M3 database review 12-13).
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pipeline import config, db, public_holidays

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Lookup:
    """A CSV column holding a natural value, resolved to a surrogate key column on load."""

    csv_column: str
    target_column: str
    scalar_sql: str  # exactly one `?` placeholder; returns one value (None = unknown -> error)

    def __post_init__(self) -> None:
        if self.scalar_sql.count("?") != 1:
            raise ValueError(f"Lookup for {self.target_column}: scalar_sql needs exactly one '?'")


@dataclass(frozen=True)
class SeedSpec:
    csv_name: str
    table: str
    key: str
    columns: tuple[str, ...]  # allowed columns; the only names ever placed in SQL text
    lookups: tuple[Lookup, ...] = ()

    def __post_init__(self) -> None:
        for lk in self.lookups:
            if lk.target_column not in self.columns:
                raise ValueError(f"{self.csv_name}: lookup target {lk.target_column} is not a seeded column")


# Order matters: parents before children (source_map -> dim_source, kpi/dq_rule -> data_source).
SEEDS: tuple[SeedSpec, ...] = (
    SeedSpec(
        "data_source.csv",
        "dw.dim_data_source",
        "data_source_code",
        ("data_source_code", "name", "provides", "licence", "url", "credit_text", "consent_status", "is_publishable"),
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
        "dim_hour.csv",
        "dw.dim_hour",
        "hour",
        ("hour", "label"),
    ),
    SeedSpec(
        "dim_grid.csv",
        "dw.dim_grid",
        "grid_code",
        ("grid_code", "name", "country_key", "utc_offset_min", "data_source_code", "is_published"),
        lookups=(Lookup("country_iso3", "country_key", "SELECT country_key FROM dw.dim_country WHERE iso3 = ?"),),
    ),
    SeedSpec("dim_region.csv", "dw.dim_region", "region_code", ("region_code", "name", "display_order")),
    SeedSpec(
        "dim_state.csv",
        "dw.dim_state",
        "state_code",
        ("state_code", "name", "geo_shape_name", "iso_3166_2", "region_key", "is_federal_territory", "display_order"),
        lookups=(Lookup("region_code", "region_key", "SELECT region_key FROM dw.dim_region WHERE region_code = ?"),),
    ),
    SeedSpec("state_alias.csv", "ref.state_alias", "alias", ("alias", "state_code")),
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


_QUERY = re.compile(r"\s*(WITH|SELECT)(?![A-Za-z0-9_])", re.IGNORECASE)


def _expected_header(spec: SeedSpec) -> set[str]:
    targets = {lk.target_column: lk.csv_column for lk in spec.lookups}
    return {targets.get(c, c) for c in spec.columns}


def _read_csv(spec: SeedSpec, seed_dir: Path) -> tuple[list[str], list[tuple[str | None, ...]]]:
    """Return (header, rows) with empty cells as None; the header must be exactly the spec's columns
    (with each lookup's CSV column in place of its target)."""
    path = seed_dir / spec.csv_name
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"{spec.csv_name}: empty file")
        expected = _expected_header(spec)
        if set(header) != expected or len(set(header)) != len(header):
            missing, extra = sorted(expected - set(header)), sorted(set(header) - expected)
            raise ValueError(f"{spec.csv_name}: header mismatch (missing {missing}, unexpected {extra})")
        rows = []
        for line_no, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(f"{spec.csv_name} line {line_no}: expected {len(header)} cells, got {len(row)}")
            rows.append(tuple(cell if cell != "" else None for cell in row))
    if spec.table == "meta.dq_rule":
        sql_at = header.index("check_sql")
        for row in rows:
            if not _QUERY.match(row[sql_at] or ""):
                raise ValueError(f"{spec.csv_name}: rule {row[0]} check_sql must start with SELECT or WITH")
    return header, rows


def _target_columns(spec: SeedSpec) -> list[tuple[str, str, Lookup | None]]:
    """(target column, csv column, lookup or None) in canonical order, allow-listed names only."""
    by_target = {lk.target_column: lk for lk in spec.lookups}
    return [(c, by_target[c].csv_column, by_target[c]) if c in by_target else (c, c, None) for c in spec.columns]


def _merge_sql(spec: SeedSpec) -> str:
    """MERGE on the natural key; column names come only from the hard-coded allow-list."""
    cols = [t for t, _, _ in _target_columns(spec)]
    source_cols = ", ".join(f"? AS {c}" for c in cols)
    updates = ", ".join(f"t.{c} = s.{c}" for c in cols if c != spec.key)
    insert_cols = ", ".join(cols)
    insert_vals = ", ".join(f"s.{c}" for c in cols)
    return (
        f"MERGE {spec.table} AS t USING (SELECT {source_cols}) AS s ON t.{spec.key} = s.{spec.key} "
        f"WHEN MATCHED THEN UPDATE SET {updates} "
        f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});"
    )


def _resolve(cursor, spec: SeedSpec, lookup: Lookup, value: str | None) -> object:
    cursor.execute(lookup.scalar_sql, (value,))
    found = cursor.fetchone()
    if value is None or found is None or found[0] is None:
        raise ValueError(f"{spec.csv_name}: unknown {lookup.csv_column} {value!r}")
    return found[0]


def seed_all(seed_dir: Path | None = None) -> dict[str, int]:
    """Load every seed CSV in one transaction; returns rows loaded per table."""
    seed_dir = seed_dir or config.SEED_DIR
    counts: dict[str, int] = {}
    conn = db.connect()
    try:
        cursor = conn.cursor()
        for spec in SEEDS:
            header, rows = _read_csv(spec, seed_dir)
            targets = _target_columns(spec)
            sql = _merge_sql(spec)
            for row in rows:
                by_name = dict(zip(header, row, strict=True))
                params = tuple(
                    _resolve(cursor, spec, lookup, by_name[csv_col]) if lookup else by_name[csv_col]
                    for _, csv_col, lookup in targets
                )
                cursor.execute(sql, params)
            counts[spec.table] = len(rows)
            log.info("Seeded %s: %d rows", spec.table, len(rows))
        counts["ref.public_holiday"] = public_holidays.load_public_holidays(cursor, seed_dir)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return counts
