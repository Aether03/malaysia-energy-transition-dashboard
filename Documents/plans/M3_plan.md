# Plan: M3 — Grid load and forecast

**Source:** [06 Implementation Plan](../06_Implementation_Plan.md) Phase 3 (tasks 3.1–3.6), plus F1 and S2 · **Complexity:** Large (about 2–3 sessions; the forecast review and the P4 GUI rounds are the slow parts) · **Status:** APPROVED 2026-10-03 in the plan canvas (Q3, Q5, Q6 accepted in round 1; the revised Q1, Q2 and Q4 accepted in round 2); in progress

## Summary
M3 adds the grid engineer's page:
1. The open Thailand hourly data (EGAT via Zenodo, CC BY 4.0) is the stand-in for Peninsular Malaysia until TNB consents. It is loaded into the generic `raw.grid_interval`, so GSO can plug in later without a schema change.
2. A careful time layer (local → UTC, odd timestamps, gaps) feeds `dim_date`/`dim_hour` and the hourly facts for demand and interconnector flows.
3. A day-ahead LightGBM load forecast is backtested against a seasonal-naive baseline and written back to SQL Server, with an independent ML review.
4. Page P4 shows load curves, a heatmap, peak and load factor, the forecast panel, and the Thailand ↔ Malaysia flows.

## Requirements restated
| FR | What M3 must deliver | Where |
|---|---|---|
| FR-22 | Typical daily load curves (weekday vs weekend, by season), monthly peak demand, load factor; open hourly data stands in for GSO (doc 02 §11 decision) | P4 |
| FR-13 | Day-ahead hourly load forecast vs a seasonal-naive baseline, with a rolling-origin backtest; MAPE/MAE, the method and the limits shown | P4, `pipeline forecast` |
| S2 | Thailand ↔ Malaysia interconnector flows, 2023–24, one single-axis chart | P4 |
| F1 | Peak and load factor as **two aligned single-axis charts** (no dual axis) | P4 |
| 3.3 | The **Unverified** item "regional demands sum to national demand", checked against a published EGAT peak; the P4 label set from the result | `docs/reconciliation.md` |
| FR-03 | DQ rules for the hourly data (gaps, duplicates, negatives) | `seed/dq_rule.csv` |

## Facts verified before planning (2026-10-03, profiled in the scratchpad, nothing committed)
- **Zenodo record 17109911:** v1.0, published 2025-09-13, CC BY 4.0. Two files, `system_2023.csv` (958,220 B) and `system_2024.csv` (958,283 B). The source is EGAT, the national system operator.
- **The two files have different headers.** This would have broken a position-based parser.
  - 2023: `… northeast_demand, malaysia_IMP, malaysia_EXP, EDL_IMP, EDL_EXP, hongsa_IMP, cambodia_EXP`
  - 2024: `… northeast_demand, hongsa_IMP, malaysia_EXP, malaysia_IMP, laos_IMP, laos_EXP, cambodia_EXP`. The columns are reordered and `EDL_*` is renamed `laos_*`.
  - On the overlapping day the values agree **by name**, which confirms the mapping (24/24 hours identical).
  - So the header check accepts exactly these two known variants and maps columns by name, never by position.
- **Each file spills into the next year.** The 2023 file runs to 2024-01-01 23:00, and the 2024 file to 2025-01-01 23:00. The 2024-01-01 overlap is identical in both files.
- **Odd timestamps:**
  - 2023 starts at `01/01/2023 0:05`, with no 0:00 row.
  - The 2024 file has **both** `0:05` (row 2) and `0:00` (row 26) for 2024-01-01, with slightly different values, and it is not sorted.
- **Gaps:** 1 missing hour in 2023 (2023-06-08 00:00) and 3 in 2024 (2024-12-07 23:00, 12-08 09:00, 12-19 17:00). That is **4 of the 17,568 hours in the files' span (0.02%)**, far under the 2% rule.
- **Demand (sum of the 5 regions):**
  - 2023: peak 33,443 MW at 2023-05-06 21:00; mean 23,319 MW.
  - 2024: peak 35,560 MW at 2024-04-29 21:00; mean 24,596 MW.
  - The annual load factor is 69.8% and 69.2%.
  - Both peak dates match the widely reported EGAT record-peak days. The published figures are **higher** (instantaneous peak vs our hourly values?). This is **Unverified** and is step 5's job.
- **Malaysia flows:**
  - Each hour has exactly one of `malaysia_IMP` / `malaysia_EXP` filled, **never both**. 61 hours (2023) and 250 (2024) have neither.
  - The typical flow is about 29 MW, with peaks near 300 MW.
  - **2023:** Thailand exported 235.3 GWh and imported 65.5 GWh, so it was a net exporter to Malaysia.
  - **2024:** 149.6 GWh exported vs 150.9 GWh imported, roughly balanced.
- `northeast_generation` has 7 small negative values (likely net of station use). Generation isn't used in M3, but it is landed in raw as published.
- Libraries are already pinned: `holidays 0.105`, `lightgbm 4.7.0`, `scikit-learn 1.9.1`. Nothing new to install.

## Decisions for your approval
| # | Question | Proposed |
|---|---|---|
| Q1 | How to handle the odd timestamps and the overlapping days | **Revised (your note: stay as close to the original dataset as possible):**<br>• **Raw is an exact copy of both files.** Every row is kept, including the spill-over days and both the `0:00` and `0:05` rows. `raw.grid_interval` gains `source_file` in its key, so the two copies of 2024-01-01 sit side by side (doc 05 one-line edit).<br>• **Warehouse:** every distinct published hour, **2025-01-01 included**: 17,564 hours, from 2023-01-01 to 2025-01-01 23:00. Each hour is taken once; the overlap day is identical in both files, and a WARN rule `OVERLAP_VALUES_AGREE` proves it on every load.<br>• **Timestamps:** `0:05` stands for hour 0 only when no `0:00` row exists (2023-01-01). When both exist, the on-the-hour reading wins. The original text is kept beside the warehouse row (`ts_text`).<br>• **No imputation anywhere in SQL.** The 4 missing hours stay missing and show as gaps (`is_imputed` stays 0 for every Thailand row; doc 05 keeps the column for GSO later). The forecast handles them as missing values (Q2).<br>• **Year-based visuals** (heatmap, monthly peaks, year slicer) cover the complete years 2023–24. The 2025-01-01 day is in the data and footnoted, but it isn't presented as a year |
| Q2 | Backtest design (doc 05's example used Oct–Dec 2024 only) | **Revised (your note: the backtest can only be used once, so guard against everything):** the design stays the same, but under a **locked test protocol**:<br>• 12 monthly rolling origins across 2024, expanding window from 2023-01-08.<br>• Forecasts issued at local midnight before the day, so every lag is ≥ 24 h.<br>• **Every modelling choice is made on 2023 only**, using a development holdout of Oct–Dec 2023.<br>• The protocol (features, parameters, folds, metrics, decision rule) is **committed before 2024 is ever forecast**, and `ecc:mle-reviewer` reviews it **before** that run, not after.<br>• The 2024 backtest then runs **once**. The 12 risks and their guards are in the next section |
| Q3 | The flows chart: 17,544 hourly points is past Power BI's line-chart sampling, so it would show noise | **Accepted.** Daily mean net flow, signed (positive = Thailand exports to Malaysia), with a zero line and the annual import and export GWh as a subtitle. Hover shows the date and the average MW. Doc 03 P4 gets a one-line edit ("hour and MW" → "day and average MW") |
| Q4 | Grid selector: only one grid can be published (`MY_PEN_GSO.is_published = 0`) | **Revised (your note: look for other countries' grids first):** step 2 searches for open hourly grid data from other ASEAN grids. Known leads: Singapore EMA (half-hourly), the Philippines IEMOP/WESM, Viet Nam NLDC and Indonesia PLN.<br>**A grid qualifies only if all four hold:** (a) hourly or finer system demand covering at least 2023–24; (b) a licence that allows reuse and published derived charts; (c) download without a login or scraping against the terms; (d) a stable format.<br>• **If one or more qualify:** a grid selector is added (single-select, Thailand by default). Each qualifying grid gets an adapter like `thailand.py`, and the forecast runs per grid (the code is grid-generic). At most **one** extra grid in M3; any others go to the v2 list.<br>• **If none qualify:** no selector, and the banner names Thailand's grid. Either way, the search result goes into doc 01 §6 |
| Q5 | Hourly DQ rules: doc 05 lists "hourly gaps ≤ 2%", but doc 06 puts it in M5 task 5.2 | **Accepted.** Pull it into M3. BLOCKING: `HOURLY_GAPS_LE_2PCT`, `NO_DUPLICATE_UTC_HOUR`, `NO_NEGATIVE_DEMAND`. WARN: `FLOW_ONE_DIRECTION`, `DEMAND_PLAUSIBLE` (5,000–60,000 MW), plus `OVERLAP_VALUES_AGREE` (Q1). Task 5.2 keeps only the P6 badge |
| Q6 | Does `pipeline run` run the forecast? | **Accepted.** A `FORECAST` step runs after a committed transform; `pipeline forecast` also runs it alone. On failure the step is FAILED and the run exits 1. The data stays committed, and the previous `is_current` forecast stays in place. Re-runs **replay the locked protocol** (deterministic, so the numbers are identical), so they never count as a second look at the test |

## Backtest protocol (Q2): what could go wrong, and the guard for each
| # | Failure mode | Guard |
|---|---|---|
| 1 | **Peeking at the test**: features, parameters or the model chosen after seeing 2024 results | All development uses 2023 only (train 2023-01-08 → 09-30, holdout Oct–Dec 2023). `docs/forecast.md` §Protocol is committed **before** the first 2024 run, and its commit hash is stored in `forecast_run.params_json`. The code refuses a 2024 run unless the protocol file is committed and unchanged (`--final`). Any change after seeing 2024 is a new, labelled **post-hoc** run, and the first run stays on record (runs are never deleted) |
| 2 | **Lag leakage**: a feature uses data from after the issue time | Lags ≥ 24 h only. The 24 h rolling mean ends at t − 24. The step 7 test shifts a toy series and asserts that no feature changes when future values change |
| 3 | **Early stopping or tuning on the test month** | Early stopping uses only the last 28 days of each fold's training window. Hyperparameters are fixed from the 2023 holdout and identical for all 12 folds |
| 4 | **Imputation leakage**: interpolation pulls a future value into a past feature | No imputation (Q1). LightGBM takes missing values natively, and a missing lag stays missing |
| 5 | **Unfair comparison**: model and baseline scored on different hours | Both are scored on the **same hour set**: hours where the actual, the model and the baseline (t − 168 h) all exist. The excluded hours are counted and reported |
| 6 | **Holiday handling**: the calendar is fine (known in advance), but holidays can fall inside the baseline's t − 168 h | Kept by design (it's what seasonal naive does). Holiday-hour error is reported separately so the effect is visible |
| 7 | **Only 2 years**: the January 2024 fold has only about a year of history | Expanding window; per-month metrics shown, so weak months are visible, not averaged away; stated on P4 |
| 8 | **Luck**: an improvement that is noise | A day-block bootstrap gives a 95% CI on the MAPE improvement. Fixed in the protocol: the model "beats the baseline" only if the CI is above 0. Otherwise P4 shows the WARN banner |
| 9 | **A weak baseline makes the model look good** | Secondary reference: naive t − 24 h, reported beside the seasonal naive (the primary baseline is fixed by doc 02) |
| 10 | **Non-determinism**: different numbers on a re-run | LightGBM `deterministic=True`, a fixed seed and thread count, pinned versions; acceptance requires an identical re-run. Seed sensitivity (3 seeds) is checked on the 2023 holdout only |
| 11 | **Time-zone or misaligned-hour bugs** shift the target vs the features | Features are built in local time from `ts_local`. The step 5 spot checks plus a test that the 168 h lag of hour h is hour h a week earlier |
| 12 | **A bug found only after the 2024 run** | The full pipeline is dry-run end to end on the 2023 holdout first (same code path, different dates), and the step 7 tests run before `--final`. A post-run bug fix is a labelled post-hoc run, never a silent replacement |

## Patterns to mirror
| Category | Source | Pattern |
|---|---|---|
| Source module | `pipeline/sources/ember.py`, `owid.py` | `EXPECTED_COLUMNS` header check → `SchemaMismatchError`; `_common.download()` to `data/raw/<src>/<date>/`; typed `records_from`; `_common.merge_into()` (#stage + MERGE with an `EXCEPT` change test) |
| CLI and run log | `pipeline/cli.py:42-62` | One `run.step("EXTRACT"/"LOAD", code)` per source; each load in its own transaction. The forecast gets `run.step("FORECAST", "DTH")` |
| Transforms | `sql/transform/030_fact_country_annual.sql` | Numbered scripts; delete-and-reload inside the caller's transaction (`pipeline/transform.py`); unknown values stay NULL |
| Views | `sql/views/R__stg_owid.sql`, `R__mart_m1.sql` | Repeatable `R__`; explicit column lists; `GO` between views |
| DQ rules | `seed/dq_rule.csv` | `check_sql` returns the offending rows; BLOCKING or WARN |
| Migrations | `sql/migrations/V008__owid_dosm_raw.sql`, `V009` | Constraint names `pk_/fk_/df_/ck_<table>_…`; grants added in the same migration |
| Tests | `tests/test_owid.py` + `tests/fixtures/owid_sample.csv` | pytest on a small fixture, no database |
| Model and DAX | `tools/gen_tmdl.py`, `_Measures.tmdl`, `tools/dax_twin_check.py` | Generated tables; hand-written measures; each measure has a SQL twin checked through Desktop's ADOMD client |
| Report pages | `tools/report_builder.py`, `build_p5_page.py`, `tools/templates/*.json` | Page frame + Desktop-captured visual shapes; `build_report.py` + `validate_report.py`. P4 is already in `NAV` as `p4_grid_load` |
| Errors | `pipeline/cli.py:main`, `pipeline/transform.py` | Exceptions are logged and exit 1; DQ fails closed and rolls `dw` back |

## Files to change
| File | Action | Why |
|---|---|---|
| `sql/migrations/V010__grid_and_forecast.sql` | CREATE | `raw.grid_interval` (key includes `source_file`, Q1), `ref.public_holiday`, `dw.dim_date`, `dim_hour`, `dim_grid`, `fact_grid_hourly`, `fact_grid_flow_hourly`, `forecast_run`, `fact_load_forecast` (doc 05 §2.1–2.4) + grants |
| `seed/dim_hour.csv`, `seed/dim_grid.csv`, `seed/dq_rule.csv` | CREATE / UPDATE | 24 hours; `TH_EGAT` (UTC+7, published) and `MY_PEN_GSO` (UTC+8, `is_published = 0`); the Q5 rules |
| `pipeline/sources/thailand.py` | CREATE | Task 3.1: both header variants mapped by name; every row of both files kept, tagged with its `source_file` (Q1); long-form records |
| `pipeline/public_holidays.py` (renamed from calendar.py: review L8), `pipeline/seeds.py` | CREATE / UPDATE | Thai and Malaysian public holidays from the pinned `holidays` package → `ref.public_holiday` at seed time |
| `pipeline/cli.py`, `pipeline/config.py`, `pipeline/transform.py` | UPDATE | DTH extract/load; the Zenodo URLs; the `forecast` command and the FORECAST step (Q6); row counts for the new facts |
| `sql/views/R__stg_thailand.sql` | CREATE | Parse `dd/mm/yyyy h:mm`, normalise `:05`, take each hour once with the on-the-hour row first (Q1), local → UTC, sum the regional demand |
| `sql/transform/040_dim_date.sql`, `050_fact_grid_hourly.sql`, `060_fact_grid_flow_hourly.sql` | CREATE | Task 3.2: calendar with seasons and holidays; hourly demand, published hours only (no imputation, Q1); flows per counterparty |
| `pipeline/forecast/__init__.py`, `features.py`, `baseline.py`, `backtest.py`, `store.py` | CREATE | Task 3.4 (Q2) |
| `tests/test_thailand.py`, `tests/test_public_holidays.py`, `tests/test_forecast.py`, `tests/fixtures/thailand_*.csv` | CREATE | Parser, time, calendar and forecast tests (task 3.5) |
| `sql/views/R__mart_m3.sql` | CREATE | `mart.dim_date`, `dim_hour`, `dim_grid` (published only), `grid_hourly` (published hours only; gaps stay gaps), `grid_flow_daily`, `forecast_run_current`, `load_forecast_current`, `run_latest` |
| `sql/showcase/08_grid_load.sql`, `09_forecast_metrics.sql` | CREATE | SQL twins: curves, peak, load factor, flows; MAPE/MAE recomputed from the facts |
| `report/.../tables/*.tmdl`, `_Measures.tmdl`, a disconnected `'Forecast Date'` table | UPDATE / CREATE | P4 model and measures. The date picker filters only the forecast panel: no hand-written visual interactions, the M2 `'Compare Country'` lesson |
| `tools/build_p4_page.py`, `tools/build_report.py`, `tools/templates/*.json` | CREATE / UPDATE | Task 3.6 |
| `tools/dax_twin_check.py` | UPDATE | P4 twins |
| `docs/reconciliation.md`, `docs/forecast.md`, `docs/grid_sources.md` | UPDATE / CREATE | Step 6 results; the locked §Protocol (step 8), then the results and limits (step 9; the P4 text cites it); the step 2 grid verdicts |
| `Documents/00_Index.md`, `06_Implementation_Plan.md`, `03_App_Flow.md` (Q3, Q4), `05_Data_Schema.md` (Q1 raw key, Q2 example), `01_Product_Requirements.md` §6 (Q4 search result) | UPDATE | Status, resume points, decisions |

## Tasks (in build order)
Model tiers per doc 06 §4: **D** = Opus 5.5 (this session) · **S** = Sonnet 5.5 subagent · **GUI** = you in Power BI Desktop, following my click-level steps. A step that fails verification twice moves up one tier (Deep → Fable 5.1). Commit after every step, **running the build and validator first** (M2 lesson). The index resume point is updated before every subagent run.

| Step | Doc 06 | What | Model | Verify |
|---|---|---|---|---|
| 1 | GUI prep | **Template capture + Desktop spike** (M2 lessons: capture before guessing, and check unverifiable features early). On a scratch page you add a **matrix with a sequential-blue background rule** (heatmap), a **date slicer**, a **tile slicer**, a **clustered column chart**, a **text box**, and a **line chart with 3 series, one dashed**. Save. I copy the JSON and delete the page | GUI + D | All six render in Desktop; JSON committed in `tools/templates/` |
| 2 | Q4 | **Other ASEAN grids:** `verified-research` checks each lead (Singapore EMA, Philippines IEMOP/WESM, Viet Nam NLDC, Indonesia PLN, plus anything the search finds) against the four Q4 criteria, citing the licence text itself. Runs in parallel with steps 3–5 | S | A table in `docs/grid_sources.md`: one verdict per grid, each with its licence quote and URL. **You decide** on any grid that qualifies before an adapter is built. If one is added, its adapter and stg view join steps 4–5 and the page gets the selector in step 12 |
| 2 → outcome | Q4 | **Done 2026-10-03:** only **Singapore (EMA)** qualifies. Its licence is the Singapore Open Data Licence v1.0, read from the primary terms page (`docs/grid_sources.md`). **Amirul: add it.** It adds steps 4b and 5b below, a forecast per grid in steps 8–9 (the same locked protocol for both grids), and the grid selector in step 12 | — | — |
| 3 | 3.1, 3.2 | V010 (`raw.grid_interval` keyed by `source_file`, Q1) + seeds (`dim_hour`, `dim_grid`, Q5 rules) + `public_holidays.py` → `ref.public_holiday`. Check the package's Thai 2023–24 list against the official one (cabinet bridge days are the known gap); any missing day goes in a small seed override | D | `migrate` applies twice cleanly; Songkran 13–15 Apr 2024 and the 2023 bridge holidays are flagged |
| 4 | 3.1 | `thailand.py`, **test first**: the fixture has both header variants, the `0:05`/`0:00` pair, a spill-over day and a blank flow cell. Land **every row of both files** (all 16 series) in `raw.grid_interval`. Time the MERGE (about 281k rows; see Risks) | D (tests S) | `pytest` green; raw row count = the files' data rows × 16, with nothing dropped; a second run merges 0 rows |
| 4b | Q4 | `singapore.py`: EMA weekly half-hourly XLSX files (2023–24) → `raw.grid_interval` (`grid_code` `SG_EMA`), test first on real excerpts; seed `DSG` (SODL v1.0 credit) and `dim_grid` `SG_EMA` (UTC+8) | D (tests S) | Every half-hour of 2023–24 landed as published; a re-run merges 0 rows |
| 5 | 3.2 | `R__stg_thailand` + `040`/`050`/`060` + the Q5 DQ rules + `transform.py` counts | D | **17,564** distinct hours (2023-01-01 → 2025-01-01 23:00), 0 imputed, 0 duplicate UTC hours; 4 known gaps reported; `OVERLAP_VALUES_AGREE` PASS; spot check 2024-04-25 14:00 local = 07:00 UTC; BLOCKING rules PASS. **Independent review: `ecc:python-reviewer` + `ecc:database-reviewer`** on steps 3–5 together (task 3.2 is High) |
| 5b | Q4 | `R__stg_singapore`: half-hours → hourly demand (mean of the two half-hours, per the period-ending convention verified on the files), the System vs NEM demand choice made explicit, into the same `050` fact | D | Spot hour equals a hand calculation from one XLSX; gaps reported; review folded into step 5's |
| 6 | 3.3 | **Regional sum vs national:** `verified-research` finds EGAT's **primary** published 2023 and 2024 peaks (M2 lesson: primary sources only). Compare them with our hourly maxima and explain the gap (hourly vs instantaneous, or demand vs generation). Set the P4 label: "System demand" or "Sum of regional demand". Also the FR-22 check: one sample week's peak and load factor by hand in pandas vs SQL | S | Result + sources in `docs/reconciliation.md`; label decided; sample-week values equal |
| 6 → outcome | 3.3 | **Done 2026-10-03:** the regional sum is 2–4% below EGAT's/ERC's published peaks (2024: same day and hour, so not just hourly vs instantaneous; the scope of the published peak is undefined in any primary source). **P4 label: "Sum of regional demand (EGAT)"**, footnoted. FR-22 sample week: pandas = SQL for TH and SG (`docs/reconciliation.md`) | — | — |
| 5 → review | 3.2 | **Done 2026-10-03:** python review (4 HIGH, 7 MEDIUM) and database review (0 CRITICAL, 1 HIGH, 5 MEDIUM) all fixed (`30adf17`, `90f30b9`); the gap-rule HIGH proven by a rolled-back wipe of SG | — | — |
| 7 | 3.5 | Forecast tests **first**: future values never change a feature (shifted toy series); baseline = the value 168 h earlier, the same hour a week before; model and baseline are scored on the same hour set; missing hours stay NaN; MAPE/MAE and the day-block bootstrap on a toy series; a fold never sees its test month; `--final` refuses an uncommitted or changed protocol; same seed → same output | S | Tests written and failing for the right reason (no implementation yet) |
| 8 | 3.4 (dev) | Forecast code (`features`, `baseline`, `backtest`, `store`; `pipeline forecast`; the FORECAST step) **developed on 2023 only**: holdout Oct–Dec 2023, 3-seed stability check, full end-to-end dry run. Then write and **commit `docs/forecast.md` §Protocol** (features, parameters, folds, metrics, the bootstrap decision rule) | D | Step 7 tests green; the 2023 holdout metrics are recorded as development results. **Independent review: `ecc:mle-reviewer` on the code AND the protocol, before step 9.** All findings are fixed and the protocol is re-committed, before 2024 is touched |
| 9 | 3.4 (final) | **The single 2024 backtest:** `pipeline forecast --final` → `forecast_run` (with the protocol commit hash) + `fact_load_forecast`. The results are written into `docs/forecast.md` as they come out, including weak months | D | MAPE/MAE for model, baseline and naive-24 h, overall and per month, with the bootstrap CI; the decision rule applied as committed; a re-run reproduces identical numbers |
| 7 → outcome | 3.5 | **Done 2026-10-03 (`bad6e31`):** the contract as stubs (Deep), then 201 tests (Sonnet), all failing with NotImplementedError. `metrics.py` and `protocol.py` were added to the file list | — | — |
| 8 → outcome | 3.4 (dev) | **Done 2026-10-03 (`be9203f`, `efb4af6`, `d7a03e2`):** developed on 2023 only. l2 with 15 leaves was chosen from 6 configs. `ecc:mle-reviewer` found 0 CRITICAL and 3 HIGH/7 MEDIUM, all fixed: fingerprints, a wider gate, the weekday-aware naive as a secondary reference, 7-day block bootstrap, DEV capped at 2023, one grid per `--final`, and the cross-grid lock. Its re-verification gave APPROVE WITH WARNINGS, and those items are fixed too. 509 tests | — | — |
| 9 → outcome | 3.4 (final) | **Done 2026-10-03, run once:** TH 3.31% vs 6.23% (improvement 46.9%, CI 39.3 to 52.8); SG 1.64% vs 2.50% (34.5%, CI 26.2 to 41.7). Both beat the baseline, and both also beat the weekday-aware naive. The replay is bit-identical. Results and weak months are in `docs/forecast.md` | — | — |
| 10 | — | `R__mart_m3` views + showcase `08_grid_load` and `09_forecast_metrics` | D | `09` recomputes MAPE/MAE from `fact_load_forecast` = the stored `forecast_run` values (±0.001); no `SELECT *` |
| 11 | 3.6 | Model: `gen_tmdl.py` tables, relationships (doc 05 §3: hourly facts use `dim_date`), `'Forecast Date'`; measures: average load by hour, day type, peak, load factor, heatmap value, actual/model/baseline, MAPE cards, improvement % and its CI, banner and WARN text, the empty and error states (doc 03 P4), daily net flow | D | `dax_twin_check.py`: at least 6 new twins (peak, load factor, 1 curve point, MAPE model and baseline, 2024 net flow) all PASS; the existing 14 still PASS |
| 12 | 3.6 | `build_p4_page.py`: banner (+ the grid selector only if step 2 adds a grid) → load curves (season tile slicer; Weekday vs Weekend & holiday) + heatmap → peak and load-factor charts (F1) → forecast panel (date picker, 24 h lines, 3 metric cards) → flows (Q3) → method and limits text. Then GUI rounds until the page passes | S + GUI | `validate_report.py` 0 problems; click-through of every row of doc 03 P4's element table; a date outside the window shows "Forecast available for …" |
| 13 | acceptance | Empty-DB rebuild (throwaway DB; the forecast replays the locked protocol), twins, doc 01/03/05/06 edits (Q1–Q4), index, skill-test memory, push | D | The acceptance list below |

**Batching and parallel work:**
- The step 4 fixture tests and the step 7 tests are separate Sonnet briefs. Each brief names only the files it may touch; M2 showed Fast-tier briefs drifting out of scope, so every test brief gets a Deep read before commit.
- Step 2 (grid search) runs **in parallel** with steps 3–5, and step 6 in parallel with steps 7–8.
- Step 12 is one Sonnet agent, continued with SendMessage across the GUI rounds.
- Everything else runs here on Opus.

**GUI rounds for you:** step 1 (templates and spike), step 12 (expect about 2 rounds), step 13 (final check). That makes about 4 rounds, against 7 in M2, because the templates come first.

**Session plan (M2 cost lesson):** this M3 session runs steps 1–6. A fresh session resumes from the index for steps 7–13, so the one-shot backtest (step 9) starts with a clean context.

## Definitions pinned for this milestone
| Measure | Definition | Note |
|---|---|---|
| System demand | Sum of the 5 regional `_demand` series (MW, hourly) | The label may become "Sum of regional demand" after step 5 |
| Typical daily load curve | Mean MW by local hour over the selected days, split into Weekday vs **Weekend & holiday** (Thai public holidays) | Season slicer: Hot (Mar–May) · Rainy (Jun–Oct) · Cool (Nov–Feb), month-based approximations of the Thai Meteorological Department seasons, footnoted |
| Monthly peak | Max hourly demand in the month, over published hours | Hourly means, so below EGAT's instantaneous peak (step 5) |
| Load factor | Mean hourly demand ÷ peak hourly demand over the same period, published hours only | % (2023 annual: 69.8%) |
| Baseline | Seasonal naive: the actual at t − 168 h | doc 02 §4 |
| MAPE / MAE | mean(\|actual − forecast\| ÷ actual) × 100 / mean \|actual − forecast\| (MW), over the hours where the actual, model and baseline all exist (protocol #5) | Overall and per month, with a day-block bootstrap 95% CI on the improvement |
| Improvement | 1 − MAPE_model ÷ MAPE_baseline | "Beats the baseline" only if the CI's lower bound is above 0 (protocol #8); otherwise the WARN banner |
| Net flow (Malaysia) | `malaysia_EXP − malaysia_IMP`, MW; positive = Thailand exports to Malaysia | Hours with neither filled are a gap, not 0; shown as daily means (Q3) |
| Time | `ts_utc` = local − 7 h (`dim_grid.utc_offset_min`, no daylight saving); the report shows local time | Malaysia would be +8 h |

## Validation (end of M3)
```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pipeline db migrate
.venv/Scripts/python -m pipeline seed
.venv/Scripts/python -m pipeline run          # exit 0; ELT + DQ + FORECAST; only the known WARNs
.venv/Scripts/python -m pipeline run          # exit 0; 0 changed rows for D1, D2, D3, DTH; same forecast metrics
.venv/Scripts/python tools/validate_report.py # 0 problems
.venv/Scripts/python tools/dax_twin_check.py  # all twins PASS (Desktop open)
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Forecast leakage, or the one-shot test is spoiled | Medium | The 12-row protocol table above: step 7 tests first, all development on 2023, a committed protocol, `ecc:mle-reviewer` before the run |
| A second grid widens M3 (adapter + forecast + selector) | Medium | At most one extra grid in M3, and only with your OK after step 2 |
| `merge_into` runs `executemany` on about 281k raw rows, which may take minutes | Medium | Timed in step 4. If it's slow: chunked inserts or a bulk-copy path. Every series is still landed (Q1) |
| Desktop can't render a hand-written matrix background rule or a date slicer | Medium | Step 1 captures and spikes both before P4 depends on them. Fallbacks: a sequential-coloured column grid for the heatmap, a dropdown of backtest dates for the picker |
| RAM: Desktop + SQL Server + LightGBM on the 7.5 GB PC | Medium | Close Desktop before `pipeline run` (standing rule); 17.5k rows is a small model |
| The `holidays` package misses Thai cabinet bridge holidays | Medium | Step 3 checks against the official list; seed override |
| Only 2 years of data: each season is seen once before the 2024 test | Certain | Stated on P4 and in `docs/forecast.md`; per-month metrics show where it's weak |
| Viewers read Thai data as Malaysian | Medium | The banner on every state of P4; the README and P6 say "open-data proxy" |
| The Zenodo record is revised | Low | The record id and version are pinned in config; the header check fails loudly on a third variant |
| Forecast doesn't beat the baseline | Low | The honest WARN banner (doc 03 P4); still a valid result |

## Acceptance (the doc 06 M3 check, plus)
- [x] The forecast beats the baseline on the 2024 backtest under the pre-committed rule: TH +46.9% (CI 39.3 to 52.8), SG +34.5% (CI 26.2 to 41.7). Both also beat the weekday-aware naive
- [x] `ecc:mle-reviewer` findings resolved before the 2024 run (`efb4af6`, `d7a03e2`; re-verification APPROVE WITH WARNINGS, warnings fixed); task 3.2 reviews resolved (`30adf17`, `90f30b9`)
- [x] On an empty DB (`EnergyDW_M3Test`, 2026-10-05): `migrate && seed && run` exits 0 (20 scripts; 4 known WARNs). The replay rebuilt both FINAL runs from the record, identical. A second run merged 0 rows for D1, D2, D3, DTH and DSG; replay identical; still 2 runs
- [x] Hourly BLOCKING rules PASS. Raw: 281,424 TH + 106,848 SG rows. TH 17,564 hours, 0 imputed, 4 known gaps; SG 17,808, complete (rebuilt DB)
- [x] §Protocol committed at `d7a03e2` before the run; the hash is in `forecast_run.protocol_commit`; one FINAL run per grid (records `d73808f`, `4198eb1`)
- [x] `docs/grid_sources.md` lists a verdict per lead. Singapore qualified and was approved by Amirul; the grid selector exists
- [x] Step 6 result in `docs/reconciliation.md`; label "Sum of regional demand (EGAT)"; FR-22 sample week: pandas = SQL for both grids
- [x] Twins 23/23 PASS (14 old + 9 P4), latest run 2026-10-05
- [x] P4 click-through passed in Desktop (GUI round 3, run by Claude via computer use, 2026-10-05): grid switch, sync both ways, season toggle, day pick and clear, nav. Caveats:
  - The empty and error states are verified by DAX query. The date list holds backtest days only, so the empty state can't be reached from the UI.
  - Hover tooltips aren't verifiable by automated hover. The card tooltip content is shown on the page anyway
- [x] Docs 01/03/04/05/06 edits, index and skill-test memory updated; pushed

## Outcome (2026-10-05)
**M3 complete.**
- **Forecast:** both grids beat the seasonal-naive baseline in a locked, once-only 2024 backtest. TH 3.31% vs 6.23% MAPE (improvement 46.9%, CI 39.3 to 52.8); SG 1.64% vs 2.50% (34.5%, CI 26.2 to 41.7). Both also beat the weekday-aware naive. The replay is bit-identical, including on an empty DB.
- **P4 is two pages**, Grid load and Forecast (Amirul, GUI round 1), with synced grid slicers.

**Lessons**
- **Freeze before the test:** stubs + tests first, then development on 2023 only, then an independent pre-test review. The review found 3 HIGH machinery gaps and a benchmark-honesty issue, all fixed before the one-shot run.
- **Rehearse in committed tests:** rehearsals that guard a one-shot step belong in committed tests. The reviewer could not see a scratch-only dry run.
- **Desktop 2.158 limits:**
  - minimum category width 20 px; legends hide below ~140 px; charts become placeholders below ~120 px; matrix header font minimum 8 pt;
  - `at` is not a usable DAX variable name;
  - card tooltips don't render.
- **Refreshing without a click:** `tools/model_refresh.ps1` refreshes Desktop's model via TMSL.
- **Launching Desktop:** under computer use, `open_application` started a second empty Desktop. Launch with `Start-Process` and focus the window by process ID.
- **A limit found after the test** is recorded, not tuned (record peaks are under-forecast; `docs/forecast.md`).
