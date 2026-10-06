-- V017: M5 hardening (plan Q4).

-- 1: the migration ledger is written by the migration runner only. role_pipeline holds INSERT and
-- UPDATE on schema meta (V005, for the run log), and a schema-level GRANT must not let the pipeline
-- forge or rewrite a migration record, so the object-level DENY takes precedence over it.
-- The runner connects as the Windows login that owns the database (dbo, sysadmin on a
-- single-user PC), which no role DENY applies to, so migrations are not affected.
DENY INSERT, UPDATE, DELETE ON OBJECT::meta.schema_version TO role_pipeline;
GO

-- 2: a mix source can report capacity without generation (M5 Q4, transform review LOW). The fact
-- keeps the row, with generation unknown, instead of dropping the capacity (transform 020).
ALTER TABLE dw.fact_generation_annual ALTER COLUMN generation_twh DECIMAL(12, 4) NULL;
