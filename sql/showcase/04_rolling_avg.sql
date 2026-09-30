-- 04_rolling_avg: is each country's renewable share trending up once year-to-year noise is
-- smoothed out? (FR-08, FR-15; supports the P5 trend and the findings)
--
-- Question: 3-year rolling average of the renewable share of generation, per country.
-- Method:   AVG() OVER a 3-row frame ordered by year. Hydro-heavy systems swing with rainfall,
--           so the rolling mean separates trend from weather. The average is only reported
--           once three years are available (COUNT over the same frame), never on a partial window.
-- Expected: Malaysia's 3-year average for 2023-2025 equals the mean of its three yearly RE
--           shares (spot check against 01_trends).

SELECT
    c.name,
    ca.year,
    ca.re_share_gen_pct,
    CASE
        WHEN COUNT(ca.re_share_gen_pct) OVER w = 3
        THEN CAST(AVG(ca.re_share_gen_pct) OVER w AS DECIMAL(7, 3))
    END AS re_share_3yr_avg_pct
FROM mart.country_annual AS ca
JOIN mart.dim_country AS c ON c.country_key = ca.country_key
WHERE c.area_type = 'COUNTRY'
WINDOW w AS (PARTITION BY ca.country_key ORDER BY ca.year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
ORDER BY c.display_order, ca.year;
