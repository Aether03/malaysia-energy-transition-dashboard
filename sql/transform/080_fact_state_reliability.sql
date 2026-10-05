-- 080: rebuild dw.fact_state_reliability from stg.handbook_state_reliability (M4 plan step 8).
-- SAIFI and SAIDI as printed; NULL = not reported. A state with two source labels in one year
-- would double its cells: NO_DUPLICATE_STATE_YEAR (BLOCKING) reports it, and the MAX() in stg
-- keeps the insert from failing on the primary key first.

DELETE FROM dw.fact_state_reliability;

INSERT INTO dw.fact_state_reliability (state_key, year, saifi, saidi_min)
SELECT d.state_key, s.year, CAST(s.saifi AS DECIMAL(6, 3)), CAST(s.saidi_min AS DECIMAL(8, 2))
FROM stg.handbook_state_reliability AS s
JOIN dw.dim_state AS d ON d.state_code = s.state_code
WHERE s.year IS NOT NULL
  AND COALESCE(s.saifi, 0) >= 0 AND COALESCE(s.saidi_min, 0) >= 0;  -- else RELIABILITY_NON_NEGATIVE (BLOCKING)
