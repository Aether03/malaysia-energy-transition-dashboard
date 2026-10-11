# Data sources and licences

The code in this repository is MIT-licensed (see `LICENSE`). The **data** belongs to its publishers and is used under their terms below. Raw source files are not committed (`data/raw/` is git-ignored); the pipeline downloads them at build time. The exceptions are small excerpts of the open sources used as test fixtures, credited in [`tests/fixtures/README.md`](tests/fixtures/README.md).

| Code | Source | Licence / terms | How it is used here |
|---|---|---|---|
| D1 | Ember, Yearly Electricity Data (https://ember-energy.org/data/yearly-electricity-data/) | CC BY 4.0 | Generation mix, capacity, emissions, demand for Malaysia and ASEAN |
| D2 | Our World in Data, Energy dataset (https://github.com/owid/energy-data) | CC BY 4.0 (cite OWID and its underlying sources) | Population, per-capita electricity, cross-checks |
| D3 | Department of Statistics Malaysia via data.gov.my (electricity_supply, electricity_consumption) | CC BY 4.0 (Government of Malaysia) | Data-quality cross-check only |
| DTH | Phumthep Bunnak (2025), Thai Power System: Hourly Power Generation, Demand, and Cross-Border Flows, v1.0 (Zenodo, doi:10.5281/zenodo.17109911) | CC BY 4.0 | Hourly grid load, forecast, Thailand-Malaysia interconnector flows |
| DSG | Energy Market Authority of Singapore, Half-hourly System Demand Data (https://www.ema.gov.sg/resources/statistics/half-hourly-system-demand-data) | Singapore Open Data Licence v1.0: "Contains information from Half-hourly System Demand Data accessed on 2026-10-03 from the Energy Market Authority of Singapore, made available under the terms of the Singapore Open Data Licence version 1.0 (https://www.ema.gov.sg/terms-of-use)" | Hourly grid load and forecast. Two weekly files are redistributed unmodified as test fixtures (`tests/fixtures/singapore/`, with the same statement) |
| D4 | Grid System Operator (GSO), Tenaga Nasional Berhad | Reuse requires TNB's prior written consent. **Not used** unless consent is granted | Disabled by default (`gso.enabled = false`) |
| D5 | Energy Commission (Suruhanjaya Tenaga), Malaysia Energy Statistics Handbook 2023 | All rights reserved; reproduction needs the Energy Commission's prior written consent (see below). **Consent granted 2026-10-09** for the use and adaptation of its charts and data in this non-commercial project (`docs/consent/st_request.md`) | Extracted locally at build time; nothing from it is committed; only derived, credited charts are published (Regions and State reliability pages, in the page images, PDF and walkthrough) |
| D6 | National Energy Transition Roadmap targets (via MIDA and IEA summaries) | Cited facts | NETR target line |
| GEO | geoBoundaries MYS ADM1, boundaryID `MYS-ADM1-15666254` (OpenStreetMap-derived) | ODbL 1.0: "Boundaries © OpenStreetMap contributors, via geoBoundaries (ODbL 1.0)" | State boundaries for the reliability map; redistributed unmodified (see below) |

**Changes.** CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) and Singapore Open Data Licence data are used **modified**: the pipeline cleans, reshapes, aggregates and combines them into derived metrics (shares, ranks, intensities, per-capita values, load factors, forecasts). The transformations are the SQL in `sql/` and the Python in `pipeline/`. No source endorses this project.

## D5: Energy Commission handbook

The handbook's own copyright page (p. 5 of the 2023 edition) is stricter than the MEIH portal terms. It reserves all rights, says that reproducing all or any part of the publication in any medium needs the Energy Commission's prior written consent, and asks that any excerpt be credited as **"Source: Energy Commission"**. This repository therefore:

- **never commits** the PDF, the extracted cells (`raw.handbook_cell`), any extracted CSV, the independent re-read transcriptions or the local golden-test values (`data/raw/` and `data/private/` are git-ignored; `tests/test_no_restricted_data.py` fails on a committed PDF, anything under `data/`, or a test fixture without its synthetic marker);
- commits only code, page and table pins, the file's MD5, **synthetic** test fixtures (every number replaced), and docs that record counts and pass/fail results, never handbook values;
- shows only derived charts (rank, change since 2015, trend, ratio), with no table that reproduces a handbook grid, credited "Source: Energy Commission, Malaysia Energy Statistics Handbook 2023" with a consent notice driven by `dim_data_source.consent_status`.

**Consent (2026-10-09).** The Energy Commission's Strategic Communications approved "the use and adaptation of charts and data from the publication" for the stated purpose (derived charts as page images, a PDF export and a video walkthrough, in this public repository and on the author's portfolio website, non-commercial only), on four conditions, each met on both pages:

1. The source is acknowledged as "Source: Energy Commission": in each page subtitle and footnote.
2. Modified or adapted charts are identified: the footnote reads "Charts adapted from the handbook with the Energy Commission's written permission (9 October 2026)".
3. The information is presented accurately: every landed cell was checked against the PDF in an independent blind re-read (989/989, M4), and 12 D5 data-quality rules run on every build.
4. No endorsement is implied: the footnote reads "Not endorsed by the Energy Commission".

Any other use needs separate permission. The consent covers the charts, not the data rows: the extracted cells stay uncommitted, the value scan still guards every committed text file, and `is_publishable` stays 0, so the web showcase's data export (`exports/`, below) leaves out every D5 view and showcase query. The showcase's About page links the two consented page images instead. Whether the permission extends to an interactive web version and its data snapshot was asked on 2026-10-11 (`docs/consent/st_request.md`); until the Energy Commission agrees, it stays out.

## Web showcase data (`exports/`)

`python -m pipeline export` writes Parquet snapshots of the `mart` views and the open SQL twins' results for the Streamlit app (`app/`). It is licence-gated and fails closed:
- a view is exported only if every source it draws on has `is_publishable = 1` (D1, D2, D3, D6, DSG, DTH, GEO);
- grid rows are kept only for grids whose source is publishable;
- an unreviewed view, an unknown source code or a restricted source's data-quality detail stops the export with nothing written.

Every run records what it left out, and why, in `exports/manifest.json`, which the app's About page shows. D5 metadata does appear in the snapshot, as on the report's About and Data quality pages: the names, descriptions and statuses of its 12 data-quality rules in `dq_latest`, and its load count and edition checksum in `source_load_latest`. None of it is a handbook value (D5 rule details are NULL by design). Nothing from D4 is exported. Each file's credit, worded as its licence asks, is in [`exports/README.md`](exports/README.md); every page of the app also credits its sources in its footer.

## GEO: state boundaries

`report/maps/mys_adm1.topojson` (pinned at geoBoundaries commit `9469f09`, SHA-256 in `report/maps/README.md`) and its byte-identical copy registered in the report (`report/EnergyTransition.Report/StaticResources/RegisteredResources/`) are redistributed **unmodified** under the Open Data Commons Open Database Licence 1.0 (https://opendatacommons.org/licenses/odbl/1-0/). The credit above appears on the State reliability page.
