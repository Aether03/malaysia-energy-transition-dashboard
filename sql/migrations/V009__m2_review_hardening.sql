-- V009: fixes from the ecc:database-reviewer pass on V008 (M2, 2026-09-30).

-- Every target must cite its source (all seed rows carry one since M2 step 1).
ALTER TABLE ref.netr_target ALTER COLUMN source_name NVARCHAR(200) NOT NULL;

-- Declare the computed column NOT NULL so the model sees a non-nullable column.
ALTER TABLE dw.dim_year DROP COLUMN hours_in_year;
ALTER TABLE dw.dim_year ADD hours_in_year AS
    CAST(CASE WHEN (year % 4 = 0 AND year % 100 <> 0) OR year % 400 = 0 THEN 8784 ELSE 8760 END AS SMALLINT) PERSISTED NOT NULL;
