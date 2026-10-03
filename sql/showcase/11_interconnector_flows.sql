-- 11_interconnector_flows: which way does power cross the Thailand ↔ Malaysia border? (S2;
-- twin of P4's flow chart subtitle)
--
-- Question: energy Thailand exported to and imported from Malaysia per year, the net, and the
--           average daily net flow.
-- Method:   from Thailand's `malaysia_EXP` / `malaysia_IMP` series; each hour fills exactly one
--           direction; an hour with neither is a gap, not 0 (mart.grid_flow_daily). GWh = sum of
--           hourly MW ÷ 1,000. Positive net = Thailand exports to Malaysia.
-- Expected: 2023 exports 235.3 GWh, imports 65.5 GWh (a net exporter); 2024 exports 149.6 GWh,
--           imports 150.9 GWh (roughly balanced) (M3 plan, profiled 2026-10-03).

SELECT
    g.grid_code,
    f.counterparty,
    f.year,
    COUNT(*) AS days,
    SUM(f.hours_present) AS hours_present,
    CAST(SUM(f.export_mwh) / 1000.0 AS DECIMAL(10, 1)) AS export_gwh,
    CAST(SUM(f.import_mwh) / 1000.0 AS DECIMAL(10, 1)) AS import_gwh,
    CAST((SUM(f.export_mwh) - SUM(f.import_mwh)) / 1000.0 AS DECIMAL(10, 1)) AS net_export_gwh,
    CAST(AVG(CAST(f.net_flow_mw AS FLOAT)) AS DECIMAL(10, 1)) AS mean_daily_net_mw
FROM mart.grid_flow_daily AS f
JOIN mart.dim_grid AS g ON g.grid_key = f.grid_key
WHERE f.counterparty = 'MY'
  AND f.year IN (2023, 2024)
GROUP BY g.grid_code, f.counterparty, f.year
ORDER BY f.year;
