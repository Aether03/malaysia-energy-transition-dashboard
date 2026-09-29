-- R__mart_m1: the M1 presentation layer read by Power BI (repeatable; re-applied when edited).
-- Explicit column lists only, so a schema change in dw/ref/meta never silently reshapes the model.

CREATE OR ALTER VIEW mart.dim_country AS
SELECT country_key, iso3, name, area_type, is_asean, is_focus, is_default_peer, display_order
FROM dw.dim_country;
GO

CREATE OR ALTER VIEW mart.dim_source AS
SELECT source_key, source_code, display_name, group_name, sort_order, color_hex
FROM dw.dim_source;
GO

CREATE OR ALTER VIEW mart.dim_year AS
SELECT year, is_complete, decade
FROM dw.dim_year;
GO

CREATE OR ALTER VIEW mart.data_source AS
SELECT data_source_code, name, licence, url, credit_text, consent_status, is_publishable
FROM dw.dim_data_source;
GO

CREATE OR ALTER VIEW mart.kpi AS
SELECT kpi_code, name, definition, formula, unit, polarity, data_source_code
FROM ref.kpi;
GO

CREATE OR ALTER VIEW mart.netr_target AS
SELECT target_year, re_capacity_share_pct, source_url
FROM ref.netr_target;
GO

CREATE OR ALTER VIEW mart.generation_annual AS
SELECT country_key, year, source_key, generation_twh, share_pct, capacity_gw, emissions_mtco2e
FROM dw.fact_generation_annual;
GO

CREATE OR ALTER VIEW mart.country_annual AS
SELECT
    country_key,
    year,
    total_generation_twh,
    demand_twh,
    net_imports_twh,
    emissions_mtco2e,
    emissions_intensity_gco2e_kwh,
    population,
    demand_per_capita_mwh,
    re_share_gen_pct,
    fossil_share_gen_pct,
    re_share_capacity_pct
FROM dw.fact_country_annual;
GO

-- The single most recent completed, non-dry run (drives the "data as of" label).
CREATE OR ALTER VIEW mart.run_latest AS
SELECT TOP (1) run_id, started_at, finished_at, status
FROM meta.load_run
WHERE status IN ('SUCCESS', 'WARN') AND is_dry_run = 0
ORDER BY run_id DESC;
GO

-- Data-quality results of the latest run that recorded any.
CREATE OR ALTER VIEW mart.dq_latest AS
SELECT
    res.run_id,
    res.rule_code,
    r.description,
    r.severity,
    r.data_source_code,
    res.status,
    res.rows_affected,
    res.detail,
    res.checked_at
FROM meta.dq_result AS res
JOIN meta.dq_rule AS r
    ON r.rule_code = res.rule_code
WHERE res.run_id = (SELECT MAX(run_id) FROM meta.dq_result);
GO
