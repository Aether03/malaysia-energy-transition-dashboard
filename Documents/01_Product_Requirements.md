# 01 — Product Requirements: Malaysia Energy Transition Dashboard

**Status:** Approved 2026-09-30 · **Updated:** 2026-09-30 · **Owner:** Amirul · **Next:** 02 Technical Requirements

> Labels: **Decided** = settled by you, don't reopen. **Recommended** = Claude's best-practice proposal, which you can change. **Unverified** = must be checked against a real source before we rely on it.

## 1. Overview

### What it is
An **end-to-end energy analytics project** that answers one question:

> **"How fast is Malaysia's electricity system decarbonising, and how does it compare with its ASEAN neighbours?"**

Public electricity data is collected automatically, cleaned and modelled in a SQL database, and presented as an interactive Power BI report. Everything (code, SQL, report file, screenshots, and a write-up of the findings) is published as a public GitHub repo.

### The problem it solves (for you)
Your CV already shows energy domain depth (EE degree, protection & control, battery-SOC research). It doesn't yet show **proof that you can build a production-style data pipeline and a BI product on real industry data**. This project closes that gap in one artefact that a recruiter can skim in 30 seconds and an engineering interviewer can dig into for 30 minutes.

### Personas
| Persona | Priority | What they look for | What must impress them |
|---|---|---|---|
| **Energy data / ML engineer hiring manager** (e.g. energy-tech firms, utility digital teams) | 1st — **Decided** | Can this person build reliable data pipelines? | Automated, re-runnable ingestion; data-quality checks; tidy repo; a sensible forecast with honest limits |
| **Power utility / grid engineer interviewer** (e.g. TNB, Hitachi Energy, Siemens Energy) | 2nd — **Decided** | Does this person understand the power system, not just charts? | Correct domain KPIs (generation mix, carbon intensity, capacity factor, demand growth), correct units, national-target context |
| **Data / BI analyst recruiter** (MNC shared-service and analytics teams in Penang/KL) | 3rd — **Decided** | SQL + Power BI skills, clean visuals, clear insights | Star schema, DAX measures, polished and consistent report pages, findings in plain English |

### Where it stands
New project. No code, data or tools installed yet (SQL Server and Power BI Desktop still need installing — see index).

## 2. Goals and objectives

| # | Goal | Measure |
|---|---|---|
| G1 | Demonstrate a working **data pipeline**: source → SQL → report | One command rebuilds the database from the public sources on a clean machine |
| G2 | Demonstrate **energy-domain insight** | At least 3 written, data-backed findings about Malaysia's transition in the README |
| G3 | Demonstrate **SQL and Power BI craft** | Star-schema model, documented SQL queries and DAX measures, a 6-page report |
| G4 | Be **viewable by anyone** without Power BI | Screenshots, an animated GIF/short video and a PDF export in the repo. After v1, a public web showcase link (FR-21) |
| G5 | Finish at portfolio quality, not endlessly | **Decided:** no fixed deadline ("at your pace"). Doc 06 sets milestones so progress stays visible |

### Non-goals / out of scope (v1)
- **Live or streaming data.** Hourly grid data is **in scope** as a historical download (FR-22), but the report is refreshed by a re-run, not in real time.
- **Electricity prices, tariffs and bills.** Different data sources, different story.
- **User accounts, login or row-level security.** It's a public showcase.
- **Cloud-hosted database or paid services.** The database runs locally for free (**Decided**: free tools only). The post-v1 web showcase (FR-21) uses exported snapshots on a free host, not a cloud database.
- **A custom-built web app in v1.** Power BI is the v1 front end. The web showcase follows once the dashboard is complete (**Decided**, see FR-21).
- **State-level generation or consumption.** No open source publishes these by state. State-level analysis covers **grid reliability** (SAIFI/SAIDI), plus Peninsular / Sabah / Sarawak for generation, capacity and demand (FR-23, FR-24).

## 3. Requirements

Priority uses MoSCoW: **M**ust / **S**hould / **C**ould.

### 3.1 Functional

**Data pipeline (for the energy data/ML engineer audience)**
| ID | Requirement | Priority | How to verify |
|---|---|---|---|
| FR-01 | Public electricity data for Malaysia and ASEAN peers is downloaded automatically by a script. No manual copy-paste. | M | Delete the local data, run one command, and the data reappears |
| FR-02 | Loading is **re-runnable**: running it twice doesn't create duplicates, and a newer source release updates existing rows. | M | Run twice; row counts are unchanged; spot-check values |
| FR-03 | **Data-quality checks** run on every load (missing years, negative values, generation shares not summing to about 100%, unit sanity) and record pass/fail results. | M | Inject a bad row and the check fails and is logged |
| FR-04 | Raw, cleaned and analysis-ready data are kept in separate, documented layers. | M | Layers are visible in the database and described in the README |
| FR-05 | Each load records when it ran, which source version was used and how many rows were loaded. | S | Load log table/view is populated after a run |

**Report content (for all audiences)**
| ID | Requirement | Priority | How to verify |
|---|---|---|---|
| FR-06 | **Overview page** with headline KPIs for Malaysia's latest year: total generation, renewables share, fossil share, carbon intensity, and year-on-year change for each. | M | Numbers match the SQL reconciliation query (FR-15) |
| FR-07 | **Generation mix over time** for Malaysia, by source (coal, gas, hydro, solar, bioenergy, other). | M | Visual shows every year in range; shares sum to about 100% |
| FR-08 | **ASEAN comparison**: Malaysia vs selected peers on renewables share, carbon intensity and per-capita demand, with Malaysia's rank. | M | Changing the country selection updates all visuals |
| FR-09 | **Emissions view**: carbon intensity (gCO₂/kWh) and total power-sector emissions over time, Malaysia vs peers. | M | Units are shown; values match source spot-checks |
| FR-10 | **Progress vs national targets**: Malaysia's renewable-energy share of installed capacity against the NETR targets of **31% by 2025, 40% by 2035 and 70% by 2050** (per MIDA/IEA summaries of NETR, July 2023; the primary NETR document is to be cited in doc 02). | M | Target line cites its source document |
| FR-11 | **Utility-engineer KPIs**: demand growth rate, per-capita demand, and **capacity factor by source** (Ember publishes capacity in GW alongside generation). | M | KPI definitions are shown in tooltips; formulas documented |
| FR-12 | **Interactive filters**: year range, country, region, energy source. Visuals cross-filter each other. | M | Manual click-through test |
| FR-13 | **Forecast** (**Decided: in v1**). Primary: a **day-ahead load forecast** for Peninsular Malaysia from the hourly GSO data (FR-22), compared against a naive seasonal baseline. Fallback, if GSO history proves too short: an annual demand and renewables-share projection to 2030. Method, error metric (e.g. MAPE on a held-out period) and limitations are shown. | M | Backtest error and baseline comparison are reported; a disclaimer is visible |
| FR-14 | **"About the data" page**: sources, licences, last refresh date, data-quality results and KPI definitions. | M | Page is present and current after a refresh |
| FR-15 | **SQL showcase**: a documented set of analytical queries (trends, rankings, year-over-year using window functions) that reproduce the report's headline numbers. | M | Query outputs equal the report KPIs |

**Added after review, 2026-09-30: grid, regional and state views (for the utility/grid engineer audience)**
| ID | Requirement | Priority | How to verify |
|---|---|---|---|
| FR-22 | **Grid load page (Peninsular Malaysia)**: historical system demand from GSO, showing typical daily load curves (weekday vs weekend), monthly peak demand, load factor, and the solar generation profile where GSO publishes it. | M, if GSO data verifies in doc 02; otherwise dropped | Peak and load-factor values match a manual calculation on one sample week |
| FR-23 | **Regional view**: Peninsular Malaysia vs Sabah (incl. Labuan) vs Sarawak, covering installed and available capacity (by fuel), electricity consumption and use per person, supply interruptions and SAIFI from the Energy Commission handbook. **As built (M4 Q3):** "generation" became "consumption", because no upright handbook table splits generation by region (the per-utility p.81 table is printed rotated and is excluded). | M | Figures match the handbook tables for two sample years |
| FR-24 | **State grid-reliability view**: SAIFI and SAIDI (both published by state) for the 13 Peninsular states and federal territories, 2015–2022, as a ranked chart plus a map, with a trend for the selected state against the Peninsular total (**as built, M4**: on its own page, P3b; small multiples didn't fit). | M | Values match the handbook's by-state tables for two sample years |

**Added after review: post-v1 web showcase**
| ID | Requirement | Priority | How to verify |
|---|---|---|---|
| FR-21 | **Public web showcase** after the Power BI dashboard is complete. It's a lightweight interactive web version, recommended on Streamlit Community Cloud (you already host HA-PIT there), reading exported data snapshots instead of the local database. The link goes on your future portfolio website. | S (post-v1) | Public URL loads in a private window; numbers match the Power BI report |

**Portfolio packaging (for the recruiter at a glance)**
| ID | Requirement | Priority | How to verify |
|---|---|---|---|
| FR-16 | README opens with the headline question, 3+ findings, a hero screenshot and an architecture diagram. | M | Someone new can state one finding within 30 s |
| FR-17 | The report can be seen without Power BI: page screenshots, a GIF or ≤2-min video walkthrough, and a PDF export. | M | All visible in the repo on GitHub |
| FR-18 | Setup guide lets someone reproduce everything on a clean Windows PC. | M | Fresh-clone rebuild succeeds following only the README |
| FR-19 | Optional live Power BI link ("Publish to web") using the UiTM account. It's still active but likely to expire in early 2027, so it's a short-lived extra; FR-21 is the durable link. | C | Link opens in a private browser window |
| FR-20 | Project linked from your GitHub profile repo and LinkedIn Featured section. | S | Links are present |

### 3.2 Non-functional
| ID | Requirement |
|---|---|
| NFR-01 **Performance** | Each report page renders in about 3 s or less on your PC. A full pipeline run takes under 5 minutes. |
| NFR-02 **Reproducibility** | Pinned tool and package versions. Setup from a clean clone takes under 30 minutes, excluding tool installs. |
| NFR-03 **Accuracy** | Headline figures reconcile to source within ±0.5%. Every KPI has a written definition and unit. |
| NFR-04 **Accessibility** | Colour-blind-safe palette, WCAG AA text contrast, alt text on report visuals, and no information carried by colour alone. |
| NFR-05 **Security / privacy** | No passwords, connection strings with secrets, or personal data committed to the repo. Public data only. **As built (M5):** two handbook figures and two third-party email addresses were removed from every commit before publication (`docs/history_rewrite.md`); gitleaks finds 0 in all history. |
| NFR-06 **Licensing** | Every dataset's licence permits redistribution and is credited as its licence requires (e.g. CC BY). |
| NFR-07 **Maintainability** | Report stored in a text-diffable format if possible (**Unverified**: Power BI Project/PBIP, to check in doc 02). SQL and Python are formatted and commented. |
| NFR-08 **Platform** | Windows 11 (Power BI Desktop is Windows-only). Viewers need only a web browser. |

### 3.3 Design, development and deployment
- **Design:** Claude drafts the report layout and visual system (doc 04). You approve it. It uses one consistent theme that fits an energy/utility setting.
- **Build:** Claude builds with you, task by task, following doc 06. You install tools and run things that need your accounts or GUI clicks.
- **Ship:** public GitHub repo under `Aether03`. The live Power BI link is optional (FR-19).

## 4. User experience

**Journey A: recruiter skim (30 seconds).** They open the GitHub link from your CV or LinkedIn. The README shows the question, a hero image of the dashboard and three bold findings (e.g. "Malaysia's renewables share rose from X% to Y% since 2015, but trails Vietnam"). They know what you built and that it's real data.

**Journey B: hiring manager deep dive (10–30 minutes).** They scroll to the architecture diagram, open the pipeline code and data-quality checks, skim the SQL showcase, and watch the video walkthrough. They leave convinced you can build and maintain a pipeline.

**Journey C: interview demo (live, 5 minutes).** You open the report and walk through the six pages (**Recommended** order; confirmed in doc 03): Overview → Malaysia generation & targets → Regions & state reliability → Grid load & forecast → ASEAN comparison → About the data. You answer "how do you know these numbers are right?" by showing the reconciliation query and the About-the-data page.

**Tone:** professional, calm, engineering-grade, like a utility's internal analytics report rather than a marketing infographic. Findings are stated plainly with numbers and caveats.

**Accessibility:** see NFR-04. Every chart has a title that states its takeaway, not just its subject.

## 5. Success metrics

| Metric | Target | How measured |
|---|---|---|
| Recruiter comprehension | A non-technical friend can state the main finding within 30 s of opening the README | Ask 1–2 people |
| Reproducibility | A fresh clone rebuilds the database and passes all data-quality checks | Run on a clean folder before launch |
| Accuracy | 5 randomly chosen headline figures match the source within ±0.5% | Reconciliation checklist |
| Completeness | All **Must** requirements pass their verification | Checklist in doc 06 |
| Visibility | Linked on GitHub profile and LinkedIn | Links present |
| Outcome (lagging) | Mentioned or asked about in at least one interview | Your job tracker |

## 6. Assumptions, dependencies and risks

### Data sources and credits (researched 2026-09-30)
Every source below will be credited in the README and on the "About the data" page, in the form its licence requires.

| # | Source | What it gives us | Granularity | Licence / reuse | Role |
|---|---|---|---|---|---|
| D1 | **Ember** — Yearly & Monthly Electricity Data ([yearly](https://ember-energy.org/data/yearly-electricity-data/), [monthly](https://ember-energy.org/data/monthly-electricity-data/)) | Generation by source (TWh, %), capacity (GW), emissions (MtCO₂e), emissions intensity (gCO₂e/kWh), demand, net imports. Covers Malaysia and all ASEAN peers | Yearly and monthly; updated twice a month | **CC BY 4.0**: redistribution allowed with credit | **Primary**: national and ASEAN pages |
| D2 | **Our World in Data** — Energy dataset ([GitHub](https://github.com/owid/energy-data), [CSV](https://owid-public.owid.io/data/energy/owid-energy-data.csv)) | Long history, per-capita electricity, carbon intensity, population for per-capita KPIs | Yearly | **CC BY 4.0**: cite OWID and its underlying sources | Secondary: back-fills history and cross-checks D1 |
| D3 | **Department of Statistics Malaysia (DOSM)** via data.gov.my / OpenDOSM ([supply](https://data.gov.my/data-catalogue/electricity_supply), [consumption](https://data.gov.my/data-catalogue/electricity_consumption)) | Monthly electricity supply and consumption by sector (million kWh). Originally from TNB, SESB, SEB and the Energy Commission | Monthly; CSV, Parquet and API | **CC BY 4.0** (credit the Government of Malaysia) | **Cross-check only** (WARN-level DQ rule, no report page): the series ends **Jun 2024** (verified in doc 05; decided 2026-09-30) |
| D4 | **Grid System Operator (GSO)** — [System Demand](https://www.gso.org.my/SystemData/SystemDemand.aspx), [Solar](https://www.gso.org.my/SystemData/Solar.aspx), [Generation Mix](https://www.gso.org.my/SystemData/CurrentGen.aspx) | Peninsular Malaysia system demand. The page has a from/to date picker and a download button | Intraday (**Unverified**: half-hourly or hourly, and how far back) | **Unverified**: GSO Terms & Conditions to be checked in doc 02 | Grid load page (FR-22) and the day-ahead forecast (FR-13) |
| D5 | **Energy Commission (Suruhanjaya Tenaga)** — [Malaysia Energy Statistics Handbook 2023](https://www.st.gov.my/sites/default/files/2026-02/Malaysia_Energy_Statistics_Handbook_2023.pdf) and earlier editions; [MEIH portal](https://meih.st.gov.my/) | Peninsular/Sabah/Sarawak capacity and supply performance; **SAIFI by state 2015–2022** (confirmed on p.84 of the 2023 edition) | Yearly (PDF tables) | **Restricted**: MEIH terms allow private use only and require written consent from the Energy Commission for reproduction. The handbook's own copyright page (p.5) is stricter: all rights reserved, prior written consent for any reproduction, excerpts credited "Source: Energy Commission" (`DATA_LICENSES.md`) | Regional and state views (FR-23, FR-24). Handled as described in risk R3 below. **As built (M4):** 2023 edition only (the 2022 edition is a local check input); extracted at runtime, nothing committed, derived charts with a consent notice |
| D6 | **National RE capacity targets**: 31% (2025) and 40% (2035) from the 12th Malaysia Plan / [SEDA MyRER](https://www.seda.gov.my/reportal/myrer/) (2021); 70% (2050) from the NETR (Ministry of Economy, 2023). Current pathway: 35% by 2030. Official progress: 31% as of Dec 2025 (Deputy PM, Jul 2026). All use the ASEAN definition, **including large hydro and off-grid** (verified in M2 step 1, 2026-09-30; see `plans/M2_plan.md`) | RE share of installed capacity: 31% (2025), 40% (2035), 70% (2050) | Policy targets | Facts, cited | Target line (FR-10) |
| DTH | **Thailand national grid (EGAT)** via [Zenodo record 17109911](https://doi.org/10.5281/zenodo.17109911) v1.0 | Hourly demand of the 5 regions, generation, and interconnector flows (incl. Malaysia), 2023–24 | Hourly | **CC BY 4.0** | P4 grid load and the day-ahead forecast: the open-data stand-in for D4 until TNB consents (M3) |
| DSG | **Singapore Energy Market Authority (EMA)** — [half-hourly system demand](https://www.ema.gov.sg/resources/statistics/half-hourly-system-demand-data) | System and NEM demand, weekly workbooks | Half-hourly (shown hourly) | **Singapore Open Data Licence v1.0** | P4 second grid (ASEAN peer), selected in the grid selector (M3) |

**ASEAN grid search (M3 step 2, 2026-10-03; `docs/grid_sources.md`).** Leads were checked against four criteria: hourly or finer demand for 2023–24, a reuse licence, download without login or scraping, and a stable format. Only **Singapore EMA** qualified and was added (Amirul). The Philippines failed (IEMOP keeps only about 90 days of data and its terms forbid reproduction). Viet Nam (NSMO) and Indonesia (PLN) are **unverified**: their sites were unreachable and no open hourly series was found. The other ASEAN grids publish daily or annual data only. Re-checking Viet Nam and Indonesia is on the v2 list.

**Also found, not used in v1:** a Johor hourly load dataset for 2009–2010 on [Kaggle](https://www.kaggle.com/datasets/pattnaiksatyajit/hourly-load-data) (licence unknown, and old). The Thailand and Singapore sources above were found via [Awesome-Electricity-Demand](https://github.com/open-energy-transition/Awesome-Electricity-Demand); both are now used (DTH, DSG).

**Assumptions**
- SQL Server Developer edition and Power BI Desktop are free to install and use for this purpose. **Unverified**: licence terms are confirmed in doc 02.
- ASEAN peer set (**Recommended**, not objected to): Indonesia, Thailand, Vietnam, Philippines and Singapore.
- No findings are assumed up front: the headline insights come out of an exploratory analysis step in the build (doc 06).

**Dependencies**
- Installing SQL Server, a SQL client and Power BI Desktop on your PC (you do these; guided in doc 06).
- A GitHub account (you have `Aether03`).

**Risks**
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| R1: UiTM account deactivated (likely early 2027), or its admin blocks "Publish to web" | High | Low | GitHub-first showcase (FR-17) plus the Streamlit web showcase (FR-21). The Power BI link is only a **Could**. |
| R2: GSO history too short, its download too coarse, or its terms forbid reuse | Medium | Medium | Verify in doc 02. Fall back to an annual forecast (FR-13) and drop FR-22. |
| R3: Energy Commission (D5) data can't be redistributed without written consent | High (it's in their terms) | Medium | (a) The repo holds the **extraction script**, not ST's raw data; the pipeline pulls the public PDFs at build time. (b) Charts show derived figures with full credit. (c) **Recommended:** email the Energy Commission for written consent. I'll draft it; you send it. If refused, the regional and state pages stay in the local report and screenshots are reviewed before publishing. |
| R4: DOSM monthly series discontinued after 2024 | Medium | Low | Used only for the sector breakdown and a cross-check. Ember monthly data covers national trends. |
| `.pbix` binary files don't diff in Git, so the history is useless | Medium | Low | Use the PBIP text format if verified (NFR-07). |
| Scope creep (prices, hourly data, a web app) | Medium | High | Non-goals list. Ideas go into a v2 backlog instead. |
| Forecast looks naive to an ML interviewer | Medium | Medium | Keep it simple but honest: baseline comparison, backtest error, stated limits. |

## 7. Fixes & improvements
Not applicable: this is a new project with nothing built yet.

## 8. Open questions
Resolved in review 2026-09-30: forecast in v1 (FR-13); UiTM account active until about early 2027 (FR-19); no deadline, at Claude's pace (G5); datasets researched and credited (§6); no prior hunches (findings come from the analysis); hourly data in scope (FR-22); post-v1 web showcase (FR-21); regional and state analysis in scope (FR-23, FR-24).

Also resolved: **Energy Commission consent (R3)**. You'll send the consent email **after the dashboard is complete** (Claude drafts it). Until a reply arrives, the public repo carries the extraction script and credited, derived charts only, never ST's raw tables. **GSO data (D4)** gets verified hands-on in doc 02.

Nothing open blocks approving this document.
