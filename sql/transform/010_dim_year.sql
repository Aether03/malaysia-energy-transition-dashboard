-- 010: upsert dw.dim_year from staged years, first in the rebuild transaction, so a DQ
-- rollback reverts it together with the facts. Years are never deleted: facts reference them.
-- is_complete: before the current calendar year and present for the focus country.

MERGE dw.dim_year AS t
USING (
    SELECT
        s.year,
        CAST(CASE
            WHEN s.year < YEAR(SYSUTCDATETIME())
             AND EXISTS (
                SELECT 1 FROM stg.ember_yearly AS f
                JOIN dw.dim_country AS c ON c.country_key = f.country_key AND c.is_focus = 1
                WHERE f.year = s.year AND f.electricity_source = 'Total generation'
             )
            THEN 1 ELSE 0 END AS BIT) AS is_complete,
        CAST(s.year / 10 * 10 AS SMALLINT) AS decade
    FROM (SELECT DISTINCT year FROM stg.ember_yearly) AS s
) AS src ON t.year = src.year
WHEN MATCHED AND t.is_complete <> src.is_complete THEN
    UPDATE SET is_complete = src.is_complete
WHEN NOT MATCHED BY TARGET THEN
    INSERT (year, is_complete, decade) VALUES (src.year, src.is_complete, src.decade);
