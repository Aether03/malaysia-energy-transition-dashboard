-- 03_ranking: where does Malaysia rank among its ASEAN peers? (FR-08, FR-15; twin of P1's
-- "vs ASEAN" card and P5's rank card)
--
-- Question: rank of each default peer (MY, ID, TH, VN, PH, SG) on RE share (high = better),
--           carbon intensity (low = better) and demand per capita (high = rank 1).
-- Method:   the comparison year is the latest year, up to the end of the selected year range
--           (range_end), that ALL compared countries have for that metric (doc 03 P5 edge
--           case), then RANK() OVER that year. Ties share a rank; countries without a value
--           that year are not counted.
--           Per-capita needs OWID population, which ends in 2024 for Indonesia, so its common
--           year can be earlier than the others'.
-- Expected: the six default peers all have 2025 generation data, so RE share and intensity
--           rank on 2025; per capita ranks on 2024. Malaysia (2026-09-30 data): RE share
--           3 of 6 (20.4%), carbon intensity 5 of 6 (606 g/kWh), per capita 2 of 6 (5.91 MWh).

WITH range_end AS (  -- the report's year-range slicer end; the full range by default
    SELECT MAX(year) AS last_year FROM mart.dim_year
),
peers AS (
    SELECT c.country_key, c.name
    FROM mart.dim_country AS c
    WHERE c.is_default_peer = 1
),
common_year AS (
    SELECT
        MIN(last_gen)        AS gen_year,
        MIN(last_per_capita) AS per_capita_year
    FROM (
        SELECT
            p.country_key,
            MAX(CASE WHEN ca.re_share_gen_pct IS NOT NULL THEN ca.year END)      AS last_gen,
            MAX(CASE WHEN ca.demand_per_capita_mwh IS NOT NULL THEN ca.year END) AS last_per_capita
        FROM peers AS p
        JOIN mart.country_annual AS ca ON ca.country_key = p.country_key
        WHERE ca.year <= (SELECT last_year FROM range_end)
        GROUP BY p.country_key
    ) AS latest
),
gen_ranked AS (
    SELECT
        p.name,
        ca.year,
        ca.re_share_gen_pct,
        RANK() OVER (ORDER BY ca.re_share_gen_pct DESC)             AS re_share_rank,
        ca.emissions_intensity_gco2e_kwh,
        RANK() OVER (ORDER BY ca.emissions_intensity_gco2e_kwh ASC) AS intensity_rank
    FROM peers AS p
    JOIN mart.country_annual AS ca ON ca.country_key = p.country_key
    JOIN common_year AS cy ON cy.gen_year = ca.year
    WHERE ca.re_share_gen_pct IS NOT NULL
),
per_capita_ranked AS (
    SELECT
        p.name,
        ca.year                                              AS per_capita_year,
        ca.demand_per_capita_mwh,
        RANK() OVER (ORDER BY ca.demand_per_capita_mwh DESC) AS per_capita_rank
    FROM peers AS p
    JOIN mart.country_annual AS ca ON ca.country_key = p.country_key
    JOIN common_year AS cy ON cy.per_capita_year = ca.year
    WHERE ca.demand_per_capita_mwh IS NOT NULL
)
SELECT
    g.name,
    g.year AS comparison_year,
    g.re_share_gen_pct,
    g.re_share_rank,
    g.emissions_intensity_gco2e_kwh,
    g.intensity_rank,
    pc.per_capita_year,
    pc.demand_per_capita_mwh,
    pc.per_capita_rank,
    COUNT(*) OVER () AS countries_compared
FROM gen_ranked AS g
LEFT JOIN per_capita_ranked AS pc ON pc.name = g.name
ORDER BY g.re_share_rank, g.name;
