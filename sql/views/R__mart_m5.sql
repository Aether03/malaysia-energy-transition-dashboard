-- R__mart_m5: the M5 presentation layer for P6 About and P6b Data quality (repeatable).
-- Explicit column lists only. DQ counts by status are DAX measures over mart.dq_latest.

-- Rows per source (doc 03 P6 "rows per source" and "last pulled"): each source's most recent
-- LOAD step in a completed, non-dry run. Not tied to mart.run_latest, because a transform-only
-- run (`pipeline transform`) records no LOAD steps and would leave the summary empty.
CREATE OR ALTER VIEW mart.source_load_latest AS
SELECT
    s.data_source_code,
    s.run_id,
    s.finished_at AS loaded_at,
    s.rows_in,
    s.rows_merged,
    s.source_version
FROM (
    SELECT
        st.data_source_code,
        st.run_id,
        st.finished_at,
        st.rows_in,
        st.rows_merged,
        st.source_version,
        ROW_NUMBER() OVER (PARTITION BY st.data_source_code ORDER BY st.run_id DESC, st.step_id DESC) AS rn
    FROM meta.load_step AS st
    JOIN meta.load_run AS r
        ON r.run_id = st.run_id
    WHERE st.stage = 'LOAD'
      AND st.status IN ('SUCCESS', 'WARN')
      AND st.data_source_code IS NOT NULL
      AND r.status IN ('SUCCESS', 'WARN')
      AND r.is_dry_run = 0
) AS s
WHERE s.rn = 1;
GO
