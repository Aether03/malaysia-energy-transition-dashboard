"""Run and step logging to meta.load_run / meta.load_step (FR-05, doc 05 §2.5).

The log uses its own autocommit connection, so entries survive when the data
transaction rolls back (doc 03 Part B).
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Self

from pipeline import config, db

log = logging.getLogger(__name__)


@dataclass
class StepRecord:
    """Mutable outcome of one step; the body of `RunLog.step()` fills it in."""

    status: str = "SUCCESS"
    rows_in: int | None = None
    rows_merged: int | None = None
    source_version: str | None = None
    message: str | None = None


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=config.ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


class RunLog:
    """Context manager for one pipeline run.

    The run ends FAILED if an exception escapes, WARN if any step reported WARN,
    otherwise SUCCESS.
    """

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.run_id: int | None = None
        self._warned = False
        self._failed = False
        self._conn = None

    def __enter__(self) -> Self:
        self._conn = db.connect(autocommit=True)
        cursor = self._conn.cursor()
        # Fail loudly rather than hang if the data transaction ever holds a lock we need.
        cursor.execute("SET LOCK_TIMEOUT 30000;")
        cursor.execute(
            "INSERT INTO meta.load_run (status, is_dry_run, git_commit) "
            "OUTPUT inserted.run_id VALUES ('RUNNING', ?, ?)",
            (int(self.dry_run), _git_commit()),
        )
        self.run_id = int(cursor.fetchone()[0])
        log.info("Run %d started%s", self.run_id, " (dry run)" if self.dry_run else "")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type or self._failed:
            status = "FAILED"
        else:
            status = "WARN" if self._warned else "SUCCESS"
        try:
            self._conn.cursor().execute(
                "UPDATE meta.load_run SET status = ?, finished_at = SYSUTCDATETIME() WHERE run_id = ?",
                (status, self.run_id),
            )
        finally:
            self._conn.close()
        log.info("Run %d finished: %s", self.run_id, status)

    def record_dq(self, results) -> None:
        """Write DQ results (pipeline.dq.DqResult) for this run."""
        cursor = self._conn.cursor()
        for r in results:
            cursor.execute(
                "INSERT INTO meta.dq_result (run_id, rule_code, status, rows_affected, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                (self.run_id, r.rule_code, r.status, r.rows_affected, r.detail),
            )

    def mark_failed(self) -> None:
        """Record a handled failure (e.g. a blocking DQ rule) without raising."""
        self._failed = True

    @contextmanager
    def step(self, stage: str, data_source_code: str | None = None) -> Iterator[StepRecord]:
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO meta.load_step (run_id, data_source_code, stage, status) "
            "OUTPUT inserted.step_id VALUES (?, ?, ?, 'RUNNING')",
            (self.run_id, data_source_code, stage),
        )
        step_id = int(cursor.fetchone()[0])
        record = StepRecord()
        try:
            yield record
        except Exception as exc:
            record.status = "FAILED"
            record.message = f"{type(exc).__name__}: {exc}"[:4000]
            raise
        finally:
            if record.status == "WARN":
                self._warned = True
            elif record.status == "FAILED":
                self._failed = True
            cursor.execute(
                "UPDATE meta.load_step SET status = ?, rows_in = ?, rows_merged = ?, source_version = ?, "
                "message = ?, finished_at = SYSUTCDATETIME() WHERE step_id = ?",
                (
                    record.status,
                    record.rows_in,
                    record.rows_merged,
                    record.source_version,
                    record.message,
                    step_id,
                ),
            )
            log.info(
                "Step %s%s: %s (rows_in=%s, merged=%s)",
                stage,
                f"[{data_source_code}]" if data_source_code else "",
                record.status,
                record.rows_in,
                record.rows_merged,
            )
