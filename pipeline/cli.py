"""Command-line entry point: `python -m pipeline <command>` (doc 02 §4)."""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys

from pipeline import config
from pipeline.db import PipelineBusyError

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
    from pipeline import db
    from pipeline.seeds import seed_all

    with db.pipeline_lock("seed"):
        log.info("Seeded: %s", seed_all())
    return 0


def _extract_and_load(run, refresh: bool) -> None:
    """Each source: download (or reuse today's file), then MERGE into raw in its own transaction."""
    from pipeline import db
    from pipeline.sources import dosm, ember, handbook, owid, singapore, thailand

    for code, source in (
        ("D1", ember),
        ("D2", owid),
        ("D3", dosm),
        ("D5", handbook),
        ("DTH", thailand),
        ("DSG", singapore),
    ):
        with run.step("EXTRACT", code) as step:
            path, version = source.download(refresh=refresh)
            step.source_version = version[:100]
        with run.step("LOAD", code) as step:
            records = source.records_from(path)
            step.rows_in = len(records)
            step.source_version = version[:100]
            conn = db.connect()
            try:
                step.rows_merged = source.load(conn, records, run.run_id, str(path.relative_to(config.ROOT)))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()


def _cmd_run(args: argparse.Namespace) -> int:
    from pipeline import db
    from pipeline.meta import RunLog

    # The lock comes first so a refused run writes no load_run row; a dry run touches no data.
    lock = contextlib.nullcontext() if args.dry_run else db.pipeline_lock("run")
    with lock, RunLog(dry_run=args.dry_run) as run:
        if args.dry_run:
            log.info("Dry run %d: no data touched", run.run_id)
            return 0
        _extract_and_load(run, refresh=args.refresh)
        if not _transform(run):
            return 1
        _forecast(run, mode="replay", grids=None)
    return 0


def _forecast(run, mode: str, grids: list[str] | None) -> None:
    """One FORECAST step per grid (M3 Q6). A failure marks the step FAILED and propagates (exit 1);
    committed data and the previous current forecast stay in place."""
    from pipeline import db
    from pipeline.forecast import run as forecast

    if mode == "replay":
        record = forecast.read_record()
        if not record:
            with run.step("FORECAST") as step:
                step.message = "no FINAL run recorded yet; nothing to replay"
            return
        targets = sorted(record) if grids is None else grids
    else:
        if grids is None:
            conn = db.connect()
            try:
                grids = forecast.forecast_grids(conn)
            finally:
                conn.close()
        targets = grids
    for grid_code in targets:
        conn = db.connect()
        try:
            source = forecast.load_grid(conn, grid_code).data_source_code
        finally:
            conn.close()
        with run.step("FORECAST", source) as step:
            if mode == "dev":
                outcome = forecast.run_dev(grid_code, run.run_id)
                step.message = f"{grid_code} DEV: {outcome.scores}"
            elif mode == "final":
                outcome = forecast.run_final(grid_code, run.run_id)
                step.message = f"{grid_code} FINAL: {outcome.scores}"
            else:
                step.message = f"{grid_code}: " + forecast.replay(grid_code, record[grid_code], run.run_id)
            step.rows_merged = None if mode == "replay" else len(outcome.results)


def _cmd_forecast(args: argparse.Namespace) -> int:
    from pipeline import db
    from pipeline.meta import RunLog

    mode = "dev" if args.dev else "final" if args.final else "replay"
    if mode == "final" and len(args.grid or []) != 1:
        # One grid per FINAL run: commit docs/forecast_final.json before the next (the gate enforces it).
        log.error("--final runs one grid at a time: pass exactly one --grid")
        return 2
    with db.pipeline_lock("forecast"), RunLog() as run:
        _forecast(run, mode=mode, grids=args.grid or None)
    return 0


def _transform(run) -> bool:
    from pipeline.transform import transform_and_check

    committed = transform_and_check(run)
    if not committed:
        run.mark_failed()
    return committed


def _cmd_transform(_: argparse.Namespace) -> int:
    from pipeline import db
    from pipeline.meta import RunLog

    with db.pipeline_lock("transform"), RunLog() as run:
        return 0 if _transform(run) else 1


def _cmd_extract_load(args: argparse.Namespace) -> int:
    from pipeline import db
    from pipeline.meta import RunLog

    # Locked here, not in _extract_and_load: `run` already holds the lock when it calls the helper.
    with db.pipeline_lock("extract-load"), RunLog() as run:
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
    db_sub.add_parser("migrate", help="apply pending migrations and changed views").set_defaults(func=_cmd_db_migrate)

    sub.add_parser("seed", help="load seed/*.csv into ref and fixed dimensions").set_defaults(func=_cmd_seed)
    extract_parser = sub.add_parser("extract-load", help="download sources and merge them into raw.*")
    extract_parser.add_argument("--refresh", action="store_true", help="re-download even if today's file exists")
    extract_parser.set_defaults(func=_cmd_extract_load)
    sub.add_parser("transform", help="rebuild dw.* from stg, gated by data-quality rules").set_defaults(
        func=_cmd_transform
    )
    forecast_parser = sub.add_parser(
        "forecast", help="day-ahead load forecast backtest: replay the recorded FINAL run (default), --dev or --final"
    )
    mode = forecast_parser.add_mutually_exclusive_group()
    mode.add_argument("--dev", action="store_true", help="development run on the protocol's 2023 months")
    mode.add_argument(
        "--final",
        action="store_true",
        help="the single locked 2024 backtest of ONE --grid (needs a committed protocol)",
    )
    forecast_parser.add_argument(
        "--grid", action="append", help="grid code (repeatable); default: every published grid"
    )
    forecast_parser.set_defaults(func=_cmd_forecast)
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
    except PipelineBusyError as exc:
        log.error("%s", exc)  # expected and self-explanatory: no traceback
        return 1
    except Exception:
        log.exception("Command failed")
        return 1
