"""Shared helpers for source modules: cached download, key checks and MERGE into raw.*.

Lifted out of `ember.py` (M2 step 2) so every source loads the same way:
- `download` saves to data/raw/<source>/<date>/, reused the same day unless refresh=True,
  with 3 attempts and exponential backoff (doc 03 Part B).
- `merge_into` bulk-inserts into a #stage table and MERGEs on the natural key; unchanged
  rows are left alone, so a repeat load reports zero changes (FR-02). Rows that disappear
  from the source are kept, not deleted.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipeline import config

log = logging.getLogger(__name__)

USER_AGENT = "malaysia-energy-transition-dashboard (portfolio project)"


class SchemaMismatchError(ValueError):
    """A downloaded file's columns differ from the verified header."""


def download(url: str, source: str, file_name: str, refresh: bool = False, retries: int = 3) -> tuple[Path, str]:
    """Download today's file (or reuse it); returns (path, source_version)."""
    folder = config.RAW_DIR / source / datetime.now(UTC).date().isoformat()
    path = folder / file_name
    version_file = path.with_suffix(".version")
    if path.exists() and not refresh:
        version = version_file.read_text(encoding="utf-8") if version_file.exists() else "cached"
        log.info("Reusing %s", path)
        return path, version

    folder.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=60, headers={"User-Agent": USER_AGENT}) as response:
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


def assert_unique_keys(records: Sequence[tuple], key_positions: Sequence[int]) -> None:
    """Raise ValueError if two records share the same natural key."""
    seen: set[tuple] = set()
    for record in records:
        key = tuple(record[i] for i in key_positions)
        if key in seen:
            raise ValueError(f"Duplicate natural key {key}")
        seen.add(key)


def merge_into(
    conn,
    table: str,
    columns: Sequence[str],
    key_columns: Sequence[str],
    records: list[tuple],
    run_id: int,
    source_file: str,
) -> int:
    """MERGE records into `table` inside the caller's transaction.

    `table` and the column names come from module constants, never from input data.
    Returns the number of rows inserted or changed (0 on an identical re-load).
    """
    cols = ", ".join(columns)
    cursor = conn.cursor()
    cursor.execute(f"SELECT TOP (0) {cols} INTO #stage FROM {table}")
    placeholders = ", ".join("?" for _ in columns)
    cursor.executemany(f"INSERT INTO #stage ({cols}) VALUES ({placeholders})", records)

    non_keys = [c for c in columns if c not in key_columns]
    on = " AND ".join(f"t.{c} = s.{c}" for c in key_columns)
    changed = (
        f"EXISTS (SELECT {', '.join('s.' + c for c in non_keys)} "
        f"EXCEPT SELECT {', '.join('t.' + c for c in non_keys)})"
    )
    updates = ", ".join(f"{c} = s.{c}" for c in non_keys)
    cursor.execute(
        f"""
        SET NOCOUNT ON;  -- otherwise the MERGE row count is returned before the SELECT
        DECLARE @changes TABLE (action NVARCHAR(10));
        MERGE {table} AS t
        USING #stage AS s ON {on}
        WHEN MATCHED AND {changed} THEN
            UPDATE SET {updates}, _run_id = ?, _source_file = ?, _loaded_at = SYSUTCDATETIME()
        WHEN NOT MATCHED BY TARGET THEN
            INSERT ({cols}, _run_id, _source_file) VALUES ({', '.join('s.' + c for c in columns)}, ?, ?)
        OUTPUT $action INTO @changes;
        SELECT COUNT(*) FROM @changes;
        """,
        (run_id, source_file, run_id, source_file),
    )
    changes = int(cursor.fetchone()[0])
    cursor.execute("DROP TABLE #stage")
    return changes
