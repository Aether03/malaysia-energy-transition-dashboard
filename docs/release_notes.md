# Release notes

The text of each GitHub Release, kept here so it is reviewed with the code. Data vintage for both: Ember's 6 October 2026 release.

## v1.1.0: web showcase

**Try it online:** [the web version](https://malaysia-energy-transition-dashboard-eayus9fbdxbagczkpiktoy.streamlit.app/) (Streamlit Community Cloud; a first visit may have to wake the app up).

- **The report in a browser, with no Power BI:** Overview, Generation, Grid load, Forecast, ASEAN (each country's deep dive through a selector, and the peer comparison on hover), About and Data quality. Titles, KPI cards, hover text and footer credits follow the Power BI pages.
- **Same numbers as the report:** the 11 open showcase queries are ported to pandas and tested equal to their SQL twins; every one of the report's 119 items on these pages has an app element (`app/coverage.json`).
- **Licence-gated data:** the app reads Parquet snapshots in `exports/` that `pipeline export` writes only for sources whose licence allows their data rows to be published. It refuses an unlisted view or a non-publishable source, and writes the set atomically. Regions and State reliability stay in the report only: the Energy Commission's permission covers the charts, not the data behind them.
- **Readable everywhere:** every chart has a text summary and a "Show data" table; light and dark themes from the report's colour tokens, with contrast checked; works at phone width.
- **CI** runs the app's tests on its own `app/requirements.txt`, separately from the pipeline.

## v1.0.0: first public release

A Power BI report on Malaysia's electricity transition, built on a reproducible SQL Server pipeline from open data.

**Findings** (details in the README):
1. Renewables' share of generation roughly doubled, from 9.6% (2013–15) to 19.7% (2023–25), mostly in one hydro-driven step.
2. Each kWh got 9.5% cleaner, yet power-sector emissions rose 27%, because generation grew 40% and all the fossil growth was coal.
3. Among the six largest ASEAN power systems, Malaysia ranks 4th of 6 on renewable share and 5th of 6 on carbon intensity.
4. A day-ahead load forecast beats the same-hour-last-week baseline by 46.9% (Thailand) and 34.5% (Singapore) in a once-only 2024 test under a protocol locked in advance.

**What's in it:**
- **Report (9 pages):** Overview, Generation, Regions, State reliability, Grid load, Forecast, ASEAN, About and Data quality, with alt text on every visual, a Fail badge on every page and report-page tooltips.
- **Viewable without Power BI:** a PNG of each page, a PDF of the report and a captioned walkthrough video.
- **Pipeline:** `pipeline run` downloads every source, loads it idempotently into SQL Server (raw → stg → dw → mart), runs 34 data-quality rules and replays the locked forecast. Every run is logged.
- **SQL showcase:** 14 commented queries in `sql/showcase/`, each with the question it answers and the values it should return; the report's numbers are tested against them.
- **Reproducible:** a fresh clone rebuilds everything from the README in under 30 minutes (6.8 minutes measured); CI runs ruff and pytest on every push; the README's numbers are re-checked against the warehouse by script.

**Data and credits:** Ember (CC BY 4.0) for Malaysia and ASEAN; hourly grid data for Thailand (Bunnak 2025, Zenodo, CC BY 4.0) and Singapore (Energy Market Authority, Singapore Open Data Licence v1.0); the Energy Commission's Malaysia Energy Statistics Handbook 2023 for Regions and State reliability, used with its written permission and not endorsed by it. Full credits and terms in `DATA_LICENSES.md`.

**Limits:** Ember's grid basis differs from official figures in places (see the README's caveats); the forecast covers Thailand and Singapore, not Malaysia.
