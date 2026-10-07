"""Build the P6 About page as PBIR visual definitions (M5 step 4, doc 03 P6 as split by the M5 plan Q3).

Layout (1280x720 frame, doc 04 §4): header (static takeaway title; the subtitle is [Run Summary], the last
refresh); row 1 = the sources and licences table (one row per data source: name, what it gives, licence,
credit wording, consent status, link); row 2 = left KPI definitions table (scrolls), right method notes, the
consent line ([Consent Summary]) and a "Source code on GitHub" button. The data-quality results live on the
next page (P6b, build_p6b_page.py).

Source links open in the browser (a WebUrl column; Ctrl+click in Desktop). The notes quote only the repo
docs (docs/forecast.md, docs/reconciliation.md, DATA_LICENSES.md, doc 05) and no handbook figure.
Re-running rebuilds the page.

    .venv/Scripts/python tools/build_p6_page.py
"""

from __future__ import annotations

import report_builder as rb
from report_builder import column_ref, lit, solid, text, visual

PAGE = "p6_about"
REPO_URL = "https://github.com/Aether03/malaysia-energy-transition-dashboard"

# --- geometry (limits are Desktop 2.158's, from the M3-M5 GUI rounds)
ROW1_Y, ROW1_H = rb.BODY_Y, 300  # 9 sources: title 28 + header 26 + rows that wrap to 2-5 lines, so it scrolls a little
ROW2_Y, ROW2_END = 420, 664
ROW2_H = ROW2_END - ROW2_Y  # 244
KPI_W = 500  # 540 left the method notes too narrow: their last line clipped (round 2)
NOTES_X = rb.CONTENT_X + KPI_W + rb.GAP  # 756
NOTES_W = rb.CONTENT_X + rb.CONTENT_W - NOTES_X  # 500
NOTES_H = 180  # about 10 lines of 9 pt at 4 px padding
LOWER_Y, LOWER_H = (
    ROW2_Y + NOTES_H + 8,
    ROW2_END - (ROW2_Y + NOTES_H + 8),
)  # 608, 56: 3 lines (40 px clipped the 2nd, round 1)
CONSENT_W = 340  # [Consent Summary] is about 140 characters: 3 lines at 9 pt
BUTTON_X = NOTES_X + CONSENT_W + 8  # 1104
BUTTON_W = rb.CONTENT_X + rb.CONTENT_W - BUTTON_X  # 152: 112 cut the label to "Source code.." (round 1)

# Column widths: the table's inner width is the visual width minus 8 px padding and ~12 px scrollbar.
SOURCE_COLUMNS = [  # (field, header, width px): 190 + 270 + 130 + 300 + 80 + 60 = 1030
    (column_ref("data_source", "name"), "Source", 190),
    (column_ref("data_source", "provides"), "What it provides", 270),
    (column_ref("data_source", "licence"), "Licence", 130),
    (column_ref("data_source", "credit_text"), "Credit", 300),
    (column_ref("data_source", "consent_status"), "Consent", 80),
    (column_ref("data_source", "url"), "Link", 60),
]
KPI_COLUMNS = [  # 120 + 170 + 140 + 50 = 480
    (column_ref("kpi", "name"), "KPI", 120),
    (column_ref("kpi", "definition"), "Definition", 170),
    (column_ref("kpi", "formula"), "Formula", 140),
    (column_ref("kpi", "unit"), "Unit", 50),
]

FOOTNOTE = (
    "Credits are worded as each licence asks. Boundaries © OpenStreetMap contributors, via geoBoundaries (ODbL 1.0). "
    "A source marked REQUESTED needs written permission and is used locally only until it is granted. Links open in "
    "your browser (Ctrl+click in Power BI Desktop). Licence texts: DATA_LICENSES.md in the repository."
)

# Method notes (text, size pt, colour, bold). Sources: docs/forecast.md, doc 05 (formula), docs/reconciliation.md.
NOTES = [
    ("Method notes", 10, rb.TEXT_PRIMARY, True),
    (
        (
            "Forecast: LightGBM issued at local midnight, scored once on a locked 2024 backtest against a seasonal-naive "
            "baseline (the same hour last week). The verdict is on the Forecast page."
        ),
        9,
        rb.TEXT_PRIMARY,
        False,
    ),
    (
        "Capacity factor = generation ÷ (capacity × hours in the year); blank if capacity is unreported.",
        9,
        rb.TEXT_PRIMARY,
        False,
    ),
    (
        (
            "States: handbook labels map to states through a reference table; reliability by state covers Peninsular "
            "states only, and Sabah includes Labuan."
        ),
        9,
        rb.TEXT_PRIMARY,
        False,
    ),
    (
        (
            "Sarawak: the 2023 handbook prints each Sarawak reliability year one year early, so the years are remapped "
            "(see docs/reconciliation.md)."
        ),
        9,
        rb.TEXT_PRIMARY,
        False,
    ),
    (
        (
            "Data lag: Ember runs to 2025 (Brunei, Laos and Myanmar to 2024); grid load covers 2023-24; DOSM supply ends "
            "in June 2024 and is a cross-check only."
        ),
        9,
        rb.TEXT_PRIMARY,
        False,
    ),
]


def github_button() -> dict:
    """Filled button with a WebUrl action (action shape: tools/templates/button_info_weburl.json).
    Navy text-on-fill has 10:1 contrast; hover and press are set so Desktop paints no theme colour."""
    return {
        "visualType": "actionButton",
        "objects": {
            "icon": [{"properties": {"shapeType": text("blank")}, "selector": {"id": "default"}}],
            "text": [
                {"properties": {"show": lit("true")}},
                {
                    "properties": {
                        "text": text("Source code on GitHub"),
                        "fontColor": solid(rb.NAV_TEXT),
                        "fontSize": lit("10D"),
                        "fontFamily": text("Segoe UI Semibold"),
                        "horizontalAlignment": text("center"),
                    },
                    "selector": {"id": "default"},
                },
            ],
            "fill": [
                {"properties": {"show": lit("true")}},
                *(
                    {"properties": {"fillColor": solid(colour), "transparency": lit("0D")}, "selector": {"id": state}}
                    for state, colour in (("default", rb.NAVY), ("hover", rb.ACCENT_BLUE), ("press", rb.NAVY))
                ),
            ],
            "outline": [{"properties": {"show": lit("false")}}],
        },
        "visualContainerObjects": {
            **rb.BARE,
            "visualLink": [
                {
                    "properties": {
                        "show": lit("true"),
                        "type": text("WebUrl"),
                        "webUrl": text(REPO_URL),
                        "enabledTooltip": text("Opens the project's GitHub repository in your browser"),
                    }
                }
            ],
        },
        "drillFilterOtherVisuals": True,
    }


def notes_box() -> dict:
    body = rb.textbox(NOTES)
    body["visualContainerObjects"]["padding"] = [
        {"properties": {side: lit("6D") for side in ("left", "top", "right", "bottom")}}
    ]
    return body


def build() -> list[dict]:
    visuals = rb.frame(
        PAGE,
        None,
        "Run Summary",
        FOOTNOTE,
        title_text="Where the data comes from, and on what terms",
    )
    sort_name = [(column_ref("data_source", "name"), "Ascending")]
    visuals.append(
        visual(
            "p6_sources",
            rb.CONTENT_X,
            ROW1_Y,
            rb.CONTENT_W,
            ROW1_H,
            40,
            rb.table("Sources and licences", SOURCE_COLUMNS, sort=sort_name),
            alt="Table: one row per data source with what it provides, its licence, the credit wording, its consent status and a link to the source",
        )
    )
    visuals.append(
        visual(
            "p6_kpis",
            rb.CONTENT_X,
            ROW2_Y,
            KPI_W,
            ROW2_H,
            41,
            rb.table("KPI definitions", KPI_COLUMNS, sort=[(column_ref("kpi", "name"), "Ascending")]),
            alt="Table: each KPI with its definition, formula and unit; scrolls",
        )
    )
    visuals.append(
        visual(
            "p6_notes",
            NOTES_X,
            ROW2_Y,
            NOTES_W,
            NOTES_H,
            42,
            notes_box(),
            alt="Text box: method notes on the forecast, the capacity factor, the state mapping, the Sarawak year remap and data lag",
        )
    )
    visuals.append(
        visual(
            "p6_consent",
            NOTES_X,
            LOWER_Y,
            CONSENT_W,
            LOWER_H,
            43,
            rb.shape(
                None, {"expr": rb.measure_ref("Consent Summary")}, 9, rb.TEXT_SECONDARY, boxed=True, left_margin=8
            ),
            alt="Text: the sources that need written permission, and the status of each request",
        )
    )
    visuals.append(
        visual(
            "p6_github",
            BUTTON_X,
            LOWER_Y,
            BUTTON_W,
            LOWER_H,
            44,
            github_button(),
            alt="Button: open the project's source code on GitHub in your browser",
        )
    )
    return visuals


def main() -> None:
    visuals = build()
    rb.write_page(PAGE, "About", visuals)
    print(f"Wrote {len(visuals)} visuals to the About page")


if __name__ == "__main__":
    main()
