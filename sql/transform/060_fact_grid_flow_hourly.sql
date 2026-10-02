-- 060: rebuild dw.fact_grid_flow_hourly from stg.grid_flow_hourly (M3 plan step 5; S2).
-- A row exists only where the source filled at least one direction (stg filters the rest).

DELETE FROM dw.fact_grid_flow_hourly;

INSERT INTO dw.fact_grid_flow_hourly (grid_key, ts_utc, counterparty, ts_local, import_mw, export_mw, date_key, hour)
SELECT
    s.grid_key,
    s.ts_utc,
    s.counterparty,
    s.ts_local,
    CAST(s.import_mw AS DECIMAL(10, 1)),
    CAST(s.export_mw AS DECIMAL(10, 1)),
    YEAR(s.ts_local) * 10000 + MONTH(s.ts_local) * 100 + DAY(s.ts_local),
    CAST(DATEPART(HOUR, s.ts_local) AS TINYINT)
FROM stg.grid_flow_hourly AS s;
