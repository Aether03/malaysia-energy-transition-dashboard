"""Shared helpers for source modules: cached download, value parsing, key checks and MERGE into raw.*.

Lifted out of `ember.py` (M2 step 2) so every source loads the same way:
- `download` saves to data/raw/<source>/<date>/, reused the same day unless refresh=True,
  with 3 attempts and exponential backoff (doc 03 Part B). A permanent HTTP error (4xx other
  than 408/429) fails at once. An optional `validate` check runs on fresh AND reused files; a
  file that fails it is deleted, so a bad body is never cached (M3 Python review M1/M2).
  Callers downloading a set of files pass one `folder`, so a run that crosses 00:00 UTC
  can't split the set (M3).
- `parse_number` is the one strict text-to-number rule for raw values (M3 L2).
- `merge_into` bulk-inserts into a #stage table and MERGEs on the natural key; unchanged
  rows are left alone, so a repeat load reports zero changes (FR-02). Rows that disappear
  from the source are kept, not deleted.
"""

from __future__ import annotations

import logging
import math
import re
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipeline import config

log = logging.getLogger(__name__)

USER_AGENT = (
    "malaysia-energy-transition-dashboard (portfolio project; "
    "https://github.com/Aether03/malaysia-energy-transition-dashboard)"
)
_RETRYABLE_4XX = {408, 429}
_NUMBER = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?")


class SchemaMismatchError(ValueError):
    """A downloaded file's layout differs from the verified one."""


class InvalidDownloadError(ValueError):
    """A downloaded file's content failed its check (checksum, file signature)."""


def parse_number(text: str) -> float | None:
    """'' (after stripping) -> None; a plain decimal -> float; anything else raises ValueError.

    Rejects 'nan', 'inf', '1_000', '#N/A' and other text that float() would accept or that
    would otherwise slip through as a blank.
    """
    text = text.strip()
    if text == "":
        return None
    if not _NUMBER.fullmatch(text):
        raise ValueError(f"not a number: {text!r}")
    number = float(text)
    if not math.isfinite(number):
        raise ValueError(f"not a finite number: {text!r}")
    return number


def today_folder(source: str) -> Path:
    return config.RAW_DIR / source / datetime.now(UTC).date().isoformat()


def _discard(*paths: Path) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def download(
    url: str,
    source: str,
    file_name: str,
    refresh: bool = False,
    retries: int = 3,
    *,
    folder: Path | None = None,
    validate: Callable[[Path], None] | None = None,
    session: requests.Session | None = None,
) -> tuple[Path, str]:
    """Download the file into `folder` (default: today's) or reuse it; returns (path, source_version).

    `validate(path)` raises InvalidDownloadError for bad content; it runs on reuse and after
    each download, and a failing file is deleted (then re-downloaded, within `retries`).
    """
    folder = folder or today_folder(source)
    path = folder / file_name
    version_file = path.with_suffix(".version")
    if path.exists() and not refresh:
        try:
            if validate:
                validate(path)
            version = version_file.read_text(encoding="utf-8") if version_file.exists() else "cached"
            log.info("Reusing %s", path)
            return path, version
        except InvalidDownloadError as exc:
            log.warning("Cached %s failed its check (%s); downloading again", path, exc)
            _discard(path, version_file)

    folder.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    getter = session.get if session else requests.get
    for attempt in range(1, retries + 1):
        try:
            with getter(url, stream=True, timeout=60, headers={"User-Agent": USER_AGENT}) as response:
                response.raise_for_status()
                with partial.open("wb") as fh:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
                version = response.headers.get("Last-Modified") or response.headers.get("ETag") or "unknown"
            partial.replace(path)
            if validate:
                validate(path)
            version_file.write_text(version, encoding="utf-8")
            log.info("Downloaded %s (%d bytes, version %s)", path, path.stat().st_size, version)
            return path, version
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and 400 <= status < 500 and status not in _RETRYABLE_4XX:
                raise  # permanent: retrying a 404 only wastes time
            if attempt == retries:
                raise
            _wait(attempt, exc)
        except (requests.RequestException, InvalidDownloadError) as exc:
            _discard(partial, path)
            if attempt == retries:
                raise
            _wait(attempt, exc)
    raise AssertionError("unreachable")


def _wait(attempt: int, exc: Exception) -> None:
    wait = 2**attempt
    log.warning("Download attempt %d failed (%s); retrying in %ds", attempt, exc, wait)
    time.sleep(wait)


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
