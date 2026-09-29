-- V007: fixes from the ecc:database-reviewer pass on V001-V006 (M1 step 2 review).

-- A source can only be publishable if it is openly licensed or consent was granted.
ALTER TABLE dw.dim_data_source ADD CONSTRAINT ck_dim_data_source_publishable
    CHECK (is_publishable = 0 OR consent_status IN ('OPEN', 'GRANTED'));

-- Countries must carry a 3-letter upper-case ISO code; only regions may omit it.
ALTER TABLE dw.dim_country ADD CONSTRAINT ck_dim_country_iso3_required
    CHECK (area_type = 'REGION' OR iso3 IS NOT NULL);
ALTER TABLE dw.dim_country ADD CONSTRAINT ck_dim_country_iso3_format
    CHECK (iso3 IS NULL OR iso3 COLLATE Latin1_General_100_BIN2 LIKE '[A-Z][A-Z][A-Z]');

-- The pipeline reads mart views for exports and SQL-vs-DAX reconciliation.
GRANT SELECT ON SCHEMA::mart TO role_pipeline;
