-- 05_capacity_factor: how hard is each source's fleet working? (FR-11, FR-15; twin of P2's
-- capacity-factor bar and D1)
--
-- Question: capacity factor by source, country and year.
-- Method:   CF = generation (GWh) ÷ (capacity (GW) × hours in the year), with 8,784 hours in
--           leap years (dim_year.hours_in_year). NULL, never 0, when capacity is not reported,
--           and NULL with a reason when the implied CF exceeds 100% (Ember's capacity is too
--           small for the generation it reports; see CF_AT_MOST_1 in docs/reconciliation.md).
-- Expected: Malaysia 2025 gas CF = 1000 × gas TWh ÷ (17.99 GW × 8,760 h); Malaysia 2024
--           Other fossil is NULL with reason 'CF_ABOVE_100' (implied 110%).

SELECT
    c.name,
    g.year,
    s.display_name AS source,
    g.generation_twh,
    g.capacity_gw,
    y.hours_in_year,
    CASE
        WHEN g.capacity_gw > 0 AND 1000 * g.generation_twh <= g.capacity_gw * y.hours_in_year
        THEN CAST(100.0 * 1000 * g.generation_twh / (g.capacity_gw * y.hours_in_year) AS DECIMAL(7, 2))
    END AS capacity_factor_pct,
    CASE
        WHEN g.generation_twh IS NULL                               THEN 'GENERATION_NOT_REPORTED'
        WHEN g.capacity_gw IS NULL                                  THEN 'CAPACITY_NOT_REPORTED'
        WHEN g.capacity_gw = 0 AND g.generation_twh > 0             THEN 'CAPACITY_NOT_REPORTED'
        WHEN g.capacity_gw = 0                                      THEN 'NO_CAPACITY'
        WHEN 1000 * g.generation_twh > g.capacity_gw * y.hours_in_year THEN 'CF_ABOVE_100'
    END AS blank_reason
FROM mart.generation_annual AS g
JOIN mart.dim_source AS s ON s.source_key = g.source_key
JOIN mart.dim_country AS c ON c.country_key = g.country_key
JOIN mart.dim_year AS y ON y.year = g.year
WHERE c.area_type = 'COUNTRY'
ORDER BY c.display_order, g.year, s.sort_order;
