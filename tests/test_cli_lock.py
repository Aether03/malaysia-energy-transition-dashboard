"""The CLI refuses a second `run` / `transform` while one is in progress (M5 hardening). No database."""

import logging

import pytest

from pipeline import cli, db, meta


@pytest.fixture(autouse=True)
def _quiet_cli(monkeypatch):
    monkeypatch.setattr(cli, "_setup_logging", lambda: None)  # don't open the real logs/pipeline.log


@pytest.fixture
def busy(monkeypatch):
    """Every attempt to take the lock reports another run in progress; a RunLog must never start."""

    def refuse(command):
        raise db.PipelineBusyError(f"another run holds the lock ({command})")

    class NoRunLog:
        def __init__(self, *args, **kwargs):
            raise AssertionError("a refused command must not write a load_run row")

    monkeypatch.setattr(db, "pipeline_lock", refuse)
    monkeypatch.setattr(meta, "RunLog", NoRunLog)


@pytest.mark.parametrize("argv", [["transform"], ["run"], ["run", "--refresh"]])
def test_busy_lock_fails_fast_with_a_clear_message_and_no_traceback(busy, caplog, argv):
    with caplog.at_level(logging.INFO, logger="pipeline"):
        assert cli.main(argv) == 1
    assert "another run holds the lock" in caplog.text
    assert "Traceback" not in caplog.text
    assert not any(record.exc_info for record in caplog.records)


def test_dry_run_does_not_need_the_lock(monkeypatch):
    class FakeRun:
        run_id = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

    def must_not_lock(command):
        raise AssertionError("a dry run touches no data and must not take the lock")

    monkeypatch.setattr(db, "pipeline_lock", must_not_lock)
    monkeypatch.setattr(meta, "RunLog", lambda dry_run=False: FakeRun())
    assert cli.main(["run", "--dry-run"]) == 0
