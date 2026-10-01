# Energy Dashboard — Planning Index

**Updated:** 2026-09-30 · **Project root:** `C:\Users\user\Desktop\PetProject\Energy_Dashboard` · **Stage:** planning complete (all 6 approved 2026-09-30). **Build NOT started**; it waits for Amirul's explicit go. Next: M0 (doc 06 Phase 0), after `/plan` on the Deep model

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
    - **Resume:** Amirul's GUI round for P1/P2/P5/T2. If the field-parameter charts fail, set `PARAM_WELL_USES_FIELDS_COLUMN = False`. Then step 11 (D1, T1, bookmarks) and filling P1's findings box.
  - **Next: M2** (Malaysia and ASEAN). Start with `/plan` on doc 06 Phase 2. Carry-overs: the NETR hydro definition, P1 polish (title alignment, as-of box), per-source colours bound explicitly.
  - **Low findings from the transform review (M5):**
    - The negative-generation rule has no tolerance.
    - YEAR() is UTC, not local time.
    - A source with capacity but NULL generation is dropped.
    - Concurrent-run guard (`sp_getapplock`).
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
