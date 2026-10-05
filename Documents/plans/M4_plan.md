# Plan: M4 — Regions and state reliability

**Source:** [06 Implementation Plan](../06_Implementation_Plan.md) Phase 4 (tasks 4.1–4.4) · **Complexity:** Medium-Large (about 2 sessions; the PDF parser and its independent re-read are the slow, careful parts) · **Status:** APPROVED 2026-10-05 in the plan canvas (Q1–Q9 accepted as proposed); in progress

## Summary
M4 adds the Malaysian regional and state view (FR-23, FR-24):
1. A test-first `pdfplumber` parser lands the pinned handbook tables, exactly as printed, in `raw.handbook_cell`, at runtime only.
2. An independent agent re-reads every landed cell from the PDF page images, blind, before anything reaches `dw`.
3. `stg`/`dw` build `fact_region_annual` and `fact_state_reliability`, with arithmetic DQ rules that catch silent number errors.
4. P3 shows the region cards, a state Shape Map, a ranked bar and a selected-state trend (small multiples ruled out by the step 1 spike), with a SAIFI/SAIDI toggle. It carries the handbook credit, the consent notice and the ODbL credit.

## Requirements restated
| FR | What M4 must deliver | Where |
|---|---|---|
| FR-23 | Peninsular vs Sabah vs Sarawak: installed capacity, available capacity, electricity consumption (generation isn't split by region in any upright table; see Q3) | P3 Regions |
| FR-24 | SAIFI, and SAIDI (it **is** published by state), by Peninsular state, 2015–2022: ranked bar, map and a trend per state | P3b State reliability |
| R3 / D5 | Runtime-only extraction; nothing from the handbook committed; credited, derived charts with a consent notice | Repo, P3, P3b |
| 4.2 | geoBoundaries MYS ADM1: all 16 shapes join to `dim_state`, none unmatched | `seed/`, `report/maps/` |
| M4 acceptance | P3 values match the handbook for 2 sample years; credits and the consent notice visible | doc 06 Phase 4 |

## Facts verified before planning (2026-10-05, profiled in the scratchpad, nothing committed)
**The handbook (D5)**
- **The 2023 edition is the latest.** The Energy Commission's download listing has 2023 (published 19 Aug 2025) and 2022 (12 Jul 2024); there is no 2024 edition.
  - The pinned URL `st.gov.my/sites/default/files/2026-02/Malaysia_Energy_Statistics_Handbook_2023.pdf` is live: 8,046,592 B, Last-Modified 31 Mar 2026. Our local copy has MD5 `ba481c7f…6b96c`.
  - The printed page number equals the PDF page index.
- **Its own copyright page (p.5) is stricter than the MEIH portal terms.** It says "All rights reserved", and reproducing any part needs prior written consent. Any excerpt must be quoted as **"Source: Energy Commission"**. That exact wording goes in every credit.
- **"2023 edition" ≠ 2023 data.** State reliability runs 2015–2022, regional key data 2015–2021, and the capacity tables are as of 31 Dec 2021.
- **Tables usable for M4** (all upright text, so `extract_words` reads them in order):

| Page | Table | Shape | Years |
|---|---|---|---|
| 13 | Installed capacity by region × fuel (MW), with utility rows inside each region block | 3 blocks + Subtotal rows, 10 columns | 31 Dec 2021 |
| 14 | Available capacity by region × fuel (MW) | 3 rows + Total, 7 columns | 31 Dec 2021 |
| 17–19 | Key economic and energy data by region (population, electricity consumption GWh, kWh per capita, …) | 1 page per region, 11 rows (labels wrap over 2–3 lines) | 2015–2021 |
| 82 | Number of electricity supply interruptions by region | 13 years × 3 regions | 2010–2022 |
| 83 | Peninsular distribution performance (summary) + **SAIDI by state** | 5 rows; 13 states + total row | 2015–2022 |
| 84 | **SAIFI by state** + CAIDI by state | 13 states + total row, each | 2015–2022 |
| 85 | Sabah and Sarawak distribution performance (SAIDI, SAIFI, CAIDI) | 5 rows / 3 rows | Sabah 2015–2022; Sarawak see below |

  - **p.81** (maximum demand and units generated or sold, per utility, 2019–2022) is printed **rotated**. `pdfplumber` returns each number with its digits reversed. It is also per utility, not per region. **Excluded** (Q3).
- **The 13 "states"** are 11 states plus WP Kuala Lumpur and "WP Putrajaya (including Cyberjaya)". The latter's label wraps over two lines, around the value line. Labuan, Sabah and Sarawak have no state rows.
- **The PDF disagrees with itself in three places** (Q4):
  1. **Peninsular totals:** p.83's Peninsular summary and p.84's total row disagree in 3 cells (SAIFI 2022, CAIDI 2017 and 2022). Only p.84's figures are consistent with SAIDI ÷ SAIFI.
  2. **Sarawak's year header reads `2014 … 2019 2020 2019`.** The last column's year is printed wrong (probably 2021, unproven).
  3. **CAIDI ≈ SAIDI ÷ SAIFI** holds within rounding for 92 of 112 state-year cells. The other 20 are a block of 2015–2018 for Pahang, Perak, Perlis and Pulau Pinang, plus Terengganu 2017, the 2017 total, and two Putrajaya cells where SAIFI rounds to zero. All of 2019–2022 is consistent.
- **Built-in arithmetic checks:**
  - p.13: subtotals add up to the Total row.
  - p.14: the rows add up too.
  - p.17: per capita equals consumption ÷ population.
  - Sabah includes Labuan in the regional data (p.18 note).

**The boundaries (GEO)**
- **geoBoundaries `MYS-ADM1-15666254`** (gbOpen, 2017 boundaries, ODbL 1.0, OSM via Wambacher), pinned at commit `9469f09`.
  - **The TopoJSON is the full-resolution file, 795,812 B.** geoBoundaries publishes the *simplified* version only as GeoJSON, which corrects doc 03's "simplified TopoJSON".
  - It has 1 object, 16 geometries, and the properties `shapeName`, `shapeISO`, `shapeID`, `shapeGroup` and `shapeType`.
- **shapeName uses English exonyms.** These need aliases: `Malacca` (handbook "Melaka"), `Penang` ("Pulau Pinang"), `Kuala Lumpur` ("WP Kuala Lumpur") and `Putrajaya` ("WP Putrajaya (including Cyberjaya)"). Every shape also carries its ISO 3166-2 code (`MY-01` … `MY-16`), which is a stable alternative join key (Q6).

**Repo state:** nothing for M4 exists yet. `report/maps/` is empty, the next migration is **V015**, `pdfplumber 0.11.10` is already pinned, and D5 is seeded as `NOT_REQUESTED` / `is_publishable = 0`.

## Decisions for your approval
| # | Question | Proposed |
|---|---|---|
| Q1 | **D5 licence handling, and what it means for the repo and P3** | **Confirm the agreed handling:** extract at runtime only; never commit the PDFs or extracted tables; show derived, credited charts with a consent notice. Concretely:<br>**Never committed:** the PDF (`data/raw/handbook/<date>/` and `docs/references/` are git-ignored); `raw.handbook_cell` and every extracted CSV; the reviewer's transcription and the local golden test's expected values (new git-ignored `data/private/`); the database, `.pbix` and `.abf` cache.<br>**Committed:** `handbook.py` (code); page pins, table titles and the file MD5 (metadata, not data); **synthetic** test fixtures (Q8); seeds of state names and aliases (public facts); SQL, DAX and report layout; the TopoJSON (ODbL); docs that record **counts and pass/fail only, never handbook values** (`docs/reconciliation.md`, findings).<br>**A guard test** fails if `git ls-files` contains a `.pdf` or anything under `data/`, or if a fixture lacks its synthetic marker.<br>**On P3/P3b:**<br>• no table or matrix visual reproducing a handbook grid;<br>• data labels only on the ranked bar (one year), values otherwise in hover;<br>• every chart adds something derived (rank, change since 2015, trend, ratio);<br>• credit "Source: Energy Commission, Malaysia Energy Statistics Handbook 2023" on both pages.<br>**The consent notice is a measure on `dim_data_source.consent_status`.** Today it reads "…written permission to be requested", because D5 is `NOT_REQUESTED` and doc 03's "permission requested" would be untrue until you send the email. It flips to "permission requested" when the seed changes to `REQUESTED`.<br>**Flagged for M5 task 5.8:** the P3 PNG and PDF exports (task 5.4) are the only place handbook-derived figures would enter the public repo. The 5.8 audit decides whether they ship before consent. The Streamlit mirror (M6) already excludes P3 and D5 (`is_publishable = 0`) |
| Q2 | Which editions | **2023 edition only as data** (the latest; 8 years of state data). The **2022 edition is a check-only input** that is never parsed. It goes to `data/private/`, and the step 7 reviewer reads two things in it: Sarawak's last column, to settle Q4.2, and the 2015–2018 cells of the four inconsistent states, to see whether they were revised. The pin structure (`edition → table → page + title`) still allows another edition later |
| Q3 | Which tables and metrics | Land **whole** tables from pp. 13, 14, 17–19, 82, 83, 84 and 85, exactly as printed (raw = exact copy, the M3 Q1 lesson); CAIDI and the p.83 summary are landed **for checks only**.<br>**Region metrics in `fact_region_annual`:** `INSTALLED_MW` and `AVAILABLE_MW` (2021, also by fuel group), `ELEC_CONSUMPTION_GWH`, `ELEC_PER_CAPITA_KWH` and `POPULATION_K` (2015–21), `SUPPLY_INTERRUPTIONS` (2010–22), and `SAIFI`/`SAIDI_MIN` per region (PEN from p.84/p.83 total rows; SAB and SAR from p.85).<br>**p.81 is excluded:** it is rotated, so digits come out reversed (silent-error risk), and it is per utility. Regional generation and peak demand therefore aren't shown; FR-23's "generation" becomes "consumption", with a doc 01 edit |
| Q4 | The PDF's internal inconsistencies | **Store as printed; never correct silently; disclose.**<br>(1) **Peninsular regional SAIFI/SAIDI** come from the state tables' total rows (p.84/p.83), the only internally consistent figures. A WARN rule, `HANDBOOK_PEN_TOTALS_AGREE`, lists the 3 p.83 summary disagreements.<br>(2) **Sarawak's last column is excluded** unless the 2022 edition (Q2) proves its year. If it does, a pinned `col_year_override` cites that page; otherwise Sarawak shows 2014–2020. Either way a footnote explains it.<br>(3) **`CAIDI_CONSISTENT`** is a WARN with the 20 cells registered as known exceptions in `docs/reconciliation.md` (as cell ids, without values), so any *new* mismatch is a parse error. P3b gets a footnote: "The handbook's 2015–2018 figures for four states are internally inconsistent (CAIDI ≠ SAIDI ÷ SAIFI); shown as published" |
| Q5 | **Page density: split P3** (M3 lesson: split rather than grow) | **P3 Regions + P3b State reliability**, with the budget below. One page would need about 640 px of the 568 px between the header and footnote. Nav rail: "Regions" and "State reliability" (8 buttons fit) |
| Q6 | Map join key and the 3 unreported shapes | `dim_state` holds **both** `geo_shape_name` (exact `shapeName`) and `iso_3166_2`. Step 1's spike decides which one Shape Map keys on: ISO if it offers that property, since it doesn't depend on spelling.<br>Sabah, Sarawak and Labuan are grey "not reported by state", with a note pointing to the Regions page. Their region values aren't painted on the map: Sabah's SAIFI is an order of magnitude higher and would wash out the Peninsular colour scale.<br>Footnote: "Putrajaya includes Cyberjaya" |
| Q7 | SAIFI/SAIDI toggle | A **disconnected `'Reliability Metric'` table plus one SWITCH measure** (`[Reliability Value]`, with unit and title measures). One measure feeds the map's colour, the bar and the trend line. A field parameter (the M2 pattern) isn't used, because Shape Map's colour well may not accept one. The step 1 spike tests the SWITCH measure in the map |
| Q8 | Test fixtures can't contain handbook numbers | **Two-layer parser.** A thin `pdfplumber` layer turns a page into words with positions, and a **pure** layer turns words into cells.<br>**Committed fixtures** are real page word layouts with **every numeric token replaced** by synthetic values, made by `tools/make_handbook_fixture.py`. The tool asserts that no original number survives and stamps `"synthetic": true`. They keep every trap: the wrapped Putrajaya label, `0.8` vs `0.80`, `-` dashes, thousands commas, the duplicate `2019` header, the 2–3-line labels on p.17 and the p.13 region blocks.<br>**The real-PDF golden test** is local only: it is skipped when the PDF is missing, and its expected values are in `data/private/` (git-ignored) |
| Q9 | Year slicer and region-card clicks (doc 03) | P3b gets its **own** single-year slicer (2015–2022, default the latest), **not synced** with P1/P2/P5, whose years run to 2025 and would show blanks.<br>Region cards **don't filter**. P3b holds only Peninsular states, so a region filter would empty it. Clicking a Regions card is replaced by the map's "not reported" note (doc 03 edit) |

### Page budget (Desktop 2.158 limits, M3: category ≥ 20 px, legends need ~140 px, charts need ≥ 120 px, matrix headers ≥ 8 pt; content area x 192–1272, y 104–672)
| Page | Row | y / h | Content | Limit check |
|---|---|---|---|---|
| **P3 Regions** | 1 | 104 / 120 | 3 region cards (349 px each): installed MW, available MW, consumption GWh and kWh per capita, latest SAIFI. Each value labelled with **its own year** (2021 / 2021 / 2022, Sarawak 2020) | Card callouts: template `card_new` |
| | 2 | 240 / 200 | Left: capacity mix by region, 2021 (100% stacked bar, 3 bars, source palette). Right: consumption 2015–21 (line, 3 regions) | 3 categories ≫ 20 px; legends at 200 px ✓ |
| | 3 | 456 / 200 | Left: SAIFI by region, latest year (bar) plus the Sabah ÷ Peninsular ratio in its title. Right: supply interruptions 2010–22 (line, 3 regions) | ✓ |
| **P3b State reliability** | 0 | 104 / 44 | SAIFI \| SAIDI tile toggle, year dropdown, the Q4 note | — |
| | 1 | 156 / 340 | Shape Map (520 px) \| ranked bar (544 px, 13 states) | 13 × 20 = 260 px + title and axis = 320 ✓ |
| | 2 | 504 / 160 | **Selected-state trend** (changed after the step 1 spike, Amirul 2026-10-05): one line chart, the state clicked on the map or bar against the Peninsular total; nothing selected = Peninsular alone | 160 px ≥ 120 ✓; legend at 160 ✓. Small multiples were ruled out: 13 panels need ~1080 × 340 (6 × 3); 7 columns (154 px panels) become a placeholder at any height, and below ~340 px the panel titles vanish |

## Patterns to mirror
| Category | Source | Pattern |
|---|---|---|
| Source module | `pipeline/sources/thailand.py`, `_common.py` | MD5-pinned download to `data/raw/<src>/<date>/`; a header check that raises `SchemaMismatchError` (here: each pinned page's title text must be present); `records_from` → `merge_into` (#stage + MERGE with `EXCEPT`) |
| CLI and run log | `pipeline/cli.py:44-62` | Add `("D5", handbook)` to the `_extract_and_load` loop; each load in its own transaction |
| Transforms | `sql/transform/050_fact_grid_hourly.sql` | Numbered scripts (`070_`, `080_`), delete-and-reload in the caller's transaction; unknown values stay NULL |
| Views | `sql/views/R__stg_grid.sql`, `R__mart_m3.sql` | `R__` repeatable; explicit columns; `GO` between views |
| DQ rules | `seed/dq_rule.csv` | `check_sql` returns offending rows; BLOCKING or WARN; known WARNs registered in `docs/reconciliation.md` |
| Migrations | `V013__m3_review_hardening.sql` | `pk_/fk_/df_/ck_` names; grants in the same migration |
| Tests | `tests/test_thailand.py` + `tests/fixtures/thailand/` | pytest on small fixtures, no database; contract stubs first (M3 step 7) |
| Model and DAX | `tools/gen_tmdl.py`, `_Measures.tmdl`, `tools/dax_twin_check.py` | Generated tables; hand-written measures; one SQL twin per key measure (twins compare DAX with SQL, so no handbook value is written in the repo) |
| Report pages | `tools/build_p4_page.py`, `report_builder.py`, `tools/templates/` | Frame + Desktop-captured shapes; geometry constants with the Desktop limit noted beside each |

## Files to change
| File | Action | Why |
|---|---|---|
| `sql/migrations/V015__regions_and_reliability.sql` | CREATE | `raw.handbook_cell` (**key `edition, page, table_code, row_pos, col_pos`**; labels as printed, so duplicate labels such as p.13's repeated "IPPs" or Sarawak's two "2019"s fit; doc 05 edit), `ref.state_alias`, `dw.dim_region`, `dw.dim_state` (+ `iso_3166_2`), `fact_region_annual`, `fact_state_reliability` + grants |
| `seed/dim_region.csv`, `dim_state.csv`, `state_alias.csv`, `dq_rule.csv`, `kpi.csv`; `pipeline/seeds.py` | CREATE / UPDATE | 3 regions; 16 states (Labuan → SAB); every handbook label, plus the geo names; the step 8 rules; SAIFI/SAIDI KPI definitions (polarity −1) |
| `tools/fetch_map.py`, `report/maps/mys_adm1.topojson`, `report/maps/README.md` | CREATE | Pinned download (commit `9469f09`, SHA-256 checked), the 16-shape check, ODbL notice and credit |
| `pipeline/sources/handbook.py`, `pipeline/config.py`, `pipeline/cli.py` | CREATE / UPDATE | Task 4.1: the URL, MD5 and page pins; the two-layer parser; the D5 extract/load |
| `tools/make_handbook_fixture.py`, `tests/fixtures/handbook/*.json`, `tests/test_handbook.py`, `tests/test_handbook_pdf.py` (local only), `tests/test_no_restricted_data.py` | CREATE | Q8 fixtures, tests and the Q1 guard |
| `sql/views/R__stg_handbook.sql`, `sql/transform/070_fact_region_annual.sql`, `080_fact_state_reliability.sql` | CREATE | Task 4.3: typed cells, state aliasing, region blocks, fuel-group mapping, Q4 policies |
| `sql/views/R__mart_m4.sql`, `sql/showcase/12_regions.sql`, `13_state_reliability.sql` | CREATE | `mart.dim_region`, `dim_state`, `region_annual`, `state_reliability`, `reliability_metric`; SQL twins (rank, change since 2015, Sabah ÷ Peninsular ratio) |
| `report/.../tables/*.tmdl`, `_Measures.tmdl`, `tools/gen_tmdl.py`, `tools/dax_twin_check.py` | UPDATE | P3/P3b model, measures and twins |
| `tools/build_p3_page.py`, `build_p3b_page.py`, `build_report.py`, `report_builder.py` (`NAV`), `tools/templates/*` | CREATE / UPDATE | Task 4.4 |
| `.gitignore`, `DATA_LICENSES.md` | UPDATE | `data/private/`; the handbook's own p.5 wording; the TopoJSON redistributed under ODbL |
| `docs/reconciliation.md` | UPDATE | Re-read result (counts), arithmetic checks, Q4 known exceptions (cell ids only) |
| Docs 01 (D5 row, FR-23 wording), 03 (P3 split, Q6, Q9, consent text), 04 (nav), 05 (raw key, `iso_3166_2`, metric codes), 06 (status); `00_Index.md` | UPDATE | As-built decisions |

## Tasks (in build order)
**Model tiers (doc 06 §4):**
- **D** = Opus 5.5, this session.
- **S** = Sonnet 5.5 subagent.
- **GUI** = Power BI Desktop. I drive it via computer use, as in M3 round 3, if you agree. Desktop is launched with `Start-Process` and refreshed with `tools/model_refresh.ps1`.

**Escalation:** a step that fails verification twice moves up one tier (Deep → Fable 5.1).

**Every commit** comes after `validate_report.py` and `dax_twin_check.py`, with Desktop open. All 23 existing twins must keep passing.

**Desktop:** close it before `pipeline run`, and never rebuild pages while it is open.

| Step | Doc 06 | What | Model | Verify |
|---|---|---|---|---|
| 1 | GUI spike | **Template capture + spike, before P3 depends on anything.**<br>First a temporary DAX `DATATABLE` with 16 shapes and **synthetic** values, written while Desktop is closed. Then, on a scratch page:<br>• **Shape Map** with `mys_adm1.topojson`: which key works (ISO or name), colour from a measure, grey for blank;<br>• **SAIFI \| SAIDI tile + SWITCH measure** driving the map and a bar;<br>• **line chart with 13 small multiples** at 1080 × 160, then smaller, to find the placeholder threshold;<br>• a **3-callout card**.<br>Save, copy the JSON plus the registered-resource path, then close **without saving** and `git checkout -- report/` (M3 clean-up lesson) | GUI + D | The map renders all 16 shapes and greys the blanks; the toggle switches both visuals; the small-multiples minimum is recorded; templates committed. **If Shape Map fails:** fall back to the ranked bar and small multiples only, with your OK (doc 03 edit) |
| 1 → outcome | GUI spike | **Done 2026-10-05** (run by Claude via computer use; synthetic values only; Desktop closed and `report/` restored, validator 0 problems):<br>• **Shape Map works** with the full-resolution TopoJSON (no preview switch). Desktop stores the file as a registered resource (`StaticResources/RegisteredResources/<name><digits>.topojson`, listed in `report.json` with type `ShapeMap`) and the visual points at it with `ResourcePackageItem`. Its key list holds every property, and **`shapeISO` joins as well as `shapeName`**, so Q6 resolves to `iso_3166_2`. Shapes with no row render grey. The saved `projectionEnum` was `albersUsa` while the canvas showed Mercator, so the builder sets it explicitly and the GUI round checks it.<br>• **SAIFI | SAIDI tile + SWITCH measure** drives both the map colour and the bar (Q7 confirmed).<br>• **Small multiples:** the role is `Rows`; layout in `smallMultiplesLayout`. Limits: panels under ~170 px wide become a placeholder; a 3-row grid needs ~340 px of height for titles. **P3b row 2 changed to a selected-state trend** (your choice).<br>• Templates: `tools/templates/shape_map.json`, `line_chart_small_multiples.json`. The multi-callout card was skipped (the `card_new` template already exists) | — | — |
| 2 | 4.2, 4.3 | V015 (Q3 key) + `seeds.py` for the new seeds | D | `migrate` applies twice cleanly; FKs and grants present |
| 3 | 4.2 | Seeds (`dim_region`, `dim_state`, `state_alias`, KPI rows) + `fetch_map.py` + join test (runs in parallel with steps 4–5) | S | pytest: all 16 `shapeName` **and** `shapeISO` values equal `dim_state`, none unmatched; every handbook row label (from the fixtures' label list) maps through the alias table |
| 4 | 4.1 | `handbook.py` **contract as stubs**: page pins (`edition → table_code → page, title, column spec, row blocks`), MD5, `words_from_page()`, the pure `cells_from_words()`, `records_from()`. The docstrings are the spec, including the Q4 rules | D | Stubs import; every pinned page's title is found in the real PDF (local check) |
| 5 | 4.1 | `make_handbook_fixture.py` (run locally by me), then **tests first** (Sonnet brief names only the test files), on synthetic fixtures: every trap in Q8; row and column counts per table; `row_pos`/`col_pos` stability; a moved page fails with `SchemaMismatchError`; a changed MD5 fails; + `test_no_restricted_data.py` | S, Deep read before commit | Tests fail for the right reason (`NotImplementedError`); the fixture tool proves no original number survives |
| 6 | 4.1 | Implement the parser + the D5 extract/load into `raw.handbook_cell`; arithmetic checks as tests (local golden test: p.13 subtotals sum to Total, p.14 rows sum, p.17–19 per capita ≈ consumption ÷ population) | D | pytest green; raw cell count per table equals the pinned spec (about 970 cells); a re-run merges 0 rows |
| 7 | 4.1 review | **Independent, blind re-read.** Two fresh-context Opus agents (pp. 13–19 and pp. 82–85) get only the PDF, the page list and an **empty** grid of row and column positions; they never see the parser's output. They read the page images (Read with `pages`, zooming in) and write their transcriptions to `data/private/`.<br>The second agent also reads the **2022 edition** for Q2: Sarawak's year and the 4-state block.<br>`tools/compare_reread.py` then diffs **every** cell, not just 2 years. Each difference is settled by viewing the page, and its cause is logged.<br>Also **`ecc:python-reviewer`** on `handbook.py` | D (agents) + S (review) | **0 unexplained differences** across all cells; review findings fixed; counts (no values) in `docs/reconciliation.md` |
| 8 | 4.3 | `R__stg_handbook` + `070`/`080` + DQ rules:<br>• **BLOCKING:** `STATE_ALIAS_COMPLETE`, `NO_DUPLICATE_STATE_YEAR`, `CAPACITY_SUBTOTALS_SUM`, `RELIABILITY_NON_NEGATIVE`;<br>• **WARN:** `CAIDI_CONSISTENT` (20 known), `HANDBOOK_PEN_TOTALS_AGREE` (3 known), `PER_CAPITA_CONSISTENT`.<br>Then **`ecc:database-reviewer`** on V015 + views + transforms | D | 13 states × 8 years = 104 state rows; NULL where not reported (none expected, but the path is tested); **2015 and 2022 for every state equal the PDF** (the doc 06 sample years), plus regions 2015 and 2021; BLOCKING PASS; only the registered WARNs |
| 9 | — | `R__mart_m4` + showcase `12`/`13` | D | Spot values equal step 8; no `SELECT *` |
| 10 | 4.4 model | `gen_tmdl.py` tables and relationships; measures: `[Reliability Value]` SWITCH, unit and title, rank (1 = most reliable), change since 2015, "Not reported", the Sabah ÷ Peninsular ratio, the consent notice (Q1), takeaway titles and as-of years; twins | D | ≥ 6 new twins PASS (SAIFI rank 1 in 2022, Johor SAIDI change since 2015, PEN SAIFI 2022, Sabah ÷ PEN ratio, Sarawak installed MW, PEN consumption 2021); **all 23 old twins still PASS** |
| 11 | 4.4 | `build_p3_page.py` + `build_p3b_page.py` to the Q5 budget (one Sonnet agent, continued with SendMessage across rounds), then **≤ 2 GUI rounds** | S + GUI | `validate_report.py` 0 problems; click-through of every row of doc 03 P3's table (as amended); credits and consent notice visible on both pages |
| 12 | acceptance | Empty-DB rebuild (throwaway DB), twins, doc 01/03/04/05/06 edits, `DATA_LICENSES.md`, index, skill-test memory, push | D | The acceptance list below |

**Batching:**
- Step 3 (S) runs in parallel with steps 4–5.
- Steps 5 and 11 are separate Sonnet briefs; each names the only files it may touch, and gets a Deep read before commit.
- The two step 7 re-read agents run in parallel.

**GUI rounds:** step 1 (spike) and step 11 (≤ 2, the last one doubling as the final check), so **3 in total**, against 4 in M3.

**Session plan:**
- **Session 1:** steps 1–7. Step 7's agents start cold by design.
- **Session 2:** steps 8–12, resumed from the index.

## Definitions pinned for this milestone
| Measure | Definition | Note |
|---|---|---|
| SAIFI | Interruptions per customer per year, as printed (p.84) | Lower is better (polarity −1) |
| SAIDI | Minutes of interruption per customer per year, as printed (p.83) | Lower is better |
| Rank | 1 = lowest value among the 13 Peninsular entries in the selected year and metric | Ties share a rank |
| Change since 2015 | Value(year) − value(2015), in the metric's unit | Not a percentage: Putrajaya's near-zero base would explode it |
| Region | PEN = Peninsular Malaysia; SAB = Sabah **incl. Labuan** (p.18 note); SAR = Sarawak | Labuan's shape belongs to SAB |
| Capacity fuel groups (p.13/14 → doc 04 palette) | Major + Mini Hydro → hydro; Natural Gas → gas; Coal → coal; Diesel/MFO → other fossil; Biomass + Biogas → bio; Solar → solar; **Others → other fossil** | "Others" is unlabelled co-generation capacity; footnoted |
| Sabah ÷ Peninsular | SAIFI(SAB) ÷ SAIFI(PEN), same year | The headline ratio on P3 |

## Validation (end of M4)
```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pipeline db migrate
.venv/Scripts/python -m pipeline seed
.venv/Scripts/python -m pipeline run          # Desktop closed; exit 0; D5 loaded; only the registered WARNs
.venv/Scripts/python -m pipeline run          # 0 changed rows for D1-D5, DTH, DSG; forecast replay identical
.venv/Scripts/python tools/compare_reread.py  # 0 unexplained cell differences
.venv/Scripts/python tools/validate_report.py # 0 problems
.venv/Scripts/python tools/dax_twin_check.py  # all twins PASS (Desktop open)
git ls-files | grep -iE '\.pdf$|^data/'       # empty
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| **Silent PDF number errors** (a digit dropped, a column shifted, a wrapped label taking the wrong row) | Medium | Pinned pages and titles + MD5; two-layer parser tested on trap fixtures; arithmetic checks (sums, per capita, CAIDI); a blind vision re-read of **every** cell by independent agents |
| Handbook data accidentally committed | Medium | Git-ignored `data/raw` and `data/private`; synthetic fixtures with a marker; the guard test; docs record counts, not values; M5 task 5.8 audits history |
| Shape Map doesn't render the TopoJSON, or won't take a SWITCH measure | Medium | Step 1 spike before anything depends on it; fallback: bar + small multiples (your OK) |
| ~~Small multiples with 13 panels turn into placeholders at 160 px~~ | Happened | Step 1 confirmed it; replaced by the selected-state trend (your choice, 2026-10-05) |
| The independent re-read is itself wrong (vision misread) | Medium | Every difference is settled by looking at the page; two methods (text vs image) rarely fail on the same cell |
| Readers take the PDF's inconsistencies as our errors | Low | Q4 footnotes + `docs/reconciliation.md` |
| The PDF URL moves or the file is replaced | Low | MD5 pin fails loudly; the URL lives in config |
| RAM with Desktop + SQL Server | Medium | Standing rule: close Desktop before `pipeline run` |

## Acceptance (the doc 06 M4 check, plus)
- [ ] P3/P3b values match the handbook for 2 sample years: states 2015 and 2022, regions 2015 and 2021 (step 8), **and** the blind re-read shows 0 unexplained differences over all cells (step 7)
- [ ] Credits visible on P3 and P3b: "Source: Energy Commission…", the consent notice (driven by the status measure), and the ODbL boundaries credit
- [ ] All 16 shapes join to `dim_state`, none unmatched; Sabah, Sarawak and Labuan greyed and explained
- [ ] `git ls-files` holds no PDF, nothing under `data/`, and no handbook value (guard test + a review of `docs/` diffs)
- [ ] Empty-DB rebuild: `migrate && seed && run` exits 0; a second run merges 0 rows; forecast replay identical
- [ ] BLOCKING rules PASS; WARNs only the registered ones
- [ ] `ecc:python-reviewer` and `ecc:database-reviewer` findings resolved
- [ ] Twins: the new ones PASS and all 23 existing ones still PASS
- [ ] Doc 03 P3 click-through passes in Desktop (≤ 2 GUI rounds)
- [ ] Docs 01/03/04/05/06, `DATA_LICENSES.md`, the index and the skill-test memory updated; pushed
