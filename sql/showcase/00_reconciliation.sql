-- 00_reconciliation: does the warehouse reproduce Ember's own figures? (NFR-03, task 1.11)
--
-- For the focus country (Malaysia) in the latest complete year, five headline figures
-- are compared with a value derived independently from Ember's raw rows:
--   1. Total generation (TWh)      vs Ember's "Total generation" row
--   2. Renewable share (%)         vs Ember's own "Renewables" aggregate share
--   3. Carbon intensity (g/kWh)    vs emissions ÷ generation recomputed from the raw total row
--   4. Solar generation (TWh)      vs Ember's "Solar" row
--   5. Gas share of generation (%) vs Ember's "Gas" share
-- Pass = within ±0.5% relative difference.

WITH focus AS (
    SELECT c.country_key, c.ember_area
    FROM dw.dim_country AS c
    WHERE c.is_focus = 1
),
latest AS (
    SELECT MAX(y.year) AS year FROM dw.dim_year AS y WHERE y.is_complete = 1
),
raw_row AS (  -- Ember's raw values for the focus country and year
    SELECT r.electricity_source, r.generation_twh, r.share_of_generation_pct, r.emissions_mtco2e
    FROM raw.ember_yearly AS r
    JOIN focus AS f ON f.ember_area = r.area
    JOIN latest AS l ON l.year = r.year
),
dw_mix AS (   -- the warehouse's own mix for the same country and year
    SELECT
        d.source_code,
        g.generation_twh,
        100.0 * g.generation_twh / SUM(g.generation_twh) OVER () AS share_of_mix_pct
    FROM dw.fact_generation_annual AS g
    JOIN dw.dim_source AS d ON d.source_key = g.source_key
    JOIN focus AS f ON f.country_key = g.country_key
    JOIN latest AS l ON l.year = g.year
),
checks AS (
    SELECT 'Total generation (TWh)' AS metric,
           ca.total_generation_twh AS warehouse_value,
           (SELECT generation_twh FROM raw_row WHERE electricity_source = 'Total generation') AS ember_value
    FROM dw.fact_country_annual AS ca JOIN focus AS f ON f.country_key = ca.country_key JOIN latest AS l ON l.year = ca.year
    UNION ALL
    SELECT 'Renewable share of generation (%)',
           ca.re_share_gen_pct,
           (SELECT share_of_generation_pct FROM raw_row WHERE electricity_source = 'Renewables')
    FROM dw.fact_country_annual AS ca JOIN focus AS f ON f.country_key = ca.country_key JOIN latest AS l ON l.year = ca.year
    UNION ALL
    SELECT 'Carbon intensity (gCO2e/kWh)',
           ca.emissions_intensity_gco2e_kwh,
           (SELECT 1000.0 * emissions_mtco2e / generation_twh FROM raw_row WHERE electricity_source = 'Total generation')
    FROM dw.fact_country_annual AS ca JOIN focus AS f ON f.country_key = ca.country_key JOIN latest AS l ON l.year = ca.year
    UNION ALL
    SELECT 'Solar generation (TWh)',
           (SELECT generation_twh FROM dw_mix WHERE source_code = 'SOLAR'),
           (SELECT generation_twh FROM raw_row WHERE electricity_source = 'Solar')
    UNION ALL
    SELECT 'Gas share of generation (%)',
           (SELECT share_of_mix_pct FROM dw_mix WHERE source_code = 'GAS'),
           (SELECT share_of_generation_pct FROM raw_row WHERE electricity_source = 'Gas')
)
SELECT
    (SELECT ember_area FROM focus) AS country,
    (SELECT year FROM latest) AS year,
    metric,
    CAST(warehouse_value AS DECIMAL(12, 3)) AS warehouse_value,
    CAST(ember_value AS DECIMAL(12, 3)) AS ember_value,
    CAST(100.0 * (warehouse_value - ember_value) / NULLIF(ember_value, 0) AS DECIMAL(9, 4)) AS diff_pct,
    CASE WHEN ABS(100.0 * (warehouse_value - ember_value) / NULLIF(ember_value, 0)) <= 0.5
         THEN 'PASS' ELSE 'FAIL' END AS result
FROM checks;
