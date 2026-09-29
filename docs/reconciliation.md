# Reconciliation evidence (NFR-03, task 1.11)

**Question:** do the warehouse's headline figures reproduce Ember's own numbers?
**Tolerance:** ±0.5% relative difference.
**Scope:** Malaysia, latest complete year (2025). Ember yearly release, `Last-Modified: Tue, 22 Sep 2026 16:24:55 GMT`.

## Check 1: SQL against Ember's raw rows (`sql/showcase/00_reconciliation.sql`), 2026-09-30

| Metric | Warehouse | Ember-derived value | Diff | Result |
|---|---|---|---|---|
| Total generation (TWh) | 210.370 | 210.370 (`Total generation` row) | 0.0000% | PASS |
| Renewable share of generation (%) | 20.411 | 20.412 (Ember's own `Renewables` aggregate) | −0.0049% | PASS |
| Carbon intensity (gCO₂e/kWh) | 605.547 | 605.547 (emissions ÷ generation, recomputed) | −0.0001% | PASS |
| Solar generation (TWh) | 6.639 | 6.639 (`Solar` row) | 0.0000% | PASS |
| Gas share of generation (%) | 33.444 | 33.443 (`Gas` share) | +0.0018% | PASS |

## Check 2: independent recomputation, 2026-09-30

A separate agent with a fresh context recomputed all five from the raw CSV using pandas only. It had no access to the SQL or the database.

| Metric | Independent value | Warehouse | Diff | Result |
|---|---|---|---|---|
| Total generation (TWh) | 210.370 | 210.370 | 0.000% | PASS |
| Renewable share (%) | 20.411 | 20.411 | 0.001% | PASS |
| Carbon intensity (gCO₂e/kWh) | 605.547 | 605.547 | 0.000% | PASS |
| Solar generation (TWh) | 6.639 | 6.639 | 0.000% | PASS |
| Gas share (%) | 33.444 | 33.444 | −0.001% | PASS |

The renewable share in check 2 was summed as (Hydro + Bioenergy + Wind + Solar + Other renewables) ÷ (those + Coal + Gas + Other fossil + Nuclear).

**Verdict:** 5/5 pass both checks. The largest difference is 0.005%, which is rounding in Ember's published 3-decimal shares.

## Re-run
```bash
.venv/Scripts/python -c "from pathlib import Path; from pipeline import db; c=db.connect().cursor(); c.execute(Path('sql/showcase/00_reconciliation.sql').read_text(encoding='utf-8')); [print(r) for r in c.fetchall()]"
```
