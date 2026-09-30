-- R__stg_dosm: staging view over raw.dosm_electricity (repeatable; re-applied when edited).
-- Annual aggregation of DOSM monthly supply and consumption for cross-checking against Ember.
-- One row per (year, measure, sector); `months` < 12 marks a partial year (2024 ends in June).

CREATE OR ALTER VIEW stg.dosm_annual AS
SELECT
    CAST(YEAR(r.month) AS SMALLINT) AS year,
    r.measure,
    r.sector,
    CAST(SUM(r.value_gwh) / 1000 AS DECIMAL(12, 4)) AS value_twh,  -- GWh -> TWh
    COUNT(*) AS months
FROM raw.dosm_electricity AS r
GROUP BY YEAR(r.month), r.measure, r.sector;
GO
