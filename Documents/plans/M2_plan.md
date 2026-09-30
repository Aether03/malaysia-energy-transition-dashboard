# Plan: M2 — Malaysia and ASEAN analysis

**Source:** [06 Implementation Plan](../06_Implementation_Plan.md) Phase 2 (tasks 2.1–2.8) plus the M1 carry-overs · **Complexity:** Large (about 3–4 sessions; the GUI checks are the slow part) · **Status:** APPROVED 2026-09-30 in the plan canvas (all six decisions Q1–Q6 accepted, with the Q2/Q4/Q6 notes below); in progress

## Summary
M2 turns the one-page slice into the headline story:
1. OWID adds population, so demand per capita and the ASEAN per-capita comparison become possible. DOSM is added as a WARN-only cross-check.
2. One DAX measure library covers every M2 page, and each measure has a SQL showcase twin that proves it.
3. The report gets a shared page frame (nav rail and header). It is used by P1 (polished) and by P2, P5, D1, T1 and T2.
4. An exploratory pass produces three audited headline findings.

## Requirements restated
| FR | What M2 must deliver | Page |
|---|---|---|
| FR-06 | P1 complete: the 5th KPI card (demand per capita), the "vs ASEAN" rank card, 3 findings, and click-through to P2/P5 | P1 |
| FR-07 | Mix over time, TWh or % toggle, every year in range | P2, D1 |
| FR-08 | Malaysia vs selected peers on RE share, carbon intensity and per-capita demand, with a rank that follows the selection | P5 |
| FR-09 | Carbon intensity **and total power-sector emissions** over time, Malaysia vs peers (see decision Q1) | P5 |
| FR-10 | NETR line with target markers and a cited source, with the hydro definition verified | P2 |
| FR-11 | Demand growth (two aligned charts, F1), per-capita demand, capacity factor by source, with tooltip definitions | P2, T1 |
| FR-12 | Year-range, country and source filters that cross-filter (region waits for M4) | P2, P5, D1 |
| FR-15 | Documented SQL showcase queries that reproduce the report numbers | `sql/showcase/` |

## Facts verified before planning (2026-09-30)
- **OWID** (`owid-energy-data.csv`: 200 OK, 15.9 MB, last modified 27 Apr 2026; 23,377 rows × 130 columns). All the doc 05 §1.1 columns are present.
  - Population runs to **2025** for MY, KH, PH, SG, TH and VN. It **ends in 2024** for BN, ID, LA and MM.
  - OWID's own generation figure for Malaysia is **lower than Ember's**: 2023 187.8 vs 202.8 TWh (−7.4%), 2024 198.1 vs 211.2 (−6.2%), 2025 201.1 vs 210.4 (−4.4%).
  - **So the doc 05 "Ember vs OWID within ±5%" WARN rule will fire for Malaysia in 2023–24.** It is kept as a WARN, and the gap is documented on P6 and in the findings caveats.
- **DOSM** supply and consumption: last modified 12 Sep 2024, with data **Jan 2018 – Jun 2024**. This answers the index open question: the series has stopped.
  - Sectors: supply = `total, local, local_public, local_private, imports, distribution`; consumption = `total, local, local_commercial, local_domestic, exports, losses`.
  - DOSM total supply is **~10–12% below Ember generation** (2023: 177.7 vs 202.8 TWh). **So the ±10% WARN also fires**, probably because of a coverage difference (for example Sarawak or self-generation). The loader records it; the cause is researched only briefly (step 3) and stated as a caveat.
- Hand-check target for per capita: Malaysia 2025 = Ember demand 209.19 TWh × 10⁶ ÷ OWID population 35,977,834 = **5.814 MWh/person**. OWID's own figure is 5.556, from its lower demand.

## Decisions for your approval
| # | Question | Proposed |
|---|---|---|
| Q1 | FR-09 total emissions over time has no home in the doc 03 layouts | **Approved.** P5's trend chart gets a **metric toggle (RE share │ Carbon intensity │ Emissions MtCO₂e)** as a field parameter. Doc 03 P5 gets a one-line edit, logged in the index |
| Q2 | Per-capita basis | **Ember demand ÷ OWID population.** Combining them is sound, because population is an independent statistic (OWID takes it from UN WPP), not an electricity figure. But the choice of population series matters (see the note below the table) |
| Q3 | The nav rail (doc 04 §4) was not built in M1; P1 uses the full width | **Approved.** Build it now in a shared frame. P1's content moves to x 200–1256 |
| Q4 | Measures on P2 and D1 must follow the drill-through country | A **"country in context" pattern**: one country filtered → that country, otherwise Malaysia. P1 measures stay Malaysia-only. The data review is below the table |
| Q5 | DAX vs SQL twin check without the Power BI Service | **Approved.** Query Desktop's local Analysis Services instance from Python/PowerShell with the free **ADOMD.NET client (NuGet)**. Fallback: a hidden QA page that you screenshot |
| Q6 | Backlog: which review items to fold into M2 | Revised after checking the data (see the note below the table): **(a)** becomes a WARN rule, not a transform change; **(b)** is a naming convention in V008 only. The other Low items and the backlog stay in M5 |

**Q2 note: which population (checked 2026-09-30).**
- OWID/UN puts Malaysia's 2025 population at **35.98 M**; DOSM's official estimate is **34.22 M**, 5.1% lower.
- Malaysia 2025 demand per capita is therefore **5.81 MWh** on the UN basis and **6.11 MWh** on the DOSM basis.
- **Proposed:** use UN/OWID for all countries, because the P5 comparison needs one method for all ten. The footnote gives the DOSM-basis figure for Malaysia.
- Gap: OWID population ends in 2024 for Brunei, Indonesia, Laos and Myanmar, so their 2025 per-capita values are blank and labelled "not reported". P5 ranks on the latest year all selected countries share anyway.

**Q4 note: is the data suitable? (Ember, checked 2026-09-30).**
- **Malaysia is fully suitable for P2.**
  - Generation, demand and emissions cover 1985–2025.
  - Capacity for every source covers 2000–2025, with no gaps, so capacity factor and the NETR line are complete from 2000.
  - Before 2000, capacity factor is blank with the "capacity not reported" footnote.
- **Peers on D1 are uneven.** Some sources generate power but report no capacity:

  | Country | Missing capacity | Effect on D1 |
  |---|---|---|
  | Thailand | Every year, 2000–2025 (26 source-years) | No RE capacity share at all; capacity factor partial |
  | Myanmar | Every year, 2000–2024 (25 source-years) | No RE capacity share at all; capacity factor partial |
  | Singapore | 2014–2025 | RE capacity share for only 14 of 26 years |
  | Indonesia, Viet Nam | 2025 only | Capacity factor and RE capacity share blank for 2025 |
  | Laos | 2000–03 | Blank for those years |

  - The mix, RE share, carbon intensity and demand are complete for every country.
  - **Proposed:** D1 shows capacity-based visuals with an explicit "capacity not reported for <country>, <years>" message, never zeros. It has no NETR panel, as doc 03 already says. P5 uses only generation-based metrics, which are complete, so it isn't affected.

**Q6 note: what proceeding changes.**
- **(a)** The "capacity reported but generation NULL" case affects **0 rows** in today's ASEAN data, so fixing it changes no numbers. It is only a guard against a future Ember revision.
  - **Proposed:** a WARN rule `CAPACITY_WITHOUT_GENERATION` that reports the case if it ever appears. It costs one seed row, doesn't touch the reviewed transform, and has no effect on current outputs.
- **(b)** Applies only to the objects V008 creates. Existing constraints are not renamed, so there is no migration risk. Cost: nothing extra.
- **Net effect on the project:** no change to any figure or page, about 10 minutes of work, and one less M5 item.

## Patterns to mirror
| Category | Source | Pattern |
|---|---|---|
| Source module | `pipeline/sources/ember.py:25-177` | `EXPECTED_COLUMNS` header check → `SchemaMismatchError`; download to `data/raw/<src>/<date>/` with ×3 retry, reused the same day; typed `to_raw_records`; `#stage` + MERGE with an `EXCEPT` change test, returning the change count |
| CLI and run log | `pipeline/cli.py:42-62` | One `run.step("EXTRACT"/"LOAD", "<data_source_code>")` per source; each load in its own transaction, committed or rolled back |
| Transforms | `sql/transform/030_fact_country_annual.sql` | Delete-and-reload inside the caller's transaction; CTEs; unknown values stay NULL, never 0 |
| DQ rules | `seed/dq_rule.csv` | `check_sql` returns offending rows; severity BLOCKING or WARN |
| Views | `sql/views/R__mart_m1.sql` | Repeatable `R__`, explicit column lists, `GO` between views |
| Tests | `tests/test_ember.py` + `tests/fixtures/ember_sample.csv` | pytest on a small fixture CSV, no database |
| Model | `tools/gen_tmdl.py` | Table TMDL generated from `mart` column metadata; measures are hand-written in `_Measures.tmdl` |
| Report pages | `tools/build_overview_page.py` | PBIR visuals generated from Python; query shapes copied from Desktop-saved templates (commit `5efb683`); re-running rebuilds the page |
| Errors | `pipeline/cli.py:134-141` | Exceptions are logged and exit 1; DQ fails closed |

## Files to change
| File | Action | Why |
|---|---|---|
| `sql/migrations/V008__owid_dosm_raw.sql` | CREATE | `raw.owid_energy`, `raw.dosm_electricity` (doc 05 §2.1); `dw.dim_year.hours_in_year` (8,760 or 8,784); `ref.netr_target.source_name`; `ref.re_capacity_official` (step 1 decision) |
| `pipeline/sources/_common.py` | CREATE | Shared `download()` and `merge_into()`, lifted out of `ember.py` so that OWID and DOSM don't copy them a third time |
| `pipeline/sources/ember.py` | UPDATE | Use `_common` (behaviour unchanged; `test_ember.py` must stay green) |
| `pipeline/sources/owid.py`, `pipeline/sources/dosm.py` | CREATE | Tasks 2.1 and 2.7 |
| `pipeline/cli.py`, `pipeline/config.py` | UPDATE | Extract/load D2 and D3; the source URLs |
| `sql/views/R__stg_owid.sql`, `R__stg_dosm.sql` | CREATE | Typed and ISO-joined staging; DOSM rolled up to annual |
| `sql/transform/010_dim_year.sql`, `030_fact_country_annual.sql` | UPDATE | `hours_in_year`; population and demand per capita |
| `sql/views/R__mart_m1.sql` | UPDATE | `mart.dim_year.hours_in_year`; a `mart.dosm_check` view only if P6 needs it (M5) |
| `seed/dq_rule.csv` | UPDATE | `OWID_GEN_WITHIN_5PCT`, `DOSM_SUPPLY_WITHIN_10PCT`, `INTENSITY_RECOMPUTED` (the M1 note), `CF_AT_MOST_1` (doc 05), `CAPACITY_WITHOUT_GENERATION` (Q6a) |
| `seed/kpi.csv`, `seed/netr_target.csv` | UPDATE | NETR hydro wording from step 1; new KPI rows (capacity factor, demand growth, emissions) |
| `sql/showcase/01_trends.sql` … `05_capacity_factor.sql` | CREATE | Task 2.6 (FR-15): the SQL twins |
| `report/.../tables/_Measures.tmdl` | UPDATE | Task 2.2 measure library |
| `report/.../tables/*.tmdl` (via `gen_tmdl.py`), field-parameter tables | UPDATE/CREATE | `hours_in_year`; the TWh/% and P5 metric toggles |
| `tools/report_builder.py` | CREATE | Shared helpers (from `build_overview_page.py`) plus the page frame: nav rail, left-aligned takeaway title, "Data as of" box, Reset, ⓘ, footnote strip; per-source colour selectors from `seed/dim_source.csv` |
| `tools/build_overview_page.py` | UPDATE | P1 in the frame, with the 5th KPI, rank card, findings and navigation actions |
| `tools/build_p2_page.py`, `build_p5_page.py`, `build_d1_page.py`, `build_tooltips.py` | CREATE | Tasks 2.3–2.5 |
| `tools/dax_twin_check.py` | CREATE | Q5: runs the DAX twins against Desktop and compares them with the SQL showcase output |
| `tests/test_owid.py`, `tests/test_dosm.py`, `tests/fixtures/*` | CREATE | Parser and filter tests |
| `docs/findings.md`, `docs/reconciliation.md` | CREATE / UPDATE | Task 2.8; M2 twin evidence |
| `Documents/00_Index.md`, `06_Implementation_Plan.md`, `03_App_Flow.md` (Q1 only) | UPDATE | Status, resume points, decisions |

## Tasks (in build order)
Model tiers per doc 06 §4: **D** = Opus 5.5 (this session) · **S** = Sonnet 5.5 subagent · **F** = Haiku 4.5 subagent · **GUI** = you in Power BI Desktop, following my click-level steps. A step that fails verification twice moves up one tier (Deep → Fable 5.1). Commit after every step. The index resume point is updated before every subagent run.

| Step | Doc 06 | What | Model | Verify |
|---|---|---|---|---|
| 1 | carry-over | **NETR hydro definition**: `verified-research` on the primary NETR document (Ministry of Economy, 2023) and the MIDA/IEA summaries. Does "RE share of installed capacity" include large hydro? Update the `kpi.csv` formula, the footnotes and the doc 01 D6 note. If large hydro is **excluded**: Ember has no large/small split, so the line is relabelled and a caveat added (no invented split) | D | The source is quoted with page and URL; the outcome is recorded in the index "Decided" list |
| 2 | 2.1 | V008 + `_common.py` refactor + OWID extractor/loader + `stg` view + population and per-capita in `030`. Test-first: the fixture test (header check, ASEAN ISO filter, blanks → NULL) comes **before** the code | D (tests F) | `pytest` green, including the unchanged `test_ember.py`; run twice → the second run merges 0 rows; **MY 2025 per capita = 5.814 MWh**; `OWID_GEN_WITHIN_5PCT` shows WARN for MY 2023–24 as predicted |
| 3 | 2.7 | DOSM loader + annual roll-up + `DOSM_SUPPLY_WITHIN_10PCT` WARN (2018–2023, full years only) + a short coverage note | F | The rules appear in `meta.dq_result` as PASS or WARN; the 2024 half-year is excluded |
| 4 | 2.6 | SQL showcase: `01_trends` (mix and RE share), `02_yoy_lag` (YoY with `LAG`, polarity), `03_ranking` (`RANK() OVER` on the latest common year), `04_rolling_avg` (3-year rolling RE share), `05_capacity_factor` (leap-year hours; NULL when capacity is missing). Each file has a header comment: question, method, expected spot value | D | Outputs equal P1's M1 figures for 3 spot values; `CF_AT_MOST_1` passes |
| 5 | GUI prep | **Template capture** (the M1 pattern): you add one of each missing visual type to a scratch page and save. That covers the page navigator, line chart, clustered bar, scatter, field-parameter slicer, button with page navigation, drill-through Back button, tooltip page and shape with a measure-bound title. Claude copies their JSON shapes, then deletes the scratch page | GUI + D | The scratch page JSON is read and committed as `tools/templates/*.json` |
| 6 | carry-over | `report_builder.py` frame + **P1 polish**: nav rail; left-aligned title (a shape with an fx-bound title; new card visual as fallback); a boxed "Data as of"; **per-source colours bound explicitly** (dataPoint selectors per `display_name`, from `seed/dim_source.csv`); P1 moved into the frame | D | You reopen the .pbip (close without saving first) and screenshot. The title is left-aligned, colours match doc 04 §3.2 even when a source is filtered out, and the nav rail switches pages |
| 7 | 2.2 | DAX library: country-in-context (Q4); shares; YoY with polarity (for every KPI); demand growth; per capita; capacity factor (`hours_in_year`); RE capacity share; rank ("N of M", latest common year); "No data" and "Select at least two countries" messages; field parameters (TWh/% and the P5 metric) | D | `tools/dax_twin_check.py`: every twin equals its SQL value (±0.05 for %, ±0.1% relative for TWh). **Independent review: a fresh-context Opus agent diffs the DAX logic against the SQL twins** and lists mismatches before any page uses them |
| 8 | 1.10 rest | P1 completion: 5th KPI (demand per capita), rank card → P5, KPI click → P2, findings box (placeholder until step 12) | S | Screenshot; the clicks navigate |
| 9 | 2.3 | P2 Generation & Targets: TWh/% toggle, mix area, NETR line + markers, capacity-factor bar, **two aligned demand charts (F1)**, synced year-range slicer, source slicer, footnotes | S + GUI | Click-through of every row in doc 03 P2's element table; the "capacity not reported" footnote appears where it should |
| 10 | 2.4 | P5 ASEAN + T2 tooltip: default peers (`is_default_peer`), trend with a metric toggle (Q1), intensity ranking bar, scatter (bubble = demand), per-capita bar, rank card, and the "Select at least two countries" state | S (same agent as step 9, continued) | Deselect Singapore → the rank card reads "N of 5"; the footnote names the latest common year |
| 11 | 2.5 | D1 drill-through (the P2 layout without NETR, with Back), T1 KPI tooltip, synced slicers. **The Reset bookmarks are created by you in Desktop** (bookmark state is Desktop-generated), following my steps | F + GUI | Journey J2: P1 → P2 → P5 → right-click Viet Nam → D1 shows Viet Nam → Back returns with P5's filters intact |
| 12 | 2.8 | Exploratory analysis → `docs/findings.md`: 3 findings, each with a number, a caveat and a source query in `sql/showcase/`. P1's findings box is then filled | D | **Independent review: `audit-my-work` in a fresh agent**, since these claims go public. Every number is re-run from its query |
| 13 | acceptance | Empty-DB rebuild (throwaway DB), reconciliation re-run, twin check, full J2, push; doc 06 M2 row, index, memory observations | D | The M2 acceptance list below |

**Batching:** steps 2's fixture test and 3 are Haiku briefs. Steps 9–10 run in **one** Sonnet agent (continued with SendMessage, so it keeps the frame context), and step 8 goes in the same brief. Step 11's builders are one Haiku brief. Everything else runs here on Opus.

**GUI rounds for you (each one is a single reopen-and-screenshot):** step 5 (templates), step 6 (P1 frame), steps 8–9 (P1 + P2), step 10 (P5), step 11 (D1, tooltips, bookmarks), step 13 (J2). That makes about 6 rounds, each with exact click steps.

## Step 1 outcome: NETR and hydro (researched 2026-09-30)
| Claim | Verdict | Evidence |
|---|---|---|
| The RE capacity targets count **large hydro** | **True** | The 31% (2025) target in the Peninsular GDP (Mar 2021), the 12th Malaysia Plan (Jul 2021) and MyRER (Dec 2021) uses the ASEAN harmonised RE definition, which counts **large hydro and off-grid** (Demmel, *Malaysia's RE Target Jungle*, ASB Working Paper 01/2025, pp. 19–21). The NETR briefing's "Renewables" footnote "includes bioenergy, solar, hydropower and hydrogen" (Ministry of Economy NETR briefing, 26 Jun 2024, p. 22). **The M1 assumption stands.** |
| 31% / 40% / 70% are all **NETR** targets | **False (misattributed)** | 31% (2025) and 40% (2035) come from the **12MP / MyRER (2021)** ([SEDA MyRER](https://www.seda.gov.my/reportal/myrer/)). **NETR (2023) sets 70% by 2050** (MOE briefing p. 22: "RE share of installed capacity 70%"). NETR itself projected 27% for 2025 (ASB p. 22, citing NETR p. 33). Demmel notes that MIDA "wrongly linked" NETR to 31%. The MOE's 2024 briefing (p. 24) also pairs "31% RE" with 2030, which is inconsistent with the 2021 plans |
| Scope | **National, including Sarawak** (MyRER lists Sarawak's resources); **includes off-grid** (ASEAN definition) | ASB pp. 18, 21; MyRER page |
| Is Malaysia on track? | **Officially yes: 32% reported for 2025** | The Energy Commission, via [Asian Power, 26 Feb 2026](https://www.renewableenergyasia.org/2026/02/malaysia-exceeds-2025-renewable-target.html); [IEA-PVPS](https://iea-pvps.org/about-iea-pvps/members/malaysia/): "achieved interim capacity target of 31%… dominated by hydro and PV" |
| **Our Ember basis** | **24.4% for 2025** (10.27 of 42.03 GW) | Ember counts grid capacity: solar 3.07 GW vs roughly 5.1 GW in official estimates, and no off-grid bioenergy. **The gap between the two definitions is 7.6 pp, so P1's "24.4 vs 31" wrongly implies Malaysia missed its target** |

**Decided (Amirul, 2026-09-30):**
- **Both, clearly labelled.**
  - Our series is renamed "RE share of capacity (Ember basis)".
  - A new seed `ref.re_capacity_official` (year, pct, source, URL; first row 2025 = 32%, Energy Commission) is shown as a separate cited marker.
  - The footnote explains the definition gap (grid-only vs. including off-grid and rooftop).
- **Each target cites its own source.**
  - `ref.netr_target` gains a `source_name` column (31 and 40 → 12MP/SEDA MyRER; 70 → NETR, Ministry of Economy).
  - The visual is called "National RE capacity targets". Doc 01 D6 is updated.
- **Where it lands:**
  - V008 and the seeds: step 2.
  - The measures: step 7.
  - The P1 labels and marker: steps 6 and 8.
  - The P2 line: step 9.
  - A finding candidate for step 12: the definition gap itself.

## Definitions pinned for this milestone
| Measure | Definition | Note |
|---|---|---|
| Demand per capita | Ember `Demand` TWh × 10⁶ ÷ OWID population | MWh/person; UN population via OWID; blank when population is missing (BN, ID, LA, MM in 2025); the footnote gives the DOSM-basis Malaysia value (6.11 for 2025) |
| Demand growth | (Demand_y − Demand_y−1) ÷ Demand_y−1 | "—" for the first year |
| Capacity factor | Generation TWh × 10³ ÷ (capacity GW × `hours_in_year`) | 8,784 h in leap years; blank + footnote when capacity is missing; `CF_AT_MOST_1` guards it |
| Rank on RE share | `RANK` descending among the selected countries, at the latest year **all** of them have | "Ranks N of M" |
| RE share of capacity (NETR) | As in M1, **pending step 1** | The label may change |
| Emissions | Ember `Emissions (MtCO2e)` on the Total generation row | FR-09 |

## Validation (end of M2)
```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pipeline db migrate
.venv/Scripts/python -m pipeline seed
.venv/Scripts/python -m pipeline run          # exit 0; OWID/DOSM WARNs expected and documented
.venv/Scripts/python -m pipeline run          # exit 0; 0 changed rows for D1, D2, D3
.venv/Scripts/python tools/dax_twin_check.py  # all twins PASS (Desktop open)
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| NETR excludes large hydro, which would break the P1/P2 NETR story | Medium | Step 1 runs first; honest relabel + caveat; no fabricated split |
| ADOMD.NET can't reach the Store edition's local AS instance | Medium | Fallback: a hidden QA page with a twin table that you screenshot |
| Field parameters, bookmarks or drill-through written by hand won't load | Medium | Templates from Desktop (step 5); bookmarks made in the GUI; check after each page |
| The nav rail shifts P1 and breaks its verified layout | Low | Rebuild from the script, then screenshot in the step 6 round |
| OWID/DOSM WARNs become noise that hides real issues | Medium | Known-cause WARNs are listed in `docs/reconciliation.md`, and the P6 notes say why |
| A findings claim doesn't survive scrutiny | Medium | Each finding cites its query; `audit-my-work` review; caveats are mandatory |
| Long session / usage limits | Medium | The index resume point is updated before each agent run and after each step |

## Acceptance (the doc 06 M2 check)
- [ ] On an empty DB: `migrate && seed && run` exits 0; a second run merges 0 rows for D1, D2 and D3
- [ ] BLOCKING rules all PASS; the WARNs are only the predicted, documented ones
- [ ] Every DAX measure equals its SQL twin (step 7), independently reviewed
- [ ] J2 works: P1 → P2 → P5 → D1 → Back, with Reset and synced slicers
- [ ] NETR hydro definition verified and cited; P1 polish done (title, as-of box, explicit colours)
- [ ] 3 findings in `docs/findings.md`, audited
- [ ] Commits pushed; doc 06, the index and the skill-test memory updated
