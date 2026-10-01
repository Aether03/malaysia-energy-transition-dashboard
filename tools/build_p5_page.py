"""Build the P5 ASEAN page as PBIR visual definitions (M2 step 10, doc 03 P5).

Layout (1280x720 frame, doc 04 §4): header (rank-label title, subtitle, synced year-range slicer);
left column = country slicer and the metric toggle; main area = trend and carbon-intensity ranking
(row 1), scatter and per-capita demand (row 2); the rank card runs along the bottom.

Every country visual carries the visual-level filter [Is Compared] = 1 (the compared set comes from
the disconnected 'Compare Country' slicer; no selection = the 6 default peers), Malaysia navy against
muted peers (doc 04 §3.3), and the T2 country tooltip. Re-running rebuilds the page.

    .venv/Scripts/python tools/build_p5_page.py
"""

from __future__ import annotations

import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, visual

PAGE = "p5_asean"
TOOLTIP_PAGE = "t2_country"
FOCUS = "Malaysia"
SIDE_X, SIDE_W = rb.CONTENT_X, 232
MAIN_X = SIDE_X + SIDE_W + rb.GAP  # 448
MAIN_W = rb.CONTENT_X + rb.CONTENT_W - MAIN_X  # 808
COL_W = (MAIN_W - rb.GAP) / 2  # 396
COL2_X = MAIN_X + COL_W + rb.GAP
ROW1_Y, ROW1_H = 104, 236
ROW2_Y, ROW2_H = 356, 224
RANK_Y, RANK_H = 596, 60

INTENSITY = "Intensity at Comparison Year (gCO2e/kWh)"


def country_visual(name: str, x: float, y: float, w: float, h: float, z: int, body: dict) -> dict:
    """A visual that shows countries: compared set only, T2 tooltip on hover."""
    rb.tooltip_page(body, TOOLTIP_PAGE)
    return visual(name, x, y, w, h, z, body, filter_config=rb.measure_filter(name, "Is Compared", 1))


def sorted_by(measure: str, direction: str) -> dict:
    return {"sort": [{"field": measure_ref(measure), "direction": direction}]}


def bar(measure: str, title: str, direction: str) -> dict:
    return {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_country", "name"), True)]},
                "Y": {"projections": [projection(measure_ref(measure))]},
            },
            "sortDefinition": sorted_by(measure, direction),
        },
        "objects": {
            "legend": [{"properties": {"show": lit("false")}}],
            "labels": [{"properties": {"show": lit("true"), "fontSize": lit("10D")}}],
            "dataPoint": rb.highlight_colours("dim_country", "name", FOCUS),
        },
        "visualContainerObjects": rb.container(title),
        "drillFilterOtherVisuals": True,
    }


def build() -> list[dict]:
    visuals = rb.frame(PAGE, "ASEAN Title", "ASEAN Subtitle", None, footnote_measure="ASEAN Footnote")

    # --- controls
    visuals.append(visual("p5_year_slicer", 1056, rb.HEADER_Y, 200, 64, 40, rb.year_range_slicer()))
    visuals.append(
        visual(
            "p5_country_slicer", SIDE_X, ROW1_Y, SIDE_W, 340, 41,
            rb.slicer("Compare Country", "name", "Countries (none ticked = 6 default peers)", mode="Basic"),
        )
    )
    visuals.append(
        visual(
            "p5_metric_slicer", SIDE_X, ROW1_Y + 356, SIDE_W, 120, 42,
            rb.slicer("ASEAN Metric", "ASEAN Metric", "Trend metric", mode="Basic", single=True, default=["RE share (%)"]),
        )
    )

    # --- row 1: trend (Malaysia 2.5 px navy, peers 1.5 px muted) and the intensity ranking
    trend = {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_year", "year"), True)]},
                "Series": {"projections": [projection(column_ref("dim_country", "name"))]},
                "Y": {"projections": [rb.param_projection("ASEAN Metric")]},
            }
        },
        "objects": {
            # Peers share one muted grey, so identity comes from the T2 hover tooltip, not a legend.
            "legend": [{"properties": {"show": lit("false")}}],
            "dataPoint": rb.highlight_colours("dim_country", "name", FOCUS),
            "lineStyles": [
                {"properties": {"strokeWidth": lit("1.5D")}},
                {
                    "properties": {"strokeWidth": lit("2.5D")},
                    "selector": rb.series_selector("dim_country", "name", FOCUS),
                },
            ],
        },
        "visualContainerObjects": rb.container("Trend by country (Malaysia in navy; pick the metric on the left)"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(country_visual("p5_trend_line", MAIN_X, ROW1_Y, COL_W, ROW1_H, 50, trend))
    visuals.append(
        country_visual(
            "p5_intensity_bar", COL2_X, ROW1_Y, COL_W, ROW1_H, 51,
            bar(INTENSITY, "Carbon intensity at the comparison year (gCO2e/kWh), lowest first", "Ascending"),
        )
    )

    # --- row 2: RE share vs intensity (bubble = demand) and demand per capita
    scatter = {
        "visualType": "scatterChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_country", "name"), True)]},
                "X": {"projections": [projection(measure_ref("RE Share at Comparison Year (%)"), True)]},
                "Y": {"projections": [projection(measure_ref(INTENSITY))]},
                "Size": {"projections": [projection(measure_ref("Demand at Comparison Year (TWh)"))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("false")}}],
            "categoryLabels": [{"properties": {"show": lit("true"), "fontSize": lit("9D")}}],
            "dataPoint": rb.highlight_colours("dim_country", "name", FOCUS),
        },
        "visualContainerObjects": rb.container("RE share vs carbon intensity (bubble = demand, TWh)"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(country_visual("p5_scatter", MAIN_X, ROW2_Y, COL_W, ROW2_H, 52, scatter))
    visuals.append(
        country_visual(
            "p5_percapita_bar", COL2_X, ROW2_Y, COL_W, ROW2_H, 53,
            bar("Demand per Capita at Common Year (MWh)", "Demand per capita at the common year (MWh)", "Descending"),
        )
    )

    # --- rank card (the doc 03 P5 rank card; the same measure is also the page title)
    visuals.append(
        visual(
            "p5_rank_card", rb.CONTENT_X, RANK_Y, rb.CONTENT_W, RANK_H, 60,
            rb.shape(None, {"expr": measure_ref("Rank Label")}, 16, rb.TEXT_PRIMARY, "Segoe UI Semibold",
                     boxed=True, left_margin=12),
        )
    )
    return visuals


def main() -> None:
    visuals = build()
    rb.write_page(PAGE, "ASEAN", visuals)
    print(f"Wrote {len(visuals)} visuals to the ASEAN page")


if __name__ == "__main__":
    main()
