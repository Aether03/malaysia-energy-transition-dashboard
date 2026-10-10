# Exports for the web showcase

Snapshots of the warehouse's `mart` views, written by `python -m pipeline export` for the Streamlit app (`app/`, FR-21). They hold only openly licensed data: the export reads each source's `is_publishable` flag and leaves out any view that draws on a source without it, listing it with the reason in `manifest.json` (`excluded_views`). The Energy Commission handbook (Regions and State reliability) and GSO data are therefore not here; see [`DATA_LICENSES.md`](../DATA_LICENSES.md).

- `*.parquet`: one file per exported view.
- `expected.json`: the results of the open `sql/showcase` queries at export time, used to test that the app computes the same numbers.
- `manifest.json`: export time, the pipeline run and source versions the snapshot comes from, each file's row count and sources, and what was left out.

To refresh: `python -m pipeline run`, then `python -m pipeline export`, then commit `exports/`.

## Licences and credits

All data are used **modified**: cleaned, reshaped, aggregated and combined into derived metrics by the SQL in `sql/` and the Python in `pipeline/`. No source endorses this project.

| Files | Source | Licence |
|---|---|---|
| `country_annual`, `generation_annual`, `dim_source`, and the annual showcase results | Ember (2026), Yearly Electricity Data, https://ember-energy.org/data/yearly-electricity-data/ | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `country_annual` (population, per-capita demand) | Our World in Data, Energy dataset, https://github.com/owid/energy-data (and its underlying sources) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Thailand rows of `grid_hourly`, `grid_flow_daily`, `load_forecast_current`, `forecast_run_current` and the grid showcase results | Bunnak, P. (2025), Thai Power System: Hourly Power Generation, Demand, and Cross-Border Flows (v1.0), Zenodo, doi:10.5281/zenodo.17109911 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Singapore rows of the same files | Contains information from Half-hourly System Demand Data accessed on 2026-10-03 from the Energy Market Authority of Singapore, made available under the terms of the Singapore Open Data Licence version 1.0 (https://www.ema.gov.sg/terms-of-use) | Singapore Open Data Licence v1.0 |
| `netr_target`, `re_capacity_official` | Ministry of Economy, National Energy Transition Roadmap (2023), via MIDA and IEA; cited facts | — |
| `data_source`, `kpi`, `dq_latest`, `run_latest`, `source_load_latest`, the other `dim_*` files | This project's own reference data and run metadata (names, definitions, statuses) | MIT, with the code |
