# Data sources and licences

The code in this repository is MIT-licensed (see `LICENSE`). The **data** belongs to its publishers and is used under their terms below. Raw source files are never committed (`data/raw/` is git-ignored); the pipeline downloads them at build time.

| Code | Source | Licence / terms | How it is used here |
|---|---|---|---|
| D1 | Ember, Yearly Electricity Data (https://ember-energy.org/data/yearly-electricity-data/) | CC BY 4.0 | Generation mix, capacity, emissions, demand for Malaysia and ASEAN |
| D2 | Our World in Data, Energy dataset (https://github.com/owid/energy-data) | CC BY 4.0 (cite OWID and its underlying sources) | Population, per-capita electricity, cross-checks |
| D3 | Department of Statistics Malaysia via data.gov.my (electricity_supply, electricity_consumption) | CC BY 4.0 (Government of Malaysia) | Data-quality cross-check only |
| DTH | Thai Power System: Hourly Power Generation, Demand, and Cross-Border Flows (Zenodo, doi:10.5281/zenodo.17109911) | CC BY 4.0 | Hourly grid load, forecast, Thailand-Malaysia interconnector flows |
| D4 | Grid System Operator (GSO), Tenaga Nasional Berhad | Reuse requires TNB's prior written consent. **Not used** unless consent is granted | Disabled by default (`gso.enabled = false`) |
| D5 | Energy Commission (Suruhanjaya Tenaga), Malaysia Energy Statistics Handbook 2023 | All rights reserved; reproduction needs the Energy Commission's prior written consent (see below). Consent to be requested | Extracted locally at build time; nothing from it is committed; only derived, credited charts are shown (Regions and State reliability pages) |
| D6 | National Energy Transition Roadmap targets (via MIDA and IEA summaries) | Cited facts | NETR target line |
| GEO | geoBoundaries MYS ADM1, boundaryID `MYS-ADM1-15666254` (OpenStreetMap-derived) | ODbL 1.0: "Boundaries © OpenStreetMap contributors, via geoBoundaries (ODbL 1.0)" | State boundaries for the reliability map; redistributed unmodified (see below) |

## D5: Energy Commission handbook

The handbook's own copyright page (p. 5 of the 2023 edition) is stricter than the MEIH portal terms. It reserves all rights, says that reproducing all or any part of the publication in any medium needs the Energy Commission's prior written consent, and asks that any excerpt be credited as **"Source: Energy Commission"**. This repository therefore:

- **never commits** the PDF, the extracted cells (`raw.handbook_cell`), any extracted CSV, the independent re-read transcriptions or the local golden-test values (`data/raw/` and `data/private/` are git-ignored; `tests/test_no_restricted_data.py` fails on a committed PDF, anything under `data/`, or a test fixture without its synthetic marker);
- commits only code, page and table pins, the file's MD5, **synthetic** test fixtures (every number replaced), and docs that record counts and pass/fail results, never handbook values;
- shows only derived charts (rank, change since 2015, trend, ratio), with no table that reproduces a handbook grid, credited "Source: Energy Commission, Malaysia Energy Statistics Handbook 2023" with a consent notice driven by `dim_data_source.consent_status`.

Until consent is granted, exports of the Regions and State reliability pages (PNG/PDF) are not committed; the M5 pre-publication audit (task 5.8) decides. The Streamlit mirror excludes D5 (`is_publishable = 0`).

## GEO: state boundaries

`report/maps/mys_adm1.topojson` (pinned at geoBoundaries commit `9469f09`, SHA-256 in `report/maps/README.md`) and its byte-identical copy registered in the report (`report/EnergyTransition.Report/StaticResources/RegisteredResources/`) are redistributed **unmodified** under the Open Data Commons Open Database Licence 1.0 (https://opendatacommons.org/licenses/odbl/1-0/). The credit above appears on the State reliability page.
