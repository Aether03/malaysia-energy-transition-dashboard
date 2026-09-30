-- 01_trends: how has Malaysia's generation mix changed? (FR-07, FR-15; twin of P2's mix chart)
--
-- Question: generation by source (TWh) and each source's share of the mix, every year.
-- Method:   read the mart layer Power BI reads; share = source TWh ÷ the year's mix total,
--           computed with a window SUM so the shares of a year always add to 100.
--           The last two columns roll the mix up to renewable vs fossil (dim_source.group_name).
-- Expected: Malaysia 2025 renewable share 20.4%, fossil share 79.6% (P1 KPIs, M1).

SELECT
    g.year,
    s.display_name                                                       AS source,
    s.group_name,
    g.generation_twh,
    CAST(100.0 * g.generation_twh
         / NULLIF(SUM(g.generation_twh) OVER (PARTITION BY g.year), 0) AS DECIMAL(7, 3))  AS share_of_mix_pct,
    CAST(100.0 * SUM(CASE WHEN s.group_name = 'RENEWABLE' THEN g.generation_twh END) OVER (PARTITION BY g.year)
         / NULLIF(SUM(g.generation_twh) OVER (PARTITION BY g.year), 0) AS DECIMAL(7, 3))  AS re_share_pct,
    CAST(100.0 * SUM(CASE WHEN s.group_name = 'FOSSIL' THEN g.generation_twh END) OVER (PARTITION BY g.year)
         / NULLIF(SUM(g.generation_twh) OVER (PARTITION BY g.year), 0) AS DECIMAL(7, 3))  AS fossil_share_pct
FROM mart.generation_annual AS g
JOIN mart.dim_source AS s ON s.source_key = g.source_key
JOIN mart.dim_country AS c ON c.country_key = g.country_key
WHERE c.is_focus = 1
ORDER BY g.year, s.sort_order;
