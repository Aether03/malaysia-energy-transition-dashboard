-- V018: what each source gives the report, for the P6 sources table (doc 03 P6 "what it gives").
-- Seeded from seed/data_source.csv; NULL until the next `pipeline seed`.
ALTER TABLE dw.dim_data_source ADD provides NVARCHAR(200) NULL;
