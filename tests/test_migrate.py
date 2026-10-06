"""Migration runner pure functions (M5 hardening): out-of-order versions and the run lock. No database."""

import pytest

from pipeline import db, migrate


def _scripts(tmp_path, *names):
    migrations = tmp_path / "migrations"
    views = tmp_path / "views"
    migrations.mkdir()
    views.mkdir()
    for name in names:
        target = views if name.startswith("R__") else migrations
        (target / name).write_text("SELECT 1;", encoding="utf-8")
    return migrate.discover(migrations, views)


def test_pending_script_below_the_highest_applied_version_is_refused(tmp_path):
    scripts = _scripts(tmp_path, "V001__a.sql", "V002__b.sql", "V003__c.sql")
    recorded = {"V001__a.sql": 1, "V003__c.sql": 3}  # V002 was never applied
    with pytest.raises(migrate.MigrationError, match=r"V002__b\.sql.*V003|V003.*V002__b\.sql"):
        migrate.check_version_order(scripts, recorded)


def test_every_out_of_order_script_is_named(tmp_path):
    scripts = _scripts(tmp_path, "V001__a.sql", "V002__b.sql", "V003__c.sql", "V004__d.sql")
    recorded = {"V004__d.sql": 4}
    with pytest.raises(migrate.MigrationError) as exc_info:
        migrate.check_version_order(scripts, recorded)
    message = str(exc_info.value)
    assert all(name in message for name in ("V001__a.sql", "V002__b.sql", "V003__c.sql"))


def test_pending_scripts_above_the_highest_applied_version_are_fine(tmp_path):
    scripts = _scripts(tmp_path, "V001__a.sql", "V002__b.sql", "V003__c.sql")
    migrate.check_version_order(scripts, {"V001__a.sql": 1})


def test_first_run_with_nothing_applied_is_fine(tmp_path):
    scripts = _scripts(tmp_path, "V001__a.sql", "V002__b.sql")
    migrate.check_version_order(scripts, {})


def test_repeatable_scripts_never_count_as_out_of_order(tmp_path):
    scripts = _scripts(tmp_path, "V001__a.sql", "R__view.sql")
    migrate.check_version_order(scripts, {"V001__a.sql": 1})  # R__ has no version and is re-applied on change


def test_an_applied_repeatable_does_not_raise_the_highest_version(tmp_path):
    scripts = _scripts(tmp_path, "V001__a.sql", "V002__b.sql", "R__view.sql")
    migrate.check_version_order(scripts, {"V001__a.sql": 1, "R__view.sql": None})


def test_migrate_takes_the_lock_before_touching_any_schema(monkeypatch):
    def refuse(command):
        raise db.PipelineBusyError(command)

    def no_connection(*args, **kwargs):
        raise AssertionError("migrate must not open a data connection while the lock is held elsewhere")

    monkeypatch.setattr(migrate, "_ensure_read_committed_snapshot", lambda: None)
    monkeypatch.setattr(db, "pipeline_lock", refuse)
    monkeypatch.setattr(db, "connect", no_connection)
    with pytest.raises(db.PipelineBusyError):
        migrate.migrate()
