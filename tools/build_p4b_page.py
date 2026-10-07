"""Build the P4b Forecast page as PBIR visual definitions (M3 step 12, doc 03 P4, split in GUI round 1).

Layout (1280x720 frame, doc 04 §4): header (title, subtitle, grid slicer synced with P4); info banner;
left column = backtest-day dropdown with the verdict, secondary result and backtest window texts; main
area = the 24 h actual / model / baseline chart (empty and error messages overlaid) over a row of five
metric cards. The forecast measures ignore dim_date, so there is no page year filter. forecast_date is
a disconnected slicer: with nothing picked the measures show the grid's 2024 peak day.

    .venv/Scripts/python tools/build_p4b_page.py
"""

from __future__ import annotations

import build_p4_page as p4
import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, solid, text, visual

PAGE = "p4b_forecast"

LEFT_W = 200
MAIN_X = rb.CONTENT_X + LEFT_W + rb.GAP  # 416
MAIN_W = rb.CONTENT_X + rb.CONTENT_W - MAIN_X  # 840
BODY_Y = 136
DATE_H = 64
CARD_H, CARD_GAP = 80, 8
CARDS_END = 664
CARDS_Y = CARDS_END - CARD_H  # 584
CHART_H = CARDS_Y - 8 - BODY_Y  # 440

FOOTNOTE = (
    "Forecast: LightGBM issued at local midnight for the next 24 h, monthly rolling-origin backtest over 2024, "
    "run once under a locked protocol (docs/forecast.md). Baseline = the same hour last week; improvement = "
    "1 − MAPE model ÷ MAPE baseline, 95% CI from a 7-day block bootstrap. Pick a day; none picked = the "
    "grid's 2024 peak day."
)

# doc 03 P4: hovering a metric card shows the MAPE/MAE definition and the backtest window.
CARD_TOOLTIPS = [
    "Backtest Window",
    "Backtest Improvement CI",
    "Backtest MAE Model (MW)",
    "Backtest MAE Baseline (MW)",
]


def date_dropdown() -> dict:
    """Backtest-day dropdown on the disconnected forecast_date table.

    Shape = tools/templates/slicer_date_dropdown.json (saved by Desktop in GUI round 1): Dropdown mode,
    single date, not strictly single (so no selection is forced), slider off, no saved filter.
    """
    field = column_ref("forecast_date", "date")
    return {
        "visualType": "slicer",
        "query": {
            "queryState": {"Values": {"projections": [projection(field, True)]}},
            "sortDefinition": {"sort": [{"field": field, "direction": "Ascending"}], "isDefaultSort": True},
        },
        "objects": {
            "data": [{"properties": {"mode": text("Dropdown")}}],
            "header": [{"properties": {"show": lit("true"), "text": text("Backtest day")}}],
            "selection": [{"properties": {"singleDate": lit("true"), "strictSingleSelect": lit("false")}}],
            "slider": [{"properties": {"show": lit("false")}}],
        },
        "drillFilterOtherVisuals": True,
    }


def forecast_chart() -> dict:
    """One 24 h day: actual (text.primary), model (navy), baseline (dashed text.secondary), doc 04 §5."""
    series = [  # (measure, colour, width, line style)
        ("Day Actual (MW)", rb.TEXT_PRIMARY, "2D", "solid"),
        ("Day Model (MW)", rb.NAVY, "2D", "solid"),
        ("Day Baseline (MW)", rb.TEXT_SECONDARY, "1.5D", "dashed"),
    ]
    return {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_hour", "hour"), True)]},
                "Y": {"projections": [projection(measure_ref(m)) for m, *_ in series]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Top")}}],
            "dataPoint": rb.measure_colours({m: c for m, c, *_ in series}),
            "lineStyles": [p4.line_style(width, style, m) for m, _, width, style in series],
        },
        "visualContainerObjects": rb.container(None, "Forecast Day Title"),
        "drillFilterOtherVisuals": True,
    }


def metric_card(measure: str, label: str) -> dict:
    """Classic card (template: card_sized_label.json): 12 pt value, 8 pt label; needs ~80 px height."""
    body = rb.card(measure, 12, solid(rb.TEXT_PRIMARY), True)
    body["objects"]["categoryLabels"][0]["properties"]["fontSize"] = lit("8D")
    body["query"]["queryState"]["Values"]["projections"][0]["displayName"] = label
    return rb.tooltip_fields(body, CARD_TOOLTIPS)


def build() -> list[dict]:
    visuals = rb.frame(PAGE, "P4 Title", "P4 Forecast Subtitle", FOOTNOTE)
    visuals += p4.header_visuals("p4b_grid_slicer")
    visuals.append(p4.banner("p4b_banner"))

    # --- left column: day picker, then the three result texts
    visuals.append(
        visual(
            "p4b_date_slicer",
            rb.CONTENT_X,
            BODY_Y,
            LEFT_W,
            DATE_H,
            50,
            date_dropdown(),
            alt="Dropdown date slicer: choose a 2024 backtest day; nothing picked shows the grid's peak day",
        )
    )
    y = BODY_Y + DATE_H + 8
    for name, measure, size, colour, h, z, alt in (
        (
            "p4b_verdict",
            "Forecast Verdict",
            10,
            rb.TEXT_PRIMARY,
            112,
            51,
            "Text: verdict on whether the model beats the seasonal-naive baseline, with its confidence interval",
        ),
        (
            "p4b_secondary",
            "Forecast Secondary",
            9,
            rb.TEXT_SECONDARY,
            96,
            52,
            "Text: how the model compares with the weekday-aware naive reference",
        ),
        (
            "p4b_window",
            "Backtest Window",
            9,
            rb.TEXT_SECONDARY,
            72,
            53,
            "Text: the dates and hours the backtest covers",
        ),
    ):
        visuals.append(visual(name, rb.CONTENT_X, y, LEFT_W, h, z, p4.note(measure, size, colour), alt=alt))
        y += h + 8

    # --- main: forecast chart with the empty / error messages over the plot area (blank normally)
    visuals.append(
        visual(
            "p4b_fc_line",
            MAIN_X,
            BODY_Y,
            MAIN_W,
            CHART_H,
            60,
            forecast_chart(),
            alt="Line chart: 24 hours of actual demand, the model forecast and the baseline forecast for the chosen day, in MW",
        )
    )
    mid = BODY_Y + CHART_H / 2
    visuals.append(
        visual(
            "p4b_fc_empty",
            MAIN_X + 12,
            mid - 26,
            MAIN_W - 24,
            26,
            61,
            rb.shape(None, {"expr": measure_ref("Forecast Empty State")}, 12, rb.TEXT_SECONDARY, align="center"),
            alt="Message over the chart: shown when the chosen day is outside the backtest window",
        )
    )
    visuals.append(
        visual(
            "p4b_fc_error",
            MAIN_X + 12,
            mid,
            MAIN_W - 24,
            26,
            62,
            rb.shape(None, {"expr": measure_ref("Forecast Error State")}, 12, rb.STATUS_FAIL, align="center"),
            alt="Message over the chart: shown when the forecast was not generated in the latest run",
        )
    )

    # --- main: five metric cards in one row under the chart
    cards = [
        ("p4b_card_model", "Backtest MAPE Model (%)", "Model MAPE (%)"),
        ("p4b_card_baseline", "Backtest MAPE Baseline (%)", "Baseline MAPE (%)"),
        ("p4b_card_improvement", "Backtest Improvement (%)", "Improvement (%)"),
        ("p4b_card_mae_model", "Backtest MAE Model (MW)", "Model MAE (MW)"),
        ("p4b_card_mae_baseline", "Backtest MAE Baseline (MW)", "Baseline MAE (MW)"),
    ]
    card_w = (MAIN_W - (len(cards) - 1) * CARD_GAP) / len(cards)
    for i, (name, measure, label) in enumerate(cards):
        visuals.append(
            visual(
                name,
                MAIN_X + i * (card_w + CARD_GAP),
                CARDS_Y,
                card_w,
                CARD_H,
                70 + i,
                metric_card(measure, label),
                alt=f"Card: {label}, a backtest result for the chosen grid",
            )
        )
    return visuals


def main() -> None:
    visuals = build()
    rb.write_page(PAGE, "Forecast", visuals)
    print(f"Wrote {len(visuals)} visuals to the Forecast page")


if __name__ == "__main__":
    main()
