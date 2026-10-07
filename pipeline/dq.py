"""Data-quality rules (FR-03, doc 05 §2.5).

Each active rule in meta.dq_rule holds a query that returns the offending rows; zero
rows is a pass. Rules are evaluated on the *data* connection, so they see the
uncommitted rebuild (database review, finding 2); results are written by the run log.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DqResult:
    rule_code: str
    severity: str
    status: str  # PASS / WARN / FAIL
    rows_affected: int
    detail: str | None


def evaluate(cursor) -> list[DqResult]:
    cursor.execute("SELECT rule_code, severity, check_sql FROM meta.dq_rule WHERE is_active = 1 ORDER BY rule_code")
    rules = cursor.fetchall()
    # Fail closed: no blocking rules must never read as "all rules passed" (transform review, finding 3).
    if not any(severity == "BLOCKING" for _, severity, _ in rules):
        raise RuntimeError("No active BLOCKING data-quality rules found; run `python -m pipeline seed`")
    results = []
    for rule_code, severity, check_sql in rules:
        cursor.execute(check_sql)
        rows = cursor.fetchall()
        if not rows:
            status, detail = "PASS", None
        else:
            status = "FAIL" if severity == "BLOCKING" else "WARN"
            detail = "; ".join(str(tuple(row)) for row in rows[:5])
            if len(rows) > 5:
                detail += f"; … {len(rows) - 5} more"
        results.append(DqResult(rule_code, severity, status, len(rows), detail))
    return results


def has_blocking_failure(results: list[DqResult]) -> bool:
    return any(r.status == "FAIL" for r in results)
