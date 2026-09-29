-- R__stg_ember: staging view over raw.ember_yearly (repeatable; re-applied when edited).
-- One row per raw row that matches a dim_country row. Countries join on iso3; the ASEAN
-- aggregate has no iso3 in Ember's file, so it joins on Ember's own area label.
-- include_in_mix / is_mapped come from ref.source_map (unmapped sources default to 0).

CREATE OR ALTER VIEW stg.ember_yearly AS
SELECT
    c.country_key,
    r.year,
    r.electricity_source,
    m.source_code,
    CAST(COALESCE(m.include_in_mix, 0) AS BIT) AS include_in_mix,
    CAST(CASE WHEN m.ember_source IS NULL THEN 0 ELSE 1 END AS BIT) AS is_mapped,
    r.generation_twh,
    r.share_of_generation_pct,
    r.capacity_gw,
    r.emissions_mtco2e,
    r.emissions_intensity_gco2e_kwh
FROM raw.ember_yearly AS r
JOIN dw.dim_country AS c
    ON c.iso3 = r.iso3
    OR (r.iso3 IS NULL AND c.ember_area = r.area)
LEFT JOIN ref.source_map AS m
    ON m.ember_source = r.electricity_source;
GO
