-- R__stg_handbook: staging views over raw.handbook_cell (M4 plan step 8; tasks 4.1, 4.3).
-- raw is an exact copy of the pinned tables as printed (pipeline/sources/handbook.py). Here:
--   * values are cast ('1,234.5' -> 1234.5, '100%' -> 100, '-' -> NULL), and each value keeps the
--     half-unit of its printed precision ('0.8' -> 0.05, '0.83' -> 0.005) for the DQ checks;
--   * years come from the printed column label, except where a pinned override says otherwise
--     (handbook_year_map below) or the table states one as-of year (handbook_table_year);
--   * state labels go through ref.state_alias; region names match dw.dim_region.name;
--   * the Q4 rules: Peninsular SAIFI/SAIDI come from the state tables' total rows (p.84/p.83), the
--     only internally consistent ones; Sarawak's misprinted header is remapped (see below).
-- Licence (M4 plan Q1): these views read restricted data; they exist only in the local database.
-- Only the latest loaded edition is used. The year map below is keyed to the 2023 edition: a new
-- edition loaded without new pins fails HANDBOOK_RAW_SHAPE and REGION_METRICS_COMPLETE (BLOCKING).

CREATE OR ALTER VIEW stg.handbook_year_map AS
-- Pinned column-year overrides. SARAWAK_DIST_PERF (2023 edition, p.85) prints its years as
-- 2014 ... 2020, 2019. The 2022 edition (pp. 86-88; check only) shows the same table for 2015-2021,
-- and its 21 values equal the 2023 edition's columns 1-7 in order, so every printed year is one
-- year early (M4 step 7, docs/reconciliation.md §M4). Column 8 is not in the 2022 edition: its year
-- is unproven, so it is excluded (year NULL). Decision: Amirul, 2026-10-05 ("proven years only").
SELECT edition, table_code, col_pos, year
FROM (VALUES
    (2023, 'SARAWAK_DIST_PERF', 1, CAST(2015 AS SMALLINT)),
    (2023, 'SARAWAK_DIST_PERF', 2, CAST(2016 AS SMALLINT)),
    (2023, 'SARAWAK_DIST_PERF', 3, CAST(2017 AS SMALLINT)),
    (2023, 'SARAWAK_DIST_PERF', 4, CAST(2018 AS SMALLINT)),
    (2023, 'SARAWAK_DIST_PERF', 5, CAST(2019 AS SMALLINT)),
    (2023, 'SARAWAK_DIST_PERF', 6, CAST(2020 AS SMALLINT)),
    (2023, 'SARAWAK_DIST_PERF', 7, CAST(2021 AS SMALLINT)),
    (2023, 'SARAWAK_DIST_PERF', 8, CAST(NULL AS SMALLINT))
) AS v (edition, table_code, col_pos, year);
GO

CREATE OR ALTER VIEW stg.handbook_table_year AS
-- Tables that state one as-of date in their pinned title ("... as of 31st December 2021").
SELECT edition, table_code, year
FROM (VALUES
    (2023, 'INSTALLED_CAPACITY', CAST(2021 AS SMALLINT)),
    (2023, 'AVAILABLE_CAPACITY', CAST(2021 AS SMALLINT))
) AS v (edition, table_code, year);
GO

CREATE OR ALTER VIEW stg.handbook_cell AS
WITH latest AS (
    SELECT MAX(edition) AS edition FROM raw.handbook_cell
), cell AS (
    SELECT
        c.edition, c.page, c.table_code, c.row_pos, c.col_pos, c.row_group, c.row_label, c.col_label,
        c.value_text,
        REPLACE(REPLACE(c.value_text, N',', N''), N'%', N'') AS num_text
    FROM raw.handbook_cell AS c
    JOIN latest AS l ON l.edition = c.edition
)
SELECT
    c.edition, c.page, c.table_code, c.row_pos, c.col_pos, c.row_group, c.row_label, c.col_label, c.value_text,
    CASE WHEN c.value_text = N'-' THEN NULL ELSE TRY_CAST(c.num_text AS DECIMAL(14, 3)) END AS value,
    CAST(CASE  -- exact DECIMAL, not FLOAT: tolerance comparisons must not false-fail at the boundary (review L8)
        WHEN c.value_text = N'-' THEN NULL
        WHEN CHARINDEX(N'.', c.num_text) = 0 THEN 0.5
        WHEN LEN(c.num_text) - CHARINDEX(N'.', c.num_text) = 1 THEN 0.05
        WHEN LEN(c.num_text) - CHARINDEX(N'.', c.num_text) = 2 THEN 0.005
        ELSE 0.0005
    END AS DECIMAL(9, 4)) AS half_unit,
    CASE
        WHEN m.table_code IS NOT NULL THEN m.year
        WHEN t.table_code IS NOT NULL THEN t.year
        ELSE TRY_CAST(c.col_label AS SMALLINT)
    END AS col_year,
    CAST(CASE WHEN m.table_code IS NOT NULL AND m.year IS NULL THEN 1 ELSE 0 END AS BIT) AS is_excluded
FROM cell AS c
LEFT JOIN stg.handbook_year_map AS m
    ON m.edition = c.edition AND m.table_code = c.table_code AND m.col_pos = c.col_pos
LEFT JOIN stg.handbook_table_year AS t
    ON t.edition = c.edition AND t.table_code = c.table_code;
GO

CREATE OR ALTER VIEW stg.handbook_state_reliability AS
-- SAIFI (p.84) and SAIDI (p.83) by Peninsular state and year; the total row is not a state.
-- A label missing from ref.state_alias drops out here and fails STATE_ALIAS_COMPLETE (BLOCKING).
SELECT
    a.state_code,
    c.col_year AS year,
    MAX(CASE WHEN c.table_code = 'SAIFI_BY_STATE' THEN c.value END) AS saifi,
    MAX(CASE WHEN c.table_code = 'SAIDI_BY_STATE' THEN c.value END) AS saidi_min,
    COUNT(*) AS source_cells  -- 2 per state-year (SAIFI + SAIDI); more = two labels for one state
FROM stg.handbook_cell AS c
JOIN ref.state_alias AS a ON a.alias = c.row_label
WHERE c.table_code IN ('SAIFI_BY_STATE', 'SAIDI_BY_STATE')
  AND c.row_label <> N'PENINSULAR MALAYSIA'
  AND c.is_excluded = 0
GROUP BY a.state_code, c.col_year;
GO

CREATE OR ALTER VIEW stg.handbook_region_metric AS
-- Regional indicators in long form, one row per region, year and metric. Row labels below are the
-- printed headings pinned in pipeline/sources/handbook.py (the parser fails if they change).
WITH region AS (
    SELECT region_code, name FROM dw.dim_region
), key_data AS (  -- p.17-19: one page per region
    SELECT v.table_code, v.region_code
    FROM (VALUES ('KEY_DATA_PEN', 'PEN'), ('KEY_DATA_SAB', 'SAB'), ('KEY_DATA_SAR', 'SAR')) AS v (table_code, region_code)
), key_metric AS (
    SELECT v.row_label, v.metric_code, v.unit
    FROM (VALUES
        (N'Electricity Consumption (GWh)', 'ELEC_CONSUMPTION_GWH', N'GWh'),
        (N'Electricity Consumption (kWh) per Capita', 'ELEC_PER_CAPITA_KWH', N'kWh per person'),
        (N'Population (''000 people)**', 'POPULATION_K', N'thousand people')
    ) AS v (row_label, metric_code, unit)
), dist_perf AS (  -- p.85 (Sabah, Sarawak) and the p.83/p.84 Peninsular total rows
    SELECT v.table_code, v.row_label, v.region_code, v.metric_code, v.unit
    FROM (VALUES
        ('SAIFI_BY_STATE', N'PENINSULAR MALAYSIA', 'PEN', 'SAIFI', N'per customer/yr'),
        ('SAIDI_BY_STATE', N'PENINSULAR MALAYSIA', 'PEN', 'SAIDI_MIN', N'min/customer/yr'),
        ('SABAH_DIST_PERF', N'SAIFI (Number of Interruption/ Customer/Year)', 'SAB', 'SAIFI', N'per customer/yr'),
        ('SABAH_DIST_PERF', N'SAIDI (Minutes/ Customer/Year)', 'SAB', 'SAIDI_MIN', N'min/customer/yr'),
        ('SARAWAK_DIST_PERF', N'SAIFI (Number of Interruptions/Customer/ Year)', 'SAR', 'SAIFI', N'per customer/yr'),
        ('SARAWAK_DIST_PERF', N'SAIDI (Minutes/Customer/ Year)', 'SAR', 'SAIDI_MIN', N'min/customer/yr')
    ) AS v (table_code, row_label, region_code, metric_code, unit)
)
-- Installed and available capacity: the printed region totals (p.13 Subtotal rows, p.14 rows)
SELECT r.region_code, c.col_year AS year, 'INSTALLED_MW' AS metric_code, c.value, N'MW' AS unit, c.page
FROM stg.handbook_cell AS c
JOIN region AS r ON r.name = c.row_group
WHERE c.table_code = 'INSTALLED_CAPACITY' AND c.row_label = N'Subtotal' AND c.col_label = N'Total'
UNION ALL
SELECT r.region_code, c.col_year, 'AVAILABLE_MW', c.value, N'MW', c.page
FROM stg.handbook_cell AS c
JOIN region AS r ON r.name = c.row_label
WHERE c.table_code = 'AVAILABLE_CAPACITY' AND c.col_label = N'Total'
UNION ALL
SELECT k.region_code, c.col_year, m.metric_code, c.value, m.unit, c.page
FROM stg.handbook_cell AS c
JOIN key_data AS k ON k.table_code = c.table_code
JOIN key_metric AS m ON m.row_label = c.row_label
UNION ALL
-- p.82: years are the row labels, regions the column labels
SELECT r.region_code, TRY_CAST(c.row_label AS SMALLINT), 'SUPPLY_INTERRUPTIONS', c.value, N'interruptions', c.page
FROM stg.handbook_cell AS c
JOIN region AS r ON r.name = c.col_label
WHERE c.table_code = 'SUPPLY_INTERRUPTIONS'
UNION ALL
SELECT d.region_code, c.col_year, d.metric_code, c.value, d.unit, c.page
FROM stg.handbook_cell AS c
JOIN dist_perf AS d ON d.table_code = c.table_code AND d.row_label = c.row_label
WHERE c.is_excluded = 0;
GO

CREATE OR ALTER VIEW stg.handbook_region_capacity AS
-- Installed (p.13 region Subtotal rows) and available (p.14) capacity by doc 04 fuel group.
-- "Others" (unlabelled co-generation) folds into other fossil, like Ember's "Other fossil" slot.
-- p.14 (available) has no "Others" column, so installed vs available is not like-for-like for
-- OTHER_FOSSIL; the report shows no available/installed ratio by fuel (review M7).
-- CAPACITY_MATCHES_TOTALS (BLOCKING) reconciles these sums to the printed region totals (review H1).
WITH fuel AS (
    SELECT v.table_code, v.col_label, v.source_code
    FROM (VALUES
        ('INSTALLED_CAPACITY', N'Major Hydro', 'HYDRO'),
        ('INSTALLED_CAPACITY', N'Mini Hydro', 'HYDRO'),
        ('INSTALLED_CAPACITY', N'Natural Gas', 'GAS'),
        ('INSTALLED_CAPACITY', N'Coal', 'COAL'),
        ('INSTALLED_CAPACITY', N'Diesel / MFO', 'OTHER_FOSSIL'),
        ('INSTALLED_CAPACITY', N'Biomass', 'BIOENERGY'),
        ('INSTALLED_CAPACITY', N'Solar', 'SOLAR'),
        ('INSTALLED_CAPACITY', N'Biogas', 'BIOENERGY'),
        ('INSTALLED_CAPACITY', N'Others', 'OTHER_FOSSIL'),
        ('AVAILABLE_CAPACITY', N'Hydro', 'HYDRO'),
        ('AVAILABLE_CAPACITY', N'Natural Gas', 'GAS'),
        ('AVAILABLE_CAPACITY', N'Coal', 'COAL'),
        ('AVAILABLE_CAPACITY', N'Diesel / MFO', 'OTHER_FOSSIL'),
        ('AVAILABLE_CAPACITY', N'Biomass / Biogas', 'BIOENERGY'),
        ('AVAILABLE_CAPACITY', N'Solar', 'SOLAR')
    ) AS v (table_code, col_label, source_code)
), installed AS (
    SELECT r.region_code, c.col_year AS year, f.source_code, SUM(c.value) AS mw
    FROM stg.handbook_cell AS c
    JOIN fuel AS f ON f.table_code = c.table_code AND f.col_label = c.col_label
    JOIN dw.dim_region AS r ON r.name = c.row_group
    WHERE c.table_code = 'INSTALLED_CAPACITY' AND c.row_label = N'Subtotal'
    GROUP BY r.region_code, c.col_year, f.source_code
), available AS (
    SELECT r.region_code, c.col_year AS year, f.source_code, SUM(c.value) AS mw
    FROM stg.handbook_cell AS c
    JOIN fuel AS f ON f.table_code = c.table_code AND f.col_label = c.col_label
    JOIN dw.dim_region AS r ON r.name = c.row_label
    WHERE c.table_code = 'AVAILABLE_CAPACITY'
    GROUP BY r.region_code, c.col_year, f.source_code
)
SELECT
    COALESCE(i.region_code, a.region_code) AS region_code,
    COALESCE(i.year, a.year) AS year,
    COALESCE(i.source_code, a.source_code) AS source_code,
    i.mw AS installed_mw,
    a.mw AS available_mw
FROM installed AS i
FULL JOIN available AS a
    ON a.region_code = i.region_code AND a.year = i.year AND a.source_code = i.source_code
WHERE COALESCE(i.mw, 0) <> 0 OR COALESCE(a.mw, 0) <> 0;  -- a fuel with no capacity in the region is left out
GO
