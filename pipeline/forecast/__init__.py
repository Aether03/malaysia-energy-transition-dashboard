"""Day-ahead hourly load forecast and its locked rolling-origin backtest (M3 plan, Q2 and Q6).

Modules:
- `features`: calendar and lag features built in local time, lags >= 24 h only.
- `baseline`: seasonal naive (t - 168 h) and the naive t - 24 h reference.
- `metrics`: MAPE/MAE on a common scored-hour set, per-group scores, day-block bootstrap CI.
- `backtest`: monthly expanding-window folds, the LightGBM wrapper and the backtest loop.
- `protocol`: parses `docs/forecast.md` §Protocol and gates `--final` on a committed, clean protocol.
- `store`: builds the `dw.forecast_run` and `dw.fact_load_forecast` rows.
"""
