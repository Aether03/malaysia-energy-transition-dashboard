"""Build the P3b State reliability page as PBIR visual definitions (M4 step 11, doc 03 P3 as amended by the M4 plan).

Layout (1280x720 frame, doc 04 §4): header (takeaway title, subtitle); row 0 = SAIFI | SAIDI tile toggle,
year dropdown, the CAIDI/year note; below it two columns: left = Shape Map of the Peninsular states (with
its "not reported" note) over a trend line for the state clicked on the map or the bar against the
Peninsular total (small multiples were ruled out by the step 1 spike); right = ranked bar of the 13 states
at the full column height (GUI round 1: 13 bars need ~496 px without a scrollbar).

The map reads the TopoJSON as a registered resource: build() registers `report/maps/mys_adm1.topojson`
(ODbL 1.0, byte-identical copy) under StaticResources/RegisteredResources and in report.json. The year
slicer is this page's own and not synced (plan Q9); nothing picked = the latest year. Re-running
rebuilds the page and is idempotent.

    .venv/Scripts/python tools/build_p3b_page.py
"""

from __future__ import annotations

import build_p4_page as p4
import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, text, visual

PAGE = "p3b_state_reliability"

# Shape Map resource: the file Desktop reads, a fixed name carrying the pinned geoBoundaries commit.
MAP_SOURCE = rb.ROOT / "report" / "maps" / "mys_adm1.topojson"
MAP_RESOURCE = "mys_adm1_9469f09.topojson"
MAP_DISPLAY_NAME = "mys_adm1.topojson"

# Sequential blue for the map (doc 04 §3.4). The validated ordinal scale runs #86b6ef -> ... -> #0d366b
# (light end 2.06:1 on surface.card); the theme's #cde2fb minimum would sit too close to the grey of the
# unreported shapes, so the map starts at #86b6ef. The ranked bar uses one solid accent blue: Desktop
# ignored a gradient fill on the bar in GUI round 1 (bars came out theme brown); its rank order and
# data labels carry the ordering.
SEQ_MIN, SEQ_MAX = "#86b6ef", "#0d366b"

# --- geometry (limits are Desktop 2.158's, from the M3 GUI rounds)
ROW0_Y, ROW0_H = rb.BODY_Y, 56  # a dropdown with its header clipped at 44 px in GUI round 1
BODY2_Y, BODY2_END = ROW0_Y + ROW0_H + 8, 664  # 168 .. 664, both columns
TOGGLE_W = 200  # two tiles of 100 px
YEAR_X = rb.CONTENT_X + TOGGLE_W + rb.GAP  # 416
YEAR_W = 152
NOTE_X = YEAR_X + YEAR_W + rb.GAP  # 584
NOTE_W = rb.CONTENT_X + rb.CONTENT_W - NOTE_X  # 672
MAP_W = 520
BAR_X = rb.CONTENT_X + MAP_W + rb.GAP  # 736
BAR_W = rb.CONTENT_X + rb.CONTENT_W - BAR_X  # 520
BAR_H = BODY2_END - BODY2_Y  # 496: 13 bars x 20 px (category minimum) plus title and axis, no scrollbar
MAP_H = 272
MAP_NOTE_H = 20  # one 9 pt line under the map
TREND_Y = BODY2_Y + MAP_H + MAP_NOTE_H + 4 + 8  # 472
TREND_H = BODY2_END - TREND_Y  # 192; at 160 the year axis disappeared in GUI round 1

MAP_NOTE = "Grey: Sabah, Sarawak and Labuan are not reported by state (see Regions)."

TOOLTIP_LABELS = {
    "Reliability State Name": "State",
    "Reliability Rank": "Rank (1 = most reliable)",
    "Reliability Change Since 2015": "Change since 2015",
}


# ---------- helpers ----------
def sequential_rule() -> dict:
    """linearGradient2 with explicit blue endpoints, nulls as the page default (Shape Map and bar)."""
    return {
        "linearGradient2": {
            "min": {"color": lit(f"'{SEQ_MIN}'")},
            "max": {"color": lit(f"'{SEQ_MAX}'")},
            "nullColoringStrategy": {"strategy": lit("'asZero'")},
        }
    }


def label_tooltips(body: dict) -> dict:
    for p in body["query"]["queryState"].get("Tooltips", {}).get("projections", []):
        if p["nativeQueryRef"] in TOOLTIP_LABELS:
            p["displayName"] = TOOLTIP_LABELS[p["nativeQueryRef"]]
    return body


def reported_states_filter(name: str) -> dict:
    """Visual filter dim_state[is_reported_by_state] = true (a boolean column, so the literal is unquoted)."""
    return {
        "filters": [
            {
                "name": rb.filter_name(f"{name}:dim_state.is_reported_by_state"),
                "field": column_ref("dim_state", "is_reported_by_state"),
                "type": "Categorical",
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "d", "Entity": "dim_state", "Type": 0}],
                    "Where": [
                        {
                            "Condition": {
                                "In": {
                                    "Expressions": [
                                        {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Source": "d"}},
                                                "Property": "is_reported_by_state",
                                            }
                                        }
                                    ],
                                    "Values": [[{"Literal": {"Value": "true"}}]],
                                }
                            }
                        }
                    ],
                },
            }
        ]
    }


# ---------- controls ----------
def metric_toggle() -> dict:
    """SAIFI | SAIDI tiles on the disconnected reliability_metric table (plan Q7); default SAIFI.
    The labels are self-explanatory, so the header is hidden to fit the 44 px row."""
    body = rb.slicer(
        "reliability_metric", "label", "Metric", mode="Basic", single=True, horizontal=True, default=["SAIFI"]
    )
    body["objects"]["header"] = [{"properties": {"show": lit("false")}}]
    return body


def year_dropdown() -> dict:
    """Year dropdown on the disconnected reliability_year table (own slicer, not synced, plan Q9).

    Shape = tools/templates/slicer_date_dropdown.json with a plain single select (not forced), so a
    cleared pick falls back to the latest year in [Reliability Year]. Newest year first.
    """
    field = column_ref("reliability_year", "year")
    return {
        "visualType": "slicer",
        "query": {
            "queryState": {"Values": {"projections": [projection(field, True)]}},
            "sortDefinition": {"sort": [{"field": field, "direction": "Descending"}]},
        },
        "objects": {
            "data": [{"properties": {"mode": text("Dropdown")}}],
            "header": [{"properties": {"show": lit("true"), "text": text("Year"), "fontSize": lit("9D")}}],
            "selection": [{"properties": {"singleSelect": lit("true"), "strictSingleSelect": lit("false")}}],
        },
        "drillFilterOtherVisuals": True,
    }


# ---------- map and bar ----------
def shape_map() -> dict:
    """Shape Map of the 16 ADM1 shapes (template: shape_map.json, saved by Desktop in the step 1 spike).

    Category = dim_state[iso_3166_2] (shapeISO joins, plan Q6); colour = [Reliability Value]. The saved
    template said projectionEnum 'albersUsa' while the canvas showed Mercator: set explicitly here.
    Shapes without a row (Sabah, Sarawak, Labuan) render grey.
    """
    body = {
        "visualType": "shapeMap",
        "query": {
            "queryState": {
                "Category": {
                    "projections": [{**projection(column_ref("dim_state", "iso_3166_2")), "displayName": "ISO code"}]
                },
                "Value": {"projections": [{**projection(measure_ref("Reliability Value")), "displayName": "Value"}]},
            }
        },
        "objects": {
            "shape": [
                {
                    "properties": {
                        "datasourceType": lit("'file_upload'"),
                        "map": {
                            "geoJson": {
                                "type": lit("'packaged'"),
                                "name": lit(f"'{MAP_DISPLAY_NAME}'"),
                                "content": {
                                    "expr": {
                                        "ResourcePackageItem": {
                                            "PackageName": "RegisteredResources",
                                            "PackageType": 1,
                                            "ItemName": MAP_RESOURCE,
                                        }
                                    }
                                },
                            }
                        },
                        "projectionEnum": lit("'mercator'"),
                    }
                }
            ],
            "dataPoint": [{"properties": {"fillRule": sequential_rule()}}],
        },
        "visualContainerObjects": rb.container(None, "Reliability Map Title"),
        "drillFilterOtherVisuals": True,
    }
    rb.tooltip_fields(body, ["Reliability State Name", "Reliability Rank", "Reliability Change Since 2015"])
    return label_tooltips(body)


def ranked_bar() -> dict:
    """The 13 reported states, rank 1 (lowest value = most reliable) at the top, labelled (the only
    data labels on P3/P3b, plan Q1: one year, one metric), one solid accent blue."""
    value = measure_ref("Reliability Value")
    body = {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_state", "name"), True)]},
                "Y": {"projections": [{**projection(value), "displayName": "Value"}]},
            },
            # Horizontal bars list the first category at the top: ascending puts rank 1 there.
            "sortDefinition": {"sort": [{"field": value, "direction": "Ascending"}]},
        },
        "objects": {
            "legend": [{"properties": {"show": lit("false")}}],
            "labels": [{"properties": {"show": lit("true"), "fontSize": lit("10D")}}],
            "dataPoint": [{"properties": {"fill": rb.solid(rb.ACCENT_BLUE)}}],
        },
        "visualContainerObjects": rb.container(None, "Reliability Bar Title"),
        "drillFilterOtherVisuals": True,
    }
    rb.tooltip_fields(body, ["Reliability Rank", "Reliability Change Since 2015"])
    return label_tooltips(body)


def trend_line() -> dict:
    """Selected state (navy) against Peninsular Malaysia (dashed text.secondary, as P4b's baseline).
    The state comes from a click on the map or the bar (default cross-filtering); nothing selected =
    Peninsular alone. The axis starts at 0 so a small change is not blown up."""
    series = [  # (measure, legend label, colour, width, line style)
        ("Reliability Selected State", "Selected state", rb.NAVY, "2D", "solid"),
        ("Reliability Peninsular", "Peninsular Malaysia", rb.TEXT_SECONDARY, "1.5D", "dashed"),
    ]
    return {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_year", "year"), True)]},
                "Y": {"projections": [{**projection(measure_ref(m)), "displayName": label} for m, label, *_ in series]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("true"), "position": text("Top")}}],
            "dataPoint": rb.measure_colours({m: colour for m, _, colour, *_ in series}),
            "lineStyles": [p4.line_style(width, style, m) for m, _, _, width, style in series],
            "valueAxis": [{"properties": {"start": lit("0D")}}],
            # Explicit: at 160 px the year axis was missing in GUI round 1.
            "categoryAxis": [{"properties": {"show": lit("true")}}],
        },
        "visualContainerObjects": rb.container(None, "Reliability Trend Title"),
        "drillFilterOtherVisuals": True,
    }


def build() -> list[dict]:
    rb.register_shape_map(MAP_SOURCE, MAP_RESOURCE)
    visuals = rb.frame(PAGE, "P3b Title", "P3b Subtitle", None, footnote_measure="P3b Footnote", title_size=16)

    # --- row 0: controls and the note moved out of the footnote
    visuals.append(
        visual(
            "p3b_metric_slicer",
            rb.CONTENT_X,
            ROW0_Y,
            TOGGLE_W,
            ROW0_H,
            40,
            metric_toggle(),
            alt="Tile slicer: switch every chart on this page between SAIFI (interruption frequency) and SAIDI (interruption duration)",
        )
    )
    visuals.append(
        visual(
            "p3b_year_slicer",
            YEAR_X,
            ROW0_Y,
            YEAR_W,
            ROW0_H,
            41,
            year_dropdown(),
            alt="Dropdown slicer: choose the year; nothing picked shows the latest year",
        )
    )
    visuals.append(
        visual(
            "p3b_note",
            NOTE_X,
            ROW0_Y,
            NOTE_W,
            ROW0_H,
            42,
            p4.note("P3b Note"),
            alt="Note: how the chosen metric relates to CAIDI, and which year is shown",
        )
    )

    # --- left: map with its note underneath | right: ranked bar of the 13 reported states
    visuals.append(
        visual(
            "p3b_map",
            rb.CONTENT_X,
            BODY2_Y,
            MAP_W,
            MAP_H,
            50,
            shape_map(),
            alt="Shape map: Peninsular Malaysian states shaded blue by the chosen reliability metric, darker is less reliable; Sabah, Sarawak and Labuan are grey because they are not reported by state; click a state to see its trend",
        )
    )
    visuals.append(
        visual(
            "p3b_map_note",
            rb.CONTENT_X + 12,
            BODY2_Y + MAP_H + 4,
            MAP_W - 12,
            MAP_NOTE_H,
            51,
            rb.shape(None, text(MAP_NOTE), 9, rb.TEXT_SECONDARY, v_align="top"),
            alt="Note under the map: the grey shapes are not reported by state",
        )
    )
    visuals.append(
        visual(
            "p3b_rank_bar",
            BAR_X,
            BODY2_Y,
            BAR_W,
            BAR_H,
            52,
            ranked_bar(),
            filter_config=reported_states_filter("p3b_rank_bar"),
            alt="Ranked bar chart: the 13 reported states by the chosen metric, most reliable at the top, each labelled with its value",
        )
    )

    # --- left column, under the map: selected-state trend
    visuals.append(
        visual(
            "p3b_trend",
            rb.CONTENT_X,
            TREND_Y,
            MAP_W,
            TREND_H,
            53,
            trend_line(),
            alt="Line chart: the chosen reliability metric over the years for the state picked on the map or bar (navy), against Peninsular Malaysia (dashed grey)",
        )
    )
    return visuals


def main() -> None:
    visuals = build()
    rb.write_page(PAGE, "State reliability", visuals)
    print(f"Wrote {len(visuals)} visuals to the State reliability page")


if __name__ == "__main__":
    main()
