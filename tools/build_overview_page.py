"""Build the P1 Overview page as PBIR visual definitions (M1 step 9; M2 step 6 frame + polish).

Layout follows the doc 04 §4 frame (nav rail, header, body, footnote strip); content
follows doc 03 P1: header, KPI row, mix trend + NETR panel (to y 520), then the rank card
and the findings box (y 536-656). Re-running rebuilds the page from scratch.

    .venv/Scripts/python tools/build_overview_page.py
"""

from __future__ import annotations

import csv

import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, solid, text, visual

P2_PAGE, P5_PAGE = "p2_generation", "p5_asean"
KPI_W = (rb.CONTENT_W - 4 * rb.GAP) / 5  # 5 equal cards (doc 04 §4)
MID_Y, MID_END = 264, 520  # mix chart and NETR panel
BOTTOM_Y, BOTTOM_H = 536, 120  # rank card and findings row
RANK_W = 400


def kpi_tooltips() -> dict[str, str]:
    """T1 text per KPI from the seeds, so the hover text matches ref.kpi and the source credits."""
    with (rb.ROOT / "seed" / "data_source.csv").open(encoding="utf-8-sig", newline="") as fh:
        sources = {row["data_source_code"]: row["credit_text"] for row in csv.DictReader(fh)}
    with (rb.ROOT / "seed" / "kpi.csv").open(encoding="utf-8-sig", newline="") as fh:
        return {
            row["kpi_code"]: (
                f"{row['name']} ({row['unit']}). {row['definition']} Formula: {row['formula']}. "
                f"Source: {sources[row['data_source_code']]}. Click for the Generation page."
            )
            for row in csv.DictReader(fh)
        }


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

    kpis = [  # (measure, delta label, delta colour measure or None = neutral, ref.kpi code)
        ("Total Generation (TWh)", "Total Generation Delta Label", None, "TOTAL_GENERATION"),
        ("RE Share (%)", "RE Share Delta Label", "RE Share Delta Color", "RE_SHARE_GEN"),
        ("Fossil Share (%)", "Fossil Share Delta Label", "Fossil Share Delta Color", "FOSSIL_SHARE_GEN"),
        ("Carbon Intensity (gCO2e/kWh)", "Carbon Intensity Delta Label", "Carbon Intensity Delta Color", "CARBON_INTENSITY"),
        ("Demand per Capita (MWh)", "Demand per Capita Delta Label", None, "DEMAND_PER_CAPITA"),
    ]
    definitions = kpi_tooltips()
    for i, (measure, delta, colour_measure, code) in enumerate(kpis):
        kx = rb.CONTENT_X + i * (KPI_W + rb.GAP)
        visuals.append(visual(f"p1_kpi_{i}", kx, rb.BODY_Y, KPI_W, 100, 50 + i, rb.card(measure, 28, solid(rb.TEXT_PRIMARY), True)))
        delta_colour = (
            {"solid": {"color": {"expr": measure_ref(colour_measure)}}} if colour_measure else solid(rb.TEXT_SECONDARY)
        )
        visuals.append(visual(f"p1_kpi_delta_{i}", kx, rb.BODY_Y + 100, KPI_W, 44, 60 + i, rb.card(delta, 10, delta_colour, False)))
        # Cards cannot be clicked reliably: a transparent button over the value card opens P2 (doc 03 P1).
        # Its hover text carries the doc 03 T1 content (report-page tooltips don't render here; M2 GUI round 6).
        visuals.append(visual(f"p1_kpi_go_{i}", kx, rb.BODY_Y, KPI_W, 100, 80 + i, rb.nav_overlay(P2_PAGE, definitions[code])))

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
    visuals.append(visual("p1_mix_area", rb.CONTENT_X, MID_Y, 640, MID_END - MID_Y, 70, area))

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
    visuals.append(visual("p1_netr_bars", 856, MID_Y, 400, 200, 71, bars))
    # A text shape wraps the long label; a classic card truncated it (M2 GUI round 3).
    visuals.append(
        visual(
            "p1_netr_label", 856, MID_Y + 208, 400, MID_END - (MID_Y + 208), 72,
            rb.shape(None, {"expr": measure_ref("NETR Progress Label")}, 9, rb.TEXT_SECONDARY, boxed=True, left_margin=12),
        )
    )

    # Bottom row: "Malaysia vs ASEAN" rank card (click -> P5) and the findings placeholder (M2 step 12).
    visuals.append(
        visual(
            "p1_rank_card", rb.CONTENT_X, BOTTOM_Y, RANK_W, BOTTOM_H, 90,
            rb.shape(None, {"expr": measure_ref("Rank Label")}, 14, rb.TEXT_PRIMARY, "Segoe UI Semibold",
                     boxed=True, left_margin=12),
        )
    )
    visuals.append(
        visual(
            "p1_rank_arrow", rb.CONTENT_X + RANK_W - 44, BOTTOM_Y, 40, BOTTOM_H, 91,
            rb.shape(None, text("→"), 20, rb.ACCENT_BLUE, "Segoe UI Semibold", align="center"), tab=False,
        )
    )
    visuals.append(
        visual("p1_rank_go", rb.CONTENT_X, BOTTOM_Y, RANK_W, BOTTOM_H, 92,
               rb.nav_overlay(P5_PAGE, "Rank among the six largest ASEAN power systems. Click for the ASEAN comparison."))
    )
    findings_x = rb.CONTENT_X + RANK_W + rb.GAP
    visuals.append(
        visual(
            "p1_findings", findings_x, BOTTOM_Y, rb.CONTENT_X + rb.CONTENT_W - findings_x, BOTTOM_H, 93,
            rb.textbox(
                [
                    # Static text from docs/findings.md (audited 2026-10-02); update both together.
                    ("Headline findings (2015–2025, Ember basis; caveats in docs/findings.md)", 10, rb.TEXT_PRIMARY, True),
                    ("1. The renewable share roughly doubled (9.6% → 19.7%, 3-year averages), mostly in a 2015–17 hydro "
                     "step; since 2017 hydro and solar share the growth.", 9, rb.TEXT_PRIMARY, False),
                    ("2. Each kWh got 9.5% cleaner, yet power-sector emissions rose 27%: generation grew 40%, and all the "
                     "fossil growth was coal.", 9, rb.TEXT_PRIMARY, False),
                    ("3. Malaysia is 3rd of 6 ASEAN peers on renewable share but 5th of 6 on carbon intensity (606 g/kWh, "
                     "2025): the coal-to-gas balance matters too.", 9, rb.TEXT_PRIMARY, False),
                ]
            ),
        )
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
