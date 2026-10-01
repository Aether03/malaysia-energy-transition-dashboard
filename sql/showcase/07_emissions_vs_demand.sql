-- 07_emissions_vs_demand: did cleaner electricity cut Malaysia's power-sector emissions?
-- (FR-09, FR-15; source query for finding 2 in docs/findings.md)
--
-- Question: change in demand, generation, carbon intensity, emissions and coal generation
--           between a base year and the latest complete year.
-- Method:   two-year pivot of mart.country_annual and mart.generation_annual, with percentage
--           changes. Emissions = intensity x generation, so the emissions change splits into
--           a volume effect (more generation) and an intensity effect (cleaner kWh).
-- Expected: 2015 -> 2025, intensity falls about 10% but emissions rise about 27%, because
--           generation rises about 40%; coal generation rises by about half while gas is flat,
--           so the fossil fleet itself gets slightly dirtier.

WITH years AS (
    SELECT 2015 AS base_year, MAX(year) AS latest_year
    FROM mart.dim_year
    WHERE is_complete = 1
),
kpis AS (
    SELECT
        MAX(CASE WHEN ca.year = y.base_year   THEN ca.demand_twh END)                    AS demand_base,
        MAX(CASE WHEN ca.year = y.latest_year THEN ca.demand_twh END)                    AS demand_latest,
        MAX(CASE WHEN ca.year = y.base_year   THEN ca.total_generation_twh END)          AS gen_base,
        MAX(CASE WHEN ca.year = y.latest_year THEN ca.total_generation_twh END)          AS gen_latest,
        MAX(CASE WHEN ca.year = y.base_year   THEN ca.emissions_intensity_gco2e_kwh END) AS intensity_base,
        MAX(CASE WHEN ca.year = y.latest_year THEN ca.emissions_intensity_gco2e_kwh END) AS intensity_latest,
        MAX(CASE WHEN ca.year = y.base_year   THEN ca.emissions_mtco2e END)              AS emissions_base,
        MAX(CASE WHEN ca.year = y.latest_year THEN ca.emissions_mtco2e END)              AS emissions_latest
    FROM mart.country_annual AS ca
    JOIN mart.dim_country AS c ON c.country_key = ca.country_key AND c.is_focus = 1
    CROSS JOIN years AS y
),
coal AS (  -- coal and gas output, and the fossil fleet's own intensity (audit MEDIUM-6)
    SELECT
        SUM(CASE WHEN g.year = y.base_year   AND s.source_code = 'COAL' THEN g.generation_twh END) AS coal_base,
        SUM(CASE WHEN g.year = y.latest_year AND s.source_code = 'COAL' THEN g.generation_twh END) AS coal_latest,
        SUM(CASE WHEN g.year = y.base_year   AND s.source_code = 'GAS'  THEN g.generation_twh END) AS gas_base,
        SUM(CASE WHEN g.year = y.latest_year AND s.source_code = 'GAS'  THEN g.generation_twh END) AS gas_latest,
        1000 * SUM(CASE WHEN g.year = y.base_year   AND s.group_name = 'FOSSIL' THEN g.emissions_mtco2e END)
             / NULLIF(SUM(CASE WHEN g.year = y.base_year   AND s.group_name = 'FOSSIL' THEN g.generation_twh END), 0) AS fossil_intensity_base,
        1000 * SUM(CASE WHEN g.year = y.latest_year AND s.group_name = 'FOSSIL' THEN g.emissions_mtco2e END)
             / NULLIF(SUM(CASE WHEN g.year = y.latest_year AND s.group_name = 'FOSSIL' THEN g.generation_twh END), 0) AS fossil_intensity_latest
    FROM mart.generation_annual AS g
    JOIN mart.dim_country AS c ON c.country_key = g.country_key AND c.is_focus = 1
    JOIN mart.dim_source AS s ON s.source_key = g.source_key
    CROSS JOIN years AS y
)
SELECT
    y.base_year,
    y.latest_year,
    k.demand_base, k.demand_latest,
    CAST(100.0 * (k.demand_latest - k.demand_base) / k.demand_base AS DECIMAL(7, 1))             AS demand_change_pct,
    k.gen_base, k.gen_latest,
    CAST(100.0 * (k.gen_latest - k.gen_base) / k.gen_base AS DECIMAL(7, 1))                      AS generation_change_pct,
    k.intensity_base, k.intensity_latest,
    CAST(100.0 * (k.intensity_latest - k.intensity_base) / k.intensity_base AS DECIMAL(7, 1))    AS intensity_change_pct,
    k.emissions_base, k.emissions_latest,
    CAST(100.0 * (k.emissions_latest - k.emissions_base) / k.emissions_base AS DECIMAL(7, 1))    AS emissions_change_pct,
    co.coal_base, co.coal_latest,
    CAST(100.0 * (co.coal_latest - co.coal_base) / co.coal_base AS DECIMAL(7, 1))                AS coal_change_pct,
    co.gas_base, co.gas_latest,
    CAST(co.fossil_intensity_base AS DECIMAL(7, 1))                                               AS fossil_intensity_base,
    CAST(co.fossil_intensity_latest AS DECIMAL(7, 1))                                             AS fossil_intensity_latest
FROM years AS y
CROSS JOIN kpis AS k
CROSS JOIN coal AS co;
