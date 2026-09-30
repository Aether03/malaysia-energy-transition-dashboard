-- R__stg_owid: staging view over raw.owid_energy (repeatable; re-applied when edited).
-- Countries join on ISO3; population feeds demand per capita (Ember demand ÷ OWID/UN
-- population, M2 plan Q2); generation is kept for the OWID_GEN_WITHIN_5PCT cross-check.

CREATE OR ALTER VIEW stg.owid_energy AS
SELECT
    c.country_key,
    r.year,
    r.population,
    r.electricity_generation,
    r.electricity_demand,
    r.per_capita_electricity
FROM raw.owid_energy AS r
JOIN dw.dim_country AS c
    ON c.iso3 = r.iso_code;
GO
