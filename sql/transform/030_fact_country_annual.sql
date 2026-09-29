-- 030: rebuild dw.fact_country_annual inside the caller's transaction (after 020).
-- Totals, demand, net imports and intensity come from Ember's own rows; the shares are
-- computed from the mix in fact_generation_annual so SQL and DAX can be reconciled.
-- RE share of capacity counts large hydro as renewable (M1 plan: assumption, verified in M2).
-- Population and per-capita demand stay NULL until OWID lands (M2).

DELETE FROM dw.fact_country_annual;

WITH totals AS (
    SELECT
        country_key,
        year,
        MAX(CASE WHEN electricity_source = 'Total generation' THEN generation_twh END)                AS total_generation_twh,
        MAX(CASE WHEN electricity_source = 'Demand' THEN generation_twh END)                          AS demand_twh,
        MAX(CASE WHEN electricity_source = 'Net imports' THEN generation_twh END)                     AS net_imports_twh,
        MAX(CASE WHEN electricity_source = 'Total generation' THEN emissions_mtco2e END)              AS emissions_mtco2e,
        MAX(CASE WHEN electricity_source = 'Total generation' THEN emissions_intensity_gco2e_kwh END) AS emissions_intensity_gco2e_kwh
    FROM stg.ember_yearly
    GROUP BY country_key, year
),
mix AS (
    SELECT
        f.country_key,
        f.year,
        SUM(CAST(f.generation_twh AS DECIMAL(18, 6)))                                            AS gen_all,
        SUM(CASE WHEN d.group_name = 'RENEWABLE' THEN CAST(f.generation_twh AS DECIMAL(18, 6)) END) AS gen_re,
        SUM(CASE WHEN d.group_name = 'FOSSIL' THEN CAST(f.generation_twh AS DECIMAL(18, 6)) END)    AS gen_fossil,
        SUM(CAST(f.capacity_gw AS DECIMAL(18, 6)))                                               AS cap_all,
        SUM(CASE WHEN d.group_name = 'RENEWABLE' THEN CAST(f.capacity_gw AS DECIMAL(18, 6)) END)    AS cap_re
    FROM dw.fact_generation_annual AS f
    JOIN dw.dim_source AS d ON d.source_key = f.source_key
    GROUP BY f.country_key, f.year
)
INSERT INTO dw.fact_country_annual
    (country_key, year, total_generation_twh, demand_twh, net_imports_twh, emissions_mtco2e,
     emissions_intensity_gco2e_kwh, population, demand_per_capita_mwh,
     re_share_gen_pct, fossil_share_gen_pct, re_share_capacity_pct)
SELECT
    t.country_key,
    t.year,
    t.total_generation_twh,
    t.demand_twh,
    t.net_imports_twh,
    t.emissions_mtco2e,
    t.emissions_intensity_gco2e_kwh,
    NULL,
    NULL,
    CAST(100 * COALESCE(m.gen_re, 0) / NULLIF(m.gen_all, 0) AS DECIMAL(7, 3)),
    CAST(100 * COALESCE(m.gen_fossil, 0) / NULLIF(m.gen_all, 0) AS DECIMAL(7, 3)),
    CAST(100 * COALESCE(m.cap_re, 0) / NULLIF(m.cap_all, 0) AS DECIMAL(7, 3))
FROM totals AS t
LEFT JOIN mix AS m ON m.country_key = t.country_key AND m.year = t.year;
