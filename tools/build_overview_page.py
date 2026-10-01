"""Build the P1 Overview page as PBIR visual definitions (M1 step 9; M2 step 6 frame + polish).

Layout follows the doc 04 §4 frame (nav rail, header, body, footnote strip); content
follows doc 03 P1. Re-running rebuilds the page from scratch.

    .venv/Scripts/python tools/build_overview_page.py
"""

from __future__ import annotations

import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, solid, text, visual

KPI_W = (rb.CONTENT_W - 4 * rb.GAP) / 5  # 5 equal cards (doc 04 §4)


def build() -> list[dict]:
    visuals = rb.frame(
        rb.OVERVIEW_PAGE,
        "Overview Title",
        "Overview Subtitle",
        "Sources: Ember Yearly Electricity Data (CC BY 4.0); OWID population (CC BY 4.0). Targets: 31% by 2025 and "
        "40% by 2035 (12MP / SEDA MyRER, 2021), 35% by 2030 (NETR pathway), 70% by 2050 (NETR, 2023). Ember counts "
        "grid capacity only; the official share also counts off-grid and rooftop capacity. Large hydro is renewable "
        "in both. KPIs describe Malaysia in the selected year.",
    )

    slicer = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [projection(column_ref("dim_year", "year"), True)]}}},
        "objects": {
            "data": [{"properties": {"mode": text("Dropdown")}}],
            "selection": [{"properties": {"singleSelect": lit("true")}}],
            "header": [{"properties": {"text": text("Year"), "fontSize": lit("9D")}}],
        },
        "drillFilterOtherVisuals": True,
    }
    visuals.append(visual("p1_year_slicer", 1056, rb.HEADER_Y, 200, 64, 40, slicer))

    kpis = [  # (measure, delta label, delta colour measure or None = neutral)
        ("Total Generation (TWh)", "Total Generation Delta Label", None),
        ("RE Share (%)", "RE Share Delta Label", "RE Share Delta Color"),
        ("Fossil Share (%)", "Fossil Share Delta Label", "Fossil Share Delta Color"),
        ("Carbon Intensity (gCO2e/kWh)", "Carbon Intensity Delta Label", "Carbon Intensity Delta Color"),
        ("Demand per Capita (MWh)", "Demand per Capita Delta Label", None),
    ]
    for i, (measure, delta, colour_measure) in enumerate(kpis):
        kx = rb.CONTENT_X + i * (KPI_W + rb.GAP)
        visuals.append(visual(f"p1_kpi_{i}", kx, rb.BODY_Y, KPI_W, 100, 50 + i, rb.card(measure, 28, solid(rb.TEXT_PRIMARY), True)))
        delta_colour = (
            {"solid": {"color": {"expr": measure_ref(colour_measure)}}} if colour_measure else solid(rb.TEXT_SECONDARY)
        )
        visuals.append(visual(f"p1_kpi_delta_{i}", kx, rb.BODY_Y + 100, KPI_W, 44, 60 + i, rb.card(delta, 10, delta_colour, False)))

    area = {
        "visualType": "stackedAreaChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_year", "year"), True)]},
                "Series": {"projections": [projection(column_ref("dim_source", "display_name"))]},
                "Y": {"projections": [projection(measure_ref("Focus Generation (TWh)"))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Top")}}],
            # Colour bound to the source, not the series order (doc 04 §3.6; M1 carry-over).
            "dataPoint": rb.series_colours("dim_source", "display_name", rb.source_colours()),
        },
        "visualContainerObjects": rb.container("Malaysia's generation mix by source (TWh), all years"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(visual("p1_mix_area", rb.CONTENT_X, 264, 640, 392, 70, area))

    targets = [  # (measure, legend label, colour): both bases beside the target (M2 step 1 decision)
        ("RE Capacity Share (%)", "Ember grid basis", rb.NAVY),
        ("Official RE Capacity Share (%)", "Official (incl. off-grid, rooftop)", rb.ACCENT_BLUE),
        ("NETR Target (%)", "Target", rb.PEER_MUTED),
    ]
    bars = {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Y": {
                    "projections": [
                        {**projection(measure_ref(m)), "displayName": label} for m, label, _ in targets
                    ]
                }
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Top")}}],
            "labels": [{"properties": {"show": lit("true"), "fontSize": lit("10D")}}],
            "valueAxis": [{"properties": {"start": lit("0D"), "end": lit("100D")}}],
            # One unnamed category holding three series: hide its axis and widen the bars.
            "categoryAxis": [{"properties": {"show": lit("false"), "preferredCategoryWidth": lit("150D"), "innerPadding": lit("10L")}}],
            "dataPoint": rb.measure_colours({m: colour for m, _, colour in targets}),
        },
        "visualContainerObjects": rb.container("Renewable share of installed capacity (%)"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(visual("p1_netr_bars", 856, 264, 400, 272, 71, bars))
    visuals.append(
        visual("p1_netr_label", 856, 536, 400, 120, 72, rb.card("NETR Progress Label", 10, solid(rb.TEXT_SECONDARY), False))
    )
    return visuals


def main() -> None:
    visuals = build()
    # The mix chart shows every year; the year slicer must not filter it (doc 03 P1).
    rb.write_page(
        rb.OVERVIEW_PAGE,
        "Overview",
        visuals,
        {"visualInteractions": [{"source": "p1_year_slicer", "target": "p1_mix_area", "type": "NoFilter"}]},
    )
    print(f"Wrote {len(visuals)} visuals to the Overview page")


if __name__ == "__main__":
    main()
