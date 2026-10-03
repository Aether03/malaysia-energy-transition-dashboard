-- 08_grid_load: how peaky is each grid? (FR-22; twin of P4's peak and load-factor charts)
--
-- Question: peak hourly demand, when it happened, and load factor, per grid, per year and month.
-- Method:   peak = the highest published hourly value (hourly means, so below an instantaneous
--           peak); load factor = mean ÷ peak over the same published hours. Gaps are left out,
--           never filled. Complete years 2023-24 only (Singapore's weekly files spill into
--           Dec 2022 and Jan 2025; Thailand's into 2025-01-01).
-- Expected: Thailand 2023 peak 33,443 MW on 2023-05-06 21:00, load factor 69.8%; 2024 peak
--           35,560 MW on 2024-04-29 21:00, load factor 69.2% (M3 plan, profiled 2026-10-03).
--           month IS NULL marks the whole-year row.

WITH hours AS (
    SELECT g.grid_code, g.display_order, h.year, h.month, h.ts_local, h.demand_mw
    FROM mart.grid_hourly AS h
    JOIN mart.dim_grid AS g ON g.grid_key = h.grid_key
    WHERE h.year IN (2023, 2024)
),
periods AS (
    SELECT grid_code, display_order, year, month, ts_local, demand_mw FROM hours
    UNION ALL
    SELECT grid_code, display_order, year, NULL, ts_local, demand_mw FROM hours
),
ranked AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (PARTITION BY p.grid_code, p.year, p.month
                           ORDER BY p.demand_mw DESC, p.ts_local) AS peak_rank
    FROM periods AS p
)
SELECT
    r.grid_code,
    r.year,
    r.month,
    COUNT(*) AS hours,
    MAX(r.demand_mw) AS peak_mw,
    MAX(CASE WHEN r.peak_rank = 1 THEN r.ts_local END) AS peak_at,
    CAST(AVG(CAST(r.demand_mw AS FLOAT)) AS DECIMAL(10, 1)) AS mean_mw,
    CAST(100.0 * AVG(CAST(r.demand_mw AS FLOAT)) / MAX(r.demand_mw) AS DECIMAL(6, 2)) AS load_factor_pct
FROM ranked AS r
GROUP BY r.grid_code, r.display_order, r.year, r.month
ORDER BY r.display_order, r.year, CASE WHEN r.month IS NULL THEN 0 ELSE 1 END, r.month;
