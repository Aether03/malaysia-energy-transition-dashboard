# Refreshing the data

A manual routine for when a source publishes new data (Ember updates about twice a month). Nothing is scheduled: each step needs Power BI Desktop or a person's judgment, and nothing is pushed unread. Run the commands from the repository root.

## 1. Pipeline (Desktop closed)
- [ ] Close Power BI Desktop (it competes with SQL Server for memory).
- [ ] `.venv\Scripts\python -m pipeline run --refresh` (re-downloads every source, even if today's file exists). It must exit 0, with the 4 known WARNs and 0 FAIL in `meta.dq_result`. The locked forecast is replayed, not retrained.
- [ ] `.venv\Scripts\python tools\check_readme_numbers.py`. If a claim fails, Ember revised a number: update the README finding, `docs/findings.md` and the expected values in the affected `sql/showcase/` headers, and the vintage ("Ember release of …") in the README heading, `docs/findings.md` and `docs/release_notes.md`.

## 2. Web showcase data
- [ ] `.venv\Scripts\python -m pipeline export` (rewrites `exports/` as a whole set, or leaves it untouched on any failure).
- [ ] `.venv\Scripts\python tools\scan_handbook_values.py`, and read its output. If `exports/expected.json`'s `known coincidence` count changed, check each new hit by hand before updating `KNOWN`.

## 3. Report (Desktop open)
- [ ] Open `report\EnergyTransition.pbip`, then `powershell -NoProfile -File tools\model_refresh.ps1` (a stale cache fails the twin check).
- [ ] `.venv\Scripts\python tools\dax_twin_check.py`: every twin PASS.
- [ ] File → Export → Export to PDF. Copy the newest `%TEMP%\Power BI Desktop\print-job-*\EnergyTransition.pdf` to `data\private\report_full.pdf`, then `.venv\Scripts\python tools\export_pages.py` (writes `docs/report.pdf` and `docs/img/`).
- [ ] Close Desktop without saving, and check that `git status` shows no change under `report/`.

## 4. Check and publish
- [ ] Close Desktop, then `.venv\Scripts\python -m pytest -q`, `.venv\Scripts\python -m ruff check .` and `.venv\Scripts\python -m ruff format --check .`.
- [ ] Run `tools\scan_handbook_values.py` again and read its output (the new PDF is scanned too).
- [ ] Look at the new page PNGs, then commit and push. CI runs on the push, and Streamlit Community Cloud redeploys the web app from `main` with the new `exports/`.
