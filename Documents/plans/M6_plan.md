# Plan: M6 task 6.2 — Streamlit web showcase (FR-21)

**Source:** [06 Implementation Plan](../06_Implementation_Plan.md) task 6.2 (M6 has 6.1–6.5; **only 6.2 is in scope here**, Amirul 2026-10-10) · **Branch:** `m6` (so `main` stays the `v1.0.0` candidate until M5 step 12) · **Complexity:** Large (about 2–3 sessions; the measure port and the licence gate are the careful parts) · **Status:** APPROVED 2026-10-10 in the Plan Canvas (Q1–Q8, with Amirul's conditions on Q1 no information left behind, Q2 open data first plus a follow-up to the Energy Commission, Q3 list the excluded views)

## Summary
A free, public, interactive web version of the report that works without Power BI and outlives the UiTM account (doc 01 R1):
1. **`pipeline export`** writes small Parquet snapshots of the open-data `mart.*` views to `exports/`, licence-gated by `dim_data_source.is_publishable` and an explicit allowlist that fails closed.
2. **A Streamlit multipage app** in `app/` mirrors P1 Overview, P2 Generation, P4 Grid load, P4b Forecast, P5 ASEAN, P6 About and P6b Data quality, with the same takeaway titles, palette and credits, reading only `exports/`.
3. **Parity is checked, not assumed:** the export also writes the key numbers from the SQL showcase twins, and a CI test requires the app's pandas calculations to match them.
4. **Built now on `m6`; deployed on Streamlit Community Cloud after the repo goes public** (M5 step 12), then merged as v1.1.0.

## Requirements restated
| FR / NFR | What 6.2 must deliver | Step |
|---|---|---|
| FR-21 (S) | Public URL loads in a private window; numbers match Power BI (doc 06: 3 numbers; this plan checks every headline number) | 2–5, 8 |
| G4 | Viewable by anyone without Power BI, on a phone too (doc 02 §2) | 3–6 |
| NFR-05 / 06 | No restricted data leaves the PC; every dataset credited as its licence asks | 1, 5, 7 |
| NFR-04 | Text alternatives, AA contrast, nothing by colour alone (doc 04) | 6 |
| NFR-07 | ruff, tests, CI | all |
| doc 02 §3.2 | Streamlit + Plotly; Parquet snapshots committed; free hosting (sleeps after 12 h idle) | 1–2, 8 |
| doc 03 Part C | Sidebar nav, same takeaway-sentence titles; P3 only with Energy Commission consent (see Q2) | 3–5 |

## Facts verified before planning (2026-10-10)
- **29 `mart` views.** The mirrored pages use `country_annual` (328 rows), `generation_annual` (2,192), `grid_hourly` (35,372), `load_forecast_current` (17,568), `grid_flow_daily` (2,206), `forecast_run_current` / `forecast_status` (2 each), `netr_target`, `re_capacity_official`, `kpi`, `data_source`, `dq_latest`, `run_latest`, `source_load_latest` and the dims. All small: well under 5 MB as Parquet.
- **Licence by view, not by row.** Only `dim_grid`, `data_source`, `dq_latest`, `kpi` and `source_load_latest` carry a `data_source_code`. Every D5 (handbook) view is in `R__mart_m4.sql` (`dim_region`, `region_annual`, `region_capacity`, `dim_state`, `state_reliability`, `reliability_metric`, `reliability_year`). `dim_grid` lists only the two open grids (DTH, DSG); the GSO grid row is inactive.
- **`dq_latest` is safe:** the 12 D5 rules have `detail = NULL` (names and statuses only, no values).
- **`is_publishable`:** 1 for D1, D2, D3, D6, DSG, DTH, GEO; 0 for D4 (GSO, REQUESTED) and D5 (GRANTED for charts, not data rows: `DATA_LICENSES.md` §D5).
- **The logic lives in DAX:** 163 measures. The mirrored pages use about 110 of them (Overview 10 + 8 deltas, Generation 10, NETR 11, Grid load 12, Forecast 21, ASEAN 18, About 15, Context 9, Flows 4, Trends 2); Regions and State reliability (36) are out. The 14 `sql/showcase/` queries are the existing SQL twins (`tools/dax_twin_check.py` matches 35 measures to them).
- **Tooling:** Python 3.13.15; `pandas` 3.0.6 and `pyarrow` 25.0.1 are pinned; `streamlit` and `plotly` are not installed (doc 02: "pinned when FR-21 starts"). The report theme is `report/.../RegisteredResources/energy-transition.json` (doc 04 tokens).
- **Not verified yet** (checked in the step that needs it, from the current Streamlit docs): that Community Cloud uses a `requirements.txt` beside the entrypoint before the root one (the root file holds the pipeline's heavier, Windows-tested pins), and which Python versions it offers.

## Decisions for your approval
| # | Question | Proposed |
|---|---|---|
| Q1 | **Pages** | **7 pages:** Overview, Generation, Grid load, Forecast, ASEAN, About, Data quality (P1, P2, P4, P4b, P5, P6, P6b). The Country Deep Dive drill-through becomes a country selector on ASEAN. The report-page tooltips become Plotly hover text. **No information left behind** (Amirul): a coverage inventory lists every visual, card, text box, slicer and tooltip on those pages, the Country Deep Dive and the T1/T2 tooltips (from the report's `visual.json` files) and maps each to its app element in `app/coverage.json`; a test fails on any unmapped item. |
| Q2 | **Regions and State reliability** (consent granted 9 Oct for charts as images, a PDF and a video, on GitHub and your portfolio site) | **Open data first; ask the Energy Commission in parallel** (Amirul). The app would need the handbook's data rows committed as Parquet, which redistributes data the consent did not cover ("permission is limited to the purpose stated"). So the app ships without them (the About page links to the two consented PNGs on GitHub), and I draft a follow-up email asking whether the permission extends to the interactive web showcase and its data snapshot of the same charts. **You preview it before it is sent.** If they agree, step 9 adds the two pages and sets D5 `is_publishable = 1`. |
| Q3 | **Licence gate** | `pipeline/export.py` holds an explicit **allowlist**: each exported view with the source codes it draws from. Export **refuses** if any listed source is not `is_publishable = 1` (read from `dw.dim_data_source` at export time), filters grid rows by `dim_grid.data_source_code`, and writes `exports/manifest.json` (file, rows, sources, export time, data vintage). A test fails if a `mart` view is neither exported nor listed as excluded, so a new view can't slip out unreviewed. **Every export prints, and the manifest records, the views left out and why** (Amirul), e.g. `region_annual: D5 not publishable`, so the excluded list is visible on each run. |
| Q4 | **Parity** | At export, `pipeline export` also runs the showcase twins and writes `exports/expected.json` (about 25 headline numbers: the P1 KPIs and deltas, ranks, RE share against targets, capacity factors, peak/load factor per grid, forecast MAPE and baseline per grid, DQ counts). A CI test runs the app's pandas functions (`app/metrics.py`, pure and unit-tested) on the Parquet and must match within the twin tolerance, max(0.05, 0.1%). No Desktop needed. |
| Q5 | **Scanner** | `tools/scan_handbook_values.py` starts reading `exports/*.parquet` as text (today it skips `.parquet`): a tightening, with a positive control (a synthetic Parquet holding a handbook value is flagged). |
| Q6 | **Look and feel** | `.streamlit/config.toml` from doc 04's light tokens (dark values from doc 04 under the theme switch); a Plotly template generated from `energy-transition.json`, so the palette is the report's, validated once with the `dataviz` skill. Takeaway titles computed like the DAX titles. One column under 768 px (doc 04). Each chart has a caption-level text summary and a "Show data" table, so nothing relies on colour or hover. |
| Q7 | **Credits** | Every page footer shows its sources' credit text from `data_source` (same as P6). `exports/README.md` credits each file as its licence asks (CC BY 4.0 creator + link + "modified"; the SODL statement), mirroring `tests/fixtures/README.md`. Data vintage on About and in the manifest. |
| Q8 | **Hosting and release** | `app/requirements.txt` (streamlit, plotly, pandas, pyarrow, pinned) so the cloud doesn't install the pipeline's stack. **You** create the app at share.streamlit.io with your existing account (HA-PIT's), from the public repo, after M5 step 12; I give you the exact settings. Then `m6` merges to `main` and, with your go, tag `v1.1.0` and add the URL to the README and the P6 About repo note. |

## Patterns to mirror
| Category | Source | Pattern |
|---|---|---|
| CLI command | `pipeline/cli.py:37` `_cmd_seed` | `_cmd_<name>` with a lazy import, `db.pipeline_lock("<name>")`, `log.info` the result, return 0; subparser with a one-line help |
| Data access | `pipeline/db.py:32` `connect()`; `tools/check_readme_numbers.py:34` | Explicit column lists; showcase queries run by name (`run(cursor, "09_forecast_metrics")`) |
| Fail-closed gate | `tools/export_pages.py` `keep_flags` | Unknown or missing consent means "not publishable"; refuses with a message rather than writing a partial set |
| Guards + controls | `tests/test_no_restricted_data.py`, `tools/scan_handbook_values.py` | Ask git what is tracked; every guard has a positive control (M5 lesson) |
| Tests | `tests/test_export_pages.py` | pytest, no DB, synthetic inputs, contract first |
| Twin tolerance | `tools/dax_twin_check.py` docstring | max(0.05, 0.1% of the SQL value); years, ranks, counts exact |
| Licence credits | `tests/fixtures/README.md`, `DATA_LICENSES.md` | Credit worded as each licence asks |
| UI tests | none yet | No Streamlit code exists; Streamlit's own `streamlit.testing.v1.AppTest` (headless, CI-friendly) is proposed, checked against the pinned version's docs |

## Files to change
| File | Action | Why |
|---|---|---|
| `pipeline/export.py`, `pipeline/cli.py` | CREATE / UPDATE | `pipeline export`: allowlist, gate, Parquet, manifest with the excluded list, expected numbers (Q3, Q4) |
| `app/coverage.json`, `tests/test_app_coverage.py` | CREATE | Every report item on the mirrored pages mapped to an app element (Q1) |
| `docs/consent/st_request.md` | UPDATE | The follow-up email (Q2) and its log |
| `exports/*.parquet`, `exports/manifest.json`, `exports/expected.json`, `exports/README.md` | CREATE | The snapshots, committed (doc 02 §3.2); credits (Q7) |
| `app/streamlit_app.py`, `app/pages/*.py`, `app/data.py`, `app/metrics.py`, `app/theme.py`, `app/requirements.txt`, `.streamlit/config.toml` | CREATE | The app (Q1, Q6, Q8) |
| `tests/test_export.py`, `tests/test_app_metrics.py`, `tests/test_app_pages.py` | CREATE | Gate, parity, every page renders |
| `tests/test_no_restricted_data.py`, `tools/scan_handbook_values.py` | UPDATE | No D4/D5 source in the manifest; Parquet scanned (Q5) |
| `requirements.txt` (dev pins), `.github/workflows/ci.yml` | UPDATE | streamlit/plotly for tests; CI runs the new tests |
| `README.md`, `DATA_LICENSES.md`, docs 02 (§3.2), 03 (Part C as built), 05 (exports), 06 (6.2), `00_Index.md` | UPDATE | As built |

## Tasks (in build order)
**Model tiers (doc 06 §4):** D = Opus 5.5 (this session); S = Sonnet 5.5 subagent (doc 06 routes 6.2 to Standard); F = Haiku 4.5. At most 2 subagents at a time. **Escalation:** a step that fails verification twice moves up one tier. **Every commit** after `pytest`, `ruff check`, `ruff format --check`, `scan_handbook_values.py`. Desktop is not needed until step 8's spot check.

| Step | What | Model | Verify |
|---|---|---|---|
| 0 | **Energy Commission follow-up** (Q2): draft asking whether the 9 Oct permission extends to the interactive web showcase and its data snapshot; preview to you; send only on your go | D + you | You approved the text; sent; logged in `docs/consent/st_request.md` |
| 1 | **Export and gate** (Q3–Q5), tests first: allowlist, fail-closed refusal (a non-publishable or missing source, an unlisted view), grid filter, manifest, `expected.json` from the showcase twins, Parquet in the scanner | D | Tests fail first, then pass; `pipeline export` writes the set (< 5 MB); manifest has no D4/D5; injected D5 view → refusal; the excluded views are printed and in the manifest, with reasons; scanner positive control flagged, real set 0 |
| 2 | **App skeleton + data layer:** `st.navigation` with the 7 pages (stubs), `data.py` (cached Parquet reads, manifest check), `metrics.py` contract (signatures + docstrings = the measure spec), theme config + Plotly template; pins in `app/requirements.txt` | D | `AppTest` opens every page without an exception; `metrics.py` contract tests written (red); **coverage inventory** (Q1) built from the report's `visual.json` files, and `test_app_coverage` lists every unmapped item (red until steps 4–5) |
| 3 | **Metrics port:** the ~25 parity numbers plus the series each chart needs, in pure pandas | S, Deep read | Parity test green against `expected.json`; unit tests on synthetic frames |
| 4 | **Pages: Overview, Generation, Grid load, Forecast** (titles, KPI cards, charts, hover text, captions, "Show data", footer credits) | S | `AppTest` per page: title equals the takeaway computed from the data; no exception; screenshot review at 1280 and 375 px (local `streamlit run` + browser preview) |
| 5 | **Pages: ASEAN (country selector), About (sources, consent, KPI definitions, links to the P3/P3b PNGs, vintage), Data quality (34 rules, status chips with icon + word)** | S | As step 4; About lists every `data_source` row with its credit |
| 6 | **Review:** `ecc:python-reviewer` (export + app), `design:accessibility-review` on the screenshots (contrast, focus order, text alternatives), `dataviz` palette check; fix findings | D + reviewers | 0 HIGH open; a11y findings fixed or listed in `docs/a11y.md` |
| 7 | **Docs + CI:** README "Try it online" section (URL placeholder), `DATA_LICENSES.md` (the exported files and their credits), docs 02/03/05/06 as built, index; CI installs `app/requirements.txt` and runs the new tests | D | CI green on `m6`; README checks 13/13 |
| 4–5 gate | **Coverage complete** | — | `test_app_coverage` green: no report item on the mirrored pages is left without an app element |
| 8 | **Deploy (after M5 step 12), asks you first:** merge `m6` → `main`; you create the app on share.streamlit.io with the settings I give; I check the public URL in a private window, 3+ numbers against Power BI (Desktop), phone width; README + P6 link; `v1.1.0` tag + Release (your go) | D + you | URL opens logged-out; numbers match; README link works |
| 9 | **Only if the Energy Commission agrees** (Q2): Regions and State reliability pages; D5 `is_publishable = 1`; D5 views move from excluded to exported; credits and the consent log updated | D | Pages render; parity on their twins (`12_regions`, `13_state_reliability`); scanner exemption reviewed with you |

## Validation
```bash
.venv/Scripts/python -m pipeline export                  # writes exports/, refuses on any non-publishable source
.venv/Scripts/python -m pytest -q                        # incl. test_export, test_app_metrics, test_app_pages
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
.venv/Scripts/python tools/scan_handbook_values.py       # 0 files to check, Parquet included
.venv/Scripts/streamlit run app/streamlit_app.py         # local look at 1280 and 375 px
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| A pandas port disagrees with its DAX measure (wrong number online) | **High without a check** | Q4 parity test against the SQL twins at every export; titles tested; step 8 spot check against Power BI |
| Restricted data leaves the PC in a Parquet file | Low | Q3 allowlist + fail-closed gate + unlisted-view test; manifest test; scanner reads Parquet (Q5) |
| Community Cloud installs the pipeline's root `requirements.txt` (heavy, Windows-tested pins) | Medium | `app/requirements.txt` beside the entrypoint; the lookup order checked in the Streamlit docs at step 2 |
| Streamlit API drift (multipage and testing APIs change between versions) | Medium | Pin versions; read the pinned version's docs (`ecc:docs-lookup`) before step 2 |
| Snapshots go stale or drift from the README | Medium | Vintage in the manifest and on About; refresh = `pipeline run` → `pipeline export` → commit; README checks re-run |
| Deploy blocked until the repo is public | Certain (by design) | Everything up to step 7 is built and tested on `m6` first |
| Free tier sleeps after 12 h idle, shared limits | Low | Small snapshots; a wake-up note on the README link |

## Acceptance
- [ ] `pipeline export` writes only open-data views; refuses on a non-publishable source or an unlisted view; manifest shows no D4/D5 and lists every excluded view with its reason
- [ ] Coverage test green: every item on the mirrored report pages has an app element (no information left behind)
- [ ] Energy Commission follow-up previewed by you and sent (or held, your call)
- [ ] The app mirrors the 7 pages with the report's titles, palette and credits; every page renders in `AppTest`
- [ ] Parity test green: every `expected.json` number matches the app within tolerance
- [ ] Value scan (Parquet included) 0, with its positive control; tests, ruff and CI green
- [ ] Python and accessibility reviews: findings fixed or recorded
- [ ] Public URL opens logged-out; 3+ numbers match Power BI; phone width works
- [ ] README, `DATA_LICENSES.md`, docs 02/03/05/06, index, vault note and skill-test memory updated; `m6` merged; `v1.1.0` (your go)

## Outcome
(Filled in as steps finish.)
