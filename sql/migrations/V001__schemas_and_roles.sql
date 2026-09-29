-- V001: layer schemas (doc 05 §1) and least-privilege roles (doc 05 §4).
-- meta already exists: the migration runner creates it to hold meta.schema_version.

IF SCHEMA_ID('raw')  IS NULL EXEC('CREATE SCHEMA raw');
IF SCHEMA_ID('stg')  IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('dw')   IS NULL EXEC('CREATE SCHEMA dw');
IF SCHEMA_ID('mart') IS NULL EXEC('CREATE SCHEMA mart');
IF SCHEMA_ID('ref')  IS NULL EXEC('CREATE SCHEMA ref');
IF SCHEMA_ID('meta') IS NULL EXEC('CREATE SCHEMA meta');
GO

-- role_pipeline: the Python pipeline (reads and writes every layer except mart).
-- role_report_reader: Power BI / exports (SELECT on mart only). Grants are in V005.
IF DATABASE_PRINCIPAL_ID('role_pipeline') IS NULL CREATE ROLE role_pipeline;
IF DATABASE_PRINCIPAL_ID('role_report_reader') IS NULL CREATE ROLE role_report_reader;
