"""SQL Server access: connections and multi-batch script execution."""

from __future__ import annotations

import contextlib
import re
from collections.abc import Iterator

import mssql_python

from pipeline.config import db_settings

# A batch separator is GO alone on its line (optionally with a trailing -- comment),
# matching sqlcmd/SSMS behaviour. GO inside a string or longer identifier is not a separator.
_GO_LINE = re.compile(r"\s*go\s*(?:--.*)?", re.IGNORECASE)


def split_batches(script: str) -> list[str]:
    """Split a T-SQL script into batches on GO lines, dropping empty batches."""
    batches: list[str] = []
    current: list[str] = []
    for line in script.splitlines():
        if _GO_LINE.fullmatch(line):
            batches.append("\n".join(current).strip())
            current = []
        else:
            current.append(line)
    batches.append("\n".join(current).strip())
    return [batch for batch in batches if batch]


def connect(database: str | None = None, autocommit: bool = False):
    """Open a Windows-authenticated connection to the configured server."""
    conn = mssql_python.connect(db_settings().connection_string(database))
    conn.autocommit = autocommit
    return conn


# One lock for everything that rewrites the warehouse (migrate, seed, extract-load, transform, forecast,
# run): a migration changing a table mid-transform is as bad as two transforms. applock names are per database.
_LOCK_RESOURCE = "energy_dashboard_pipeline"


class PipelineBusyError(RuntimeError):
    """Another migration or pipeline run holds the lock."""


@contextlib.contextmanager
def pipeline_lock(command: str) -> Iterator[None]:
    """Hold the pipeline's exclusive applock for the body; fail fast if someone else has it.

    Session-owned on a dedicated autocommit connection that touches no table: the work itself
    runs on other connections and commits on its own, so there is no single transaction for a
    transaction-owned lock to live in. SQL Server frees a session lock when the connection
    drops, so a crashed or killed run can never leave it stuck.
    """
    conn = connect(autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DECLARE @r INT; "
            "EXEC @r = sys.sp_getapplock @Resource = ?, @LockMode = 'Exclusive', "
            "@LockOwner = 'Session', @LockTimeout = 0; "
            "SELECT @r;",
            (_LOCK_RESOURCE,),
        )
        if cursor.fetchone()[0] < 0:  # -1 timeout (held elsewhere), -2 cancelled, -3 deadlock, -999 error
            raise PipelineBusyError(
                f"Another pipeline run or migration is in progress (lock '{_LOCK_RESOURCE}' is held); "
                f"`{command}` was not started. Wait for it to finish and run it again."
            )
        try:
            yield
        finally:
            # Explicit: closing a pooled connection keeps the session (and its lock) alive. If the
            # connection is already broken, the server has dropped the session and the lock with it.
            with contextlib.suppress(mssql_python.Error):
                cursor.execute("EXEC sys.sp_releaseapplock @Resource = ?, @LockOwner = 'Session';", (_LOCK_RESOURCE,))
    finally:
        conn.close()


def run_script(cursor, script: str) -> int:
    """Execute every batch of a script on an open cursor; returns the batch count.

    XACT_ABORT makes any runtime error abort the transaction, and draining every
    result set surfaces errors raised by later statements in a batch.
    """
    batches = split_batches(script)
    cursor.execute("SET XACT_ABORT ON;")
    for batch in batches:
        cursor.execute(batch)
        while cursor.nextset():
            pass
    return len(batches)
