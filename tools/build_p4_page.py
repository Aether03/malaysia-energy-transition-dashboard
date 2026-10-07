"""Build the P4 Grid load page as PBIR visual definitions (M3 step 12, doc 03 P4).

P4 is split in two pages (GUI round 1 decision): this one holds the load shapes and flows; the
day-ahead forecast lives on `p4b_forecast` (build_p4b_page.py, which reuses the helpers below).

Layout (1280x720 frame, doc 04 §4): header (title, subtitle, grid slicer); info banner; row 1 =
typical-day load curve with the season tiles (left) and the month x hour heatmap (right); row 2 = two
aligned single-axis charts on the same month axis (peak demand | load factor, doc 04 F1); row 3 = the
Thailand-Malaysia interconnector flows with its subtitle. Re-running rebuilds the page.

The page filter keeps 2023-24. The grid slicer saves its default selection so [Grid Selected] is true
on open, and is synced with the Forecast page's grid slicer (syncGroup); season_pick is a disconnected
slicer that reaches only the load-curve measure (no visualInteractions needed).

    .venv/Scripts/python tools/build_p4_page.py
"""

from __future__ import annotations

import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, solid, text, visual

PAGE = "p4_grid_load"
DEFAULT_GRID = "Thailand national grid (EGAT)"
GRID_SYNC_GROUP = "p4_grid"  # keeps the grid slicer in step across P4 and P4b
YEARS = (2023, 2024)
# Light sequential-blue step (doc 04 §3.4) for the older year, navy for the newer one.
YEAR_COLOURS = {2023: "#86b6ef", 2024: rb.NAVY}
BANNER_FILL = "#cde2fb"  # doc 04 §3.4 theme minimum: the light end of the info tint

# Vertical rhythm (everything sits between the header at y 88 and the footnote at y 672).
BANNER_Y, BANNER_H = 104, 26
ROW1_Y, ROW1_H = 132, 260  # full-width heatmap: title + header + 12 rows at 8 pt (GUI round 2)
ROW2_Y, ROW2_H = 398, 140  # below ~140 px Desktop hides the legends (GUI round 3)
ROW3_Y, ROW3_H = 544, 120  # the flows chart turns into a placeholder below 120 px

# Row 1 (GUI round 2): the heatmap takes the full width. One-decimal GW values at 8 pt need about
# 34 px per column (at 20-28 px they wrapped onto two lines), so 24 hours + the month header at 40 px.
HEAT_COL_W = 40
# Row 2: typical-day curve, season list, monthly peak and load factor (F1: same month axis). The
# monthly charts need ~300 px: Desktop's minimum category width is 20 px, so 12 months at 222 px
# scrolled (GUI round 3). Row 3: the interconnector flows, full width, its note in the title row.
SEASON_W, CURVE_W = 170, 196  # 170: Singapore's monsoon labels fit
PAIR_W = (rb.CONTENT_W - 3 * rb.GAP - SEASON_W - CURVE_W) / 2  # 333
SEASON_X = rb.CONTENT_X + CURVE_W + rb.GAP
PEAK_X = SEASON_X + SEASON_W + rb.GAP
LF_X = PEAK_X + PAIR_W + rb.GAP

FOOTNOTE = (
    "Thailand: sum of 5 regional demands, hourly means (published peaks are 2–4% higher). Singapore: EMA "
    "system demand, hourly mean of half-hours. Seasons are month-based. Gaps shown, never filled. Flows: "
    "Thailand's malaysia_EXP/IMP, daily means. Data: EGAT via Zenodo (CC BY 4.0); EMA (SODL v1.0)."
)


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


# ---------- shared visuals (also used by the Forecast page) ----------
def note(measure: str, size: int = 9, colour: str = rb.TEXT_SECONDARY, align: str = "left") -> dict:
    """Measure-bound text shape (blank when the measure is blank)."""
    return rb.shape(None, {"expr": measure_ref(measure)}, size, colour, v_align="top", align=align)


def grid_slicer() -> dict:
    """Header grid slicer: single select, saved default, synced across P4 and P4b."""
    return rb.slicer(
        "dim_grid", "name", "Grid", mode="Dropdown", single=True, default=[DEFAULT_GRID], sync_group=GRID_SYNC_GROUP
    )


def header_visuals(slicer_name: str) -> list[dict]:
    """The grid slicer in the header, right of the title (x 1048, as on every page)."""
    return [
        visual(
            slicer_name, 1048, rb.HEADER_Y, 208, 64, 40, grid_slicer(),
            alt="Dropdown slicer: choose the grid, Thailand or Singapore; it is kept in step between the Grid load and Forecast pages",
        )
    ]


def banner(name: str) -> dict:
    return visual(
        name, rb.CONTENT_X, BANNER_Y, rb.CONTENT_W, BANNER_H, 41,
        rb.shape(BANNER_FILL, {"expr": measure_ref("Grid Banner")}, 11, rb.NAVY, left_margin=12),
        alt="Banner: which grid is shown and how it relates to Peninsular Malaysia",
    )


def line_style(width: str, style: str = "solid", metadata: str | None = None) -> dict:
    entry: dict = {"properties": {"strokeWidth": lit(width), "lineStyle": text(style)}}
    if metadata:
        entry["selector"] = {"metadata": f"_Measures.{metadata}"}
    return entry


# ---------- P4 visual bodies ----------
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
        "visualContainerObjects": rb.container("Typical day (MW)"),
        "drillFilterOtherVisuals": True,
    }


def heatmap() -> dict:
    """Month x hour matrix of average load (GW) with the theme-driven sequential-blue background rule.

    Shape = tools/templates/matrix_heatmap_fixed_width.json (saved by Desktop in GUI round 1):
    fixed-width columns (HEAT_COL_W), 8 pt headers and values (Desktop's header minimum), row padding 0,
    no subtotals.
    """
    value = measure_ref("Avg Load (GW)")
    rule = {
        "FillRule": {
            "Input": value,
            "FillRule": {
                "linearGradient2": {
                    "min": {"color": {"Literal": {"Value": "'minColor'"}}},
                    # Not the theme's maxColor (#0d366b): dark values on it were ~2:1. #5a91d6 keeps the 8 pt
                    # #0b0b0b values at 6:1 in every cell (WCAG 1.4.3; M5 step 5 accessibility review).
                    "max": {"color": {"Literal": {"Value": "'#5a91d6'"}}},
                    "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}},
                }
            },
        }
    }
    return {
        "visualType": "pivotTable",
        "query": {
            "queryState": {
                "Columns": {"projections": [{**projection(column_ref("dim_hour", "hour"), True), "displayName": "Hour"}]},
                "Rows": {"projections": [{**projection(column_ref("dim_date", "month_name"), True), "displayName": " "}]},
                "Values": {"projections": [projection(value)]},
            }
        },
        "objects": {
            "values": [
                {
                    "properties": {"backColor": {"solid": {"color": {"expr": rule}}}},
                    "selector": {
                        "data": [{"dataViewWildcard": {"matchingOption": 1}}],
                        "metadata": "_Measures.Avg Load (GW)",
                    },
                },
                {"properties": {"fontSize": lit("8D"), "fontColor": solid(rb.TEXT_PRIMARY)}},
            ],
            "columnHeaders": [
                {
                    "properties": {
                        "fontSize": lit("8D"),
                        "columnAdjustment": text("fixedWidth"),
                        "defaultColumnWidth": lit(f"{HEAT_COL_W}D"),
                    }
                }
            ],
            "rowHeaders": [{"properties": {"fontSize": lit("8D")}}],
            "grid": [{"properties": {"rowPadding": lit("0D")}}],
            "subTotals": [{"properties": {"rowSubtotals": lit("false"), "columnSubtotals": lit("false")}}],
        },
        "visualContainerObjects": rb.container("Average load by month and hour (GW)"),
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
        "visualContainerObjects": rb.container("Thailand ↔ Malaysia daily net flow (MW)"),
        "drillFilterOtherVisuals": True,
    }


def build() -> list[dict]:
    visuals = rb.frame(PAGE, "P4 Load Title", "P4 Subtitle", FOOTNOTE)
    visuals += header_visuals("p4_grid_slicer")
    visuals.append(banner("p4_banner"))

    # --- row 1: month x hour heatmap, full width; the year's peak at the right of its title row
    visuals.append(
        visual("p4_heatmap", rb.CONTENT_X, ROW1_Y, rb.CONTENT_W, ROW1_H, 50, heatmap(),
               alt="Heatmap table: average load in GW by month (rows) and hour of day (columns); darker blue means higher load")
    )
    visuals.append(
        visual(
            "p4_peak_text", rb.CONTENT_X + rb.CONTENT_W - 300, ROW1_Y + 6, 292, 18, 51,
            note("Peak Text", align="right"),
            alt="Text: when the highest demand of the year occurred",
        )
    )

    # --- row 2: typical day + season | monthly peak | load factor (doc 04 F1: no dual axis)
    visuals.append(
        visual("p4_load_curve", rb.CONTENT_X, ROW2_Y, CURVE_W, ROW2_H, 52, load_curve(),
               alt="Line chart: average load by hour of day for a typical weekday and a typical weekend or holiday")
    )
    visuals.append(
        visual(
            "p4_season_slicer", SEASON_X, ROW2_Y, SEASON_W, ROW2_H, 53,
            rb.slicer("season_pick", "season", "Season", mode="Basic"),
            alt="List slicer: narrow the typical-day chart to one season; the other charts stay whole-year",
        )
    )
    visuals.append(
        visual(
            "p4_peak_cols", PEAK_X, ROW2_Y, PAIR_W, ROW2_H, 54,
            month_chart("clusteredColumnChart", "Peak Load (MW)", "Monthly peak (MW)"),
            alt="Column chart: highest demand in each month in MW, one colour per year",
        )
    )
    visuals.append(
        visual(
            "p4_lf_line", LF_X, ROW2_Y, PAIR_W, ROW2_H, 55,
            month_chart("lineChart", "Load Factor (%)", "Load factor (%)"),
            alt="Line chart: monthly load factor in percent, one line per year, on the same month axis as the peak chart",
        )
    )

    # --- row 3: interconnector flows, full width; the export/import note at the right of its title row
    visuals.append(
        visual("p4_flow_line", rb.CONTENT_X, ROW3_Y, rb.CONTENT_W, ROW3_H, 56, flow_chart(),
               alt="Line chart: daily average net electricity flow between Thailand and Malaysia in MW; above zero means Thailand exports")
    )
    visuals.append(
        visual(
            "p4_flow_note", rb.CONTENT_X + 320, ROW3_Y + 6, rb.CONTENT_W - 328, 22, 57,
            note("Flow Subtitle", align="right"),
            alt="Text: annual export and import totals for the flow chart",
        )
    )
    return visuals


def main() -> None:
    visuals = build()
    rb.write_page(PAGE, "Grid load", visuals, {"filterConfig": year_page_filter()})
    print(f"Wrote {len(visuals)} visuals to the Grid load page")


if __name__ == "__main__":
    main()
