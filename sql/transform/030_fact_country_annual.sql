-- 030: rebuild dw.fact_country_annual inside the caller's transaction (after 020).
-- Totals, demand, net imports and intensity come from Ember's own rows; the shares are
-- computed from the mix in fact_generation_annual so SQL and DAX can be reconciled.
-- RE share of capacity counts large hydro as renewable (M1 plan: assumption, verified in M2);
-- NULL when capacity reporting is incomplete.
-- Population comes from OWID (UN WPP basis); demand per capita = Ember demand ÷ population
-- (M2 plan Q2), NULL where OWID has no population for that year.

DELETE FROM dw.fact_country_annual;

WITH totals AS (
    SELECT
        country_key,
        year,
        MAX(CASE WHEN electricity_source = 'Total generation' THEN generation_twh END)                AS total_generation_twh,
        MAX(CASE WHEN electricity_source = 'Demand' THEN generation_twh END)                          AS demand_twh,
        MAX(CASE WHEN electricity_source = 'Net imports' THEN generation_twh END)                     AS net_imports_twh,
        MAX(CASE WHEN electricity_source = 'Total generation' THEN emissions_mtco2e END)              AS emissions_mtco2e,
        MAX(CASE WHEN electricity_source = 'Total generation' THEN emissions_intensity_gco2e_kwh END) AS emissions_intensity_gco2e_kwh,
        MAX(CASE WHEN electricity_source = 'Total generation' THEN capacity_gw END)                   AS total_capacity_gw
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
        SUM(CASE WHEN d.group_name = 'RENEWABLE' THEN CAST(f.capacity_gw AS DECIMAL(18, 6)) END)    AS cap_re,
        -- any slot that generated power but reports no capacity makes the share unknowable
        -- (e.g. Lao PDR 2000-03 "Other fossil", Thailand "Other fossil"); so does renewable
        -- capacity too small for its generation (capacity factor > 1), e.g. Ember's 0-0.01 GW
        -- geothermal for the Philippines and Indonesia beside 10-15 TWh (M2 step 2, CF_AT_MOST_1)
        SUM(CASE WHEN f.generation_twh > 0
                  AND (f.capacity_gw IS NULL
                       OR (d.group_name = 'RENEWABLE' AND 1000 * f.generation_twh > f.capacity_gw * y.hours_in_year))
                 THEN 1 ELSE 0 END)                                                              AS re_cap_unreliable
    FROM dw.fact_generation_annual AS f
    JOIN dw.dim_source AS d ON d.source_key = f.source_key
    JOIN dw.dim_year AS y ON y.year = f.year
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
    o.population,
    CAST(t.demand_twh * 1000000 / NULLIF(o.population, 0) AS DECIMAL(10, 4)),  -- TWh -> MWh per person
    CAST(100 * COALESCE(m.gen_re, 0) / NULLIF(m.gen_all, 0) AS DECIMAL(7, 3)),
    CAST(100 * COALESCE(m.gen_fossil, 0) / NULLIF(m.gen_all, 0) AS DECIMAL(7, 3)),
    -- Denominator is Ember's own total capacity, not the sum of whatever sources report
    -- capacity (review finding 1: Viet Nam 2025 came out at 100%). Unknown stays NULL.
    CASE WHEN m.re_cap_unreliable = 0
         THEN CAST(100 * m.cap_re / NULLIF(t.total_capacity_gw, 0) AS DECIMAL(7, 3)) END
FROM totals AS t
LEFT JOIN mix AS m ON m.country_key = t.country_key AND m.year = t.year
LEFT JOIN stg.owid_energy AS o ON o.country_key = t.country_key AND o.year = t.year;
