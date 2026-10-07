"""Build the hidden tooltip pages (M2 step 10): T2 country tooltip, 320x240 (doc 03 T1/T2).

T2 shows the hovered country's name and comparison year, its generation mix as a 100% stacked bar
(source colours) and two cards: RE share and carbon intensity at the comparison year.
The page is hidden in view mode and used from P5 visuals via visualTooltip. Re-running rebuilds it.

    .venv/Scripts/python tools/build_tooltips.py
"""

from __future__ import annotations

import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, solid, text, visual

T2_PAGE = "t2_country"
W, H = 320, 280  # 280, not 240: a titled card needs ~90 px to show its value (M5 GUI round 1)
PAD = 8


def build_t2() -> list[dict]:
    visuals = [
        visual(
            "t2_title",
            PAD,
            PAD,
            W - 2 * PAD,
            28,
            1,
            rb.shape(None, {"expr": measure_ref("T2 Title")}, 12, rb.TEXT_PRIMARY, "Segoe UI Semibold"),
            tab=False,
            alt="Tooltip title: the hovered country and the comparison year",
        )
    ]
    mix = {
        "visualType": "hundredPercentStackedBarChart",
        "query": {
            "queryState": {
                "Series": {"projections": [projection(column_ref("dim_source", "display_name"))]},
                "Y": {"projections": [projection(measure_ref("T2 Generation Share (%)"))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Bottom"), "fontSize": lit("8D")}}],
            "categoryAxis": [{"properties": {"show": lit("false")}}],
            "valueAxis": [{"properties": {"show": lit("false")}}],
            "dataPoint": rb.series_colours("dim_source", "display_name", rb.source_colours()),
        },
        "visualContainerObjects": rb.container("Generation mix by source (%)"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(
        visual(
            "t2_mix_bar",
            PAD,
            40,
            W - 2 * PAD,
            128,
            2,
            mix,  # 116 px rendered as an icon (GUI round 4)
            alt="100% stacked bar: the hovered country's generation mix by source, one colour per source",
        )
    )
    card_w = (W - 3 * PAD) / 2
    for i, (measure, label, alt) in enumerate(
        [
            (
                "RE Share at Comparison Year (%)",
                "RE share (%)",
                "Card: the hovered country's renewable share of generation at the comparison year",
            ),
            (
                "Intensity at Comparison Year (gCO2e/kWh)",
                "gCO2e/kWh",  # "Intensity (gCO2e/kWh)" wrapped and hid the value
                "Card: the hovered country's carbon intensity of electricity at the comparison year",
            ),
        ]
    ):
        visuals.append(
            visual(
                f"t2_card_{i}",
                PAD + i * (card_w + PAD),
                176,
                card_w,
                H - 176 - PAD,
                3 + i,
                rb.card(measure, 20, solid(rb.TEXT_PRIMARY), False, title=label),
                alt=alt,
            )
        )
    return visuals


def main() -> None:
    visuals = build_t2()
    rb.write_page(
        T2_PAGE,
        "T2 Country",
        visuals,
        {"type": "Tooltip", "visibility": "HiddenInViewMode"},
        width=W,
        height=H,
    )
    print(f"Wrote {len(visuals)} visuals to the T2 tooltip page")


if __name__ == "__main__":
    main()
