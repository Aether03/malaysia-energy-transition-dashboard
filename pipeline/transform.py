"""Rebuild dw from stg, gated by data-quality rules (doc 03 Part B).

All `sql/transform/*.sql` scripts (dim_year first, then the facts) run in one
transaction on one connection, and the DQ rules are evaluated on that same connection.
A BLOCKING failure rolls the whole rebuild back, so the previous dw stays intact;
otherwise it commits. The run log writes on its own connection and touches no table
this transaction locks (transform review, finding 2).
"""

from __future__ import annotations

import logging

from pipeline import config, db, dq

log = logging.getLogger(__name__)


def transform_and_check(run) -> bool:
    """Returns True if the rebuild was committed, False if DQ rolled it back."""
    scripts = sorted(config.TRANSFORM_DIR.glob("*.sql"))
    conn = db.connect()
    try:
        cursor = conn.cursor()
        with run.step("TRANSFORM") as step:
            for path in scripts:
                db.run_script(cursor, path.read_text(encoding="utf-8-sig"))
            cursor.execute(
                "SELECT (SELECT COUNT(*) FROM dw.fact_generation_annual), "
                "(SELECT COUNT(*) FROM dw.fact_country_annual)"
            )
            gen_rows, country_rows = cursor.fetchone()
            step.rows_merged = int(gen_rows) + int(country_rows)
            step.message = f"fact_generation_annual={gen_rows}, fact_country_annual={country_rows} (uncommitted)"

        with run.step("CHECK") as step:
            results = dq.evaluate(cursor)
            run.record_dq(results)
            failed = [r.rule_code for r in results if r.status == "FAIL"]
            warned = [r.rule_code for r in results if r.status == "WARN"]
            step.rows_in = len(results)
            if failed:
                conn.rollback()
                step.status = "FAILED"
                step.message = f"Blocking DQ failures {failed}; dw rolled back to the previous good state"
                log.error(step.message)
                return False
            conn.commit()
            if warned:
                step.status = "WARN"
            step.message = f"{len(results)} rules: committed" + (f"; warnings {warned}" if warned else "")
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
