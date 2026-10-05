-- 13_state_reliability: which Peninsular states have the least reliable supply, and is it
-- improving? (FR-24; twin of P3b's ranked bar, map colour and trend)
--
-- Question: per state and year, SAIFI and SAIDI, the state's rank among the 13 Peninsular
--           entries (1 = most reliable, i.e. the lowest value), and the change since 2015.
-- Method:   printed handbook values (p.84 SAIFI, p.83 SAIDI). Ranks use RANK(), so ties share a
--           rank. Change since 2015 is an absolute difference in the metric's unit, not a
--           percentage: Putrajaya's near-zero base would make a percentage meaningless.
-- Expected: 13 states x 8 years (2015-2022) = 104 rows; ranks 1-13 within each year and metric.
--           (No values here: the handbook is restricted, M4 plan Q1.)
-- Source:   Energy Commission.

WITH r AS (
    SELECT
        d.name AS state,
        d.iso_3166_2,
        f.year,
        f.saifi,
        f.saidi_min,
        RANK() OVER (PARTITION BY f.year ORDER BY f.saifi) AS saifi_rank,
        RANK() OVER (PARTITION BY f.year ORDER BY f.saidi_min) AS saidi_rank,
        f.saifi - FIRST_VALUE(f.saifi) OVER (PARTITION BY f.state_key ORDER BY f.year) AS saifi_change_since_2015,
        f.saidi_min - FIRST_VALUE(f.saidi_min) OVER (PARTITION BY f.state_key ORDER BY f.year) AS saidi_change_since_2015
    FROM mart.state_reliability AS f
    JOIN mart.dim_state AS d ON d.state_key = f.state_key
    WHERE f.year >= 2015
)
SELECT state, iso_3166_2, year, saifi, saifi_rank, saifi_change_since_2015, saidi_min, saidi_rank, saidi_change_since_2015
FROM r
ORDER BY year DESC, saifi_rank, state;
