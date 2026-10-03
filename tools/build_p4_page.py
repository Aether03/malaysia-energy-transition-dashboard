"""Build the P4 Grid load page as PBIR visual definitions (M3 step 12, doc 03 P4).

Layout (1280x720 frame, doc 04 §4): header (title, subtitle, grid slicer); info banner; row 1 =
typical-day load curve with the season tiles (left) and the month x hour heatmap (right); row 2 = two
aligned single-axis charts on the same month axis (peak demand | load factor, doc 04 F1); row 3 = the
forecast panel (backtest-day picker, actual / model / baseline lines, MAPE cards, verdict) on the left
and the Thailand-Malaysia interconnector flows on the right. Re-running rebuilds the page.

The page filter keeps 2023-24 (the forecast measures ignore dim_date by design). The grid slicer saves
its default selection so [Grid Selected] is true on open; season_pick and forecast_date are disconnected
slicers that reach only their own measures (no visualInteractions needed).

    .venv/Scripts/python tools/build_p4_page.py
"""

from __future__ import annotations

import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, solid, text, visual

PAGE = "p4_grid_load"
DEFAULT_GRID = "Thailand national grid (EGAT)"
YEARS = (2023, 2024)
# Light sequential-blue step (doc 04 §3.4) for the older year, navy for the newer one.
YEAR_COLOURS = {2023: "#86b6ef", 2024: rb.NAVY}
BANNER_FILL = "#cde2fb"  # doc 04 §3.4 theme minimum: the light end of the info tint

# Vertical rhythm (everything sits between the header at y 88 and the footnote at y 672).
BANNER_Y, BANNER_H = 104, 28
ROW1_Y, ROW1_H = 140, 170
ROW2_Y, ROW2_H = 320, 130  # charts under ~120 px render as a placeholder icon (M2 GUI round 4)
ROW3_Y = 460
ROW3_END = 664

# Row 1: the left block (curve + season tiles) is narrower than the heatmap, which needs 24 columns.
SEASON_W = 136
LEFT1_W = 456
CURVE_W = LEFT1_W - rb.GAP / 2 - SEASON_W  # 312
SEASON_X = rb.CONTENT_X + LEFT1_W - SEASON_W
HEAT_X = rb.CONTENT_X + LEFT1_W + rb.GAP  # 672
HEAT_W = rb.CONTENT_X + rb.CONTENT_W - HEAT_X  # 584

# Row 2: two halves on the same x grid as P2.
HALF_W = (rb.CONTENT_W - rb.GAP) / 2  # 520
RIGHT_X = rb.CONTENT_X + HALF_W + rb.GAP  # 736

# Row 3: forecast panel on the left (~60%), flows on the right.
FC_W = 624
FC_RIGHT = rb.CONTENT_X + FC_W  # 824
FLOW_X = FC_RIGHT + rb.GAP  # 840
FLOW_W = rb.CONTENT_X + rb.CONTENT_W - FLOW_X  # 416
CTRL_W = 168  # date picker and the three MAPE cards
CHART_X = rb.CONTENT_X + CTRL_W + rb.GAP  # 384
CHART_W = FC_RIGHT - CHART_X  # 440
CARD_H = 44
DATE_H = 56

FOOTNOTE = (
    "Thailand: sum of the 5 regional demands, hourly means (EGAT's published system peaks are 2–4% higher). "
    "Seasons are month-based approximations. Forecast: LightGBM issued at local midnight for the next 24 h, "
    "backtested once on 2024 under a locked protocol (docs/forecast.md); baseline = same hour last week. "
    "Gaps are shown, never filled. Data: EGAT via Zenodo (CC BY 4.0); EMA (Singapore Open Data Licence v1.0)."
)

# doc 03 P4: hovering a metric card shows the MAPE/MAE definition and the backtest window.
CARD_TOOLTIPS = [
    "Backtest Window",
    "Backtest Improvement CI",
    "Backtest MAE Model (MW)",
    "Backtest MAE Baseline (MW)",
]


# ---------- int-valued year helpers (rb.series_selector / rb.in_filter assume string columns) ----------
def year_literal(year: int) -> dict:
    return {"Literal": {"Value": f"{year}L"}}


def year_series_colours() -> list[dict]:
    """dataPoint fills per year series; dim_date[year] is an int64, so the selector literal is `2023L`."""
    return [
        {
            "properties": {"fill": solid(colour)},
            "selector": {
                "data": [
                    {
                        "scopeId": {
                            "Comparison": {
                                "ComparisonKind": 0,
                                "Left": column_ref("dim_date", "year"),
                                "Right": year_literal(year),
                            }
                        }
                    }
                ]
            },
        }
        for year, colour in YEAR_COLOURS.items()
    ]


def year_page_filter() -> dict:
    """Page-level Categorical filter dim_date[year] IN (2023, 2024), the shape Desktop writes."""
    return {
        "filters": [
            {
                "name": rb.filter_name("p4_grid_load:dim_date.year"),
                "field": column_ref("dim_date", "year"),
                "type": "Categorical",
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}],
                    "Where": [
                        {
                            "Condition": {
                                "In": {
                                    "Expressions": [
                                        {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "year"}}
                                    ],
                                    "Values": [[year_literal(y)] for y in YEARS],
                                }
                            }
                        }
                    ],
                },
            }
        ]
    }


# ---------- visual bodies ----------
def note(measure: str, size: int = 9, colour: str = rb.TEXT_SECONDARY, align: str = "left") -> dict:
    """Measure-bound text shape (blank when the measure is blank)."""
    return rb.shape(None, {"expr": measure_ref(measure)}, size, colour, v_align="top", align=align)


def line_style(width: str, style: str = "solid", metadata: str | None = None) -> dict:
    entry: dict = {"properties": {"strokeWidth": lit(width), "lineStyle": text(style)}}
    if metadata:
        entry["selector"] = {"metadata": f"_Measures.{metadata}"}
    return entry


def load_curve() -> dict:
    """Typical day: average load by local hour, weekday vs weekend & holiday; the season tiles narrow it."""
    return {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_hour", "hour"), True)]},
                "Series": {"projections": [projection(column_ref("grid_hourly", "day_type"))]},
                "Y": {"projections": [projection(measure_ref("Avg Load Curve (MW)"))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Top")}}],
            "dataPoint": rb.series_colours("grid_hourly", "day_type", {"Weekday": rb.NAVY, "Weekend & holiday": rb.ACCENT_BLUE}),
            "lineStyles": [{"properties": {"strokeWidth": lit("2D")}}],
        },
        "visualContainerObjects": rb.container("A typical day: weekday vs weekend & holiday (MW)"),
        "drillFilterOtherVisuals": True,
    }


def heatmap() -> dict:
    """Month x hour matrix of average load with the theme-driven sequential-blue background rule
    (template: matrix_heatmap.json; 'minColor'/'maxColor' resolve to the theme minimum/maximum)."""
    value = measure_ref("Avg Load (MW)")
    rule = {
        "FillRule": {
            "Input": value,
            "FillRule": {
                "linearGradient2": {
                    "min": {"color": {"Literal": {"Value": "'minColor'"}}},
                    "max": {"color": {"Literal": {"Value": "'maxColor'"}}},
                    "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}},
                }
            },
        }
    }
    return {
        "visualType": "pivotTable",
        "query": {
            "queryState": {
                "Columns": {"projections": [projection(column_ref("dim_hour", "hour"), True)]},
                "Rows": {"projections": [projection(column_ref("dim_date", "month_name"), True)]},
                "Values": {"projections": [projection(value)]},
            }
        },
        "objects": {
            "values": [
                {
                    "properties": {"backColor": {"solid": {"color": {"expr": rule}}}},
                    "selector": {
                        "data": [{"dataViewWildcard": {"matchingOption": 1}}],
                        "metadata": "_Measures.Avg Load (MW)",
                    },
                },
                # Not in the template (GUI round checks): small type so 24 hours x 12 months fit.
                {"properties": {"fontSize": lit("7D")}},
            ],
            "columnHeaders": [{"properties": {"fontSize": lit("8D")}}],
            "rowHeaders": [{"properties": {"fontSize": lit("8D")}}],
            "grid": [{"properties": {"rowPadding": lit("0D")}}],
            "subTotals": [{"properties": {"rowSubtotals": lit("false"), "columnSubtotals": lit("false")}}],
        },
        "visualContainerObjects": rb.container("Average load by month and hour (MW)"),
        "drillFilterOtherVisuals": True,
    }


def month_chart(visual_type: str, measure: str, title: str) -> dict:
    """Monthly chart on dim_date[month_name] (calendar order via sortByColumn) with one series per year."""
    return {
        "visualType": visual_type,
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_date", "month_name"), True)]},
                "Series": {"projections": [projection(column_ref("dim_date", "year"))]},
                "Y": {"projections": [projection(measure_ref(measure))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Top")}}],
            "dataPoint": year_series_colours(),
            **({"lineStyles": [{"properties": {"strokeWidth": lit("2D")}}]} if visual_type == "lineChart" else {}),
        },
        "visualContainerObjects": rb.container(title),
        "drillFilterOtherVisuals": True,
    }


def date_picker() -> dict:
    """Backtest-day picker (template: slicer_date_picker.json) on the disconnected forecast_date table."""
    field = column_ref("forecast_date", "date")
    return {
        "visualType": "slicer",
        "query": {
            "queryState": {"Values": {"projections": [projection(field, True)]}},
            "sortDefinition": {"sort": [{"field": field, "direction": "Ascending"}], "isDefaultSort": True},
        },
        "objects": {
            "data": [{"properties": {"mode": text("RelativeDatePicker")}}],
            # Not in the template: the same header block the other slicers use (rb.slicer).
            "header": [{"properties": {"show": lit("true"), "text": text("Backtest day"), "fontSize": lit("9D")}}],
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
            "lineStyles": [line_style(width, style, m) for m, _, width, style in series],
        },
        "visualContainerObjects": rb.container(None, "Forecast Day Title"),
        "drillFilterOtherVisuals": True,
    }


def metric_card(measure: str, label: str) -> dict:
    body = rb.card(measure, 16, solid(rb.TEXT_PRIMARY), True)
    body["query"]["queryState"]["Values"]["projections"][0]["displayName"] = label
    return rb.tooltip_fields(body, CARD_TOOLTIPS)


def flow_chart() -> dict:
    return {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_date", "date"), True)]},
                "Y": {"projections": [projection(measure_ref("Daily Net Flow (MW)"))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("false")}}],
            "dataPoint": rb.measure_colours({"Daily Net Flow (MW)": rb.NAVY}),
            "lineStyles": [line_style("1.5D", "solid", "Daily Net Flow (MW)")],
        },
        "visualContainerObjects": rb.container("Thailand ↔ Malaysia interconnector: daily net flow (MW)"),
        "drillFilterOtherVisuals": True,
    }


def build() -> list[dict]:
    visuals = rb.frame(PAGE, "P4 Title", "P4 Subtitle", FOOTNOTE)

    # --- header grid slicer (single select, saved default), then the info banner
    visuals.append(
        visual(
            "p4_grid_slicer", 1048, rb.HEADER_Y, 208, 64, 40,
            rb.slicer("dim_grid", "name", "Grid", mode="Dropdown", single=True, default=[DEFAULT_GRID]),
        )
    )
    visuals.append(
        visual(
            "p4_banner", rb.CONTENT_X, BANNER_Y, rb.CONTENT_W, BANNER_H, 41,
            rb.shape(BANNER_FILL, {"expr": measure_ref("Grid Banner")}, 11, rb.NAVY, left_margin=12),
        )
    )

    # --- row 1: typical-day curve + season tiles | month x hour heatmap
    visuals.append(visual("p4_load_curve", rb.CONTENT_X, ROW1_Y, CURVE_W, ROW1_H, 50, load_curve()))
    visuals.append(
        visual(
            "p4_season_slicer", SEASON_X, ROW1_Y, SEASON_W, ROW1_H, 51,
            rb.slicer("season_pick", "season", "Season (none = all year)", mode="Basic"),
        )
    )
    visuals.append(visual("p4_heatmap", HEAT_X, ROW1_Y, HEAT_W, ROW1_H, 52, heatmap()))

    # --- row 2: monthly peak and load factor on the same month axis (doc 04 F1: no dual axis)
    visuals.append(
        visual(
            "p4_peak_cols", rb.CONTENT_X, ROW2_Y, HALF_W, ROW2_H, 53,
            month_chart("clusteredColumnChart", "Peak Load (MW)", "Monthly peak demand (MW)"),
        )
    )
    visuals.append(
        visual(
            "p4_peak_text", rb.CONTENT_X + HALF_W - 292, ROW2_Y + 4, 284, 18, 54,
            note("Peak Text", align="right"),
        )
    )
    visuals.append(
        visual(
            "p4_lf_line", RIGHT_X, ROW2_Y, HALF_W, ROW2_H, 55,
            month_chart("lineChart", "Load Factor (%)", "Monthly load factor (%)"),
        )
    )

    # --- row 3 left: forecast panel (controls column | chart, verdict and secondary result)
    visuals.append(visual("p4_date_slicer", rb.CONTENT_X, ROW3_Y, CTRL_W, DATE_H, 56, date_picker()))
    cards = [
        ("p4_card_model", "Backtest MAPE Model (%)", "Model MAPE (%)"),
        ("p4_card_baseline", "Backtest MAPE Baseline (%)", "Baseline MAPE (%)"),
        ("p4_card_improvement", "Backtest Improvement (%)", "Improvement (%)"),
    ]
    for i, (name, measure, label) in enumerate(cards):
        y = ROW3_Y + DATE_H + 4 + i * (CARD_H + 4)
        visuals.append(visual(name, rb.CONTENT_X, y, CTRL_W, CARD_H, 57 + i, metric_card(measure, label)))

    chart_h = 140
    visuals.append(visual("p4_fc_line", CHART_X, ROW3_Y, CHART_W, chart_h, 60, forecast_chart()))
    # Empty / error messages sit over the plot area, transparent; both measures are blank normally.
    mid = ROW3_Y + chart_h / 2
    visuals.append(
        visual(
            "p4_fc_empty", CHART_X + 12, mid - 22, CHART_W - 24, 22, 61,
            rb.shape(None, {"expr": measure_ref("Forecast Empty State")}, 11, rb.TEXT_SECONDARY, align="center"),
        )
    )
    visuals.append(
        visual(
            "p4_fc_error", CHART_X + 12, mid, CHART_W - 24, 22, 62,
            rb.shape(None, {"expr": measure_ref("Forecast Error State")}, 11, rb.STATUS_FAIL, align="center"),
        )
    )
    verdict_y = ROW3_Y + chart_h + 4
    visuals.append(
        visual("p4_verdict", CHART_X, verdict_y, CHART_W, 30, 63, note("Forecast Verdict", 9, rb.TEXT_PRIMARY))
    )
    visuals.append(
        visual("p4_secondary", CHART_X, verdict_y + 30, CHART_W, ROW3_END - verdict_y - 30, 64, note("Forecast Secondary"))
    )

    # --- row 3 right: interconnector flows, subtitle under the chart
    flow_h = 152
    visuals.append(visual("p4_flow_line", FLOW_X, ROW3_Y, FLOW_W, flow_h, 65, flow_chart()))
    visuals.append(
        visual(
            "p4_flow_note", FLOW_X, ROW3_Y + flow_h + 4, FLOW_W, ROW3_END - ROW3_Y - flow_h - 4, 66,
            note("Flow Subtitle"),
        )
    )
    return visuals


def main() -> None:
    visuals = build()
    rb.write_page(PAGE, "Grid load", visuals, {"filterConfig": year_page_filter()})
    print(f"Wrote {len(visuals)} visuals to the Grid load page")


if __name__ == "__main__":
    main()
