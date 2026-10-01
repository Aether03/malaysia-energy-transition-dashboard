"""Build the P2 Generation page as PBIR visual definitions (M2 step 9, doc 03 P2).

Layout (1280x720 frame, doc 04 §4): header (title, subtitle, synced year-range slicer); row 1 =
generation mix area (left) with the TWh | % toggle, source slicer and empty-state message in a
right-hand column; row 2 = NETR target line and capacity-factor bar, each with a note; row 3 =
two aligned single-axis demand charts (doc 04 F1: never a dual axis). Re-running rebuilds the page.

    .venv/Scripts/python tools/build_p2_page.py
"""

from __future__ import annotations

import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, solid, text, visual

PAGE = "p2_generation"
SIDE_X, SIDE_W = 1000, 256  # right-hand control column
AREA_W = SIDE_X - rb.GAP - rb.CONTENT_X  # 784
HALF_W = (rb.CONTENT_W - rb.GAP) / 2  # 520
RIGHT_X = rb.CONTENT_X + HALF_W + rb.GAP
ROW1_Y, ROW1_H = 104, 208
ROW2_Y, ROW2_H, NOTE_H = 328, 148, 36
ROW3_Y, ROW3_H = 528, 128

FOOTNOTE = (
    "Sources: Ember Yearly Electricity Data (CC BY 4.0). Capacity factor = generation ÷ (capacity × hours in the "
    "year; 8,784 h in leap years), shown at the last year of the selected range; blank, never 0, when capacity is not "
    "reported. Targets: 31% by 2025 and 40% by 2035 (12MP / SEDA MyRER, 2021); 35% by 2030 and 70% by 2050 (NETR). "
    "Ember counts grid capacity only; the official share also counts off-grid and rooftop capacity. The target chart "
    "always spans 2000-2050 and ignores the year range."
)


def note(measure: str) -> dict:
    """Small measure-bound text under a chart; empty when the measure is blank."""
    return rb.shape(None, {"expr": measure_ref(measure)}, 9, rb.TEXT_SECONDARY, v_align="top")


def build() -> list[dict]:
    visuals = rb.frame(PAGE, "Generation Title", "Generation Subtitle", FOOTNOTE)
    colours = rb.source_colours()

    # --- controls (header slicer, then the right-hand column)
    visuals.append(visual("p2_year_slicer", 1056, rb.HEADER_Y, 200, 64, 40, rb.year_range_slicer()))
    visuals.append(
        visual(
            "p2_unit_slicer", SIDE_X, ROW1_Y, SIDE_W, 64, 41,
            rb.slicer("Mix Unit", "Mix Unit", "Unit", mode="Basic", single=True, horizontal=True),
            filter_config=rb.in_filter("Mix Unit", "Mix Unit", ["TWh"], "p2_unit_slicer"),
        )
    )
    visuals.append(
        visual(
            "p2_source_slicer", SIDE_X, ROW1_Y + 72, SIDE_W, 64, 42,
            rb.slicer("dim_source", "display_name", "Source", mode="Dropdown"),
        )
    )
    visuals.append(
        visual(
            "p2_empty_state", SIDE_X, ROW1_Y + 144, SIDE_W, 64, 43,
            rb.shape(None, {"expr": measure_ref("No Source Generation Message")}, 11, rb.TEXT_SECONDARY, v_align="top"),
        )
    )

    # --- row 1: generation mix, TWh or % per the field parameter
    area = {
        "visualType": "stackedAreaChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_year", "year"), True)]},
                "Series": {"projections": [projection(column_ref("dim_source", "display_name"))]},
                "Y": {"projections": [rb.param_projection("Mix Unit")]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Top")}}],
            "dataPoint": rb.series_colours("dim_source", "display_name", colours),
        },
        "visualContainerObjects": rb.container("Generation by source (TWh or % of the year's total, per the Unit toggle)"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(visual("p2_mix_area", rb.CONTENT_X, ROW1_Y, AREA_W, ROW1_H, 50, area))

    # --- row 2 left: RE share of installed capacity against the national targets
    series = [  # (measure, legend label, colour, line width, markers, line style)
        ("Axis RE Capacity Share (%)", "Ember grid basis", rb.NAVY, "2.5D", False, "solid"),
        ("Axis Official (%)", "Official (incl. off-grid, rooftop)", rb.ACCENT_BLUE, "2D", True, "solid"),
        ("Axis Target (%)", "Target", rb.PEER_MUTED, "1.5D", True, "dashed"),
    ]
    target = {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("Target Axis", "year"), True)]},
                "Y": {"projections": [{**projection(measure_ref(m)), "displayName": label} for m, label, *_ in series]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Top")}}],
            "valueAxis": [{"properties": {"start": lit("0D"), "end": lit("100D")}}],
            # Sparse series (one official point, four targets) need a numeric year axis to join their points.
            "categoryAxis": [{"properties": {"axisType": text("Scalar")}}],
            "dataPoint": rb.measure_colours({m: c for m, _, c, *_ in series}),
            "lineStyles": [
                {
                    "properties": {
                        "strokeWidth": lit(width),
                        "showMarker": lit("true" if markers else "false"),
                        "lineStyle": text(style),
                    },
                    "selector": {"metadata": f"_Measures.{m}"},
                }
                for m, _, _, width, markers, style in series
            ],
        },
        "visualContainerObjects": rb.container("National RE capacity targets: share of installed capacity (%)"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(visual("p2_target_line", rb.CONTENT_X, ROW2_Y, HALF_W, ROW2_H, 51, target))
    visuals.append(visual("p2_target_note", rb.CONTENT_X, ROW2_Y + ROW2_H, HALF_W, NOTE_H, 52, note("Target Source Note")))

    # --- row 2 right: capacity factor per source at the last year of the range
    cf = {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_source", "display_name"), True)]},
                "Y": {"projections": [projection(measure_ref("Ctx Capacity Factor (%)"))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("false")}}],
            "labels": [{"properties": {"show": lit("true"), "fontSize": lit("10D")}}],
            "valueAxis": [{"properties": {"start": lit("0D"), "end": lit("100D")}}],
            "dataPoint": rb.series_colours("dim_source", "display_name", colours),
        },
        "visualContainerObjects": rb.container(None, "Capacity Factor Title"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(visual("p2_cf_bar", RIGHT_X, ROW2_Y, HALF_W, ROW2_H, 53, cf))
    visuals.append(visual("p2_cf_note", RIGHT_X, ROW2_Y + ROW2_H, HALF_W, NOTE_H, 54, note("Capacity Factor Note")))

    # --- row 3: demand as two aligned single-axis charts on the same year axis (doc 04 F1)
    def columns(measure: str, colour: str, title: str) -> dict:
        return {
            "visualType": "clusteredColumnChart",
            "query": {
                "queryState": {
                    "Category": {"projections": [projection(column_ref("dim_year", "year"), True)]},
                    "Y": {"projections": [projection(measure_ref(measure))]},
                }
            },
            "objects": {
                "legend": [{"properties": {"show": lit("false")}}],
                "dataPoint": [{"properties": {"fill": solid(colour)}}],
            },
            "visualContainerObjects": rb.container(title),
            "drillFilterOtherVisuals": True,
        }

    visuals.append(
        visual("p2_demand_cols", rb.CONTENT_X, ROW3_Y, HALF_W, ROW3_H, 55,
               columns("Ctx Demand (TWh)", rb.NAVY, "Electricity demand (TWh)"))
    )
    visuals.append(
        visual("p2_growth_cols", RIGHT_X, ROW3_Y, HALF_W, ROW3_H, 56,
               columns("Ctx Demand Growth (%)", rb.ACCENT_BLUE, "Demand growth, year on year (%)"))
    )
    return visuals


def main() -> None:
    visuals = build()
    # The NETR chart always spans to 2050 (M2 plan, step 7 review): the year range must not filter it.
    rb.write_page(
        PAGE,
        "Generation",
        visuals,
        {"visualInteractions": [{"source": "p2_year_slicer", "target": "p2_target_line", "type": "NoFilter"}]},
    )
    print(f"Wrote {len(visuals)} visuals to the Generation page")


if __name__ == "__main__":
    main()
