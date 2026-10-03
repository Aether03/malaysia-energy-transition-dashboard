-- V014: a rolling-origin backtest's forecast_run row spans every fold (M3 step 8). train_end is
-- the end of the LAST fold's training window, so with monthly folds it lies after test_start
-- (the first fold's test month). V010's check assumed a single train/test split.
ALTER TABLE dw.forecast_run DROP CONSTRAINT ck_forecast_run_dates;
ALTER TABLE dw.forecast_run ADD CONSTRAINT ck_forecast_run_dates
    CHECK (train_start <= train_end AND train_start < test_start AND test_start <= test_end AND train_end < test_end);
