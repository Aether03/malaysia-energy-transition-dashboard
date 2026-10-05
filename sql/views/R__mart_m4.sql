-- R__mart_m4: the M4 presentation layer for P3 Regions and P3b State reliability (repeatable).
-- Explicit column lists only. Source D5 (Energy Commission handbook) is restricted (M4 plan Q1):
-- these views live only in the local database and feed the local report; dim_data_source
-- .is_publishable = 0 keeps them out of any export.

CREATE OR ALTER VIEW mart.dim_region AS
SELECT region_key, region_code, name, display_order
FROM dw.dim_region;
GO

-- is_reported_by_state: the handbook publishes SAIFI/SAIDI by state for Peninsular states only;
-- Sabah, Sarawak and Labuan shapes are greyed on the map and explained (doc 03 P3b, plan Q6).
CREATE OR ALTER VIEW mart.dim_state AS
SELECT
    s.state_key,
    s.state_code,
    s.name,
    s.geo_shape_name,
    s.iso_3166_2,
    s.region_key,
    s.is_federal_territory,
    CAST(CASE WHEN r.region_code = 'PEN' THEN 1 ELSE 0 END AS BIT) AS is_reported_by_state,
    s.display_order
FROM dw.dim_state AS s
JOIN dw.dim_region AS r
    ON r.region_key = s.region_key;
GO

CREATE OR ALTER VIEW mart.region_annual AS
SELECT region_key, year, metric_code, value, unit
FROM dw.fact_region_annual;
GO

CREATE OR ALTER VIEW mart.region_capacity AS
SELECT region_key, year, source_key, installed_mw, available_mw
FROM dw.fact_region_capacity;
GO

CREATE OR ALTER VIEW mart.state_reliability AS
SELECT state_key, year, saifi, saidi_min
FROM dw.fact_state_reliability;
GO

-- Disconnected SAIFI | SAIDI toggle for P3b (plan Q7): one SWITCH measure reads the selection.
CREATE OR ALTER VIEW mart.reliability_metric AS
SELECT metric_code, label, unit, sort_order
FROM (VALUES
    ('SAIFI', N'SAIFI', N'interruptions per customer per year', CAST(1 AS TINYINT)),
    ('SAIDI', N'SAIDI', N'minutes per customer per year', CAST(2 AS TINYINT))
) AS v (metric_code, label, unit, sort_order);
GO

-- Disconnected year picker for P3b's map and ranked bar (plan Q9: its own slicer, not synced with
-- P1/P2/P5, whose years run past the handbook's). The trend line ignores it by construction.
CREATE OR ALTER VIEW mart.reliability_year AS
SELECT DISTINCT year
FROM dw.fact_state_reliability;
GO
