"""Tests that need the local SQL Server (database EnergyDW, V001-V017 applied).

They skip cleanly when the server is unreachable (CI has no database). Anything that changes
data runs in a transaction that is rolled back, so nothing persists.
"""

import subprocess
import sys

import mssql_python
import pytest

from pipeline import config, db


def _db_reachable() -> bool:
    try:
        mssql_python.connect(db.db_settings().connection_string(), timeout=3).close()
    except mssql_python.Error:
        return False
    return True


pytestmark = pytest.mark.skipif(not _db_reachable(), reason="SQL Server is not reachable")


@pytest.fixture
def conn():
    """A transactional connection (autocommit off); always rolled back."""
    connection = db.connect()
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def _denied(cursor, sql):
    with pytest.raises(mssql_python.Error, match="permission was denied"):
        cursor.execute(sql)


# --- the run lock ------------------------------------------------------------------------------


def test_second_holder_fails_fast_with_a_clear_message():
    with (
        db.pipeline_lock("first"),
        pytest.raises(db.PipelineBusyError, match="Another pipeline run or migration is in progress"),
        db.pipeline_lock("second"),
    ):
        pytest.fail("the second holder must not get in")


@pytest.fixture
def observer():
    """A second session, checked out for the whole test so the pool can't hand the lock holder's
    session back: a session can re-take its own lock, so only another session sees a missed release."""
    connection = db.connect(autocommit=True)
    try:
        yield connection
    finally:
        connection.close()


def _lock_is_free(observer) -> bool:
    cursor = observer.cursor()
    cursor.execute("SELECT APPLOCK_TEST('public', 'energy_dashboard_pipeline', 'Exclusive', 'Session')")
    return cursor.fetchone()[0] == 1


def test_lock_is_free_again_after_the_holder_exits(observer):
    with db.pipeline_lock("first"):
        assert not _lock_is_free(observer)
    assert _lock_is_free(observer)


def test_lock_is_released_when_the_body_raises(observer):
    with pytest.raises(RuntimeError, match="boom"), db.pipeline_lock("first"):
        assert not _lock_is_free(observer)
        raise RuntimeError("boom")
    assert _lock_is_free(observer)


@pytest.mark.parametrize("args", [["db", "migrate"], ["transform"]])
def test_cli_command_refuses_while_the_lock_is_held(args):
    with db.pipeline_lock("held by the test"):
        done = subprocess.run(
            [sys.executable, "-m", "pipeline", *args],
            cwd=config.ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    assert done.returncode == 1
    assert "Another pipeline run or migration is in progress" in done.stdout
    assert "Traceback" not in done.stdout + done.stderr


# --- roles (users without logins, inside a rolled-back transaction) ------------------------------


def _user_in_role(cursor, user, role):
    cursor.execute(f"CREATE USER {user} WITHOUT LOGIN")
    cursor.execute(f"ALTER ROLE {role} ADD MEMBER {user}")


def test_report_reader_can_select_mart_but_nothing_else(conn):
    cursor = conn.cursor()
    _user_in_role(cursor, "test_reader", "role_report_reader")
    cursor.execute("EXECUTE AS USER = 'test_reader'")
    try:
        cursor.execute("SELECT COUNT(*) FROM mart.country_annual")
        assert cursor.fetchone()[0] > 0
        cursor.execute("SELECT COUNT(*) FROM mart.dim_year")
        assert cursor.fetchone()[0] > 0
        _denied(cursor, "INSERT INTO mart.dim_year (year, is_complete, decade) VALUES (1900, 0, 1900)")
        _denied(cursor, "UPDATE mart.dim_year SET decade = 0")
        _denied(cursor, "DELETE FROM mart.dim_year")
        _denied(cursor, "SELECT COUNT(*) FROM dw.fact_country_annual")  # the reader sees mart only
        _denied(cursor, "INSERT INTO dw.dim_year (year, is_complete, decade) VALUES (1900, 0, 1900)")
        _denied(cursor, "UPDATE dw.dim_year SET decade = 0")
        _denied(cursor, "DELETE FROM dw.dim_year")
    finally:
        cursor.execute("REVERT")


def test_pipeline_role_cannot_write_the_migration_ledger(conn):
    cursor = conn.cursor()
    _user_in_role(cursor, "test_pipeline", "role_pipeline")
    cursor.execute("EXECUTE AS USER = 'test_pipeline'")
    try:
        cursor.execute("SELECT COUNT(*) FROM meta.schema_version")
        assert cursor.fetchone()[0] > 0
        _denied(
            cursor,
            "INSERT INTO meta.schema_version (script_name, kind, version, checksum) "
            "VALUES ('V999__forged.sql', 'V', 999, REPLICATE('0', 64))",
        )
        _denied(cursor, "UPDATE meta.schema_version SET checksum = REPLICATE('0', 64)")
        _denied(cursor, "DELETE FROM meta.schema_version")
        # the DENY is targeted: the role still writes the layers it owns
        cursor.execute(
            "SELECT HAS_PERMS_BY_NAME('dw.dim_year', 'OBJECT', 'INSERT'), "
            "HAS_PERMS_BY_NAME('meta.load_run', 'OBJECT', 'INSERT'), "
            "HAS_PERMS_BY_NAME('meta.schema_version', 'OBJECT', 'SELECT')"
        )
        assert tuple(cursor.fetchone()) == (1, 1, 1)
    finally:
        cursor.execute("REVERT")


# --- transform LOW items ---------------------------------------------------------------------------


def test_malaysia_time_zone_name_used_by_dim_year_exists():
    connection = db.connect(autocommit=True)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT current_utc_offset FROM sys.time_zone_info WHERE name = 'Singapore Standard Time'")
        assert cursor.fetchone()[0] == "+08:00"
    finally:
        connection.close()


def test_capacity_without_generation_is_kept_with_null_generation(conn):
    with db.pipeline_lock("test"):  # it rebuilds a fact table: never alongside a real run
        _capacity_without_generation_is_kept(conn)


def _capacity_without_generation_is_kept(conn):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE raw.ember_yearly SET generation_twh = NULL "
        "WHERE iso3 = 'MYS' AND year = 2024 AND electricity_source = 'Bioenergy' AND capacity_gw > 0"
    )
    assert cursor.rowcount == 1
    db.run_script(cursor, (config.TRANSFORM_DIR / "020_fact_generation_annual.sql").read_text(encoding="utf-8-sig"))
    cursor.execute(
        "SELECT f.generation_twh, f.capacity_gw FROM dw.fact_generation_annual AS f "
        "JOIN dw.dim_country AS c ON c.country_key = f.country_key AND c.iso3 = 'MYS' "
        "JOIN dw.dim_source AS d ON d.source_key = f.source_key AND d.source_code = 'BIOENERGY' "
        "WHERE f.year = 2024"
    )
    generation, capacity = cursor.fetchone()
    assert generation is None
    assert capacity > 0
