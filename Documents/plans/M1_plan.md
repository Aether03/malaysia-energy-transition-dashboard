# Plan: M1 — Vertical slice (Ember → SQL Server → thin P1 Overview)

**Source:** [06 Implementation Plan](../06_Implementation_Plan.md) Phase 1 (tasks 1.1–1.11) · **Complexity:** Medium–Large (about 2 sessions) · **Status:** awaiting approval

## Summary
Build the thinnest end-to-end path that proves the architecture.
1. One command downloads Ember's yearly CSV.
2. It MERGEs the ASEAN rows into `raw`, rebuilds the annual star schema in one transaction guarded by BLOCKING data-quality rules, and logs everything to `meta`.
3. Power BI (a PBIP project) shows four Malaysia KPIs, the generation-mix trend and NETR progress.
4. Five headline figures are reconciled against Ember within ±0.5%.

## Requirements restated
- FR-01/02: `python -m pipeline run` downloads Ember and loads idempotently (the second run changes nothing).
- FR-03: three BLOCKING DQ rules. On failure, `dw` rolls back to the last good state and the run exits 1.
- FR-04: `raw → stg → dw → mart` layers exist as SQL schemas; `ref` and `meta` are seeded and logged.
- FR-05: every run and step is logged in `meta.load_run` / `meta.load_step` with row counts and a source version.
- FR-06 (partial): P1 shows total generation, RE share, fossil share and carbon intensity for Malaysia's latest complete year, with YoY.
  - **Demand per capita needs population (OWID, M2)**, so its card is added in M2.
- NFR-03: 5 figures within ±0.5% of Ember (task 1.11).

## Facts verified before planning (2026-09-30, from the Ember file on disk)
- The global file has 104,203 rows. The ASEAN extract (10 members plus the `ASEAN` aggregate) has **5,070 rows**, with no duplicate `(Area, Year, Electricity source)` keys.
- Ember's area names include "Viet Nam", "The Philippines" and "Lao PDR", so **`dim_country` joins on `ISO 3 code`**, not on names.
- Malaysia's non-aggregate sources are Bioenergy, Coal, Gas, Hydro, Nuclear (0), Other fossil, Solar, Wind, **and "Net imports", which is flagged non-aggregate**. It must be excluded from the mix explicitly (`ref.source_map.include_in_mix = 0`).
- Malaysia covers 1985–2025, with capacity 2000–2025. Brunei, Laos and Myanmar end at 2024; Malaysia, Thailand and Vietnam start at 1985, the rest at 2000.
- Malaysia's share sums are 99.49% (2024) and 99.44% (2025) **only if Net imports is wrongly included**: Malaysia is a net exporter, so that share is negative. Excluding it, the mix sums to **100.0%** (checked for Malaysia, Singapore and ASEAN, 2024). "Net imports" and "Demand" carry inconsistent `Is aggregated source` flags, so **map by label, never by that flag**. "Other renewables" (Philippine geothermal) exists → `WIND_OTHER_RE`.
- Malaysia 2025: total generation 210.37 TWh, emissions intensity 605.547 gCO₂e/kWh. These are reconciliation candidates.

## Patterns to mirror
There's no existing code in this repo (new project), so no in-repo pattern exists. The patterns come from the approved docs and skills:
| Category | Source | Pattern |
|---|---|---|
| Layering and naming | doc 05 §1–2 | `raw`/`stg`/`dw`/`mart`/`ref`/`meta` schemas; snake_case; `dim_*`/`fact_*`; explicit column lists in views |
| Migrations | doc 05 §5 | Numbered `V###__name.sql` (run once, checksummed) plus repeatable `R__name.sql` for views (re-applied when their checksum changes) |
| Errors | doc 03 Part B | Retry the download ×3 with backoff; a schema mismatch stops the run; a blocking DQ failure rolls back `dw` and exits 1; `meta` rows are written on a **separate connection**, so the log survives rollbacks |
| Logging | doc 02 §8 | Python `logging` to console and `logs/pipeline.log`, plus `meta.load_step` rows |
| Tests | `ecc:python-testing` | `pytest`, small fixture CSVs in `tests/fixtures/`, no database needed for unit tests |

## Files to create
| File | Why |
|---|---|
| `pipeline/__init__.py`, `pipeline/__main__.py`, `pipeline/cli.py` | `python -m pipeline {db migrate, seed, extract, load, transform, check, run [--dry-run]}` |
| `pipeline/config.py` | `.env` (server, database), repo paths, source URLs |
| `pipeline/db.py` | `connect()` (mssql-python, Windows auth, `TrustServerCertificate=yes` for the local dev certificate), `run_script()` that splits on `GO` |
| `pipeline/migrate.py` | Bootstraps `meta.schema_version`; applies `V###` in order and `R__` when their checksums change; SHA-256 checksums |
| `pipeline/meta.py` | `start_run`, `log_step`, `finish_run` on their own autocommit connection |
| `pipeline/seeds.py` | `seed/*.csv` → `ref.*` and fixed dimensions via MERGE |
| `pipeline/sources/ember.py` | Download (streamed, retry ×3), save to `data/raw/ember/<date>/`, filter to ASEAN, validate the header against the expected 24 columns, bulk insert into a `#staging` table, MERGE into `raw.ember_yearly` |
| `pipeline/transform.py` | Runs `sql/transform/*.sql` in one transaction; calls DQ before COMMIT |
| `pipeline/dq.py` | Runs each `meta.dq_rule.check_sql`; writes `meta.dq_result` (separate connection); returns whether a blocking rule failed |
| `sql/migrations/V001__schemas_and_roles.sql` | 6 schemas; `role_pipeline`, `role_report_reader` |
| `sql/migrations/V002__meta.sql` | `load_run`, `load_step`, `dq_rule`, `dq_result` |
| `sql/migrations/V003__ref_and_dims.sql` | `ref.source_map`, `ref.netr_target`, `ref.kpi`; `dw.dim_country`, `dim_source`, `dim_year`, `dim_data_source` |
| `sql/migrations/V004__ember_raw_and_annual_facts.sql` | `raw.ember_yearly`, `dw.fact_generation_annual`, `dw.fact_country_annual` |
| `sql/migrations/V005__grants.sql` | Grants: pipeline on all schemas; reader `SELECT` on `mart` only |
| `sql/views/R__stg_ember.sql` | Typed, mapped view over raw (source_map join, ISO3 → country) |
| `sql/views/R__mart_m1.sql` | `mart.dim_country`, `dim_source`, `dim_year`, `kpi`, `netr_target`, `generation_annual`, `country_annual`, `run_latest`, `dq_latest` |
| `sql/transform/010_dim_year.sql`, `020_fact_generation_annual.sql`, `030_fact_country_annual.sql` | Truncate-and-reload inside the caller's transaction |
| `sql/showcase/00_reconciliation.sql` | The 5 reconciliation figures (task 1.11) |
| `seed/dim_source.csv`, `dim_country.csv`, `source_map.csv`, `netr_target.csv`, `kpi.csv`, `data_source.csv`, `dq_rule.csv` | Seeds (doc 04 palette hexes exactly; NETR 31/40/70) |
| `tests/test_ember.py`, `tests/test_db_script_split.py`, `tests/fixtures/ember_sample.csv` | Unit tests (no database) |
| `report/` PBIP project, `report/theme/energy-transition.json` | Tasks 1.9–1.10 |
| `docs/reconciliation.md` | Evidence for NFR-03 |

## Tasks (in build order)
Model tiers per doc 06 §4: **D** Opus 5.5 (this session) · **S** Sonnet 5.5 subagent · **F** Haiku 4.5 subagent. GUI = main session.

| Step | Doc 06 task | What | Model | Verify |
|---|---|---|---|---|
| 1 | 1.3a | `config`, `db` (with GO splitting), `cli` skeleton, **migration runner**; unit test for the GO splitter | D | `pytest tests/test_db_script_split.py`; `python -m pipeline db migrate` on an empty DB creates `meta.schema_version` |
| 2 | 1.1 | V001–V005 migrations | D | `db migrate` twice: second run applies 0. **Review: `ecc:database-reviewer`** (its advice is Postgres-leaning, so check the T-SQL points) |
| 3 | 1.2 + 1.7 | Seeds (7 CSVs + `seeds.py`) and the `R__` stg/mart views | **S (one batched subagent brief)** | `python -m pipeline seed` → row counts; `dim_source.color_hex` equals doc 04 §3.2; the views compile; `grep -c "SELECT \*" sql/views` = 0 |
| 4 | 1.3b | `meta.py`, `run --dry-run` | D | A dry run writes 1 `load_run` row with status SUCCESS |
| 5 | 1.4 (+1.8) | Ember extractor/loader, test-first: the fixture test (header check, ASEAN filter, Net imports kept in raw) **before** the code | D (tests F) | `pytest tests/test_ember.py`; run twice → `raw.ember_yearly` = 5,070 rows both times, and `rows_merged` = 0 changes on the second run |
| 6 | 1.5 | Transforms: `dim_year` (`is_complete` = year < current year, *and* present for Malaysia), `fact_generation_annual` (7 display slots via `source_map`; Nuclear folded, Net imports excluded), `fact_country_annual` (total, demand, net imports, intensity, RE shares; population and per-capita NULL until M2) | D | Row counts; Malaysia 2025 total = 210.37 TWh; **review: `ecc:database-reviewer`** |
| 7 | 1.6 | DQ framework + 3 BLOCKING rules; transaction with DQ before COMMIT | D | Inject `generation_twh = -1` into stg → `run` exits 1, `dw` row counts unchanged, `meta.dq_result` shows FAIL; revert → PASS |
| 8 | 1.9 | PBIP: **you** open Power BI Desktop → File → Save as → *Power BI project* (`report/EnergyTransition.pbip`), so the skeleton is valid. Then Claude writes the TMDL tables (Sql.Database queries against `mart.*`), relationships (doc 05 §3), the `_Measures` table and the theme JSON | D + GUI | Desktop opens the project without errors; Refresh succeeds; the model view matches doc 05 |
| 9 | 1.10 | P1 thin page: 4 KPI cards (+ YoY with polarity), mix stacked area 2000→latest, NETR progress (RE capacity share vs 31/40/70) | S + GUI | Screenshot vs the doc 04 wireframe; picking a year with no data shows the "No data" measure |
| 10 | 1.11 | Reconciliation SQL + `docs/reconciliation.md`: 2025 total TWh, RE share of generation, carbon intensity, solar TWh, gas share | D | All within ±0.5% of Ember's own figures; **review: a fresh-context agent recomputes the 5 figures from the raw CSV independently** |
| 11 | — | Commit per step; push at milestone end; update the doc 06 M1 row and the index | — | `git log`; the index says M1 done |

**Batching (doc 06 error controls):**
- Step 3 is one Sonnet subagent brief, containing the doc 05 §2.2–2.3 and doc 04 §3.2 excerpts plus the migration DDL.
- Step 5's fixture test is a Haiku brief.
- Everything else runs here on Opus.
- A step that fails verification twice escalates one tier (to Fable 5.1 for Deep).

## Definitions pinned for this milestone
| Measure | Definition | Note |
|---|---|---|
| RE share of generation | (Hydro + Bioenergy + Wind + Solar) ÷ Total generation | Ember's own "Renewables" aggregate is used as the cross-check |
| Fossil share | (Coal + Gas + Other fossil) ÷ Total generation | |
| RE share of capacity (NETR) | Renewable capacity ÷ total capacity (Net imports excluded) | **Unverified:** whether NETR's 31% target counts large hydro. Assumed **yes** and footnoted; checked against the NETR text in M2 |
| Carbon intensity | Ember `Emissions intensity (gCO2e/kWh)` on the `Total generation` row | Recomputed from emissions ÷ generation as a DQ WARN cross-check in M2 |
| Latest complete year | Max year < current calendar year with Malaysia data | 2025 today |

## Validation (end of M1)
```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pipeline db migrate
.venv/Scripts/python -m pipeline seed
.venv/Scripts/python -m pipeline run          # exit 0
.venv/Scripts/python -m pipeline run          # exit 0, 0 changed rows
sqlcmd -S localhost -E -d EnergyDW -Q "SELECT rule_code,status FROM mart.dq_latest"
sqlcmd -S localhost -E -d EnergyDW -i sql/showcase/00_reconciliation.sql
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| A hand-written PBIP won't open in Desktop | Medium | Step 8 starts from a Desktop-saved skeleton; Claude only adds TMDL/theme files; check after each change |
| mssql-python bulk insert is slow or behaves unexpectedly | Low | 5k rows is tiny; `executemany` into `#staging` then MERGE; if it's slow, fall back to `BULK INSERT` from the landing CSV |
| `GO` splitting edge cases (GO inside strings/comments) | Low | Unit test in step 1; migrations avoid `GO` inside strings |
| The NETR hydro definition is wrong | Medium | Footnote now; verify in M2 before any public claim (task 2.8 audit) |
| Ember revises past values between runs | Expected | MERGE overwrites (Type-1); `source_version` logged |
| Re-downloading 16 MB every run | Low | Skip the download if today's file already exists; `--refresh` forces it |

## Acceptance (the doc 06 M1 check)
- [ ] On an empty `EnergyDW`: `db migrate && seed && run` exits 0; a second `run` is idempotent
- [ ] `mart.dq_latest` is all PASS; an injected failure rolls back and exits 1
- [ ] Task 1.11: 5 figures within ±0.5%, independently re-checked
- [ ] P1 thin page matches the wireframe; the Refresh works
- [ ] Commits pushed; doc 06 and the index updated
