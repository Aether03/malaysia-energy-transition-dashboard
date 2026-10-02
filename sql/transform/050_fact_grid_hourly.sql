-- 050: rebuild dw.fact_grid_hourly from stg.grid_hourly (M3 plan step 5; Q1: published hours only,
-- no imputation). Incomplete hours (a missing regional part) are left out and reported by the
-- PARTIAL_GRID_HOURS rule. Delete-and-reload inside the rebuild transaction; nothing references it.

DELETE FROM dw.fact_grid_hourly;

INSERT INTO dw.fact_grid_hourly (grid_key, ts_utc, ts_local, demand_mw, is_imputed, date_key, hour, file_name, ts_text)
SELECT
    s.grid_key,
    s.ts_utc,
    s.ts_local,
    CAST(s.demand_mw AS DECIMAL(10, 1)),
    0,
    YEAR(s.ts_local) * 10000 + MONTH(s.ts_local) * 100 + DAY(s.ts_local),
    CAST(DATEPART(HOUR, s.ts_local) AS TINYINT),
    s.file_name,
    s.ts_text
FROM stg.grid_hourly AS s
WHERE s.is_complete = 1
  AND s.demand_mw >= 0;  -- a negative hour fails NO_NEGATIVE_DEMAND (BLOCKING) instead of the CHECK
