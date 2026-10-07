# Plan: M5 — Finish and ship v1.0.0

**Source:** [06 Implementation Plan](../06_Implementation_Plan.md) Phase 5 (tasks 5.1–5.9) · **Complexity:** Large (about 3 sessions; the pre-publish audit and the history decision are the careful parts) · **Status:** APPROVED 2026-10-07 (Q1–Q8 as proposed; Q2 option taken: the Energy Commission consent email, task 6.1, moved into M5 and sent at approval); in progress

## Summary
M5 turns the working project into a public v1.0.0:
1. **Finish the report:** P6 About the Data (sources, licences, consent, run summary, DQ results, KPI definitions), a Fail badge on the nav rail, an ⓘ About button, and alt text on every visual.
2. **Make it viewable without Power BI:** PNG per page, a PDF, and a ≤ 2-min walkthrough that you record from a script I write.
3. **Make it reproducible and checked:** README, CI, a timed fresh-clone rebuild, then the pre-publish audit.
4. **Ship:** with your go, make the repo public, tag `v1.0.0`, and link it from your profile.

## Requirements restated
| FR / NFR | What M5 must deliver | Task |
|---|---|---|
| FR-14 | "About the data": sources, licences, last refresh, DQ results, KPI definitions; current after a refresh | 5.1, 5.2 |
| FR-16 | README opens with the question, 3+ findings, a hero screenshot and an architecture diagram; someone new states one finding within 30 s | 5.5 |
| FR-17 | Report visible without Power BI: page screenshots, a ≤ 2-min video or GIF, a PDF; all visible on GitHub | 5.4 |
| FR-18 | A clean-clone rebuild succeeds following only the README | 5.7 |
| FR-20 (S) | Linked from your GitHub profile repo and LinkedIn Featured | 5.9 |
| NFR-02 | Setup < 30 min from a clean clone, excluding tool installs | 5.7 |
| NFR-04 | Alt text on visuals, AA contrast, no information by colour alone | 5.3 |
| NFR-05 / 06 | No secrets or personal data; every dataset credited as its licence requires | 5.8 |
| NFR-07 | SQL and Python formatted and commented (ruff, sqlfluff) | 5.6 |
| M5 acceptance | Every **Must** in doc 01 passes its verification column, and the 5.8 verdict is "go" | step 13 |

## Facts verified before planning (2026-10-05)
- **Repo:** private, 104 commits. No `.github/`. `README.md` is a 10-line placeholder. `ruff` 0.16.9 and `sqlfluff` 4.3.0 are pinned but have no config files. `ruff check .` reports **20 findings** (10 auto-fixable). `docs/consent/` holds only the GSO request.
- **Task 5.2 is mostly done already.** Both rules it names exist and run: `HOURLY_GAPS_LE_2PCT` (M3) and `CF_AT_MOST_1` (M2). What remains is the Fail badge on the nav and its injected-fail test.
- **The P6 model is mostly there:** `data_source` (licence, url, credit_text, consent_status, is_publishable), `kpi` (definition, formula, unit), `run_latest` (one row: start, end, status) and `dq_latest` (rule, severity, source, status, rows affected, detail). **Missing:** rows per source for the run summary (doc 03 P6 asks for it), so a small mart view is needed.
- **CI scope:** the 948 tests need neither SQL Server nor Desktop. The PDF golden tests skip without the local PDF, and the git tests skip without git. So CI can run `pytest` on a hosted runner.
- **Exports:** Desktop has **File → Export → PDF**, but no per-page PNG. `pypdfium2` is already installed (a `pdfplumber` dependency), so a script can render the PDF to 1280×720 PNGs and drop pages.
- **The history leak (M4 step 12):** two real handbook figures sit in commits from 2026-09-30 (doc 05 sample row) and `7aaa6bf` (a V015 comment). `git filter-repo` is **not installed**.
  - **A rewrite has a hidden cost.** The forecast replay re-reads the protocol at the record's `protocol_commit` (`pipeline/forecast/run.py:385`, `protocol_at_commit`). Rewriting history changes `d7a03e2` and every hash after the first leak. The replay would then fail on every clone until `docs/forecast_final.json` is re-pointed to the new hashes. The tree content stays identical, so the re-pointing is honest, but it touches the "locked" record (see Q1).
- **D4 (GSO):** request sent 2026-09-30; no reply recorded. **D5:** consent email is task 6.1 (after completion, your decision); `consent_status = NOT_REQUESTED`.

## Decisions for your approval
| # | Question | Proposed |
|---|---|---|
| Q1 | **The two handbook values in git history** (they must not ship publicly) | **Rewrite, gated by a dry run.** In a throwaway clone:<br>1. `pip install git-filter-repo`; `--replace-text` swaps the two exact strings for the synthetic ones now in the tree.<br>2. Re-point `protocol_commit`/`git_commit` in `docs/forecast_final.json` with filter-repo's commit map, in one documented commit that explains the mapping (same tree, new hash).<br>3. Update the hashes cited in `Documents/` the same way.<br>4. Run the full tests, a history-wide value scan (new `--history` mode) and the forecast replay on a throwaway DB.<br>Only if all of that passes: back up with `git bundle`, then force-push to the private repo **with your explicit go** (it rewrites every hash on GitHub).<br>**Alternatives:** (b) **accept**, the two figures stay in history: not recommended, because the handbook's p.5 covers "any part"; (c) **publish a fresh single-commit repo** and keep this one private as the archive: clean, but it loses the 100-commit history that shows how the work was done, and the replay's commit would not exist in public either |
| Q2 | **P3/P3b in public exports and README before Energy Commission consent** (M4 Q1 left this to M5) | **Leave them out of every committed export.** The PNG/PDF set skips P3 and P3b. The README names the two pages, says they render locally when you run the pipeline, and says consent is to be requested. The PBIP itself holds no data (Import cache and `.pbix` are git-ignored), so the repo stays clean.<br>**Optional:** move task 6.1 (the consent email) into M5 so the notice reads "permission requested" at launch. It's your earlier call, "after completion", so it stays unless you say otherwise |
| Q3 | **P6 density** (M3/M4 lesson: budget first, split rather than grow) | **Split into P6 About + P6b Data quality** (budget below). One page would need ~900 px for 9 sources, 34 DQ rules, 11 KPI definitions and the notes. The nav goes to 9 buttons + Reset, which fits the rail (104 + 9 × 48 + 72 = 608 px < 720) |
| Q4 | **Backlog carried to M5** (index) | **In:**<br>• all 20 ruff findings fixed (CI must be green);<br>• the 4 cheap DB hardening items: role tests via `CREATE USER … WITHOUT LOGIN`, an `sp_getapplock` guard on migrations and runs, an out-of-order-version check, DENY on `meta.schema_version` for `role_pipeline`;<br>• the 4 transform-review LOW items (negative-generation tolerance, UTC `YEAR()`, capacity without generation, concurrent-run guard = the same applock);<br>• the ⓘ About button;<br>• **one** time-boxed retry of report-page tooltips in the first GUI round (keep T2 if it renders, else delete the unused T1/T2 pages so the public repo carries no dead pages).<br>**Time-boxed (30 min):** the cause of the DOSM gap. If it's still unknown, it's documented as an open caveat.<br>**Out (to M6/never):** constraint-naming consistency (cosmetic churn on applied migrations) |
| Q5 | **CI** | GitHub Actions on `ubuntu-latest`, Python 3.13: `ruff check`, `ruff format --check`, `sqlfluff lint` (T-SQL dialect, a pragmatic `.sqlfluff`), `pytest`. **sqlfluff starts non-blocking** if its first run on 30 SQL files is noisy; blocking once clean. Dependabot weekly for pip and Actions. Private-repo minutes (doc 02 **Unverified**) are checked on the account before the first push; a run is ~2 min |
| Q6 | **Walkthrough format** (you record it; doc 06 decided) | **MP4, ≤ 2 min,** from Snipping Tool, following a J2 script I write (no P3/P3b in it if Q2 stands). Upload it through GitHub's README editor (`user-attachments`), so it plays inline and stays out of git history. The README hero is a static PNG of P1 |
| Q7 | **Fresh-clone reproduction (5.7)** | Clone into this session's scratchpad (outside the vault, so graphify and Obsidian don't index it), with a new venv and a new DB `EnergyDW_FreshClone`. Follow **only** the README, timed. Desktop opens via `Start-Process`, with no file dialogs. Tool installs are excluded from the 30 min (NFR-02). Any README gap found is fixed and the clock restarts |
| Q8 | **Going public (5.9)** | I ask you right before: make public, tag `v1.0.0` with a GitHub Release (notes from the plan Outcomes), add a pinned link in the `Aether03` profile README (shown to you first). LinkedIn Featured is yours |

### Page budget (Desktop 2.158 limits: category ≥ 20 px, legends ~140 px, charts ≥ 120 px, header ≥ 8 pt, 44 px dropdowns clip; content x 200–1256, y 104–664)
| Page | Row | y / h | Content | Check |
|---|---|---|---|---|
| **P6 About** | 1 | 104 / 300 | Sources and licences table (9 rows: source, what it gives, licence, credit, consent status, link) | Table at 9 rows × ~26 px + header ≈ 270 ✓ |
| | 2 | 420 / 244 | Left: KPI definitions table (11 rows; scrolls if needed). Right: method notes text (forecast, capacity factor, state mapping, Sarawak remap) + repo link | — |
| **P6b Data quality** | 1 | 104 / 88 | Last run cards: started, finished, status, rows per source (new mart view); "No pipeline run recorded" when empty | Card ≥ 40 px ✓ |
| | 2 | 208 / 456 | DQ table (34 rules: rule, source, severity, status chip, rows affected), status filter tiles (Pass/Warn/Fail), source click-filter; reconciliation note | 34 rows scroll inside a fixed table ✓ |
| **Every page** | rail | — | ⓘ About button; red Fail count on the About nav item when any rule FAILs | Badge 20 × 20 over the nav button |

## Patterns to mirror
| Category | Source | Pattern |
|---|---|---|
| Report pages | `tools/build_p3b_page.py`, `report_builder.py` | Frame + Desktop-captured shapes; geometry constants with the Desktop limit beside each; `build_report.py` runs the builders twice |
| Desktop JSON capture | M4 step 11 | Back up `report/`, change one thing in the GUI, Ctrl+S, read the `visual.json`, close without saving, restore. Used here for the **table** visual, **alt text**, the **status chip** conditional format and the **badge** |
| Mart views | `sql/views/R__mart_m4.sql` | `R__` repeatable, explicit columns, `GO` between views |
| Measures and twins | `_Measures.tmdl`, `tools/dax_twin_check.py` | Display folder per page; one SQL twin per key measure |
| DQ rules | `seed/dq_rule.csv` | `check_sql` returns offending rows; fault injection inside a rolled-back transaction (M4 step 8) |
| Tests | `tests/test_handbook.py` | pytest, no DB; contract first |
| Value guard | `tools/scan_handbook_values.py` | Names, lines and counts only, never values |

## Files to change
| File | Action | Why |
|---|---|---|
| `sql/views/R__mart_m5.sql` | CREATE | `mart.run_step_latest` (rows per source for the last run), DQ counts by status |
| `_Measures.tmdl`, `tools/gen_tmdl.py`, `tools/dax_twin_check.py` | UPDATE | P6/P6b measures (fail count, run text, empty states), new table; twins |
| `tools/build_p6_page.py`, `build_p6b_page.py`, `report_builder.py` (NAV, ⓘ, badge, alt text), all `build_*_page.py` | CREATE / UPDATE | 5.1, 5.2, 5.3 |
| `tools/templates/table.json` (+ alt-text and chip captures) | CREATE | Desktop captures |
| `tools/export_pages.py` | CREATE | PDF → per-page PNG, drop P3/P3b (Q2), hidden pages excluded |
| `docs/img/*.png`, `docs/report.pdf`, `docs/walkthrough_script.md`, `docs/a11y.md` | CREATE | 5.3, 5.4 |
| `README.md` | REWRITE | 5.5 |
| `.github/workflows/ci.yml`, `.github/dependabot.yml`, `ruff.toml`, `.sqlfluff` | CREATE | 5.6 |
| `pipeline/migrate.py`, `pipeline/cli.py`, `sql/migrations/V017__m5_hardening.sql`, `sql/transform/*`, `seed/dq_rule.csv`, tests | UPDATE / CREATE | Q4 hardening |
| 20 ruff findings across `pipeline/` and `tests/` | UPDATE | Q4 |
| `tools/scan_handbook_values.py` | UPDATE | `--history` mode: every blob in every commit (5.8) |
| `docs/forecast_final.json`, `Documents/*` hashes | UPDATE (only if Q1 rewrite) | Re-point to rewritten hashes, documented |
| `DATA_LICENSES.md`, docs 01/03/04/06, `00_Index.md` | UPDATE | As built |

## Tasks (in build order)
**Model tiers (doc 06 §4):** D = Opus 5.5 (this session); S = Sonnet 5.5 subagent; F = Haiku 4.5 subagent; GUI = Power BI Desktop, which I drive via computer use (`Start-Process`, `tools/model_refresh.ps1`).

**Escalation:** a step that fails verification twice moves up one tier.

**Every commit** comes after `validate_report.py`, `dax_twin_check.py` (Desktop open; all 31 + new twins pass) and `scan_handbook_values.py`.

**Desktop:** close it before `pipeline run`; never rebuild pages while it is open.

| Step | Doc 06 | What | Model | Verify |
|---|---|---|---|---|
| 1 | 5.1, 5.3 spike | **GUI capture round** on a scratch page (synthetic, then discarded): table visual (+ conditional-format status chip), alt text on a chart, a shape badge bound to a measure, a URL action on a button (ⓘ / repo link); **one** report-page tooltip retry (Q4). `report/` backed up and restored | GUI + D | Templates committed; tooltip outcome recorded; validator 0 problems |
| 2 | backlog | **Hardening batch** (Q4): 20 ruff fixes, `ruff.toml`, V017 (DENY), applock + version-order check in `migrate.py`/`cli.py`, the 4 transform LOW items, role tests. Tests first | S, Deep read | pytest green; `ruff check .` 0; applock proven by two concurrent runs (one waits); role tests show `role_report_reader` can't write. **Then `ecc:database-reviewer`** on V017 + transforms |
| 2b | backlog | DOSM gap cause, **time-boxed 30 min** | D | Cause found and noted in `docs/reconciliation.md`, or "unexplained" recorded as a caveat |
| 3 | 5.1, 5.2 | `R__mart_m5` + P6/P6b measures (fail count, run summary text, empty states, consent text) + twins; DQ Fail badge measure. Injected FAIL (rolled back) shows count 1 | D | New twins PASS; all 31 old twins PASS; the badge measure = 1 under injection, 0 after rollback |
| 1–3 → outcome | 5.1–5.3 | **Done 2026-10-07** (session 1; Gmail checked first: no reply from the Energy Commission or GSO):<br>• **Step 1** (`49b7083`, Claude via computer use, scratch page, `report/` backed up and restored, validator 0): templates `table_status_chip_alt_tooltip.json` (tableEx; text-rule conditional background; alt text = `visualContainerObjects.general.altText`), `shape_fill_measure.json` (fill bound to a measure), `button_info_weburl.json` (the built-in **Information** button = ⓘ; `visualLink` `WebUrl`). **Report-page tooltip retry: it renders.** Desktop writes `visualTooltip` with only `show` + `section`; our `tooltip_page()` also wrote `type 'ReportPage'`, the likely M2 cause. **T2 stays** (Q4) and is wired back in step 4.<br>• **Step 2** (`c4ab786`, Sonnet, tests first, Deep-read): one session applock (fail fast) on migrate/seed/extract-load/transform/forecast/run, proven with a held lock (second process exits 1 with a clear message); out-of-order V-script check; V017 DENY on `meta.schema_version` for `role_pipeline` (role tests via `CREATE USER … WITHOUT LOGIN`, rolled back); LOW items: 1 GWh negative tolerance, `is_complete` in Malaysia time, capacity-only sources kept (`generation_twh` nullable; 0 such rows today, Malaysia checksums unchanged). `ruff.toml` (0.16.9, py313, 120 columns): `ruff check` 0; `ruff format --check` would change 40 files (step 8 decision). **`ecc:database-reviewer`:** 0 CRITICAL, 0 HIGH, 3 MEDIUM, all fixed (lock coverage, release tests that couldn't fail, 020 filter `capacity_gw > 0` + showcase 05 reason). 971 tests.<br>• **Step 2b** (12 of 30 min): **partly explained**, in `docs/reconciliation.md`: a stable 4–7% net-vs-gross / self-generation part, plus an Ember revision of Malaysia 2021+ (OWID carries the older Ember vintage). Which component Ember revised stays unverified.<br>• **Step 3** (`c9f47ad`): `mart.source_load_latest` (each source's latest completed load, since a transform-only run has none), V018 `dim_data_source.provides` (doc 03 "what it gives"), `url` as WebUrl, 2 relationships, 15 measures (folder About), **twins 35/35**. **Badge proof:** rolled-back FAIL injection gives SQL 0 → 1 → 0; the Import model can't see uncommitted rows, so the DAX side used a committed flip of one result, reverted: `[DQ Fail Count]` 0 → 1 (text "1", fill red) → 0 (blank, rail navy). Plan deviation: DQ counts are measures, not a view. Badge sits on the **Data quality** nav item (the DQ table moved to P6b in Q3) | — | — |
| 4 | 5.1–5.3 | `build_p6_page.py` + `build_p6b_page.py` + NAV/ⓘ/badge in `report_builder.py` + alt text on **every** visual (from a per-visual description in each builder). One Sonnet brief, continued across rounds | S + GUI | validator 0 problems; **≤ 2 GUI rounds**: every doc 03 P6 row (links open, DQ row click filters, status filter, empty state), badge on every page under an injected FAIL, alt text present (Desktop's alt-text pane spot-check on 5 visuals), Windows high-contrast check, tab order |
| 4 → outcome | 5.1–5.3 | **Done 2026-10-07** (Sonnet built it; 2 GUI rounds driven by Claude via computer use; a committed FAIL flip, reverted at the end, lit the badge):<br>• **Built:** `build_p6_page.py` (sources table with link icons, KPI definitions, method notes, consent line, GitHub WebUrl button), `build_p6b_page.py` (run + DQ summaries, Pass/Warn/Fail tiles, a rows-per-source table that cross-filters the DQ table, DQ table with icon + word chips, empty-state overlay, expected-WARN note), NAV 9 + Reset, the Fail badge (measure-bound fill + text) on the Data quality item of every railed page, the ⓘ button on every page, alt text on every visual (validator-enforced; 3 decorative exclusions), `tooltip_page()` without `type`, and **T2 wired back** on 4 P5 visuals.<br>• **Round 1 found:** `Run Summary` was a SYNTAXERROR (`id` is reserved as a variable name in this Desktop, like `at`); `Consent Summary` and the rows-per-source table picked up the **blank `data_source` row** that the new `dq_latest` relationship creates (`ALLNOBLANKROW`; `Source Last Loaded` now returns BLANK, not ""); the ⓘ in the header cut long titles to 800 px (moved to the foot of the rail, white); the T2 cards had no room for their values (page now 320 × 280); the GitHub label and consent line clipped.<br>• **Every doc 03 P6 row passes:** source click → the DQ table filters to that source (the summary stays page-wide); FAIL tile → only the failing rule; badge "1" in red on every page under the injected FAIL and **invisible at 0**; the ⓘ and the badge navigate; T2 renders on hover with the right country; the link column renders as link icons (Claude did not click external links: Ctrl+click them once). Alt text spot-checked in Desktop's pane on 5 visuals (DQ table, rows-per-source, status tiles, a nav button, the P1 area chart).<br>• **Tab order:** Desktop's Tab order pane lists the **highest** `tabOrder` first, so every page was in reverse reading order; `rb.visual()` now writes `1000 − z` (901–998). Fixed after round 2, with the T2 card label and the notes width: **these three are checked by the validator only, not yet in the GUI** (check them at the step 5 export round). Not done: the Windows high-contrast check (it changes a system setting: Amirul toggles it, or we skip it). Desktop hung once on close ("Working on it"); that instance was ended after confirming `report/` was untouched.<br>• Validator 269 visuals, 0 problems; twins 35/35; 971 tests; ruff 0; value scan 0 | — | — |
| 5 | 5.4 | Export PDF in Desktop (GUI), `tools/export_pages.py` → `docs/img/p*.png` + `docs/report.pdf` without P3/P3b (Q2). **`design:accessibility-review`** on the PNGs; `docs/a11y.md` checklist | F + GUI + S | PNGs 1280×720, render on GitHub (checked after push); a11y checklist all ticked; value scan finds 0 (PNGs are images, so the PDF text is scanned too) |
| 5 → outcome | 5.4 | **Done 2026-10-07** (same session as steps 1–4, at Amirul's "continue with step 5"; `tools/export_pages.py` written inline instead of by a Haiku agent, about 80 lines):<br>• **The three validator-only fixes from step 4 passed in the GUI:** tab order (also confirmed independently: a Desktop save renumbers `tabOrder` with the first nav button highest and the footnote 0), T2 card label, P6 method notes.<br>• **Export:** Desktop's Export to PDF writes to `%TEMP%\Power BI Desktop\print-job-*\` and opens the viewer (no save dialog). The full PDF goes to `data/private/report_full.pdf` (git-ignored, because it holds P3/P3b). `export_pages.py` maps PDF pages to the visible pages (the counts must agree), drops pages whose source consent isn't GRANTED (**fails closed**; a test caught my first version, which would have published a page whose source was missing from the seed), and refuses to write if restricted marker text ("SAIFI by region", "darker = less reliable") is missing from a dropped page or present on a kept one. Output: `docs/report.pdf` (7 of 9 pages, new document with no Desktop metadata) and `docs/img/01–07_*.png` at 1280 × 720.<br>• **Guards:** `test_no_restricted_data.py` allows exactly `docs/report.pdf` and checks its text for the markers; `scan_handbook_values.py` now reads PDF text layers (0 files to check).<br>• **`design:accessibility-review`** on the 7 PNGs, recorded in `docs/a11y.md`: **critical** dark heatmap values on the theme's darkest blue (~2:1), fixed (gradient ends at `#5a91d6`, 6.05:1); **major** reversed tab order (fixed in step 4, plus non-focusable frame shapes now sort last); **major** stacked areas keyed by colour only, fixed in part with Desktop's **series labels** (captured by save; Desktop hides colliding labels, legend kept). Open minors: scrolling tables export only their first rows; P2's main chart is ~40 px tall; three truncated labels. Not done: Windows high contrast and a screen-reader pass (checklist items left unticked).<br>• **RAM:** with Desktop + the PDF viewer + SQL Server open, `pytest` died in collection with `MemoryError` (the M2 memory issue); with Desktop closed, 979 pass. Twins 35/35 (Desktop open, final state); validator 269 visuals, 0 problems; ruff 0; value scan 0 | — | — |
| 6 | 5.4 | `docs/walkthrough_script.md` (J2 without P3/P3b, ≤ 2 min, click by click). **You record** whenever ready | D → you | Script ≤ 2 min when read through; video uploaded at step 12 |
| 7 | 5.5 | README: question, 3+ findings (from `docs/findings.md`, re-verified against the warehouse), hero PNG, architecture diagram (Mermaid, from doc 02 §1), setup, "How to explore", credits and licences, D5/GSO notes, honest limits | D | Every number in the README matches the warehouse (scripted check); the 30-second test: a fresh-context agent reads only the README top and states a finding |
| 8 | 5.6 | CI + Dependabot + `.sqlfluff` (Q5) | F | Green run on push (minutes checked first); sqlfluff blocking or explicitly non-blocking |
| 9 | 5.7 | **Fresh-clone reproduction** (Q7), timed, following only the README | D | < 30 min excluding installs; `pipeline run` exit 0; P6b shows the run and only the known WARNs; any README fix committed and the clone redone |
| 6–9 → outcome | 5.4–5.7 | **Done 2026-10-07** (session 2; Gmail checked first: the Energy Commission redirected the request to two named officers, not consent; resend drafted for Amirul, unsent; GSO: no reply):<br>• **Step 6:** `docs/walkthrough_script.md`, J2 without P3/P3b, about 1:50 (210 words of narration), click by click, with a pre-recording checklist (Ctrl+click for buttons in Desktop).<br>• **Step 7:** README rewritten (question, 4 findings, hero PNG, Mermaid architecture, how to explore, setup, data and consent, limits incl. the open a11y minors, repo map). New `tools/check_readme_numbers.py` rebuilds every README claim as its exact phrase from the showcase queries (13 claims). **30-second test passed:** a Haiku agent given only the README top, no tools, stated finding 2 correctly; it re-read finding 3, which was reworded.<br>• **Step 8:** `.github/workflows/ci.yml` (ubuntu, Python 3.13: ruff check, ruff format --check, sqlfluff **non-blocking** (623 findings: alias/layout style, 3 parse errors on valid T-SQL), pytest), Dependabot weekly (pip + Actions; opened 7 PRs at once, all green, not merged), `.sqlfluff` (tsql, LT01/LT05 excluded). **Format decision (Amirul):** `ruff format` applied to 41 files, `pipeline/forecast/` excluded so the locked FINAL code stays byte-identical; proven behaviour-neutral by the tests and a byte-identical rebuild of every page; `.git-blame-ignore-revs`. Actions minutes checked first (gh `user` scope granted by Amirul): 0 used. First CI run failed on one race (the runner's git detaches auto-maintenance in a throwaway test repo), fixed in `debfc3e`; CI green (960 passed, 19 skipped).<br>• **Step 9:** the first clone failed at checkout ("Filename too long": the scratchpad path is 120 chars, the deepest file 108 below the repo folder), so the README now says to clone into a short folder and the clone moved to `C:\src` (plan deviation from Q7's scratchpad). Run 1 took 12 min wall-clock and found two more gaps: Desktop's **Apply changes** bar after Edit parameters (added to the README) and **Ember's 6 Oct 2026 release**, which revised Thailand (2025 bioenergy 10.2 → 22.1 TWh, RE share 16.6% → 21.7%), Vietnam and the Philippines, but not Malaysia. The README check caught it: Malaysia is now **4th of 6** on renewable share (was 3rd). Amirul chose to move to the new release: live run 46, finding 3 rewritten (findings.md, README, P1 box, walkthrough, showcase 03), PDF/PNGs re-exported (`dc7bc1a`). **Redo: 6.8 min wall-clock** following only the README (pip 2 min, migrate + seed + run 1.5 min, Desktop apply + load ~2 min); `pipeline run` exit 0, 30 PASS / 4 known WARN / 0 FAIL, both forecast replays identical, 13/13 README claims match the fresh DB. Twins 35/35, validator 0, 979 tests, value scan 0 | — | — |
| 10 | 5.8 | **History decision (Q1):** dry run on a throwaway clone (filter-repo, record re-pointing, tests, replay on a throwaway DB, `scan_handbook_values.py --history`). Report to you; force-push **only with your go** | D | All checks green on the clone; bundle backup made; after the push, a fresh clone replays the forecast and the history scan finds 0 |
| 11 | 5.8 | **Pre-publish audit:** secrets scan over all history, no `data/`, `.pbix` or PDF other than `docs/report.pdf` in any commit, licence credits complete (every `dim_data_source` row, README, P6), GSO/D5 values absent (history scan). **`ecc:security-reviewer` + `anthropic-skills:audit-my-work` go/no-go** | D + reviewers | Verdict "go"; findings fixed and re-checked |
| 12 | 5.9 | **Asks you first:** public, tag `v1.0.0` + Release, profile link; walkthrough added to the README | F + you | The public URL opens in a private window; README video plays |
| 13 | acceptance | Doc 01 Must sweep (each verification column, with evidence), docs 01/03/04/06 as built, `DATA_LICENSES.md`, plan Outcome, index, vault note, skill-test memory | D | The acceptance list below |

**Batching:** steps 2 and 3 can run in parallel (Sonnet on 2 while I do 3). Step 6 can be done anytime after step 4. Steps 10–12 are strictly in order.

**GUI rounds:** step 1 (capture) and step 4 (≤ 2; the last doubles as the final check), plus the export in step 5 and the fresh clone in step 9.

**Sessions:** 1 = steps 1–4; 2 = steps 5–9; 3 = steps 10–13 (the irreversible ones, in a fresh session with a clear head).

## Definitions pinned for this milestone
| Term | Definition |
|---|---|
| "Current after a refresh" (FR-14) | P6b shows the latest `meta.load_run`, and its timestamps change after `pipeline run` + model refresh |
| Fail badge | The count of rules with status FAIL in the latest run; hidden when 0 |
| Public export set | Visible pages except P3 and P3b (while D5 consent ≠ GRANTED); hidden pages (D1, T2) never |
| "go" (5.8) | 0 secrets, 0 restricted values or files in any commit, every source credited per its licence, both reviewers agree |

## Validation (end of M5)
```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m sqlfluff lint sql/
.venv/Scripts/python -m pipeline run                    # Desktop closed; exit 0; only the registered WARNs
.venv/Scripts/python tools/validate_report.py           # 0 problems
.venv/Scripts/python tools/dax_twin_check.py            # all twins PASS (Desktop open)
.venv/Scripts/python tools/scan_handbook_values.py --history   # 0 files to check, in every commit
git log --all --name-only --format= | grep -iE '\.pdf$|^data/|\.pbix$' | grep -vx 'docs/report.pdf' | sort -u   # empty (docs/report.pdf is the public export, M5 step 5)
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| The history rewrite breaks the forecast replay or reproducibility | **High if done blind** | Q1 dry run on a clone first, replay on a throwaway DB, bundle backup, force-push only with your go |
| Restricted content ships in an export (PNG text isn't scannable) | Medium | P3/P3b dropped by script, not by hand; the PDF text layer is scanned; the 5.8 reviewer looks at every PNG |
| P6 doesn't fit, or table visuals behave differently from templates | Medium | Q3 split + step 1 capture before any build |
| Alt text, chips or badges have no template | Medium | Step 1 capture by save (the M4 pattern) |
| CI fails on Linux (Windows-only paths, `mssql-python` wheels) | Medium | Tests already need no DB; first run checks the wheel install; Windows runner as fallback |
| Private-repo Actions minutes | Low | Checked before the first push; ~2 min per run |
| The fresh clone exposes README gaps | Likely (that's its job) | Fix and re-run; time each run |
| Desktop quirks (second instance, overlays, unsaved-change prompts) | Medium | `Start-Process`; never `open_application` for focus; close without saving |

## Acceptance (the doc 06 M5 check, plus)
- [ ] Every **Must** in doc 01 passes its verification column, with the evidence noted (FR-13/22 as built on Thailand/Singapore, as accepted in M3)
- [ ] P6 + P6b: every source credited; consent status shown; run summary and DQ table current after a refresh; empty state works; the badge shows on an injected FAIL
- [ ] Alt text on every visual; `docs/a11y.md` checklist ticked; `design:accessibility-review` findings fixed
- [ ] PNGs, PDF and walkthrough visible on GitHub, without P3/P3b (Q2)
- [ ] README passes the 30-second test; every number in it matches the warehouse
- [ ] CI green; Dependabot on
- [ ] Fresh clone < 30 min following only the README
- [ ] History decision (Q1) carried out; the history scan finds 0; the replay works on a fresh clone
- [ ] 5.8 verdict "go" from `ecc:security-reviewer` + `audit-my-work`
- [ ] Repo public, `v1.0.0` tagged, profile link added (your go)
- [ ] Twins all PASS; validator 0 problems; tests green
- [ ] Docs, `DATA_LICENSES.md`, index, vault note and skill-test memory updated; pushed
