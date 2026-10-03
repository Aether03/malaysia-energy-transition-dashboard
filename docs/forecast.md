# Day-ahead load forecast

A day-ahead hourly forecast of system demand for each published grid: Thailand (EGAT, the open-data stand-in for Peninsular Malaysia) and Singapore (EMA). It is backtested once, under the protocol below, against a seasonal-naive baseline (M3 plan Q2, FR-13). Code: `pipeline/forecast/`. Command: `python -m pipeline forecast [--dev | --final]`.

## Method
- **Target:** hourly demand in MW from `dw.fact_grid_hourly`. Thailand uses the sum of the 5 regional demands (`docs/reconciliation.md`); Singapore uses system demand as the hourly mean of two half-hours. Published hours only: the 4 missing Thailand hours stay missing and are never imputed.
- **Issue time:** local midnight before the forecast day. Every input for hour *t* is an actual from *t* − 24 h or earlier, which is the last hour known at issue time.
- **Features (11):**
  - local hour, ISO weekday, month;
  - weekend, public holiday (the grid's own country, from `ref.public_holiday`), and day off (either);
  - the actual 24, 48, 168 and 336 hours earlier;
  - the mean of the 24 hours ending at *t* − 24 h (at least 18 of them present).
  - A missing actual leaves its feature missing; LightGBM handles missing values natively.
- **Model:** LightGBM regression, deterministic for a fixed seed and thread count.
- **Backtest:** monthly folds with an expanding window from 2023-01-08, the first hour with a 168 h lag.
  - Each fold trains once on everything before its test month.
  - Early stopping uses only the last 28 days before the test month.
  - The fold then forecasts every hour of the month.
- **Baseline:** seasonal naive, the actual at *t* − 168 h. A secondary reference is naive *t* − 24 h.
- **Scoring:** MAPE (primary) and MAE, on the hours where the actual, the model and the baseline all exist. Excluded hours are counted. Results are also given per month and for holiday vs other days.
- **Uncertainty:** a day-block bootstrap, resampling whole local days, gives a 95% CI on the MAPE improvement, 1 − MAPE_model / MAPE_baseline.

## Protocol
Locked before any 2024 data is forecast. Every modelling choice was made on 2023 only: training from 2023-01-08, holdout Oct–Dec 2023 (see "Development results").
- The FINAL run reads its settings only from the block below.
- `python -m pipeline forecast --final` refuses to run unless this file and `pipeline/forecast/` are committed and unchanged.
- The commit hash of this file is stored with the run, and the database allows one FINAL run per grid.
- **Decision rule, per grid:** the model beats the baseline only if the lower bound of the 95% CI on the improvement is above 0. Otherwise P4 shows the WARN banner.
- **Benchmarks:** only the seasonal-naive baseline and the naive *t* − 24 h reference are compared. EMA's published NEM forecast for Singapore is not used: it forecasts NEM demand, not system demand, and its issue time and horizon are not documented.
- **After the run:** any change is a new, labelled POST_HOC run, and the FINAL run stays on record. Re-running `pipeline run` replays the recorded FINAL run and must reproduce its numbers exactly (`docs/forecast_final.json`).

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
  "bootstrap": {"n_boot": 2000, "level": 0.95}
}
```

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
- **Seed stability** (seeds 20231008, 7 and 12345): TH 4.36–4.56%, SG 1.45–1.48%. Improvement over the baseline: TH 32–35%, SG 25–27%.
- **Weak spot found:** Thailand, 22–31 December 2023. Model error was 12–20% a day, and the baseline's 15–28%.
  - The data is not at fault. Central, metropolitan and north demand all fall smoothly by 25–35% into the New Year, which fits the late-December cold spell plus the year-end holidays.
  - The model has no weather inputs, and the December 2023 fold trains from 2023-01-08, so it has seen no year-end period. The December 2024 fold will have seen one. This is listed under Limits rather than tuned for.

The development runs are stored as DEV rows in `dw.forecast_run`; the report never shows them.

## Results (2024 backtest)
Not run yet. It will be filled in from the single FINAL run per grid, weak months included.

## Limits
- **Only two years of data:** each season is seen once before it is tested. January 2024 trains on about one year.
- **No weather inputs:** cold spells and heat waves show up only through the lags.
- **Holidays:** the baseline's *t* − 168 h can fall on a holiday. That is how seasonal naive works, so holiday-hour error is reported separately.
- **Thailand stands in for Peninsular Malaysia** until TNB consents to GSO data use. The P4 banner says so.
