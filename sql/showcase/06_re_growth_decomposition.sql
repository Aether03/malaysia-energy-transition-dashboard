-- 06_re_growth_decomposition: which renewable sources drove Malaysia's rising renewable
-- share? (FR-15; source query for finding 1 in docs/findings.md)
--
-- Question: change in generation by renewable source between a base year and the latest
--           complete year, and each source's share of the total renewable increase.
-- Method:   pivot the two years from mart.generation_annual with conditional aggregation,
--           then divide each source's increase by the summed increase (window SUM). Ember
--           does not split large from small hydro, so "Hydro" is all hydro.
-- Expected: 2015 -> 2025, renewables rise by about 28 TWh, and hydro supplies about three
--           quarters of the increase.

WITH years AS (
    SELECT 2015 AS base_year, MAX(year) AS latest_year
    FROM mart.dim_year
    WHERE is_complete = 1
),
by_source AS (
    SELECT
        s.display_name                                                         AS source,
        SUM(CASE WHEN g.year = y.base_year THEN g.generation_twh END)          AS base_twh,
        SUM(CASE WHEN g.year = y.latest_year THEN g.generation_twh END)        AS latest_twh
    FROM mart.generation_annual AS g
    JOIN mart.dim_source AS s ON s.source_key = g.source_key
    JOIN mart.dim_country AS c ON c.country_key = g.country_key
    CROSS JOIN years AS y
    WHERE c.is_focus = 1
      AND s.group_name = 'RENEWABLE'
      AND g.year IN (y.base_year, y.latest_year)
    GROUP BY s.display_name, s.sort_order
)
SELECT
    (SELECT base_year FROM years)                                              AS base_year,
    (SELECT latest_year FROM years)                                            AS latest_year,
    source,
    base_twh,
    latest_twh,
    latest_twh - base_twh                                                      AS increase_twh,
    CAST(100.0 * (latest_twh - base_twh)
         / NULLIF(SUM(latest_twh - base_twh) OVER (), 0) AS DECIMAL(7, 1))     AS share_of_increase_pct
FROM by_source
ORDER BY increase_twh DESC;
