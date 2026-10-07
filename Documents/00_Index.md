# Energy Dashboard — Planning Index

**Updated:** 2026-10-07 · **Project root:** `C:\Users\user\Desktop\PetProject\Energy_Dashboard` · **Stage:** building. M0–M4 are done. **M5 IN PROGRESS: steps 1–5 done (session 1, 2026-10-07); resume at step 6 (walkthrough script), in a fresh session.**

**M3 COMPLETE (2026-10-05):**
- **Forecast:** both grids beat the baseline in the locked, once-only 2024 backtest (TH +46.9%, SG +34.5%).
- **P4 is two pages**, Grid load and Forecast.
- **Acceptance:** the empty-DB rebuild passes and replays the FINAL runs identically. Twins 23/23; 509 tests.
- **Details:** `plans/M3_plan.md` (Outcome).

**M5 session 1 (2026-10-07): steps 1–5 done** (outcome rows in `plans/M5_plan.md`). **Resume at step 6** (session 2 = steps 6–9; session 3 = steps 10–13).
- **Step 5:** `docs/report.pdf` + `docs/img/01–07_*.png` (P3/P3b dropped by `tools/export_pages.py`, which fails closed); `docs/a11y.md` (heatmap contrast fixed, series labels added; open minors listed). Re-export: Desktop → File → Export → Export to PDF, copy the newest `%TEMP%\Power BI Desktop\print-job-*\EnergyTransition.pdf` to `data/private/report_full.pdf`, run `tools/export_pages.py`. Run `pytest` with Desktop closed (RAM).
- **Built:** P6 About + P6b Data quality, the Fail badge (Data quality nav item, every page; invisible at 0), the ⓘ button (foot of the rail), alt text on every visual, the T2 report-page tooltip back on P5, the hardening batch (applock, version order, V017/V018), and the DOSM gap partly explained. Twins 35/35; 971 tests; validator 269 visuals, 0 problems.
- **Amirul, once:** Ctrl+click one P6 source link and the GitHub button in Desktop (Claude doesn't click external links).
- **Desktop quirks learned:** `id` (like `at`) is a SYNTAXERROR as a DAX variable name; a new relationship from a table with NULL keys gives the dimension a blank row (use `ALLNOBLANKROW`, and return BLANK, not ""); report-page tooltips render when `visualTooltip` has only `show` + `section`; Desktop can hang on close: confirm `report/` is untouched, then end the process.
- **Open:** the Windows high-contrast check (a system setting: Amirul toggles it, or we skip it); `ruff format` would change 40 files (decide at step 8).
- **Consent emails sent 2026-10-07** (Amirul's go):
  - Energy Commission request to `sc@st.gov.my`, asking them to forward it to the Energy Data and Research Unit (`docs/consent/st_request.md`). D5 is now `REQUESTED`, so the page notice reads "permission requested"; `is_publishable` stays 0.
  - GSO follow-up in the 30 Sep thread (`docs/consent/gso_request.md`).
  - **Check Gmail for replies at the start of each M5 session.**
- **Standing M5 decisions:** P3/P3b stay out of every published export until D5 consent (Q2). The history rewrite is only done after a dry run on a clone, and only with Amirul's go (Q1; the forecast replay depends on `protocol_commit`). P6 splits into About + Data quality (Q3).

**M4 COMPLETE (2026-10-05):** plan `plans/M4_plan.md` (step outcome rows + Outcome).
- **Data:** 12 handbook tables (989 cells) land at runtime only. Blind re-read: 0 differences. The Sarawak year remap is proven by the 2022 edition. 12 D5 rules; twins 31/31; 948 tests.
- **Pages:** **P3 Regions** + **P3b State reliability** (Shape Map on a registered TopoJSON, Mercator, ISO join; ranked bar; selected-state trend; SAIFI | SAIDI; own year dropdown). Built by `tools/build_p3_page.py` / `build_p3b_page.py`; 2 GUI rounds by Claude via computer use; every doc 03 row passes; credits, consent notice and ODbL credit visible.
- **Acceptance:** the empty-DB rebuild passes (second run merges 0; only the 4 known WARNs; FINAL replays identical). Docs 01/03/04/05/06 as built; `DATA_LICENSES.md` has the handbook's p.5 terms and the ODbL redistribution.
- **⚠ For M5 task 5.8 (before the repo goes public):** two real handbook figures were in committed text (doc 05 sample row; a comment in V015/`R__stg_handbook`). They're fixed in the tree, and `tools/scan_handbook_values.py` now guards it, but **they remain in git history**: rewrite history or accept that, deliberately.
- **Rules still standing:**
  - Close Desktop before `pipeline run`, and never rebuild pages while it is open.
  - `Start-Process` to launch Desktop; `tools/model_refresh.ps1` to refresh it.
  - Validator + twins (Desktop open) before every commit.
  - No handbook value in any committed file (`tools/scan_handbook_values.py` + the guard test).
  - Desktop captures: back up `report/` before saving in Desktop, then restore it.

**M3 history (kept for reference):** step plan `Documents/plans/M3_plan.md`, approved 2026-10-03 (Q1–Q6).

**M3 resume point (2026-10-03, end of session 1). Steps 2–6 are done and pushed:**
- **Step 2:** of the other ASEAN grids, only **Singapore (EMA)** qualifies (SODL v1.0, read from the primary terms page; `docs/grid_sources.md`). **Amirul: add it.** So P4 has two grids, TH_EGAT (default) and SG_EMA, with a selector.
- **Steps 3–5b:**
  - V010–V013.
  - `thailand.py` (281,424 raw rows; MD5-pinned) and `singapore.py` (106 weekly .xls, 106,848 raw rows).
  - `public_holidays.py` (TH/MY/SG, 2021–26; renamed from `calendar.py`).
  - `R__stg_grid.sql`; `040`–`060`.
  - **Facts:** TH 17,564 h (4 published gaps), SG 17,808 h (complete), 52,708 flow rows.
  - 22 DQ rules: every hourly rule PASSes; only the 4 known M2 WARNs remain.
- **Step 5 review done:**
  - Python: 4 HIGH, 7 MEDIUM, LOW items.
  - Database: 0 CRITICAL, 1 HIGH, 5 MEDIUM, LOW items.
  - All fixed in `30adf17` and `90f30b9`. 269 tests pass.
- **Step 6 done:**
  - The P4 Thailand label is **"Sum of regional demand (EGAT)"**, with a footnote: hourly mean; published system peaks are 2–4% higher (`docs/reconciliation.md`).
  - The FR-22 sample week matches pandas vs SQL for both grids.
- **Step 1 done (2026-10-03):** 7 Desktop-made templates in `tools/templates/` (`36c0667`, `5db6303`). The tile style is stored as mode Basic + orientation 1D; Date Picker as RelativeDatePicker. **Clean-up done (2026-10-03):** Scratch page and table deleted in Desktop. That save also renumbered z-order and tabOrder on every visual, so the report files were restored to the committed, M2-verified state (`git checkout -- report/`); validator 0 problems. **Close Desktop WITHOUT saving** before the next pipeline run.
- **Step 7 done (`bad6e31`):** the forecast contract as stubs (docstrings are the spec), plus 201 tests by a Sonnet agent, Deep-read before commit. `metrics.py` and `protocol.py` are additions to the plan's file list.
- **Step 8 code + protocol draft done (`be9203f`). 2023 only; no 2024 hour was ever read.**
  - **Code:** `pipeline/forecast/` is implemented and all 470 tests pass.
  - **Modes:** `pipeline forecast --dev` (DEV) / `--final` (FINAL) / no flag (replay). `pipeline run` gets a FORECAST step, which replays the recorded FINAL run and is a no-op until one exists.
  - **V014:** the date check now fits a rolling backtest (`train_end < test_end`).
  - **`docs/forecast.md`:** method, the §Protocol JSON (l2, 15 leaves, chosen from 6 configs on the Oct–Dec 2023 holdout), development results and limits. Singapore's NEM forecast is settled as **not** a benchmark.
  - **2023 holdout:** TH 4.56% vs 6.70% baseline (improvement CI 24.9 to 37.7); SG 1.47% vs 1.98% (CI 15.4 to 34.5). Seeds are stable. Weak spot: TH 22–31 Dec 2023, a real cold spell plus year-end, listed under Limits.
  - **Dry run:** the FINAL/replay path ran on 2023 with a stand-in protocol and was rolled back, 9/9 checks pass. 2 DEV runs are stored (model_run_id 1–2).
  - **The gate:** `docs/forecast_final.json` will hold the FINAL record. `committed_protocol()` refuses `--final` unless `docs/forecast.md` and `pipeline/forecast/` are committed and clean (verified on the real repo).
- **`ecc:mle-reviewer` done; fixes in `efb4af6`, 505 tests pass.**
  - The review found 0 CRITICAL, 3 HIGH, 7 MEDIUM and some LOW. All are fixed:
    - FINAL/replay tests on fakes;
    - input fingerprints and a forecast hash;
    - a wider gate, which also guards the record;
    - the weekday-aware naive as a secondary reference;
    - DEV capped at 2023; `--final` takes one `--grid`;
    - 7-day block bootstrap.
  - DEV runs 5–6 use the final method.
  - **Thailand finding, dev only:** the model beats the seasonal naive (CI 21.8 to 39.3) but **not** the weekday-aware naive (+8.4%, CI −15.3 to 24.6). SG beats every reference.
  - **Re-verification: APPROVE WITH WARNINGS.** Its 3 remaining items are fixed in `d7a03e2` (509 tests):
    - a second grid must match the first grid's recorded settings and code;
    - Python major.minor only in the fingerprint;
    - atomic record write.
  - The gate is clean at `d7a03e2`.
- **Step 9 DONE (2026-10-03), run once per grid with Amirul's go.** The H3 policy is report-only: the banner follows the seasonal naive.
  - **TH_EGAT** (FINAL run 7): 3.31% vs 6.23%, improvement 46.9% (CI 39.3 to 52.8).
  - **SG_EMA** (FINAL run 8): 1.64% vs 2.50%, improvement 34.5% (CI 26.2 to 41.7).
  - Both beat the baseline, so **no WARN banner**. Both also beat the weekday-aware naive (TH 33.9%, CI 26.0 to 40.1; SG 24.4%, CI 15.7 to 32.4).
  - Weak months: TH April (Songkran) and January. Records: `d73808f`, `4198eb1`. `pipeline forecast` replay: identical.
  - **Never run `--final` again.** A change means a labelled POST_HOC run.
- **Step 10 done (`52fc295`):** `R__mart_m3` (published grids only), plus showcase `08` peak/LF, `09` forecast metrics recomputed from the facts (max diff 0.0005), `10` load curves and `11` flows. All expected values match.
- **Step 11 done (`1840270`, `1d620cf`, `228c604`, `4797887`):** 10 generated tables and 11 relationships.
  - `forecast_date` and `season_pick` are disconnected controls (no hand-written interactions).
  - 34 P4 measures. **Twins: 22/22 pass, plus a season-toggle twin, untested until the next Desktop open.**
  - New tool: `tools/model_refresh.ps1` refreshes Desktop's model via TMSL, so no click is needed.
  - `dax_query.ps1` now writes UTF-8 (en-dash season labels).
  - Desktop quirk: `at` can't be a DAX variable name (it parses as SYNTAXERROR).
- **Docs 01/03/05 as-built edits done (`1bf4b34`).**
- **Step 12: GUI rounds 1–3 done (round 3 run by Claude via computer use, at Amirul's request, 2026-10-05).**
  - **P4 split into Grid load + Forecast** (Amirul's choice). Grid slicers are synced. The date dropdown holds 2024 days only, with nothing forced. Final layout is in `c8f9303`.
  - **Checks:**
    - ✅ Grid → Singapore switches the whole page.
    - ✅ The sync carries both ways.
    - ✅ The season toggle changes the curve only.
    - ✅ Picking a day works.
    - ✅ Clearing returns to the peak day.
    - ✅ The nav rail works.
    - Twins 23/23.
    - ⚠ Tooltips (heatmap and card hover) can't be checked by automated hover, because no chart tooltip appears under synthetic mouse moves. The card tooltip content is shown on the page anyway.
    - Cosmetic: Singapore's season labels truncate slightly.
  - **Desktop limits learned:** minimum category width is 20 px; legends hide below ~140 px; charts become placeholders below ~120 px; header font minimum is 8 pt.
  - **Next:** the forecast-doc note on the record-peak under-forecast, then step 13.
- **Step 12 (original notes):** a Sonnet agent is building `tools/build_p4_page.py`, which will be continued across GUI rounds. Then step 13: acceptance (empty-DB rebuild, twins, doc 06, push). DEV runs 1–6 stay in `dw.forecast_run` and are never shown.
- **Old step 9 note:** it needed Amirul's go because the run is irreversible and H3's banner policy was his call.
  - **Runbook:**
    1. `pipeline forecast --final --grid TH_EGAT`
    2. Commit `docs/forecast_final.json`.
    3. `pipeline forecast --final --grid SG_EMA`
    4. Commit the record again.
    5. Write the results into `docs/forecast.md`.
    6. `pipeline forecast` (replay), which must be identical.
- **Original plan for this session, from step 7:** forecast tests first, then step 8 (development on 2023 only, protocol committed, `ecc:mle-reviewer` BEFORE any 2024 run), then step 9 (the single FINAL 2024 run per grid).
  - Use a fresh session, per the plan.
  - Both grids use the same locked protocol. V013 enforces one FINAL run per grid.
  - Singapore's NEM forecast (`stg.singapore_hourly.nem_forecast_mw`) is a candidate third benchmark. Settle it in the protocol, and only on the NEM basis.
- **Backlog → M5:** ruff findings in the M2 DOSM/OWID files.
- **Rules:** close Desktop before `pipeline run`; never rebuild report pages while Desktop is open.

> **Skill test in progress.** This project is the live test of the `plan-project` skill. Every session must append its observations on the skill (friction, cost, routing, what worked) to the memory file `~/.claude/projects/C--Users-user-Desktop-PetProject/memory/project_plan_project_first_test.md`. Evaluate and improve the skill **only after the project is complete** (Amirul, 2026-09-30).

## Project summary
A portfolio project: an end-to-end energy analytics pipeline that ingests public electricity data, models it in SQL Server, and presents it in a Power BI report on **Malaysia's energy transition, benchmarked against ASEAN peers**. It is built to support Amirul's job search. The primary audience is energy data/ML engineer roles, then power utility/grid engineer roles, then data/BI analyst roles. Hard constraints: free tools only, runs on his Windows 11 PC, public and openly licensed data, and a showcase that works without a Power BI Service account.

## Document status
| # | Document | Status | Approved on |
|---|---|---|---|
| 01 | Product Requirements | Approved | 2026-09-30 |
| 02 | Technical Requirements | Approved | 2026-09-30 |
| 03 | App Flow | Approved | 2026-09-30 |
| 04 | UI/UX Design Brief | Approved | 2026-09-30 |
| 05 | Data Schema | Approved | 2026-09-30 |
| 06 | Implementation Plan | Approved | 2026-09-30 |

Status values: Not started · Drafting · In review · Approved

## Capabilities selected
| Capability | Type | Use for |
|---|---|---|
| `verified-research` | skill | Checking dataset coverage and licences (Ember, OWID, Energy Commission), Malaysia's NETR targets, and Power BI licensing and publishing rules (docs 01–02) |
| `ecc:docs-lookup` | agent | Current SQL Server, Power BI Desktop and PBIP-format documentation for version facts (doc 02) |
| `dataviz` | skill | Chart palette, KPI tiles and chart-type choices (doc 04) |
| `design:accessibility-review` / `design:design-critique` | skill | Colour-blind safety and contrast, then a critique of report mockups (doc 04, build) |
| `ecc:database-reviewer` | agent | Reviewing the star schema, indexes and T-SQL (doc 05, build). Note: it is Postgres-leaning, so its T-SQL advice needs checking |
| `ecc:python-patterns` + `ecc:python-testing` | skill | Ingestion scripts and data-quality tests (build) |
| `engineering:testing-strategy` | skill | Data-validation and reconciliation test plan (docs 02, 06) |
| `anthropic-skills:audit-my-work` | skill | Go/no-go review before the repo goes public |
| `ecc:plan-canvas` | CLI | Per-document review and approval |
| Computer use | MCP | Driving Power BI Desktop (a native app) for visual checks and screenshots during the build |

Useful but unavailable: **GitHub connector**. Authorize it in the claude.ai connector settings to let Claude create the public repo and manage issues. Otherwise, pushing with `git` works.

## Decided (settled — don't reopen)
- Project housed at `PetProject/Energy_Dashboard/` — source: user, 2026-09-30
- Story: Malaysia/ASEAN electricity transition (generation mix, renewables, carbon intensity) — source: user, 2026-09-30
- Audience priority: 1) energy data/ML engineer, 2) power utility/grid engineer, 3) data/BI analyst — source: user, 2026-09-30
- Database: Microsoft SQL Server (Developer edition, local) — source: user, 2026-09-30
- Presentation layer: Power BI Desktop — source: project brief
- Primary showcase: public GitHub repo (github.com/Aether03). A live Power BI link is optional because the UiTM student account may expire after graduation (Aug 2026) — source: user, 2026-09-30
- Machine state: Python 3.10.10 (EOL, not used), Git 2.51.1, **Power BI Desktop 2.158.1177.0 (Store, not signed in)** and winget installed; SQL Server, SSMS and Python 3.13 **not** installed — source: scans, 2026-09-30
- Stack (doc 02): SQL Server 2025 Enterprise Developer, SSMS 22, Python 3.13 + mssql-python, PBIP (PBIR + TMDL), Import mode, layered DB raw/stg/dw/mart/meta, Windows auth — source: doc 02 review
- Build start: Claude installs and updates the dependencies itself (winget/pip); Amirul clicks the UAC prompts — source: user, 2026-09-30
- Repo name `malaysia-energy-transition-dashboard`; default open hourly source Thailand (Zenodo, CC BY 4.0) — source: doc 02 review
- Report: 6 pages P1–P6 plus hidden D1 drill-through (kept) and T1/T2 tooltips; P3 map = Shape Map + geoBoundaries MYS ADM1 TopoJSON (ODbL 1.0, credit OSM contributors) — source: doc 03 review
- Visual system (doc 04): Segoe UI; navy accent #104281; validated energy-source palette coal #a0522d · other fossil #4a3aa7 · gas #eb6834 · hydro #2a78d6 · bio #008300 · wind/other RE #1baf7a · solar #eda100; sequential blue for SAIFI/heatmap; no dual axes; 1280×720 canvas; nav labels Overview · Generation · Regions · Grid load · ASEAN · About — source: doc 04 review
- Data model (doc 05): layers raw→stg→dw→mart + ref + meta; star schema with 9 dims, 7 facts + forecast_run; generic raw.grid_interval and raw.handbook_cell; no cascades; numbered T-SQL migrations; roles role_pipeline / role_report_reader; is_published / is_publishable consent gates — source: doc 05 review
- Plan (doc 06): milestones M0–M6, M1 = vertical slice (Ember → SQL → thin P1); 49 tasks routed 20 Deep (Opus 5.5) / 18 Standard (Sonnet 5.5) / 11 Fast (Haiku 4.5); 10 High-risk tasks with independent reviewers; repo private until the 5.8 audit; Amirul records the walkthrough — source: doc 06 review

- Forecast in v1; primary = day-ahead Peninsular load forecast from GSO data, fallback = annual projection — source: doc 01 review, 2026-09-30
- No deadline; Claude paces the work ("at your pace") — source: doc 01 review
- UiTM account active until about early 2027, so the Power BI live link is a short-lived Could — source: doc 01 review
- Post-v1 public web showcase (Streamlit recommended) for the portfolio website — source: doc 01 review
- In scope: hourly GSO demand, regional (Peninsular/Sabah/Sarawak) and state grid reliability (SAIFI/SAIDI) — source: doc 01 review
- Data sources D1–D6 (Ember, OWID, DOSM, GSO, Energy Commission handbook, NETR), all credited — source: doc 01 §6
- **RE capacity targets (M2 step 1, 2026-09-30).**
  - Large hydro **is** included (ASEAN definition; off-grid too).
  - 31% (2025) and 40% (2035) are cited to the 12MP/SEDA MyRER (2021); only 70% (2050) is cited to NETR. Visual name: "National RE capacity targets".
  - P1/P2 show **both** "RE share of capacity (Ember basis)", which is 24.4% for 2025, and the official government point, 31% as of Dec 2025, as a separate cited marker, with a footnote on the definition gap. An earlier "32%" reading, from a news item, was corrected the same day. Targets seeded: 31% (2025), 35% (2030), 40% (2035), 70% (2050).
  - Source: user, 2026-09-30.
- GSO data: request TNB written consent NOW (Claude drafts the email, Amirul sends it); build the forecast and grid-load page on open hourly data (Thailand Zenodo CC BY default); GSO adapter off until consent — source: user, 2026-09-30

- **M0 progress (2026-09-30):**
  - **Done:**
    - Python 3.13.15 installed (user scope) and `.venv` created, with pinned requirements (pandas 3.0.6, mssql-python 1.15.0, lightgbm 4.7.0, …).
    - SQL Server **17.0.1000.7 Standard Developer** running as the default instance. winget installed Standard, not Enterprise, Developer; doc 02 allows either.
    - `EnergyDW` created and reachable from Python via Windows auth.
    - Git repo initialised; first commit `9a77069`.
    - Reference documents saved in `docs/references/` (git-ignored).
    - GSO consent email saved as a Gmail **draft** to admin@gso.org.my.
    - Task 0.6: Deep = Opus 5.5, with Fable 5.1 as the escalation rung.
  - **Pending:**
    - ~~sqlcmd and SSMS 22 installs~~ done: SSMS 22.10.12217.157; `sqlcmd -S localhost -E` verified.
    - ~~Sending the GSO email~~ sent 2026-09-30 to admin@gso.org.my; awaiting reply (D4 = REQUESTED).
    - ~~GitHub repo~~ done: private repo https://github.com/Aether03/malaysia-energy-transition-dashboard, main pushed. **M0 COMPLETE 2026-09-30. Next: `/plan` M1 (Deep), then build.**

- **M1 progress (2026-09-30; step plan: `Documents/plans/M1_plan.md`):**
  - **Done, pushed at `1f8f3f5`:** steps 1–7.
    - Migration runner and V001–V007.
    - Seeds and views (Sonnet subagent).
    - Run log.
    - Ember extract/load: 5,070 rows, idempotent.
    - Transforms (2,192 + 328 facts) and the DQ gate. The injection test proved rollback.
    - Database review of the migrations: no critical or high findings; medium fixes are in V007.
  - **Also done, pushed at `4a4bab4`:**
    - Step 10 reconciliation: 5/5 within 0.005%, plus an independent pandas recheck within 0.001% (`docs/reconciliation.md`).
    - Transform review: 1 HIGH finding (RE capacity share under partial reporting), fixed. Malaysia unchanged.
    - RCSI on; DQ fails closed; 7 rules, 4 of them WARN.
  - **M1 COMPLETE 2026-09-30.** PBIP model (10 generated tables, 27 measures, theme) and P1 Overview (15 visuals from `tools/build_overview_page.py`) verified in Desktop. Empty-DB rebuild passed.
  - **M2 (2026-09-30):** step plan `Documents/plans/M2_plan.md` **approved 2026-09-30** (Q1–Q6 accepted: P5 metric toggle for FR-09; Ember demand ÷ UN/OWID population, with the DOSM value in a footnote; nav-rail frame; country-in-context measures; ADOMD twin check; a CAPACITY_WITHOUT_GENERATION WARN rule + V008 naming). Step 1 (NETR research) **done**, with its outcome and decision in the plan.
    - Step 2 (V008, the `_common` refactor, OWID, population and per capita; MY 2025 = 5.8144 MWh) is **done** and idempotent.
    - New WARN rules: OWID ±5% (MY 2023–24, as predicted); CF_AT_MOST_1, which found Ember's zero geothermal capacity, so `030` now nulls implausible RE capacity (MY unaffected).
    - **Known issue:** the PC runs out of RAM (270 MB free with Power BI Desktop open), so SQL Server stalls and the transform takes about 1–2 min instead of about 1 s. Close Desktop and Discord before a pipeline run; `min server memory` is proposed to Amirul.
    - Step 3 (DOSM D3) **done** (`6156d81`). The DOSM WARN fires for 2022–23 only; the gap grows from 4% to 14%. Known WARNs are registered in `docs/reconciliation.md`.
    - The database review of the M2 changes found **0 CRITICAL, 0 HIGH**. Its 3 MEDIUM findings (NULLIF-safe rule division, NULL cases that passed silently, the OWID staging row check) and 3 LOW ones are fixed in V009 and the seeds.
    - SQL `min server memory` is set to 1024 MB (Amirul approved it, 2026-09-30). Transform plus checks is back to about 1 s.
    - Step 4 (SQL showcase `01`–`05` + mart: `hours_in_year`, target `source_name`, `mart.re_capacity_official`) **done**. The spot values equal P1.
      - MY 2025 ranks: 3/6 on RE share, 5/6 on intensity; per capita 2/6 (2024).
    - Step 5 (template capture) **done**: `tools/templates/`. Desktop's auto date/time tables were removed and the setting turned off.
    - Step 6 is built: `tools/report_builder.py` frame (nav rail, takeaway title, subtitle with the as-of date, footnote) and P1 rebuilt with 5 KPIs, explicit source colours and the Ember-vs-official-vs-target bars. **Untested in Desktop.**
    - Step 6: P1 verified in Desktop (2 rounds). The final cosmetic fixes (frame borders, nav text, card padding) are unverified and get checked in the next GUI round.
    - Step 7 is written: 73 measures (country in context, shares and YoY, capacity factor, demand growth, rank on the common year, target axis, T1/T2) + field parameters `Mix Unit` / `ASEAN Metric` + `Target Axis` table.
      - `tools/dax_query.ps1` uses Desktop's own `Microsoft.PowerBI.AdomdClient.dll`; `tools/dax_twin_check.py` has 10 twins.
    - Step 7 **done**. Review: 0 CRITICAL; 3 HIGH/4 MEDIUM fixed (`'Compare Country'` selection table, exact twins). The **twin check passes 14/14** (`docs/reconciliation.md`).
    - Step 12 findings **audited**: all numbers verified (warehouse + raw CSV), and the 4 HIGH framing issues fixed (2015 base year → 3-year averages; intensity rank fragile; data-lag caveat).
    - Steps 8–10 are built by the Sonnet agent: P1 rank, findings and KPI→P2 links; P2; P5; T2. Rebuild everything with `tools/build_report.py`, validate with `tools/validate_report.py` (73 visuals, 0 problems). **Untested in Desktop.**
    - GUI rounds 3–4 (2026-10-02):
      - Slicer defaults now stored as the selection.
      - Field parameters use Desktop's `fieldParameters` shape (captured from Amirul's rebind); the P2 mix toggle is verified.
      - P5 title shows both ranks (new `Focus Intensity Rank` + twin).
      - **Twins 14/14 on the saved model.**
    - **Tooltips decided (Amirul, 2026-10-02):** report-page tooltips don't render in this Desktop, even when set in the GUI (round 6).
      - So T2's figures go into each ASEAN chart's built-in tooltip.
      - T1's definition, formula and source (from `seed/kpi.csv`) go into the hover text of P1's KPI click-through buttons.
      - The T2 page stays in the project, unused. **Backlog M5:** retry report-page tooltips (mini mix bar).
    - GUI rounds 5–6: P2 fully works; the P5 trend toggle works; peer colours muted explicitly.
    - **Rule:** never rebuild while Desktop is open, because a Desktop save overwrites the files.
    - D1 drill-through page built (`tools/build_d1_page.py`, untested); P1 findings box filled from `docs/findings.md`.
    - Round 7: the J2 journey works (P1 → P2 → P5 → D1 → Back, synced years). The Reset bookmarks are Desktop-made, and the Reset buttons are wired to them.
  - **M2 COMPLETE 2026-10-03.**
    - Empty-DB rebuild passes (13 migrations, idempotent, BLOCKING all PASS, 4 known WARNs, reconciliation 5/5).
    - Twins 14/14; findings audited.
    - Outcome and lessons: `plans/M2_plan.md` "Outcome".
    - Final Desktop check passed (2026-10-03): Reset buttons restore the defaults on P1, P2 and P5; KPI hover stays white. **M2 fully closed.**
  - **Next: M3** (grid load and forecast, Thailand open data; doc 06 Phase 3). Start with `/plan`.
    - **Rule:** rebuild report pages only while Desktop is closed.
    - **Desktop quirk (2026-10-03):** Desktop 2.158 saves `preserveNewVisualVisibility` in bookmark options, then refuses to open the file. Remove it after any save that touches bookmarks; `validate_report.py` flags it.
    - Use `tools/build_report.py` + `validate_report.py`, and `tools/dax_twin_check.py` with Desktop open.
  - **Next: M2** (Malaysia and ASEAN). Start with `/plan` on doc 06 Phase 2. Carry-overs: the NETR hydro definition, P1 polish (title alignment, as-of box), per-source colours bound explicitly.
  - **Low findings from the transform review (M5):**
    - The negative-generation rule has no tolerance.
    - YEAR() is UTC, not local time.
    - A source with capacity but NULL generation is dropped.
    - Concurrent-run guard (`sp_getapplock`).
  - **Backlog from M2 (M5):** retry report-page tooltips (T1/T2 pages exist, unused); find the cause of the DOSM gap; add the ⓘ About button with P6.
  - **Backlog from the review (M5):** exercise the roles with `CREATE USER … WITHOUT LOGIN` tests; an `sp_getapplock` guard on migrations; a check for out-of-order versions; DENY on `meta.schema_version` for `role_pipeline`; constraint-naming consistency.

## Fixes & improvements backlog
| # | Item | Found in | Priority | Scheduled in |
|---|---|---|---|---|
| F1 | Dual-axis combo charts (P2 demand growth, P4 peak/load factor) replaced by two aligned single-axis charts | doc 04 | P1 | **Done**: doc 03 edited 2026-09-30 |
| S1 | DOSM (D3) demoted to a WARN cross-check (series ends Jun 2024); doc 01 D3 text updated | doc 05 | P3 | **Done** 2026-09-30 |
| S2 | Thailand↔Malaysia interconnector flows visual added to P4 (doc 03) + `dw.fact_grid_flow_hourly` | doc 05 | P2 (Could→in scope) | **Done**: docs edited 2026-09-30 |

## Open questions
- [ ] **GSO data: technically verified 2026-09-30.** 10-minute Peninsular demand (MW) from about Jan 2017 to present (none before mid-2016), via the `SystemDemand.aspx/GetChartDataSource` POST endpoint (dd/mm/yyyy, JSON `{DT, MW}`); the Solar endpoint returns 401. **But GSO's T&C (gso.org.my/TermsConditions.aspx) prohibit downloading, storing or distributing without TNB's prior written consent.** Decision pending with Amirul: request consent / use an open alternative (Singapore EMA, Thailand Zenodo) / annual-only fallback — blocks FR-13 and FR-22 design in doc 02
- [x] Energy Commission consent: Amirul sends the email **after completion**; Claude drafts it (task in doc 06). Until then: script plus derived, credited charts only
- [ ] Does the UiTM tenant allow "Publish to web"? Only matters for FR-19 (Could) — doc 02
- [x] Is the DOSM monthly supply series still updated after Sep 2024? **No**: last modified 12 Sep 2024, data ends Jun 2024 (checked 2026-09-30, M2 plan)
