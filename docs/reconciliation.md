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

## Known cross-check warnings (M2, 2026-09-30)
These WARN rules fire by design. Each gap is a real difference between sources or a known source limitation, not a pipeline fault. BLOCKING rules all pass.

| Rule | Rows | What it shows | Handling |
|---|---|---|---|
| `OWID_GEN_WITHIN_5PCT` | MY 2023, 2024 | OWID's Malaysia generation is 7.4% and 6.2% below Ember's (187.8 vs 202.8 TWh; 198.1 vs 211.2). OWID's energy dataset uses a different upstream vintage; the gap narrows to 4.4% for 2025 | Ember stays the single generation basis. OWID supplies population only |
| `DOSM_SUPPLY_WITHIN_10PCT` | MY 2022, 2023 | Ember generation is above DOSM's total supply by a gap that grows over time: 4.3% (2018), 6.0%, 6.8%, 7.0%, 11.4% (2022), 14.1% (2023). DOSM's series ends in Jun 2024. The cause is **not established**; plausible contributors are self-generation, co-generation and rooftop solar outside DOSM's supply statistics | Cross-check only (S1); no report page uses DOSM. The growing gap is stated as a caveat, not a finding |
| `CF_AT_MOST_1` | 117 source-years | Ember's capacity is too small for the generation it reports. Examples: geothermal ("Other renewables") at 0–0.01 GW for the Philippines and Indonesia beside 10–15 TWh; Singapore waste-to-energy; Indonesian captive coal and bioenergy. Malaysia: only Other fossil 2024 (CF 1.10) | `030` treats implausible **renewable** capacity as unreported, so the RE capacity share is NULL for PHL, IDN, SGP and 4 VNM years instead of being understated. Capacity-factor visuals blank values above 1 |
| `STALE_COUNTRY_YEARS` | Brunei, Laos, Myanmar | Ember's data for these three ends in 2024 | The ASEAN ranking uses the latest year all selected countries share (doc 03 P5) |
