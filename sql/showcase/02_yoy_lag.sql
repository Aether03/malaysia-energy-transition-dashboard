-- 02_yoy_lag: year-on-year change of each headline KPI, with its polarity (FR-06, FR-11, FR-15;
-- twin of P1's delta labels and P2's demand-growth chart)
--
-- Question: how did each KPI move against the previous year, and was that good or bad?
-- Method:   LAG() over the year within each country. Shares move in percentage points (pp);
--           totals, intensity and demand move in percent. Polarity comes from mart.kpi
--           (+1 = up is good, -1 = down is good, doc 04 §3.5). The first year has no previous
--           value, so its change is NULL (shown as "—" in the report), never 0.
-- Expected: Malaysia 2025 total generation −0.4% vs 2024 (210.37 vs 211.17 TWh);
--           demand growth 2025 −0.4% (209.19 vs 210.09 TWh).

WITH focus AS (
    SELECT
        ca.year,
        ca.total_generation_twh,
        ca.demand_twh,
        ca.re_share_gen_pct,
        ca.fossil_share_gen_pct,
        ca.emissions_intensity_gco2e_kwh,
        ca.demand_per_capita_mwh,
        LAG(ca.total_generation_twh)          OVER (ORDER BY ca.year) AS prev_total_generation_twh,
        LAG(ca.demand_twh)                    OVER (ORDER BY ca.year) AS prev_demand_twh,
        LAG(ca.re_share_gen_pct)              OVER (ORDER BY ca.year) AS prev_re_share_gen_pct,
        LAG(ca.fossil_share_gen_pct)          OVER (ORDER BY ca.year) AS prev_fossil_share_gen_pct,
        LAG(ca.emissions_intensity_gco2e_kwh) OVER (ORDER BY ca.year) AS prev_intensity,
        LAG(ca.demand_per_capita_mwh)         OVER (ORDER BY ca.year) AS prev_demand_per_capita_mwh
    FROM mart.country_annual AS ca
    JOIN mart.dim_country AS c ON c.country_key = ca.country_key
    WHERE c.is_focus = 1
),
changes AS (
    SELECT year, 'TOTAL_GENERATION' AS kpi_code, total_generation_twh AS value,
           CAST(100.0 * (total_generation_twh - prev_total_generation_twh) / NULLIF(prev_total_generation_twh, 0) AS DECIMAL(9, 3)) AS change, '%' AS change_unit
    FROM focus
    UNION ALL
    SELECT year, 'DEMAND_GROWTH', demand_twh,
           CAST(100.0 * (demand_twh - prev_demand_twh) / NULLIF(prev_demand_twh, 0) AS DECIMAL(9, 3)), '%'
    FROM focus
    UNION ALL
    SELECT year, 'RE_SHARE_GEN', re_share_gen_pct, CAST(re_share_gen_pct - prev_re_share_gen_pct AS DECIMAL(9, 3)), 'pp'
    FROM focus
    UNION ALL
    SELECT year, 'FOSSIL_SHARE_GEN', fossil_share_gen_pct, CAST(fossil_share_gen_pct - prev_fossil_share_gen_pct AS DECIMAL(9, 3)), 'pp'
    FROM focus
    UNION ALL
    SELECT year, 'CARBON_INTENSITY', emissions_intensity_gco2e_kwh,
           CAST(100.0 * (emissions_intensity_gco2e_kwh - prev_intensity) / NULLIF(prev_intensity, 0) AS DECIMAL(9, 3)), '%'
    FROM focus
    UNION ALL
    SELECT year, 'DEMAND_PER_CAPITA', demand_per_capita_mwh,
           CAST(100.0 * (demand_per_capita_mwh - prev_demand_per_capita_mwh) / NULLIF(prev_demand_per_capita_mwh, 0) AS DECIMAL(9, 3)), '%'
    FROM focus
)
SELECT
    ch.year,
    ch.kpi_code,
    ch.value,
    ch.change,
    ch.change_unit,
    CASE
        WHEN ch.change IS NULL OR ch.change = 0 THEN 'NEUTRAL'
        WHEN SIGN(ch.change) = k.polarity        THEN 'GOOD'
        ELSE 'BAD'
    END AS direction
FROM changes AS ch
JOIN mart.kpi AS k ON k.kpi_code = ch.kpi_code
ORDER BY ch.kpi_code, ch.year;
