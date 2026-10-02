-- 040: upsert dw.dim_date for every local date the hourly grids cover (M3 plan step 5).
-- Singapore shares Malaysia's monsoon seasons (season_my) and has its own holiday flag.
-- Runs after 010 (dim_year), inside the rebuild transaction. Dates are never deleted:
-- dw.fact_load_forecast keeps old forecast runs that reference them.
-- iso_weekday is computed from a fixed Monday (1900-01-01) so SET DATEFIRST can't shift it.

WITH bounds AS (
    SELECT MIN(CAST(ts_local AS DATE)) AS first_date, MAX(CAST(ts_local AS DATE)) AS last_date
    FROM stg.grid_hourly
),
days AS (  -- one row per date between the bounds (a few thousand at most)
    SELECT DATEADD(DAY, n.n, b.first_date) AS d
    FROM bounds AS b
    CROSS APPLY (
        SELECT TOP (DATEDIFF(DAY, b.first_date, b.last_date) + 1)
            ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS n
        FROM sys.all_objects AS a CROSS JOIN sys.all_objects AS c
    ) AS n
    WHERE b.first_date IS NOT NULL
),
calendar AS (
    SELECT
        YEAR(d) * 10000 + MONTH(d) * 100 + DAY(d)                AS date_key,
        d                                                        AS date,
        CAST(YEAR(d) AS SMALLINT)                                AS year,
        CAST(MONTH(d) AS TINYINT)                                AS month,
        CAST(LEFT(DATENAME(MONTH, d), 3) AS CHAR(3))             AS month_name,
        CAST(DATEDIFF(DAY, '19000101', d) % 7 + 1 AS TINYINT)    AS iso_weekday
    FROM days
),
src AS (
    SELECT
        c.date_key, c.date, c.year, c.month, c.month_name, c.iso_weekday,
        CAST(CASE WHEN c.iso_weekday >= 6 THEN 1 ELSE 0 END AS BIT) AS is_weekend,
        -- Month-based approximations (M3 plan Definitions), so each heatmap month has one season.
        -- TH (Thai Meteorological Department, boundaries really mid-month): Hot Mar-May, Rainy Jun-Oct, Cool Nov-Feb.
        -- MY (MetMalaysia): NE monsoon Nov-Mar, SW monsoon May-Sep, inter-monsoon Apr and Oct.
        CAST(CASE WHEN c.month BETWEEN 3 AND 5 THEN 'HOT'
                  WHEN c.month BETWEEN 6 AND 10 THEN 'RAINY'
                  ELSE 'COOL' END AS VARCHAR(10))              AS season_th,
        CAST(CASE WHEN c.month IN (11, 12, 1, 2, 3) THEN 'NE_MONSOON'
                  WHEN c.month BETWEEN 5 AND 9 THEN 'SW_MONSOON'
                  ELSE 'INTER' END AS VARCHAR(12))             AS season_my,
        CAST(CASE WHEN EXISTS (SELECT 1 FROM ref.public_holiday AS h
                               WHERE h.country_code = 'TH' AND h.holiday_date = c.date)
                  THEN 1 ELSE 0 END AS BIT)                      AS is_holiday_th,
        CAST(CASE WHEN EXISTS (SELECT 1 FROM ref.public_holiday AS h
                               WHERE h.country_code = 'MY' AND h.holiday_date = c.date)
                  THEN 1 ELSE 0 END AS BIT)                      AS is_holiday_my,
        CAST(CASE WHEN EXISTS (SELECT 1 FROM ref.public_holiday AS h
                               WHERE h.country_code = 'SG' AND h.holiday_date = c.date)
                  THEN 1 ELSE 0 END AS BIT)                      AS is_holiday_sg
    FROM calendar AS c
)
MERGE dw.dim_date AS t
USING src AS s ON t.date_key = s.date_key
WHEN MATCHED AND EXISTS (
    SELECT s.season_th, s.season_my, s.is_holiday_th, s.is_holiday_my, s.is_holiday_sg
    EXCEPT
    SELECT t.season_th, t.season_my, t.is_holiday_th, t.is_holiday_my, t.is_holiday_sg
) THEN
    UPDATE SET season_th = s.season_th, season_my = s.season_my,
               is_holiday_th = s.is_holiday_th, is_holiday_my = s.is_holiday_my, is_holiday_sg = s.is_holiday_sg
WHEN NOT MATCHED BY TARGET THEN
    INSERT (date_key, date, year, month, month_name, iso_weekday, is_weekend,
            season_th, season_my, is_holiday_th, is_holiday_my, is_holiday_sg)
    VALUES (s.date_key, s.date, s.year, s.month, s.month_name, s.iso_weekday, s.is_weekend,
            s.season_th, s.season_my, s.is_holiday_th, s.is_holiday_my, s.is_holiday_sg);
