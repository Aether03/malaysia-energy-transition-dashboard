"""Build the D1 Country Deep Dive page (doc 03 D1; M2 step 11): hidden, reached by drill-through.

Same layout as P2 for one country, without the national-target chart (NETR targets are
Malaysia-only). P2's measures follow the country in context (M2 plan Q4), so the drill-through
filter on dim_country[name] retargets every visual. A Back button returns to the ASEAN page with
its filters intact. The drill-through binding mirrors tools/templates/page_drillthrough.json.

    .venv/Scripts/python tools/build_d1_page.py
"""

from __future__ import annotations

import copy

import build_p2_page
import report_builder as rb
from report_builder import column_ref, lit, text, visual

PAGE = "d1_country"
DROP = {"p2_target_line"}  # NETR targets are Malaysia-specific (doc 03 D1)
FOOTNOTE = (
    "Sources: Ember Yearly Electricity Data (CC BY 4.0); OWID population (CC BY 4.0). Capacity factor = generation ÷ "
    "(capacity × hours in year); blank, never 0, where Ember reports no capacity or capacity too small for the "
    "generation (e.g. Philippine and Indonesian geothermal, Thailand and Myanmar in every year). Right-click a country "
    "on the ASEAN page to drill here; Back returns with its filters."
)
FILTER_NAME, BINDING_NAME, PARAM_NAME = "d1countryfilter00001", "d1countrybinding0001", "d1countryparam000001"


def back_button() -> dict:
    """Back to the page the user drilled from (template: back_button.json), styled for the nav rail."""
    return {
        "visualType": "actionButton",
        "objects": {
            "icon": [
                {"properties": {"shapeType": text("back"), "lineColor": rb.solid(rb.NAV_TEXT)}, "selector": {"id": "default"}},
            ],
            "text": [
                {"properties": {"show": lit("true")}},
                {
                    "properties": {
                        "text": text("Back"),
                        "fontColor": rb.solid(rb.NAV_TEXT),
                        "fontSize": lit("10D"),
                        "fontFamily": text("Segoe UI Semibold"),
                    },
                    "selector": {"id": "default"},
                },
            ],
            "fill": rb.CLEAR_BUTTON_FILL,
            "outline": [{"properties": {"show": lit("false")}}],
        },
        "visualContainerObjects": {
            **rb.BARE,
            "visualLink": [{"properties": {"show": lit("true"), "type": text("Back")}}],
        },
        "drillFilterOtherVisuals": True,
    }


def build() -> list[dict]:
    visuals = []
    for v in build_p2_page.build():
        if v["name"] in DROP or v["name"].startswith(("frame_nav", "frame_reset")):
            continue  # hidden page: no rail highlight; the Back button replaces it
        v = copy.deepcopy(v)
        v["name"] = v["name"].replace("p2_", "d1_", 1)
        if v["name"] == "d1_cf_bar" or v["name"] == "d1_cf_note":
            # The target chart's column is free: the capacity factor spans the full width.
            v["position"]["x"] = rb.CONTENT_X
            v["position"]["width"] = rb.CONTENT_W
        visuals.append(v)
    visuals = [v for v in visuals if v["name"] != "frame_footnote"]
    visuals.append(
        visual("frame_footnote", rb.CONTENT_X, rb.FOOTNOTE_Y, rb.CONTENT_W, 44, 99, rb.footnote(FOOTNOTE),
               alt="Footnote: sources, licences and caveats for this page")
    )
    visuals.append(
        visual("d1_back", 8, rb.BODY_Y, 160, 44, 2, back_button(),
               alt="Button: go back to the page you drilled through from, keeping its filters")
    )
    return visuals


def drillthrough_page() -> dict:
    field = column_ref("dim_country", "name")
    return {
        "visibility": "HiddenInViewMode",
        "filterConfig": {"filters": [{"name": FILTER_NAME, "field": field, "type": "Categorical", "howCreated": "Drillthrough"}]},
        "pageBinding": {
            "name": BINDING_NAME,
            "type": "Drillthrough",
            "parameters": [
                {
                    "name": PARAM_NAME,
                    "boundFilter": FILTER_NAME,
                    "asAggregation": False,
                    "qnaSingleSelectRequired": False,
                    "fieldExpr": field,
                }
            ],
        },
    }


def main() -> None:
    visuals = build()
    rb.write_page(PAGE, "Country Deep Dive", visuals, drillthrough_page())
    print(f"Wrote {len(visuals)} visuals to the D1 page")


if __name__ == "__main__":
    main()
