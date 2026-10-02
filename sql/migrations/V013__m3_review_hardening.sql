-- V013: fixes from the ecc:database-reviewer pass on V010-V012 (M3 plan step 5 review, 2026-10-03).

-- 5a: a forecast fact row must name a run of its own grid.
ALTER TABLE dw.forecast_run ADD CONSTRAINT uq_forecast_run_grid UNIQUE (model_run_id, grid_key);
ALTER TABLE dw.fact_load_forecast DROP CONSTRAINT fk_flf_run;
ALTER TABLE dw.fact_load_forecast ADD CONSTRAINT fk_flf_run
    FOREIGN KEY (model_run_id, grid_key) REFERENCES dw.forecast_run (model_run_id, grid_key);

-- 5b: the locked protocol allows ONE final 2024 backtest per grid (M3 plan Q2, protocol #1).
CREATE UNIQUE INDEX uq_forecast_run_final ON dw.forecast_run (grid_key) WHERE run_kind = 'FINAL';

-- 5c: a scored hour has every input its metrics need (protocol #5).
ALTER TABLE dw.fact_load_forecast ADD CONSTRAINT ck_flf_scored
    CHECK (is_scored = 0 OR (actual_mw IS NOT NULL AND baseline_mw IS NOT NULL));

-- 14: commit hashes are 40 lowercase hex characters; a CI is ordered; the report never shows a DEV run.
ALTER TABLE dw.forecast_run ADD CONSTRAINT ck_forecast_run_git_commit
    CHECK (git_commit IS NULL OR (LEN(git_commit) = 40 AND git_commit NOT LIKE '%[^0-9a-f]%'));
ALTER TABLE dw.forecast_run ADD CONSTRAINT ck_forecast_run_protocol_commit
    CHECK (protocol_commit IS NULL OR (LEN(protocol_commit) = 40 AND protocol_commit NOT LIKE '%[^0-9a-f]%'));
ALTER TABLE dw.forecast_run ADD CONSTRAINT ck_forecast_run_ci
    CHECK (improvement_ci_low IS NULL OR improvement_ci_high IS NULL OR improvement_ci_low <= improvement_ci_high);
ALTER TABLE dw.forecast_run ADD CONSTRAINT ck_forecast_run_current_not_dev
    CHECK (is_current = 0 OR run_kind <> 'DEV');

-- 10: raw interval rows must belong to a known grid (a third grid's rows can't be silently ignored).
ALTER TABLE raw.grid_interval ADD CONSTRAINT fk_grid_interval_grid
    FOREIGN KEY (grid_code) REFERENCES dw.dim_grid (grid_code);

-- 11: flows are magnitudes per direction.
ALTER TABLE dw.fact_grid_flow_hourly ADD CONSTRAINT ck_fgfh_non_negative
    CHECK (COALESCE(import_mw, 0) >= 0 AND COALESCE(export_mw, 0) >= 0);
