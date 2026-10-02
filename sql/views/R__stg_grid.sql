-- R__stg_grid: staging views over raw.grid_interval for every hourly grid (M3 plan steps 5, 5b).
-- One file, because the union view at the bottom must be created after the per-grid views
-- (repeatable views are applied in file-name order).
--
-- Thailand (TH_EGAT, M3 plan Q1): raw is an exact copy of both Zenodo files. Here:
--   * ts_text 'dd/mm/yyyy h:mm' is parsed; a ':05' stamp stands for that hour.
--   * Each local hour is taken from ONE published row: the on-the-hour row beats ':05', then the
--     file whose year matches the hour's year, then file name. Boundary days published in both
--     files are identical (the OVERLAP_VALUES_AGREE rule proves it on every load).
--   * System demand = sum of the 5 regional *_demand series; an hour is complete only when all 5
--     are present. Flows map the published column names to a counterparty and a direction.
--   * No imputation: a missing hour is simply absent.

CREATE OR ALTER VIEW stg.thailand_row AS
-- One row per published (file, timestamp) with its parsed local time.
SELECT
    p.grid_code,
    p.file_name,
    p.ts_text,
    p.local_date,
    p.hour_part,
    p.minute_part,
    CASE WHEN p.local_date IS NOT NULL AND p.hour_part BETWEEN 0 AND 23 AND p.minute_part IN (0, 5)
         THEN DATEADD(HOUR, p.hour_part, CAST(p.local_date AS DATETIME2(0))) END AS ts_local
FROM (
    SELECT DISTINCT
        r.grid_code,
        r.file_name,
        r.ts_text,
        TRY_CONVERT(DATE, LEFT(r.ts_text, 10), 103) AS local_date,  -- 103 = dd/mm/yyyy
        TRY_CAST(SUBSTRING(r.ts_text, 12, CHARINDEX(':', r.ts_text + ':', 12) - 12) AS INT) AS hour_part,
        TRY_CAST(RIGHT(r.ts_text, 2) AS INT) AS minute_part
    FROM raw.grid_interval AS r
    WHERE r.grid_code = 'TH_EGAT'
) AS p;
GO

CREATE OR ALTER VIEW stg.thailand_chosen_row AS
-- The single published row each local hour is taken from (Q1 precedence).
SELECT grid_code, file_name, ts_text, ts_local
FROM (
    SELECT
        t.grid_code, t.file_name, t.ts_text, t.ts_local,
        ROW_NUMBER() OVER (
            PARTITION BY t.grid_code, t.ts_local
            ORDER BY
                CASE WHEN t.minute_part = 0 THEN 0 ELSE 1 END,
                CASE WHEN t.file_name = CONCAT('system_', YEAR(t.ts_local), '.csv') THEN 0 ELSE 1 END,
                t.file_name
        ) AS pick
    FROM stg.thailand_row AS t
    WHERE t.ts_local IS NOT NULL
) AS ranked
WHERE pick = 1;
GO

CREATE OR ALTER VIEW stg.thailand_hourly AS
SELECT
    g.grid_key,
    c.ts_local,
    DATEADD(MINUTE, -g.utc_offset_min, c.ts_local) AS ts_utc,
    SUM(r.value) AS demand_mw,
    COUNT(r.value) AS parts_present,
    CAST(CASE WHEN COUNT(r.value) = 5 THEN 1 ELSE 0 END AS BIT) AS is_complete,
    c.file_name,
    c.ts_text
FROM stg.thailand_chosen_row AS c
JOIN dw.dim_grid AS g
    ON g.grid_code = c.grid_code
JOIN raw.grid_interval AS r
    ON  r.grid_code = c.grid_code
    AND r.file_name = c.file_name
    AND r.ts_text   = c.ts_text
    AND r.series IN ('north_demand', 'south_demand', 'metropolitan_demand', 'central_demand', 'northeast_demand')
GROUP BY g.grid_key, g.utc_offset_min, c.ts_local, c.file_name, c.ts_text;
GO

CREATE OR ALTER VIEW stg.thailand_flow_hourly AS
-- Flows from Thailand's point of view. EDL_* (2023 file) and laos_* (2024 file) are the same
-- link to Electricite du Laos under two published names.
SELECT
    g.grid_key,
    c.ts_local,
    DATEADD(MINUTE, -g.utc_offset_min, c.ts_local) AS ts_utc,
    m.counterparty,
    MAX(CASE WHEN m.direction = 'IMP' THEN r.value END) AS import_mw,
    MAX(CASE WHEN m.direction = 'EXP' THEN r.value END) AS export_mw
FROM stg.thailand_chosen_row AS c
JOIN dw.dim_grid AS g
    ON g.grid_code = c.grid_code
JOIN raw.grid_interval AS r
    ON  r.grid_code = c.grid_code
    AND r.file_name = c.file_name
    AND r.ts_text   = c.ts_text
JOIN (VALUES
    ('malaysia_IMP', 'MY', 'IMP'), ('malaysia_EXP', 'MY', 'EXP'),
    ('EDL_IMP', 'LA_EDL', 'IMP'), ('EDL_EXP', 'LA_EDL', 'EXP'),
    ('laos_IMP', 'LA_EDL', 'IMP'), ('laos_EXP', 'LA_EDL', 'EXP'),
    ('hongsa_IMP', 'LA_HONGSA', 'IMP'),
    ('cambodia_EXP', 'KH', 'EXP')
) AS m (series, counterparty, direction)
    ON m.series = r.series
GROUP BY g.grid_key, g.utc_offset_min, c.ts_local, m.counterparty
HAVING MAX(CASE WHEN m.direction = 'IMP' THEN r.value END) IS NOT NULL
    OR MAX(CASE WHEN m.direction = 'EXP' THEN r.value END) IS NOT NULL;
GO

-- Every grid's hourly demand in one shape; dw.fact_grid_hourly loads the complete hours.
CREATE OR ALTER VIEW stg.grid_hourly AS
SELECT grid_key, ts_local, ts_utc, demand_mw, is_complete, file_name, ts_text
FROM stg.thailand_hourly;
GO

CREATE OR ALTER VIEW stg.grid_flow_hourly AS
SELECT grid_key, ts_local, ts_utc, counterparty, import_mw, export_mw
FROM stg.thailand_flow_hourly;
GO
