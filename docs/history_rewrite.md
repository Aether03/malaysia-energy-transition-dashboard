# History rewrite (M5 steps 10–11, 2026-10-07)

## Why
- **Restricted data.** Two figures from the Malaysia Energy Statistics Handbook (D5) had been typed into committed text: a "synthetic" sample row in `Documents/05_Data_Schema.md` (from the first commit) and an example value in comments in `sql/migrations/V015__regions_and_reliability.sql` and `sql/views/R__stg_handbook.sql`. M4 removed them from the tree (`aefb12e`), but they stayed in history. The handbook's licence (p.5, `DATA_LICENSES.md`) does not allow redistributing any part without the Energy Commission's written consent.
- **Personal data.** Two Energy Commission officers' personal email addresses had been written into planning notes (`Documents/00_Index.md`, `Documents/plans/M5_plan.md`). Third-party personal data doesn't belong in a public repository (NFR-05).

Both had to go before the repo became public (M5 plan, Q1; the step 11 audit found the addresses).

## What changed
- `git filter-repo --replace-text` replaced the affected lines in every commit: each handbook line with the text the M4 fix put in its place, and each address with a description ("the two officers the Energy Commission named"). Nothing else changed.
- The first leak is in the first commit, so **every commit hash changed**. Commit dates, authors and messages are unchanged.
- One commit then re-pointed every hash cited in the tree to its new value (table below): `docs/forecast_final.json` (`protocol_commit`, `git_commit` for both FINAL runs), `docs/forecast.md`, `.git-blame-ignore-revs`, `tools/report_builder.py` (a comment) and the planning documents in `Documents/`.

## The forecast record
The FINAL backtests were not re-run, and no number in `docs/forecast_final.json` changed. The replay reads the protocol at the record's `protocol_commit`; the new commit `50dcc1a` holds a `docs/forecast.md` byte-identical to the old `d7a03e2`, and its tree differs only in the rewritten line of doc 05. So the re-pointing changes where the replay finds the same protocol, not what it finds.

## Checks (on a throwaway clone, before anything was pushed)
- `tools/scan_handbook_values.py --history`, including its label-plus-value check: 0 files to check in every blob of every commit. The same scan flags all four leaked blobs in the old history.
- The removed numbers (and the comma-free form of one) searched in every commit: 0 hits; the same search finds them in the old history.
- The two addresses searched in every commit: 0 hits. gitleaks over every commit: 0 findings.
- Full test suite; the forecast replay of both FINAL runs on an empty database: identical.

## Old → new commit map
Old hashes still appear in notes outside this repo (vault notes, session logs). Use this table to translate them.

| Old | New | Date | Subject |
|---|---|---|---|
| `fe3a44d` | `c55592e` | 2026-10-03 | feat(pipeline): Thailand hourly source (DTH) -> raw.grid_interval as an exact copy of both |
| `f6bb02e` | `ca704d5` | 2026-10-03 | docs: index notes M3 step 1 done (Scratch clean-up pending) |
| `f0cb629` | `d53b875` | 2026-10-05 | docs: index after P4 GUI round 3 |
| `efb4af6` | `413adec` | 2026-10-03 | fix(forecast): ecc:mle-reviewer pre-test findings (M3 step 8 review) |
| `ef089e9` | `3c6e1a0` | 2026-09-30 | docs: index notes the live plan-project skill test (log observations every session; evalua |
| `eb2fa16` | `9322508` | 2026-09-30 | docs(M2 step 1): RE capacity targets verified: large hydro included; 31/40 re-attributed t |
| `e94f8e9` | `7e787ce` | 2026-10-02 | feat(report): D1 Country Deep Dive drill-through page (P2 layout per country, no NETR pane |
| `e733c8e` | `a50e169` | 2026-10-03 | docs: M2 complete (acceptance passed, outcome and backlog recorded; next M3) |
| `e71b571` | `144758a` | 2026-10-02 | fix(report): P5 peers muted via explicit per-country colours (line series ignore the defau |
| `e6607f3` | `031c610` | 2026-09-30 | feat(sql): SQL showcase 01-05 (trends, YoY with LAG + polarity, RANK on latest common year |
| `e3689fb` | `e72e50d` | 2026-09-30 | docs: GSO consent request sent (task 0.4); gh installed |
| `df00641` | `012be5e` | 2026-09-30 | docs: M0 task 0.2 complete (SSMS 22, sqlcmd verified) |
| `debfc3e` | `c431991` | 2026-10-07 | test: disable git auto-maintenance in the throwaway protocol repos (CI race) |
| `dc7bc1a` | `b0d2aef` | 2026-10-07 | feat(m5): step 9: move to Ember's 6 Oct 2026 release; finding 3 rewritten; README gaps fro |
| `dbe91d7` | `71bfc64` | 2026-09-30 | feat(pipeline): shared source helpers (_common) + OWID D2 module, test-first (M2 step 2, p |
| `db8b371` | `2d77311` | 2026-10-05 | docs: index resume point -> M4 step 11 |
| `d8fae79` | `0bc5c13` | 2026-10-03 | docs: M3 step 1 closed (Scratch removed; Desktop's z-order/tabOrder resave discarded, repo |
| `d7a03e2` | `50dcc1a` | 2026-10-03 | fix(forecast): mle-reviewer re-verification items before the one-shot run |
| `d73808f` | `a251448` | 2026-10-03 | data(forecast): FINAL 2024 backtest record for TH_EGAT (M3 step 9, run once) |
| `d24a305` | `a62a9ff` | 2026-09-30 | docs: record M0 progress and model routing decision (task 0.6) |
| `cf03999` | `57d29b6` | 2026-10-02 | fix(report): P1 Desktop test 1: show flags outside state selectors (transparent shapes, na |
| `cea39ea` | `c37308a` | 2026-10-02 | feat(report): shared page frame (report_builder) + P1 polish: nav rail, left-aligned takea |
| `cc3d721` | `a36d9b5` | 2026-09-30 | feat(sql): reconciliation showcase query; 5/5 Malaysia 2025 figures within 0.005% (M1 step |
| `c9f47ad` | `334b29e` | 2026-10-07 | feat(m5): step 3: P6/P6b model: source_load_latest, provides column, About measures, fail  |
| `c9db318` | `34a5464` | 2026-09-30 | feat(db): V006 consent status NOT_REQUESTED; plan note on Net imports share |
| `c8f9303` | `2dcea1c` | 2026-10-05 | fix(report): P4 GUI round 3 (checked by Claude via computer use): monthly charts widened t |
| `c70ec48` | `de3f866` | 2026-10-03 | feat(report): Reset buttons wired to Desktop-made bookmarks (P1, P2, P5); transparent hove |
| `c6e1b61` | `5a4d76a` | 2026-10-03 | docs: M2 final Desktop check passed (Reset buttons, KPI hover) |
| `c4ab786` | `b82db10` | 2026-10-07 | feat(m5): step 2: hardening batch (applock, version order, V017 DENY, transform LOW items, |
| `c1ddb90` | `c0f2d7a` | 2026-09-30 | feat(db): migrations V001-V005 (schemas, roles, meta, dims, Ember raw, annual facts, grant |
| `be9203f` | `724203a` | 2026-10-03 | feat(forecast): day-ahead LightGBM backtest developed on 2023 only; protocol drafted (M3 s |
| `bad6e31` | `f2abda5` | 2026-10-03 | test(forecast): M3 step 7 test-first suite + the forecast contract as stubs |
| `b9d883e` | `6b57a1c` | 2026-09-30 | docs: M1 complete (empty-DB rebuild, P1 verified in Desktop); plan outcome + friction note |
| `b82b365` | `53fc209` | 2026-10-03 | docs: index M3 steps 7-8 done; mle-reviewer approved; step 9 awaits Amirul's go |
| `b7fa02e` | `e8accec` | 2026-09-30 | feat(report): model gets hours_in_year, target source_name and re_capacity_official; gen_t |
| `adc9f47` | `3b27659` | 2026-10-03 | docs: index M3 resume point (steps 2-6 done; next session starts at step 7) |
| `ad205be` | `d57438f` | 2026-09-30 | docs: reconciliation evidence, SQL + independent pandas recheck, 5/5 pass (M1 step 10) |
| `abb5272` | `03beeeb` | 2026-10-02 | fix(model): DAX review findings: Compare Country selection table, exact twin comparison, h |
| `a12868e` | `5bca0a4` | 2026-10-02 | docs(findings): 3 headline findings with source queries 06/07, draft for audit (M2 step 12 |
| `a0bb3a4` | `b15bb7e` | 2026-10-03 | docs: index marks M2 complete with the M3 resume point and the M2 backlog |
| `9dabb2a` | `abe6025` | 2026-10-02 | docs(findings): cite Ember lifecycle methodology; verify peer set = six largest systems |
| `9a77069` | `1793df6` | 2026-09-30 | chore: scaffold repo, planning docs, licences (M0 task 0.3) |
| `9a059bd` | `eb3e0e3` | 2026-10-02 | feat(report): P1 rank/findings/KPI links, P2 Generation, P5 ASEAN, T2 tooltip pages + buil |
| `9999b24` | `141a4b9` | 2026-10-07 | ci(m5): step 8: GitHub Actions (ruff check + format, sqlfluff non-blocking, pytest), Depen |
| `981f6b7` | `de577e9` | 2026-09-30 | feat: seeds, stg/mart views (M1 step 3) + database-review hardening (V007, XACT_ABORT, res |
| `948f3ac` | `ca50805` | 2026-10-04 | fix(model): P4 GUI round 1: shorter takeaway and forecast-day titles (one line), [Avg Load |
| `92fdbf8` | `de20fc2` | 2026-09-30 | feat(pipeline): OWID D2 load, population + demand per capita, V008, re-sourced targets, 4  |
| `91bce23` | `8a84c8c` | 2026-10-02 | feat(report): P1 headline findings box filled from the audited docs/findings.md (M2 step 1 |
| `91abadb` | `e8fab8d` | 2026-10-04 | feat(model): titles for the P4 split (Grid load takeaway; Forecast subtitle) |
| `90f30b9` | `8a04ebb` | 2026-10-03 | fix(db): M3 database review: gap rule driven from dim_grid (a grid with 0 hours now fails, |
| `8edf66a` | `81d7b4a` | 2026-10-02 | feat(model): M2 DAX measure library, field parameters, target axis; DAX/SQL twin check via |
| `8a8c7a1` | `6356235` | 2026-10-02 | fix(report): build_tooltips syntax (comment inside call); T2 rebuilt |
| `895fd33` | `8a12c0b` | 2026-10-05 | feat(m4): steps 8-10: handbook stg/dw, 12 DQ rules, mart + showcase, P3/P3b model and 8 tw |
| `87b8b44` | `54b7798` | 2026-10-02 | fix(report): frame shapes and nav buttons opt out of the theme's card background/border; n |
| `7f98ede` | `e343f3a` | 2026-10-02 | chore(report): Desktop-saved visual templates for M2 pages (step 5); auto date/time off, s |
| `7f7ef3c` | `73ab558` | 2026-10-07 | feat(m5): step 10: scan_handbook_values.py --history (every blob reachable from any ref) |
| `7e2fd6b` | `eedc1a2` | 2026-09-30 | feat(pipeline): Ember D1 extract + idempotent MERGE load, test-first (M1 step 5) |
| `7da0d9b` | `b31ea73` | 2026-10-05 | test(m4): step 5: handbook parser tests first, on synthetic page fixtures + licence guard |
| `7aaa6bf` | `2d4439a` | 2026-10-05 | feat(m4): steps 1-4: Desktop spike templates, V015, state seeds and boundary map, handbook |
| `7a9f4f5` | `baa1fa4` | 2026-10-05 | feat(m4): steps 6-7: handbook parser, D5 runtime load, blind re-read (0 differences), revi |
| `71e69c3` | `09b8dba` | 2026-09-30 | docs: M2 step plan approved (Q1-Q6 decisions, OWID/DOSM coverage facts) |
| `6ed1788` | `768b30b` | 2026-10-03 | fix(report): drop bookmark option preserveNewVisualVisibility (Desktop 2.158 writes it but |
| `6e714cb` | `9e5ad48` | 2026-10-02 | docs: index resume point before GUI round 7 |
| `67b6544` | `afb94f4` | 2026-10-04 | fix(report): P4 Grid load relayout after GUI round 2: full-width 12x24 heatmap at 40 px co |
| `66dfbb6` | `c6faba2` | 2026-10-03 | feat(db): V010 grid, calendar and forecast tables; dim_hour/dim_grid seeds (lookup-resolve |
| `665adf8` | `fe50d4d` | 2026-10-02 | fix(report): field parameters use Desktop's fieldParameters shape; P2 rows and T2 sizes so |
| `6657091` | `2cf2882` | 2026-09-30 | feat(pipeline): run/step logging to meta with separate autocommit connection; run --dry-ru |
| `65bb3df` | `2cb51fa` | 2026-10-04 | feat(report): P4 Grid load page (banner, grid slicer, load curve + season toggle, heatmap, |
| `63e8171` | `312e317` | 2026-10-03 | feat(dw): Thailand hourly staging (Q1 row precedence, local->UTC, 5-region sum, flows by c |
| `61cb6f6` | `0ce9e40` | 2026-09-30 | feat(report): PBIP semantic model (M1 step 8, untested in Desktop yet) |
| `61a5b2e` | `a82bf55` | 2026-10-03 | docs: index notes the Desktop bookmark-option quirk |
| `6156d81` | `44df64b` | 2026-09-30 | feat(pipeline): DOSM D3 cross-check loader + annual staging + WARN rule, test-first (M2 st |
| `609385f` | `3a870db` | 2026-10-02 | fix(model): selection measures use FILTER (IF cannot return a table); DAX/SQL twins 14/14  |
| `5efb683` | `4ac7967` | 2026-09-30 | chore(report): Desktop-saved scaffold visuals (templates for P1 build) + lineage tags |
| `5db6303` | `2520e8d` | 2026-10-03 | feat(report): Desktop-captured Date Picker slicer template (mode 'RelativeDatePicker') for |
| `5a5267a` | `5d9916a` | 2026-10-04 | feat(report): P4 split into Grid load (curve, season, 12x24 heatmap, peak/LF, flows) and n |
| `52fc295` | `80d3c15` | 2026-10-04 | feat(mart): P4 mart views (published grids only; season/day type per grid; daily net flow; |
| `511b22d` | `2f72da0` | 2026-10-04 | docs: P4 split into Grid load + Forecast (docs 03, 04) |
| `5071e98` | `a1a14c7` | 2026-10-04 | fix(report): P4 GUI round 1: heatmap fits 12x24 in GW, forecast chart 160 px, cards in one |
| `4b0f92f` | `51eb959` | 2026-10-02 | fix(report): GUI round 3: field parameters bind the visible column, slicer defaults stored |
| `4a4bab4` | `e02c2d7` | 2026-09-30 | fix: transform review findings (capacity share, single transaction, fail-closed DQ, RCSI,  |
| `49b7083` | `17692bb` | 2026-10-07 | feat(m5): step 1: Desktop captures for P6 (table + status chip + alt text + page tooltip,  |
| `4797887` | `2d754d2` | 2026-10-04 | feat(model): P4 takeaway title and subtitle measures |
| `4198eb1` | `5d2b75d` | 2026-10-03 | data(forecast): FINAL 2024 backtest record for SG_EMA (M3 step 9, run once) |
| `3d302ea` | `2601f11` | 2026-10-07 | style: ruff format at 120 columns (41 files; pipeline/forecast excluded) |
| `39006db` | `4d91ab7` | 2026-09-30 | fix(db): M2 database-review findings (NULLIF-safe DQ division, NULL-aware intensity rule,  |
| `38b60f8` | `a43d165` | 2026-10-07 | feat(m5): step 5: public PDF + page PNGs without P3/P3b, accessibility review and fixes |
| `3850918` | `fbd1c41` | 2026-10-03 | docs(forecast): 2024 backtest results (both grids beat the baseline and the weekday-aware  |
| `37e0ba4` | `c5f80dc` | 2026-10-07 | docs(m5): steps 6-7: walkthrough script and README; scripted README number check |
| `36c0667` | `e518282` | 2026-10-03 | feat(report): Desktop-captured templates for P4: matrix heatmap (linearGradient2 backColor |
| `33fb7e8` | `049d38f` | 2026-10-05 | docs: M3 complete (acceptance ticked, Outcome, doc 06 status, index resume point -> M4) |
| `33e8b36` | `68f78d2` | 2026-10-07 | feat(m5): step 4: P6 About + P6b Data quality, Fail badge, info button, alt text everywher |
| `33c36bf` | `90f672b` | 2026-10-02 | docs(findings): apply audit-my-work corrections (3-yr averages + 2015-17 hydro step, coal- |
| `313cb39` | `7dfac57` | 2026-10-07 | docs(m5): M5 plan approved (Q1-Q8); Energy Commission consent request sent, GSO follow-up; |
| `30adf17` | `e4c3ae5` | 2026-10-03 | fix(pipeline): M3 python review: strict row width and number parsing, Excel error cells st |
| `2ef1bc6` | `a88e9c2` | 2026-10-02 | docs: index resume point after GUI round 4 |
| `2ea643e` | `d4212fb` | 2026-10-02 | feat(report): built-in tooltips carry T2 figures (P5) and T1 KPI definitions from seeds (P |
| `2a30a9e` | `b0bd933` | 2026-10-03 | docs: M3 resume point after steps 2-6 (Singapore added, reviews fixed, P4 TH label decided |
| `2915897` | `51c91f6` | 2026-09-30 | feat(report): P1 Overview page built from script (M1 step 9, untested in Desktop yet) |
| `26bc2bc` | `bc829ef` | 2026-10-05 | docs(forecast): limit found in the P4 review: record peaks are under-forecast (trees can't |
| `25f49a1` | `9905869` | 2026-10-05 | docs: M4 step plan approved in the plan canvas (Q1-Q9 as proposed); index and doc 06 statu |
| `228c604` | `2e206e8` | 2026-10-04 | feat(model): season_pick, a grid-scoped disconnected season toggle for the P4 load curve o |
| `1f8f3f5` | `b2c877e` | 2026-09-30 | feat(pipeline): transforms + DQ gate in one transaction (M1 steps 6-7) |
| `1d620cf` | `2d6fd9f` | 2026-10-04 | fix(model): P4 measure fixes from the Desktop check ('at' is reserved in Peak Text; flow G |
| `1bf4b34` | `5582bd2` | 2026-10-04 | docs: M3 as-built edits to docs 01 (DTH/DSG sources, grid-search result), 03 (P4 flows dai |
| `1b37a48` | `422a608` | 2026-09-30 | docs: index resume point after transform review |
| `1873118` | `48af68a` | 2026-10-07 | docs(m5): steps 6-9 outcome; index resume point -> step 10; Dependabot ignores the replay- |
| `1840270` | `4eb49b9` | 2026-10-04 | feat(model): P4 semantic model: 9 mart tables (generated), 10 relationships (hourly facts  |
| `1486144` | `aefb12e` | 2026-10-05 | feat(m4): steps 11-12: P3 Regions + P3b State reliability pages, acceptance, M4 complete |
| `1251556` | `9f45fc9` | 2026-10-03 | feat(pipeline): Singapore EMA half-hourly source (DSG) -> raw (106 weekly .xls, full preci |
| `11308ad` | `942ec57` | 2026-10-03 | docs: M3 step plan approved in the plan canvas (Q1-Q6; locked one-shot backtest protocol;  |
| `0e6811e` | `6f8b259` | 2026-10-03 | feat(db): Singapore (EMA) as the second grid per the Q4 search (SODL v1.0 verified from th |
| `070cd0f` | `9b3d986` | 2026-09-30 | docs: M0 complete (private repo created and pushed) |
| `06f6d75` | `31b804c` | 2026-10-04 | chore: Desktop-captured P4 templates from GUI round 1 (heatmap fixed column width, date dr |
| `0586e2e` | `f79e4c1` | 2026-09-30 | fix(report): P1 layout from first Desktop test (card heights for text, hidden auto subtitl |
| `0430ebf` | `fcafa2b` | 2026-09-30 | fix(report): remove /// description on relationship (TMDL relationships have no descriptio |
| `020203f` | `e2be28e` | 2026-09-30 | feat(pipeline): CLI skeleton, db helper with GO splitting, migration runner (M1 step 1) |
