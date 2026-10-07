# Test fixtures

Small excerpts of the open sources, used by the tests so they run without a download, plus synthetic stand-ins for the restricted handbook. Licences and credits:

| Fixture | Source | Licence | Changes |
|---|---|---|---|
| `ember_sample.csv` | Ember (2026), Yearly Electricity Data, https://ember-energy.org/data/yearly-electricity-data/ | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | A few rows kept |
| `owid_sample.csv` | Our World in Data, Energy dataset, https://github.com/owid/energy-data (and its underlying sources) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | A few rows kept |
| `dosm_supply_sample.csv`, `dosm_consumption_sample.csv` | Department of Statistics Malaysia, via https://data.gov.my | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | A few rows kept |
| `thailand/system_2023.csv`, `thailand/system_2024.csv` | Bunnak, P. (2025), Thai Power System: Hourly Power Generation, Demand, and Cross-Border Flows (v1.0), Zenodo, doi:10.5281/zenodo.17109911 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | The first rows of each year kept |
| `singapore/*.xls` | Energy Market Authority of Singapore, Half-hourly System Demand Data | Singapore Open Data Licence v1.0 (statement in [`singapore/README.md`](singapore/README.md)) | None (unmodified files) |
| `handbook/*.json` | **Synthetic.** Page layouts of the Energy Commission handbook with every number replaced (`tools/make_handbook_fixture.py`); no handbook value is in this repository | — | — |
