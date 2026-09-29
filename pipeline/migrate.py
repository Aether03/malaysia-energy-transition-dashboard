"""Schema migrations (doc 05 §5).

- `sql/migrations/V###__name.sql` run once, in numeric order. Editing one after it has
  been applied is an error (its checksum no longer matches).
- `sql/views/R__name.sql` are repeatable: re-applied whenever their checksum changes.

Each script runs in its own transaction and is recorded in `meta.schema_version`.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pipeline import config, db

log = logging.getLogger(__name__)

_VERSIONED = re.compile(r"V(\d{3})__\w+\.sql")
_REPEATABLE = re.compile(r"R__\w+\.sql")

_BOOTSTRAP = """
IF SCHEMA_ID('meta') IS NULL EXEC('CREATE SCHEMA meta');
GO
IF OBJECT_ID('meta.schema_version') IS NULL
CREATE TABLE meta.schema_version (
    script_name NVARCHAR(200) NOT NULL CONSTRAINT pk_schema_version PRIMARY KEY,
    kind        CHAR(1)       NOT NULL CONSTRAINT ck_schema_version_kind CHECK (kind IN ('V', 'R')),
    version     INT           NULL,
    checksum    CHAR(64)      NOT NULL,
    applied_at  DATETIME2(0)  NOT NULL CONSTRAINT df_schema_version_applied DEFAULT SYSUTCDATETIME()
);
"""


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Script:
    path: Path
    kind: str  # 'V' or 'R'
    version: int | None

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8-sig")  # tolerate a BOM from Windows editors

    @property
    def checksum(self) -> str:
        # Normalise line endings so Git's autocrlf can't change the checksum.
        normalised = self.text.replace("\r\n", "\n").encode("utf-8")
        return hashlib.sha256(normalised).hexdigest()


def discover(migrations_dir: Path, views_dir: Path) -> list[Script]:
    """Versioned scripts in numeric order, then repeatable scripts in name order."""
    versioned = []
    for path in migrations_dir.glob("*.sql"):
        match = _VERSIONED.fullmatch(path.name)
        if not match:
            raise MigrationError(f"Unexpected file in migrations: {path.name}")
        versioned.append(Script(path, "V", int(match.group(1))))
    versioned.sort(key=lambda s: s.version)
    numbers = [s.version for s in versioned]
    if len(numbers) != len(set(numbers)):
        raise MigrationError(f"Duplicate migration versions: {numbers}")

    repeatable = sorted(
        (Script(p, "R", None) for p in views_dir.glob("*.sql") if _REPEATABLE.fullmatch(p.name)),
        key=lambda s: s.name,
    )
    return versioned + repeatable


def _ensure_read_committed_snapshot() -> None:
    """Readers (Power BI, mart queries) never wait on a rebuild (transform review, finding 4).

    ALTER DATABASE can't run inside a user transaction, so this uses its own autocommit connection.
    """
    conn = db.connect(autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT is_read_committed_snapshot_on FROM sys.databases WHERE name = DB_NAME()")
        if not cursor.fetchone()[0]:
            log.info("Enabling READ_COMMITTED_SNAPSHOT")
            cursor.execute("ALTER DATABASE CURRENT SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE")
    finally:
        conn.close()


def migrate() -> list[str]:
    """Apply pending scripts; returns the names applied."""
    _ensure_read_committed_snapshot()
    applied: list[str] = []
    conn = db.connect()
    try:
        cursor = conn.cursor()
        db.run_script(cursor, _BOOTSTRAP)
        conn.commit()

        cursor.execute("SELECT script_name, checksum FROM meta.schema_version")
        recorded = {name: checksum for name, checksum in cursor.fetchall()}

        for script in discover(config.MIGRATIONS_DIR, config.VIEWS_DIR):
            previous = recorded.get(script.name)
            if previous == script.checksum:
                continue
            if previous is not None and script.kind == "V":
                raise MigrationError(
                    f"{script.name} was edited after being applied; add a new migration instead"
                )
            log.info("Applying %s", script.name)
            try:
                db.run_script(cursor, script.text)
                cursor.execute(
                    "MERGE meta.schema_version AS t "
                    "USING (SELECT ? AS script_name, ? AS kind, ? AS version, ? AS checksum) AS s "
                    "ON t.script_name = s.script_name "
                    "WHEN MATCHED THEN UPDATE SET checksum = s.checksum, applied_at = SYSUTCDATETIME() "
                    "WHEN NOT MATCHED THEN INSERT (script_name, kind, version, checksum) "
                    "VALUES (s.script_name, s.kind, s.version, s.checksum);",
                    (script.name, script.kind, script.version, script.checksum),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            applied.append(script.name)
    finally:
        conn.close()
    return applied
