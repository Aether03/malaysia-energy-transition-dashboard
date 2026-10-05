-- 070: rebuild dw.fact_region_annual and dw.fact_region_capacity from the handbook staging views
-- (M4 plan step 8; task 4.3). Printed values only: totals are the printed totals, never re-summed
-- (CAPACITY_SUBTOTALS_SUM proves they add up). A printed '-' lands as NULL (not reported).

DELETE FROM dw.fact_region_capacity;
DELETE FROM dw.fact_region_annual;

INSERT INTO dw.fact_region_annual (region_key, year, metric_code, value, unit, page)
SELECT r.region_key, m.year, m.metric_code, m.value, m.unit, m.page
FROM stg.handbook_region_metric AS m
JOIN dw.dim_region AS r ON r.region_code = m.region_code
WHERE m.year IS NOT NULL
  AND (m.value IS NULL OR m.value >= 0);  -- else RELIABILITY_NON_NEGATIVE reports it (BLOCKING), not a CHECK crash

INSERT INTO dw.fact_region_capacity (region_key, year, source_key, installed_mw, available_mw)
SELECT r.region_key, c.year, s.source_key, CAST(c.installed_mw AS DECIMAL(10, 1)), CAST(c.available_mw AS DECIMAL(10, 1))
FROM stg.handbook_region_capacity AS c
JOIN dw.dim_region AS r ON r.region_code = c.region_code
JOIN dw.dim_source AS s ON s.source_code = c.source_code
WHERE COALESCE(c.installed_mw, 0) >= 0 AND COALESCE(c.available_mw, 0) >= 0;
