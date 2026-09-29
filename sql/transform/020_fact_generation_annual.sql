-- 020: rebuild dw.fact_generation_annual inside the caller's transaction.
-- Mix sources only (ref.source_map.include_in_mix = 1): Net imports, Demand and Ember's
-- aggregates are excluded by label. Sources sharing a display slot (Wind + Other
-- renewables; Other fossil + Nuclear) are summed. Rows with no generation value are
-- skipped (database review, finding 5).

DELETE FROM dw.fact_generation_annual;

INSERT INTO dw.fact_generation_annual
    (country_key, year, source_key, generation_twh, share_pct, capacity_gw, emissions_mtco2e)
SELECT
    s.country_key,
    s.year,
    d.source_key,
    SUM(s.generation_twh),
    SUM(s.share_of_generation_pct),
    SUM(s.capacity_gw),       -- NULL when no capacity is reported for any member source
    SUM(s.emissions_mtco2e)
FROM stg.ember_yearly AS s
JOIN dw.dim_source AS d ON d.source_code = s.source_code
WHERE s.include_in_mix = 1
  AND s.generation_twh IS NOT NULL
GROUP BY s.country_key, s.year, d.source_key;
