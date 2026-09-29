# Data sources and licences

The code in this repository is MIT-licensed (see `LICENSE`). The **data** belongs to its publishers and is used under their terms below. Raw source files are never committed (`data/raw/` is git-ignored); the pipeline downloads them at build time.

| Code | Source | Licence / terms | How it is used here |
|---|---|---|---|
| D1 | Ember, Yearly Electricity Data (https://ember-energy.org/data/yearly-electricity-data/) | CC BY 4.0 | Generation mix, capacity, emissions, demand for Malaysia and ASEAN |
| D2 | Our World in Data, Energy dataset (https://github.com/owid/energy-data) | CC BY 4.0 (cite OWID and its underlying sources) | Population, per-capita electricity, cross-checks |
| D3 | Department of Statistics Malaysia via data.gov.my (electricity_supply, electricity_consumption) | CC BY 4.0 (Government of Malaysia) | Data-quality cross-check only |
| DTH | Thai Power System: Hourly Power Generation, Demand, and Cross-Border Flows (Zenodo, doi:10.5281/zenodo.17109911) | CC BY 4.0 | Hourly grid load, forecast, Thailand-Malaysia interconnector flows |
| D4 | Grid System Operator (GSO), Tenaga Nasional Berhad | Reuse requires TNB's prior written consent. **Not used** unless consent is granted | Disabled by default (`gso.enabled = false`) |
| D5 | Energy Commission (Suruhanjaya Tenaga), Malaysia Energy Statistics Handbook | Reproduction requires the Energy Commission's written consent; consent to be requested | Extracted locally at build time; only derived, credited charts are shown |
| D6 | National Energy Transition Roadmap targets (via MIDA and IEA summaries) | Cited facts | NETR target line |
| GEO | geoBoundaries MYS ADM1 (OpenStreetMap-derived) | ODbL 1.0: "© OpenStreetMap contributors" | State boundaries for the reliability map |
