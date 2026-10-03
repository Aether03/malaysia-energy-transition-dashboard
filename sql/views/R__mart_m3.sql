-- R__mart_m3: the M3 presentation layer for P4 Grid load & forecast (repeatable).
-- Explicit column lists only. Published grids only (dim_grid.is_published, the consent gate):
-- an unpublished grid never reaches the report, whatever the facts hold.

CREATE OR ALTER VIEW mart.dim_date AS
SELECT date_key, date, year, month, month_name, iso_weekday, is_weekend,
       season_th, season_my, is_holiday_th, is_holiday_my, is_holiday_sg
FROM dw.dim_date;
GO

CREATE OR ALTER VIEW mart.dim_hour AS
SELECT hour, label
FROM dw.dim_hour;
GO

-- demand_label is what P4 calls the series: Thailand's is the sum of the 5 regional demands,
-- 2-4% below EGAT's published system peaks (M3 step 6, docs/reconciliation.md).
CREATE OR ALTER VIEW mart.dim_grid AS
SELECT
    g.grid_key,
    g.grid_code,
    g.name,
    c.name AS country_name,
    g.utc_offset_min,
    g.data_source_code,
    CAST(CASE g.grid_code
             WHEN 'TH_EGAT' THEN N'Sum of regional demand (EGAT)'
             WHEN 'SG_EMA'  THEN N'System demand (EMA)'
             ELSE N'System demand'
         END AS NVARCHAR(60)) AS demand_label,
    CAST(CASE WHEN g.grid_code = 'MY_PEN_GSO' THEN 0 ELSE 1 END AS BIT) AS is_open_data_proxy,
    CAST(CASE g.grid_code
             WHEN 'TH_EGAT' THEN N'Open-data stand-in for Peninsular Malaysia until TNB consents to GSO data use'
             WHEN 'SG_EMA'  THEN N'ASEAN peer grid (open data)'
             ELSE N''
         END AS NVARCHAR(100)) AS banner_note,
    CAST(CASE g.grid_code WHEN 'TH_EGAT' THEN 1 WHEN 'SG_EMA' THEN 2 ELSE 9 END AS TINYINT) AS display_order
FROM dw.dim_grid AS g
JOIN dw.dim_country AS c
    ON c.country_key = g.country_key
WHERE g.is_published = 1;
GO

-- The forecast panel's date picker (P4). Deliberately not related to any fact: it filters only
-- the forecast measures (via TREATAS on date_key), never the load or flow charts. It spans every
-- calendar date, so a day outside the backtest window can be picked and shows the empty state.
CREATE OR ALTER VIEW mart.forecast_date AS
SELECT date_key, date
FROM dw.dim_date;
GO

-- Published hours only: a missing hour has no row, so charts show a gap, never a filled value.
-- Season and day type follow the grid's own country: Thailand's Thai Meteorological Department
-- seasons and Thai holidays; Singapore's monsoon seasons (shared with Malaysia) and SG holidays.
CREATE OR ALTER VIEW mart.grid_hourly AS
SELECT
    f.grid_key,
    f.ts_local,
    f.date_key,
    f.hour,
    d.year,
    d.month,
    f.demand_mw,
    CAST(CASE WHEN g.grid_code = 'TH_EGAT' THEN
                  CASE d.season_th WHEN 'HOT' THEN N'Hot (Mar–May)' WHEN 'RAINY' THEN N'Rainy (Jun–Oct)'
                                   ELSE N'Cool (Nov–Feb)' END
              ELSE
                  CASE d.season_my WHEN 'NE_MONSOON' THEN N'NE monsoon (Nov–Mar)'
                                   WHEN 'SW_MONSOON' THEN N'SW monsoon (May–Sep)'
                                   ELSE N'Inter-monsoon (Apr, Oct)' END
         END AS NVARCHAR(30)) AS season,
    CAST(CASE WHEN g.grid_code = 'TH_EGAT' THEN
                  CASE d.season_th WHEN 'HOT' THEN 1 WHEN 'RAINY' THEN 2 ELSE 3 END
              ELSE
                  CASE d.season_my WHEN 'NE_MONSOON' THEN 1 WHEN 'SW_MONSOON' THEN 2 ELSE 3 END
         END AS TINYINT) AS season_order,
    CAST(CASE WHEN d.is_weekend = 1
                OR (g.grid_code = 'TH_EGAT' AND d.is_holiday_th = 1)
                OR (g.grid_code = 'SG_EMA' AND d.is_holiday_sg = 1)
                OR (g.grid_code = 'MY_PEN_GSO' AND d.is_holiday_my = 1)
              THEN N'Weekend & holiday' ELSE N'Weekday' END AS NVARCHAR(20)) AS day_type
FROM dw.fact_grid_hourly AS f
JOIN dw.dim_grid AS g
    ON g.grid_key = f.grid_key
JOIN dw.dim_date AS d
    ON d.date_key = f.date_key
WHERE g.is_published = 1;
GO

-- The load-curve season toggle (P4). Related to dim_grid only, so the grid slicer narrows it to
-- that grid's three seasons, but never to grid_hourly: the pick reaches the curve alone, through
-- [Avg Load Curve (MW)] (TREATAS), and leaves the heatmap and peak charts whole-year.
CREATE OR ALTER VIEW mart.season_pick AS
SELECT DISTINCT grid_key, season, season_order
FROM mart.grid_hourly;
GO

-- Daily net flow per counterparty (M3 Q3): positive = the grid exports. Only hours the source
-- filled count (an hour with neither direction is a gap, not 0). MWh = MW over one hour.
CREATE OR ALTER VIEW mart.grid_flow_daily AS
SELECT
    f.grid_key,
    f.counterparty,
    f.date_key,
    MIN(d.date) AS date,
    MIN(d.year) AS year,
    COUNT(*) AS hours_present,
    CAST(SUM(COALESCE(f.export_mw, 0)) AS DECIMAL(12, 1)) AS export_mwh,
    CAST(SUM(COALESCE(f.import_mw, 0)) AS DECIMAL(12, 1)) AS import_mwh,
    CAST(AVG(COALESCE(f.export_mw, 0) - COALESCE(f.import_mw, 0)) AS DECIMAL(10, 1)) AS net_flow_mw
FROM dw.fact_grid_flow_hourly AS f
JOIN dw.dim_grid AS g
    ON g.grid_key = f.grid_key
JOIN dw.dim_date AS d
    ON d.date_key = f.date_key
WHERE g.is_published = 1
GROUP BY f.grid_key, f.counterparty, f.date_key;
GO

-- The current run per published grid: the single locked FINAL 2024 backtest (docs/forecast.md).
-- The secondary references and the decision come from metrics_json; DEV runs never appear.
CREATE OR ALTER VIEW mart.forecast_run_current AS
SELECT
    r.model_run_id,
    r.grid_key,
    r.run_kind,
    r.model_name,
    r.trained_at,
    r.train_start,
    r.test_start,
    r.test_end,
    r.mape_model,
    r.mape_baseline,
    r.mae_model,
    r.mae_baseline,
    r.improvement_pct,
    r.improvement_ci_low,
    r.improvement_ci_high,
    r.scored_hours,
    r.excluded_hours,
    CAST(CASE JSON_VALUE(r.metrics_json, '$.beats_baseline') WHEN 'true' THEN 1 ELSE 0 END AS BIT) AS beats_baseline,
    CAST(JSON_VALUE(r.metrics_json, '$.secondary.weekday_naive.mape_baseline') AS DECIMAL(8, 3)) AS mape_weekday_naive,
    CAST(JSON_VALUE(r.metrics_json, '$.secondary.weekday_naive.improvement_pct') AS DECIMAL(8, 3)) AS improvement_weekday_pct,
    CAST(JSON_VALUE(r.metrics_json, '$.secondary.weekday_naive.ci[0]') AS DECIMAL(8, 3)) AS improvement_weekday_ci_low,
    CAST(JSON_VALUE(r.metrics_json, '$.secondary.weekday_naive.ci[1]') AS DECIMAL(8, 3)) AS improvement_weekday_ci_high,
    CAST(JSON_VALUE(r.metrics_json, '$.secondary.naive24.mape_baseline') AS DECIMAL(8, 3)) AS mape_naive24,
    r.protocol_commit
FROM dw.forecast_run AS r
JOIN dw.dim_grid AS g
    ON g.grid_key = r.grid_key
WHERE r.is_current = 1
  AND g.is_published = 1;
GO

CREATE OR ALTER VIEW mart.load_forecast_current AS
SELECT
    f.model_run_id,
    f.grid_key,
    f.ts_local,
    f.date_key,
    f.hour,
    f.actual_mw,
    f.forecast_mw,
    f.baseline_mw,
    f.is_scored
FROM dw.fact_load_forecast AS f
JOIN dw.forecast_run AS r
    ON r.model_run_id = f.model_run_id
JOIN dw.dim_grid AS g
    ON g.grid_key = f.grid_key
WHERE r.is_current = 1
  AND g.is_published = 1;
GO

-- P4's error state (doc 03): the FORECAST step of the latest run that had one, per published
-- grid. A grid without its own step in that run shows FAILED if another forecast step failed
-- there (the loop stopped early), otherwise NOT_RUN.
CREATE OR ALTER VIEW mart.forecast_status AS
WITH latest AS (
    SELECT MAX(s.run_id) AS run_id
    FROM meta.load_step AS s
    JOIN meta.load_run AS r
        ON r.run_id = s.run_id
    WHERE s.stage = 'FORECAST'
      AND r.is_dry_run = 0
)
SELECT
    g.grid_key,
    l.run_id,
    COALESCE(
        own.status,
        CASE WHEN EXISTS (SELECT 1 FROM meta.load_step AS f
                          WHERE f.run_id = l.run_id AND f.stage = 'FORECAST' AND f.status = 'FAILED')
             THEN 'FAILED' ELSE 'NOT_RUN' END
    ) AS status,
    own.message,
    own.finished_at
FROM dw.dim_grid AS g
CROSS JOIN latest AS l
OUTER APPLY (
    SELECT TOP (1) s.status, s.message, s.finished_at
    FROM meta.load_step AS s
    WHERE s.run_id = l.run_id
      AND s.stage = 'FORECAST'
      AND s.data_source_code = g.data_source_code
    ORDER BY s.step_id DESC
) AS own
WHERE g.is_published = 1;
GO
