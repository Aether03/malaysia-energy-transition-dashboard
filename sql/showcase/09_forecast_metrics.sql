-- 09_forecast_metrics: does the stored forecast score add up? (FR-13; twin of P4's metric cards)
--
-- Question: MAPE and MAE of the model and the seasonal-naive baseline, recomputed in SQL from
--           the hourly forecast facts, overall and per month, beside the values Python stored.
-- Method:   scored hours only (actual, model and baseline all present; protocol #5).
--           MAPE = mean(|actual − forecast| ÷ actual) × 100; MAE = mean |actual − forecast|.
--           Facts hold MW at 0.1 MW, so the recomputed values may differ from the stored ones
--           (computed at full precision) in the third decimal at most. The *_diff columns show it.
-- Expected: Thailand all-year model 3.309% vs baseline 6.227%; Singapore 1.638% vs 2.501%
--           (FINAL runs 7 and 8, docs/forecast.md); every |diff| <= 0.001. month IS NULL marks
--           the whole-run row.

WITH scored AS (
    SELECT
        f.grid_key,
        d.month,
        CAST(f.actual_mw AS FLOAT) AS actual,
        ABS(CAST(f.actual_mw AS FLOAT) - CAST(f.forecast_mw AS FLOAT)) AS err_model,
        ABS(CAST(f.actual_mw AS FLOAT) - CAST(f.baseline_mw AS FLOAT)) AS err_baseline
    FROM mart.load_forecast_current AS f
    JOIN mart.dim_date AS d ON d.date_key = f.date_key
    WHERE f.is_scored = 1
),
recomputed AS (
    SELECT
        grid_key,
        month,
        COUNT(*) AS scored_hours,
        100.0 * AVG(err_model / actual) AS mape_model,
        100.0 * AVG(err_baseline / actual) AS mape_baseline,
        AVG(err_model) AS mae_model,
        AVG(err_baseline) AS mae_baseline
    FROM scored
    GROUP BY GROUPING SETS ((grid_key, month), (grid_key))
)
SELECT
    g.grid_code,
    r.month,
    r.scored_hours,
    CAST(r.mape_model AS DECIMAL(8, 3)) AS mape_model,
    CAST(r.mape_baseline AS DECIMAL(8, 3)) AS mape_baseline,
    CAST(r.mae_model AS DECIMAL(10, 3)) AS mae_model,
    CAST(r.mae_baseline AS DECIMAL(10, 3)) AS mae_baseline,
    CAST(100.0 * (1 - r.mape_model / r.mape_baseline) AS DECIMAL(8, 3)) AS improvement_pct,
    CAST(r.mape_model - COALESCE(
        CASE WHEN r.month IS NULL THEN CAST(c.mape_model AS FLOAT) END,
        CAST(JSON_VALUE(fr.metrics_json, CONCAT('$.per_month."', YEAR(c.test_start), '-',
             RIGHT(CONCAT('0', r.month), 2), '".mape_model')) AS FLOAT)) AS DECIMAL(8, 4)) AS mape_model_diff,
    CAST(r.mape_baseline - COALESCE(
        CASE WHEN r.month IS NULL THEN CAST(c.mape_baseline AS FLOAT) END,
        CAST(JSON_VALUE(fr.metrics_json, CONCAT('$.per_month."', YEAR(c.test_start), '-',
             RIGHT(CONCAT('0', r.month), 2), '".mape_baseline')) AS FLOAT)) AS DECIMAL(8, 4)) AS mape_baseline_diff
FROM recomputed AS r
JOIN mart.forecast_run_current AS c ON c.grid_key = r.grid_key
JOIN dw.forecast_run AS fr ON fr.model_run_id = c.model_run_id
JOIN mart.dim_grid AS g ON g.grid_key = r.grid_key
ORDER BY g.display_order, CASE WHEN r.month IS NULL THEN 0 ELSE 1 END, r.month;
