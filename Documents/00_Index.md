# Energy Dashboard — Planning Index

**Updated:** 2026-09-30 · **Project root:** `C:\Users\user\Desktop\PetProject\Energy_Dashboard` · **Stage:** planning complete (all 6 approved 2026-09-30). **Build NOT started**; it waits for Amirul's explicit go. Next: M0 (doc 06 Phase 0), after `/plan` on the Deep model

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
- [ ] Is the DOSM monthly supply series still updated after Sep 2024? — doc 02
