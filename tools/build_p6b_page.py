"""Build the P6b Data quality page as PBIR visual definitions (M5 step 4, doc 03 P6 as split by the M5 plan Q3).

Layout (1280x720 frame, doc 04 §4): header (static title and subtitle); a summary row (the last run line and
the pass / warn / fail count); a left column (x 200-580) with the status tiles, the rows-per-source table
and a note on the expected warnings; a right column (x 596-1256) with the data-quality rules table, fixed
height so its 34 rules scroll inside it. An empty-state message is laid over the first table rows.

Interactions: a click on a source row filters the rules table to that source's rules (data_source ->
dq_latest, many-to-one; the page interaction is set to DataFilter explicitly); the status tiles slicer on
dq_latest[status] filters the rules table only (no relationship leads back to data_source). The summary
measures ignore both. The status chip is a conditional background on the [DQ Status Label] cell (rules on
dq_latest[status], the shape Desktop saved in tools/templates/table_status_chip_alt_tooltip.json).
Re-running rebuilds the page.

    .venv/Scripts/python tools/build_p6b_page.py
"""

from __future__ import annotations

import report_builder as rb
from report_builder import column_ref, lit, measure_ref, visual

PAGE = "p6b_data_quality"

# --- geometry (limits are Desktop 2.158's, from the M3-M5 GUI rounds)
SUMMARY_Y, SUMMARY_H = rb.BODY_Y, 48  # a card needs >= 40 px
RUN_W = 600
DQ_SUM_X = rb.CONTENT_X + RUN_W + rb.GAP  # 816
DQ_SUM_W = rb.CONTENT_X + rb.CONTENT_W - DQ_SUM_X  # 440
BODY_Y, BODY_END = SUMMARY_Y + SUMMARY_H + 8, 664  # 160 .. 664
LEFT_W = 380
RIGHT_X = rb.CONTENT_X + LEFT_W + rb.GAP  # 596
RIGHT_W = rb.CONTENT_X + rb.CONTENT_W - RIGHT_X  # 660
TILES_H = 48  # tile slicer with its header hidden (a 44 px dropdown with a header clips)
SOURCES_Y = BODY_Y + TILES_H + 8  # 216
SOURCES_H = 320  # title 28 + header 26 + 9 rows (long names wrap to 2 lines): scrolls a little
WARN_NOTE_Y = SOURCES_Y + SOURCES_H + 8  # 544
WARN_NOTE_H = BODY_END - WARN_NOTE_Y  # 120
DQ_H = BODY_END - BODY_Y  # 504
EMPTY_Y, EMPTY_H = BODY_Y + 60, 32  # over the first rows, under the title and header; the scrollbar stays free

# Status colours (doc 04 §3.5 marks) and the chip's font colour: the better of white and text.primary on
# each mark, asserted >= 4.5:1 below (Pass: dark text 5.9:1; Warn: dark text 10.7:1; Fail: white text 4.8:1).
STATUS_MARKS = {"PASS": "#0ca30c", "WARN": "#fab219", "FAIL": rb.STATUS_FAIL}

SOURCE_COLUMNS = [  # (field, header, width px): 136 + 66 + 66 + 92 = 360
    (column_ref("data_source", "name"), "Source", 136),
    (measure_ref("Source Rows Read"), "Rows read", 66),
    (measure_ref("Source Rows Changed"), "Rows changed", 66),
    (measure_ref("Source Last Loaded"), "Last loaded", 92),  # 70 wrapped the date (round 1)
]
DQ_COLUMNS = [  # 250 + 80 + 100 + 100 + 110 = 640, inside 660 - 8 padding - 12 scrollbar
    (column_ref("dq_latest", "rule_code"), "Rule", 250),
    (column_ref("dq_latest", "data_source_code"), "Source", 80),
    (column_ref("dq_latest", "severity"), "Severity", 100),
    (measure_ref("DQ Status Label"), "Result", 100),
    (column_ref("dq_latest", "rows_affected"), "Rows affected", 110),
]

FOOTNOTE = (
    "Rules run on every pipeline run; the number on the Data quality button counts rules that FAIL. The four "
    "WARNs above are expected differences between sources, not pipeline faults (docs/reconciliation.md). Click a "
    "source on the left to see only its rules; click it again to clear. Rules with no source check the grid data."
)

WARN_NOTE = [  # (text, size pt, colour, bold); from docs/reconciliation.md "Known cross-check warnings"
    ("Expected WARNs (docs/reconciliation.md)", 10, rb.TEXT_PRIMARY, True),
    ("OWID_GEN_WITHIN_5PCT: OWID uses a different upstream vintage than Ember.", 9, rb.TEXT_PRIMARY, False),
    (
        "DOSM_SUPPLY_WITHIN_10PCT: DOSM's supply is a net balance below Ember's gross generation, and Ember revised 2021 on.",
        9,
        rb.TEXT_PRIMARY,
        False,
    ),
    ("CF_AT_MOST_1: Ember's capacity is too small for the generation it reports.", 9, rb.TEXT_PRIMARY, False),
    ("STALE_COUNTRY_YEARS: Brunei, Laos and Myanmar end in 2024.", 9, rb.TEXT_PRIMARY, False),
]


# ---------- status chip ----------
def luminance(hex_colour: str) -> float:
    """WCAG relative luminance of #rrggbb."""

    def channel(i: int) -> float:
        c = int(hex_colour[1 + 2 * i : 3 + 2 * i], 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def chip_font(mark: str) -> str:
    """The better of white and text.primary on a mark colour; asserted to pass 4.5:1."""
    best = max((rb.NAV_TEXT, rb.TEXT_PRIMARY), key=lambda c: contrast(c, mark))
    assert contrast(best, mark) >= 4.5, f"no font colour reaches 4.5:1 on {mark}"
    return best


def status_cases(values: dict[str, str]) -> list[dict]:
    """One text-rule case per status (shape: the capture; the rule reads dq_latest[status], Min of a text)."""
    return [
        {
            "Condition": {
                "Comparison": {
                    "ComparisonKind": 0,
                    "Left": {
                        "Aggregation": {
                            "Expression": {"Column": column_ref("dq_latest", "status")["Column"]},
                            "Function": 3,
                        }
                    },
                    "Right": {"Literal": {"Value": f"'{status}'"}},
                },
                "Annotations": {"PowerBI.SQExprEvaluationKind": 1, "PowerBI.SQExprTextOperatorOption": 2},
            },
            "Value": {"Literal": {"Value": f"'{colour}'"}},
        }
        for status, colour in values.items()
    ]


def chip_format() -> dict:
    """Conditional background and font colour on the [DQ Status Label] cells (icon + word, never colour alone)."""

    def rule(values: dict[str, str]) -> dict:
        return {"solid": {"color": {"expr": {"Conditional": {"Cases": status_cases(values)}}}}}

    return {
        "properties": {
            "backColor": rule(STATUS_MARKS),
            "fontColor": rule({status: chip_font(mark) for status, mark in STATUS_MARKS.items()}),
        },
        "selector": {
            "data": [{"dataViewWildcard": {"matchingOption": 1}}],
            "metadata": "_Measures.DQ Status Label",
        },
    }


# ---------- visuals ----------
def status_tiles() -> dict:
    """PASS | WARN | FAIL tiles on dq_latest[status]: multi-select, none picked = all; header hidden."""
    body = rb.slicer("dq_latest", "status", "Result", mode="Basic", horizontal=True)
    body["objects"]["header"] = [{"properties": {"show": lit("false")}}]
    return body


def empty_message() -> dict:
    return rb.shape(None, {"expr": measure_ref("DQ Empty Message")}, 12, rb.TEXT_SECONDARY, align="center")


def warn_note() -> dict:
    body = rb.textbox(WARN_NOTE)
    body["visualContainerObjects"]["padding"] = [
        {"properties": {side: lit("6D") for side in ("left", "top", "right", "bottom")}}
    ]
    return body


def build() -> list[dict]:
    visuals = rb.frame(
        PAGE,
        None,
        None,
        FOOTNOTE,
        title_text="Every data-quality rule, checked on each pipeline run",
        subtitle_text="Results of the most recent run · pass, warn or fail · click a source to see its rules",
    )
    box = {"boxed": True, "left_margin": 12}
    visuals.append(
        visual(
            "p6b_run_summary",
            rb.CONTENT_X,
            SUMMARY_Y,
            RUN_W,
            SUMMARY_H,
            40,
            rb.shape(None, {"expr": measure_ref("Run Summary")}, 10, rb.TEXT_PRIMARY, **box),
            alt="Text card: the latest pipeline run, with its status and start and finish times",
        )
    )
    visuals.append(
        visual(
            "p6b_dq_summary",
            DQ_SUM_X,
            SUMMARY_Y,
            DQ_SUM_W,
            SUMMARY_H,
            41,
            rb.shape(None, {"expr": measure_ref("DQ Summary")}, 11, rb.TEXT_PRIMARY, "Segoe UI Semibold", **box),
            alt="Text card: how many data-quality rules passed, warned and failed in the latest run",
        )
    )
    visuals.append(
        visual(
            "p6b_status_slicer",
            rb.CONTENT_X,
            BODY_Y,
            LEFT_W,
            TILES_H,
            42,
            status_tiles(),
            alt="Tile slicer: show only the rules that passed, warned or failed; none picked shows all",
        )
    )
    visuals.append(
        visual(
            "p6b_sources",
            rb.CONTENT_X,
            SOURCES_Y,
            LEFT_W,
            SOURCES_H,
            43,
            rb.table(
                "Rows per source (click one to filter the rules)",
                SOURCE_COLUMNS,
                sort=[(column_ref("data_source", "name"), "Ascending")],
            ),
            alt="Table: each source with the rows read and changed in its latest load and the date it was loaded; clicking a row filters the rules table to that source",
        )
    )
    visuals.append(
        visual(
            "p6b_warn_note",
            rb.CONTENT_X,
            WARN_NOTE_Y,
            LEFT_W,
            WARN_NOTE_H,
            44,
            warn_note(),
            alt="Text box: the four warnings that are expected, and why each fires",
        )
    )
    visuals.append(
        visual(
            "p6b_dq_table",
            RIGHT_X,
            BODY_Y,
            RIGHT_W,
            DQ_H,
            45,
            rb.table(
                "Data-quality rules",
                DQ_COLUMNS,
                sort=[
                    (column_ref("dq_latest", "rows_affected"), "Descending"),
                    (column_ref("dq_latest", "rule_code"), "Ascending"),
                ],
                extra_values=[chip_format()],
            ),
            alt="Table: every data-quality rule with its source, severity, result (icon and word, coloured green, amber or red) and the number of rows affected; scrolls, and rules with problems come first",
        )
    )
    visuals.append(
        visual(
            "p6b_dq_empty",
            RIGHT_X + 12,
            EMPTY_Y,
            RIGHT_W - 36,
            EMPTY_H,
            46,
            empty_message(),
            alt="Message over the rules table: reads No pipeline run recorded when no rule has been checked yet, otherwise blank",
        )
    )
    return visuals


def main() -> None:
    visuals = build()
    rb.write_page(
        PAGE,
        "Data quality",
        visuals,
        # Explicit, not left to the default: a click on a source row filters the rules (doc 03 P6).
        {"visualInteractions": [{"source": "p6b_sources", "target": "p6b_dq_table", "type": "DataFilter"}]},
    )
    print(f"Wrote {len(visuals)} visuals to the Data quality page")


if __name__ == "__main__":
    main()
