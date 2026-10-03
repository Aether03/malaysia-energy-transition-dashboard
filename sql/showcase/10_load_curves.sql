-- 10_load_curves: what does a typical day look like? (FR-22; twin of P4's load-curve chart)
--
-- Question: mean demand by local hour, per grid, season and day type (Weekday vs Weekend &
--           holiday, the grid's own public holidays), over the complete years 2023-24.
-- Method:   an arithmetic mean of the published hourly values; gaps are left out.
--           Seasons are month-based approximations (Thailand: Thai Meteorological Department
--           hot/rainy/cool; Singapore: monsoon seasons), labelled in mart.grid_hourly.
-- Expected: 2 grids × 3 seasons × 2 day types × 24 hours = 288 rows; on weekdays Thailand's
--           curve peaks in the evening, and weekend & holiday curves sit below the weekday ones.

SELECT
    g.grid_code,
    h.season,
    h.season_order,
    h.day_type,
    h.hour,
    COUNT(*) AS hours,
    CAST(AVG(CAST(h.demand_mw AS FLOAT)) AS DECIMAL(10, 1)) AS mean_mw
FROM mart.grid_hourly AS h
JOIN mart.dim_grid AS g ON g.grid_key = h.grid_key
WHERE h.year IN (2023, 2024)
GROUP BY g.grid_code, g.display_order, h.season, h.season_order, h.day_type, h.hour
ORDER BY g.display_order, h.season_order, h.day_type DESC, h.hour;
