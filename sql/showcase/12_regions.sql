-- 12_regions: how differently do Peninsular Malaysia, Sabah and Sarawak run? (FR-23; twin of P3)
--
-- Question: per region, the latest capacity mix (installed MW by fuel group, 2021), electricity
--           consumption and per-capita use, and supply reliability; and how many times more
--           often a Sabah customer loses supply than a Peninsular one (SAIFI ratio).
-- Method:   printed handbook values (Energy Commission, Malaysia Energy Statistics Handbook 2023).
--           Peninsular SAIFI/SAIDI are the by-state tables' total rows (plan Q4.1). Sarawak's
--           years are remapped from its misprinted header (2015-2021 proven; plan Q4.2).
-- Expected: one row per region and year; the capacity shares of each region sum to 100.
--           (No values here: the handbook is restricted, M4 plan Q1.)
-- Source:   Energy Commission.

-- 1. Capacity mix by region (installed, as of 31 Dec 2021), share of the region's total
SELECT
    r.name AS region,
    c.year,
    s.display_name AS fuel_group,
    c.installed_mw,
    CAST(100.0 * c.installed_mw / SUM(c.installed_mw) OVER (PARTITION BY c.region_key, c.year) AS DECIMAL(5, 1)) AS share_pct,
    c.available_mw
FROM mart.region_capacity AS c
JOIN mart.dim_region AS r ON r.region_key = c.region_key
JOIN mart.dim_source AS s ON s.source_key = c.source_key
ORDER BY r.display_order, c.year, s.sort_order;

-- 2. One row per region and year: consumption, per capita, SAIFI, SAIDI and the Sabah ratio
WITH m AS (
    SELECT
        a.region_key,
        a.year,
        MAX(CASE WHEN a.metric_code = 'ELEC_CONSUMPTION_GWH' THEN a.value END) AS consumption_gwh,
        MAX(CASE WHEN a.metric_code = 'ELEC_PER_CAPITA_KWH' THEN a.value END) AS kwh_per_person,
        MAX(CASE WHEN a.metric_code = 'SAIFI' THEN a.value END) AS saifi,
        MAX(CASE WHEN a.metric_code = 'SAIDI_MIN' THEN a.value END) AS saidi_min,
        MAX(CASE WHEN a.metric_code = 'SUPPLY_INTERRUPTIONS' THEN a.value END) AS interruptions
    FROM mart.region_annual AS a
    GROUP BY a.region_key, a.year
)
SELECT
    r.name AS region,
    m.year,
    m.consumption_gwh,
    m.kwh_per_person,
    m.saifi,
    m.saidi_min,
    m.interruptions,
    CAST(m.saifi / NULLIF(pen.saifi, 0) AS DECIMAL(6, 1)) AS saifi_vs_peninsular  -- 1.0 for Peninsular itself
FROM m
JOIN mart.dim_region AS r ON r.region_key = m.region_key
LEFT JOIN m AS pen
    ON pen.year = m.year
   AND pen.region_key = (SELECT region_key FROM mart.dim_region WHERE region_code = 'PEN')
ORDER BY r.display_order, m.year;
