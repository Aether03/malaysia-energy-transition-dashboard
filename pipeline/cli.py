"""Command-line entry point: `python -m pipeline <command>` (doc 02 §4)."""

from __future__ import annotations

import argparse
import logging
import sys

from pipeline import config

log = logging.getLogger("pipeline")


def _setup_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.LOG_DIR / "pipeline.log", encoding="utf-8"),
        ],
    )


def _cmd_db_migrate(_: argparse.Namespace) -> int:
    from pipeline.migrate import migrate

    applied = migrate()
    log.info("Migrations applied: %d %s", len(applied), applied)
    return 0


def _cmd_seed(_: argparse.Namespace) -> int:
    from pipeline.seeds import seed_all

    log.info("Seeded: %s", seed_all())
    return 0


def _extract_and_load(run, refresh: bool) -> None:
    """Ember D1: download (or reuse today's file), then MERGE into raw in one transaction."""
    from pipeline import db
    from pipeline.sources import ember

    with run.step("EXTRACT", "D1") as step:
        path, version = ember.download(refresh=refresh)
        step.source_version = version[:100]
    with run.step("LOAD", "D1") as step:
        records = ember.to_raw_records(ember.filter_asean(ember.read_csv(path)))
        step.rows_in = len(records)
        step.source_version = version[:100]
        conn = db.connect()
        try:
            step.rows_merged = ember.load(conn, records, run.run_id, str(path.relative_to(config.ROOT)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _cmd_run(args: argparse.Namespace) -> int:
    from pipeline.meta import RunLog

    with RunLog(dry_run=args.dry_run) as run:
        if args.dry_run:
            log.info("Dry run %d: no data touched", run.run_id)
            return 0
        _extract_and_load(run, refresh=args.refresh)
    return 0


def _cmd_extract_load(args: argparse.Namespace) -> int:
    from pipeline.meta import RunLog

    with RunLog() as run:
        _extract_and_load(run, refresh=getattr(args, "refresh", False))
    return 0


def _not_yet(step: str):
    def handler(_: argparse.Namespace) -> int:
        log.error("Not implemented yet (M1 %s)", step)
        return 2

    return handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pipeline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    db_parser = sub.add_parser("db", help="database administration")
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("migrate", help="apply pending migrations and changed views").set_defaults(
        func=_cmd_db_migrate
    )

    sub.add_parser("seed", help="load seed/*.csv into ref and fixed dimensions").set_defaults(func=_cmd_seed)
    extract_parser = sub.add_parser("extract-load", help="download sources and merge them into raw.*")
    extract_parser.add_argument("--refresh", action="store_true", help="re-download even if today's file exists")
    extract_parser.set_defaults(func=_cmd_extract_load)
    sub.add_parser("transform", help="rebuild dw.* from stg").set_defaults(func=_not_yet("step 6"))
    sub.add_parser("check", help="run data-quality rules").set_defaults(func=_not_yet("step 7"))
    run_parser = sub.add_parser("run", help="extract, load, transform and check")
    run_parser.add_argument("--dry-run", action="store_true", help="log a run without touching data")
    run_parser.add_argument("--refresh", action="store_true", help="re-download even if today's file exists")
    run_parser.set_defaults(func=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception:
        log.exception("Command failed")
        return 1
