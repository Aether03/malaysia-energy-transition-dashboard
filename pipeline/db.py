"""SQL Server access: connections and multi-batch script execution."""

from __future__ import annotations

import re

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


def run_script(cursor, script: str) -> int:
    """Execute every batch of a script on an open cursor; returns the batch count."""
    batches = split_batches(script)
    for batch in batches:
        cursor.execute(batch)
    return len(batches)
