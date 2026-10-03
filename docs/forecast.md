# Day-ahead load forecast

A day-ahead hourly forecast of system demand for each published grid: Thailand (EGAT, the open-data stand-in for Peninsular Malaysia) and Singapore (EMA). It is backtested once, under the protocol below, against a seasonal-naive baseline (M3 plan Q2, FR-13). Code: `pipeline/forecast/`. Command: `python -m pipeline forecast [--dev | --final --grid <code>]`.

## Method
- **Target:** hourly demand in MW from `dw.fact_grid_hourly`. Thailand uses the sum of the 5 regional demands (`docs/reconciliation.md`); Singapore uses system demand as the hourly mean of two half-hours. Published hours only: the 4 missing Thailand hours stay missing and are never imputed.
- **Issue time:** local midnight before the forecast day. Every input for hour *t* is an actual from *t* − 24 h or earlier, which is the last hour known at issue time.
- **Features (11):**
  - local hour, ISO weekday, month;
  - weekend, public holiday (the grid's own country, from `ref.public_holiday`), and day off (either);
  - the actual 24, 48, 168 and 336 hours earlier;
  - the mean of the 24 hours ending at *t* − 24 h (at least 18 of them present).
  - A missing actual leaves its feature missing; LightGBM handles missing values natively.
- **Model:** LightGBM regression. The code always adds `deterministic=True`, `force_row_wise=True`, and the protocol's seed and thread count, so a re-run is bit-identical.
- **Backtest:** monthly folds with an expanding window from 2023-01-08, the first hour with a 168 h lag.
  - Each fold trains once on everything before its test month.
  - Early stopping uses only the last 28 days before the test month.
  - The fold then forecasts every hour of the month.
  - The model is not refitted on those 28 days, so within a test month it is 28–59 days old. This handicaps the model, not the baseline.
- **Primary baseline:** seasonal naive, the actual at *t* − 168 h (doc 02 §4).
- **Secondary references:**
  - naive *t* − 24 h;
  - the **weekday-aware naive**: *t* − 24 h on Tuesday to Friday, *t* − 168 h on Saturday, Sunday and Monday.
- **Scoring:** MAPE (primary) and MAE, on the hours where the actual, the model and the reference all exist. Excluded hours are counted. Results are also given per month, for holiday vs other days, and as bias (mean forecast − actual).
- **Uncertainty:**
  - A circular moving-block bootstrap gives a 95% CI on the MAPE improvement, 1 − MAPE_model / MAPE_reference. Blocks are 7 consecutive days, with 2,000 replicates.
  - Week blocks keep the day-to-day correlation of errors. On 2023, the lag-1 autocorrelation of daily error differences was 0.65 for Thailand.
  - The CI covers only sampling variation within the test year. It does not include variation from the seed, the training data or year-to-year change.

## Protocol
Locked before any 2024 data is forecast. Every modelling choice was made on 2023 data only: training from 2023-01-08, holdout Oct–Dec 2023 (see "Development results").
- **Settings:** the FINAL run reads them only from the block below.
- **The gate:** `python -m pipeline forecast --final --grid <code>` runs one grid at a time. It refuses to run unless every input that can change the numbers is committed and unchanged:
  - this file and the record (`docs/forecast_final.json`);
  - `pipeline/forecast/` and `pipeline/cli.py`;
  - the holiday code and overrides;
  - `requirements.txt`;
  - the SQL that builds hourly demand.
  - A file hidden from `git status` (assume-unchanged or skip-worktree) also stops it.
- **Once only:** the commit hash of this file is stored with the run. The database allows one FINAL run per grid, and the record must be committed before the next grid runs.
- **Decision rule, per grid:** the model beats the baseline only if the lower bound of the 95% CI on the improvement over the **seasonal-naive baseline** is above 0. Otherwise P4 shows the WARN banner.
- **Secondary references:** both are reported on P4 and here, each with its own CI. They don't change the banner. If the CI against the weekday-aware naive includes 0, P4's method text says so in plain words: the model's advantage over a simple weekday-aware rule is not established.
- **Not used as a benchmark:** EMA's published NEM forecast for Singapore. It forecasts NEM demand, not system demand, and its issue time and horizon are not documented.
- **Sanity bound:** a run that can't score at least 98% of its test hours stops.
- **After the run:** any change is a new, labelled POST_HOC run, and the FINAL run stays on record.
  - Re-running `pipeline run` replays each recorded FINAL run. The replay checks the record against this file at its commit, and the inputs against the recorded SHA-256 fingerprints (demand, holidays, library versions).
  - The forecast and metrics must then be bit-identical.
  - A mismatch is an environment failure, not a result. Its message names the fields that differ, never the new values.

```json
{
  "features": ["hour", "iso_weekday", "month", "is_weekend", "is_holiday", "is_day_off",
               "lag_24", "lag_48", "lag_168", "lag_336", "roll_mean_24"],
  "data_start": "2023-01-08",
  "es_days": 28,
  "dev": {"first_month": "2023-10", "last_month": "2023-12"},
  "final": {"first_month": "2024-01", "last_month": "2024-12"},
  "lightgbm": {
    "objective": "l2",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "n_estimators": 2000,
    "early_stopping_rounds": 100
  },
  "seed": 20231008,
  "num_threads": 1,
  "bootstrap": {"n_boot": 2000, "level": 0.95, "block_days": 7}
}
```

**What was seen of 2024 before this lock.** No model was fitted, tuned or scored on 2024, and no 2024 forecast was made. Earlier milestones did look at the 2024 series as data, though:
- the data-quality checks and gap counts;
- the reconciliation of 2024 peaks against EGAT and ERC;
- annual means and load factors;
- the 2024 interconnector flow totals.

The Thai holiday calendar was checked against the official holiday lists, not against demand dips.

## Development results (2023 holdout, Oct–Dec 2023)
These are development numbers, used to choose the settings above. They are not the test result.

**Settings compared** (one seed, MAPE % on all 2,208 holdout hours; none were excluded):

| Setting | TH model | SG model |
|---|---|---|
| l2, 31 leaves | 4.72 | 1.50 |
| l1, 31 leaves | 4.53 | 1.50 |
| MAPE objective, 31 leaves | 4.47 | 1.54 |
| **l2, 15 leaves (chosen)** | **4.56** | **1.47** |
| l2, 63 leaves | 4.59 | 1.53 |
| l2, 31 leaves, learning rate 0.02 | 4.75 | 1.49 |
| *Seasonal-naive baseline* | *6.70* | *1.98* |

- **Why l2 with 15 leaves:** the gaps between settings are within seed noise, so the simplest model that is best or near-best on both grids was chosen. It was not tuned further on a 3-month holdout.
- **Seed stability** (seeds 20231008, 7 and 12345): TH 4.36–4.56%, SG 1.45–1.48%.

**The chosen setting against every reference** (DEV runs 5–6; improvement in %, 95% CI with 7-day blocks):

| Reference | TH reference MAPE | TH improvement (CI) | SG reference MAPE | SG improvement (CI) |
|---|---|---|---|---|
| Seasonal naive (primary) | 6.70 | 31.9 (21.8 to 39.3) | 1.98 | 25.6 (13.8 to 35.9) |
| Naive *t* − 24 h | 5.59 | 18.4 (−18.0 to 44.5) | 3.17 | 53.5 (48.3 to 58.5) |
| Weekday-aware naive | 4.98 | 8.4 (−15.3 to 24.6) | 1.99 | 26.0 (11.3 to 37.7) |

- **The honest reading for Thailand:** on 2023 the model clearly beats the seasonal naive, but its edge over a simple weekday-aware rule is not established.
- **Bias** (mean forecast − actual): TH +413 MW, mostly from the year-end; SG +19 MW.
- **Weak spot found:** Thailand, 22–31 December 2023. Model error was 12–20% a day, and the baseline's 15–28%.
  - The data is not at fault. Central, metropolitan and north demand all fall smoothly by 25–35% into the New Year, which fits the late-December cold spell plus the year-end holidays.
  - The model has no weather inputs, and the December 2023 fold trains from 2023-01-08, so it has seen no year-end period. This is listed under Limits rather than tuned for.
- **Dev-to-final transfer:** the holdout months were unseen by the `month` feature, while in the 2024 run every month has been seen once. Dev numbers are therefore only indicative.

The development runs are stored as DEV rows in `dw.forecast_run`; the report never shows them.

## Results (2024 backtest)
Not run yet. It will be filled in from the single FINAL run per grid, weak months included.

## Limits
- **Only two years of data:** each season is seen once before it is tested. January 2024 trains on about one year, and its early-stopping window is the atypical year-end period.
- **No weather inputs:** cold spells and heat waves show up only through the lags.
- **No refit on the latest 28 days:** within a test month the model is 28–59 days old.
- **Holidays:** the baseline's *t* − 168 h can fall on a holiday. That is how seasonal naive works, so holiday-hour error is reported separately.
- **The CI is narrow in scope:** it covers test-period sampling only (see Method).
- **Thailand stands in for Peninsular Malaysia** until TNB consents to GSO data use. The P4 banner says so.
