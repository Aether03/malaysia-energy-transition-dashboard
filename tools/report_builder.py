"""Shared PBIR building blocks for every report page (M2 step 6).

Layout tokens follow doc 04 §4 (1280x720 canvas, nav rail x 0-176, content x 200-1256,
header y 16-88, body y 104-680, footnote strip at the bottom); colours and type follow
doc 04 §2-3. JSON shapes mirror visuals saved by Power BI Desktop: commit 5efb683 for the
classic card, slicer and charts, and `tools/templates/` (M2 step 5) for shapes, buttons,
navigators, new cards, field parameters, tooltip and drill-through pages.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "report" / "EnergyTransition.Report" / "definition" / "pages"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

# doc 04 §3.1 tokens
TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED = "#0b0b0b", "#52514e", "#6b6a66"
SURFACE_CARD, BORDER_SUBTLE = "#fcfcfb", "#e4e3df"
NAVY, ACCENT_BLUE, PEER_MUTED = "#104281", "#256abf", "#8a8984"
NAV_TEXT, NAV_TEXT_INACTIVE, NAV_SELECTED_BAR = "#ffffff", "#cde2fb", "#86b6ef"
STATUS_FAIL = "#d03b3b"

# doc 04 §4 regions
CONTENT_X, CONTENT_W = 200, 1056
HEADER_Y, BODY_Y, FOOTNOTE_Y = 16, 104, 672
GAP = 16

OVERVIEW_PAGE = "59dacfc5089b163e62a0"  # created by Desktop in M1; other pages use readable names
# Nav rail order = doc 04 nav labels; a page without a builder yet is simply not listed.
NAV = (
    ("Overview", OVERVIEW_PAGE),
    ("Generation", "p2_generation"),
    ("Regions", "p3_regions"),
    ("Grid load", "p4_grid_load"),
    ("ASEAN", "p5_asean"),
    ("About", "p6_about"),
)


# ---------- expression helpers ----------
def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def text(value: str) -> dict:
    return lit("'" + value.replace("'", "''") + "'")


def solid(hex_colour: str) -> dict:
    return {"solid": {"color": text(hex_colour)}}


def measure_ref(name: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": name}}


def column_ref(table: str, column: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def projection(field: dict, active: bool = False) -> dict:
    kind = "Measure" if "Measure" in field else "Column"
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    proj = {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if active:
        proj["active"] = True
    return proj


def container(title: str | None, title_measure: str | None = None) -> dict:
    """Title block. `title_measure` binds the title text to a measure (e.g. 'Capacity Factor Title')."""
    # Subtitles are auto-generated from field names ("X by year and display_name"): always hidden.
    hidden_subtitle = [{"properties": {"show": lit("false")}}]
    if title is None and title_measure is None:
        return {"title": [{"properties": {"show": lit("false")}}], "subTitle": hidden_subtitle}
    return {
        "title": [
            {
                "properties": {
                    "show": lit("true"),
                    "text": {"expr": measure_ref(title_measure)} if title_measure else text(title),
                    "fontSize": lit("12D"),
                    "fontColor": solid(TEXT_PRIMARY),
                }
            }
        ],
        "subTitle": hidden_subtitle,
    }


def visual(
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    z: int,
    body: dict,
    tab: bool = True,
    filter_config: dict | None = None,
) -> dict:
    position = {"x": x, "y": y, "z": z, "width": w, "height": h}
    if tab:
        position["tabOrder"] = z
    out = {"$schema": SCHEMA, "name": name, "position": position, "visual": body}
    if filter_config:
        out["filterConfig"] = filter_config  # container top level, a sibling of "visual" (card_new.json)
    return out


def filter_name(seed: str) -> str:
    """Stable 20-hex filter id, as Desktop writes them."""
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:20]


def measure_filter(visual_name: str, measure: str, value: int = 1) -> dict:
    """Visual-level filter `[measure] = value` (Desktop's Advanced shape for a measure filter)."""
    return {
        "filters": [
            {
                "name": filter_name(f"{visual_name}:{measure}"),
                "field": measure_ref(measure),
                "type": "Advanced",
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "m", "Entity": "_Measures", "Type": 0}],
                    "Where": [
                        {
                            "Condition": {
                                "Comparison": {
                                    "ComparisonKind": 0,
                                    "Left": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": measure}},
                                    "Right": {"Literal": {"Value": f"{value}L"}},
                                }
                            }
                        }
                    ],
                },
            }
        ]
    }


def tooltip_page(body: dict, page_name: str) -> dict:
    """Assign a report-page tooltip to a visual (visualContainerObjects.visualTooltip)."""
    body.setdefault("visualContainerObjects", {})["visualTooltip"] = [
        {"properties": {"show": lit("true"), "type": text("ReportPage"), "section": text(page_name)}}
    ]
    return body


# ---------- components ----------
# The theme gives every visual a card background and border (theme "*"); frame shapes and
# nav buttons opt out so they sit directly on the page or the rail.
BARE = {
    "background": [{"properties": {"show": lit("false")}}],
    "border": [{"properties": {"show": lit("false")}}],
}


def card(measure: str, size: int, colour: dict, show_label: bool, title: str | None = None) -> dict:
    """Classic card (M1). Needs about 40 px of height or more to render text."""
    return {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [projection(measure_ref(measure))]}}},
        "objects": {
            "labels": [{"properties": {"fontSize": lit(f"{size}D"), "color": colour}}],
            "categoryLabels": [
                {
                    "properties": {
                        "show": lit("true" if show_label else "false"),
                        "fontSize": lit("10D"),
                        "color": solid(TEXT_SECONDARY),
                    }
                }
            ],
        },
        # Narrow side padding so long labels such as "Carbon Intensity (gCO2e/kWh)" fit a 198 px card.
        "visualContainerObjects": {**container(title), "padding": [{"properties": {"left": lit("4D"), "right": lit("4D")}}]},
        "drillFilterOtherVisuals": True,
    }


def shape(
    fill: str | None,
    text_value: dict | None = None,
    font_size: int = 10,
    font_colour: str = TEXT_PRIMARY,
    font_family: str = "Segoe UI",
    align: str = "left",
    v_align: str = "middle",
    boxed: bool = False,
    left_margin: int = 0,
) -> dict:
    """Rectangle (template: shape_measure_title.json). `text_value` is text() or a measure expr.

    `boxed` keeps the theme's card background and border on the container (instead of BARE) so a
    text shape reads as a card; the shape fill itself stays transparent.
    """
    objects: dict = {
        "shape": [{"properties": {"tileShape": text("rectangle")}}],
        "rotation": [{"properties": {"shapeAngle": lit("0L")}}],
        # `show` goes in a selector-free entry and colours in the {"id": "default"} state entry,
        # as Desktop writes them; a `show` inside the state entry is ignored (P1 test, M2 step 6).
        "fill": [
            {"properties": {"show": lit("true")}},
            {
                "properties": {"fillColor": solid(fill or SURFACE_CARD), "transparency": lit("0D" if fill else "100D")},
                "selector": {"id": "default"},
            },
        ],
        "outline": [{"properties": {"show": lit("false")}}],
    }
    if text_value is not None:
        objects["text"] = [
            {"properties": {"show": lit("true")}},
            {
                "properties": {
                    "text": text_value,
                    "fontSize": lit(f"{font_size}D"),
                    "fontColor": solid(font_colour),
                    "fontFamily": text(font_family),
                    "horizontalAlignment": text(align),
                    "verticalAlignment": text(v_align),
                    "leftMargin": lit(f"{left_margin}D"),
                },
                "selector": {"id": "default"},
            },
        ]
    return {
        "visualType": "shape",
        "objects": objects,
        "visualContainerObjects": container(None) if boxed else BARE,
        "drillFilterOtherVisuals": True,
    }


def nav_button(label: str, page_name: str, selected: bool) -> dict:
    """Blank button with a page-navigation action (template: nav_button.json)."""
    return {
        "visualType": "actionButton",
        "objects": {
            "icon": [{"properties": {"shapeType": text("blank")}, "selector": {"id": "default"}}],
            "text": [
                {"properties": {"show": lit("true")}},
                {
                    "properties": {
                        "text": text(label),
                        "fontColor": solid(NAV_TEXT if selected else NAV_TEXT_INACTIVE),
                        "fontSize": lit("10D"),
                        "fontFamily": text("Segoe UI Semibold"),
                        "horizontalAlignment": text("left"),
                    },
                    "selector": {"id": "default"},
                }
            ],
            "fill": [
                {"properties": {"show": lit("true")}},
                {"properties": {"fillColor": solid(NAVY), "transparency": lit("100D")}, "selector": {"id": "default"}},
            ],
            "outline": [{"properties": {"show": lit("false")}}],
        },
        "visualContainerObjects": {
            **BARE,
            "visualLink": [
                {
                    "properties": {
                        "show": lit("true"),
                        "type": text("PageNavigation"),
                        "navigationSection": text(page_name),
                    }
                }
            ]
        },
        "drillFilterOtherVisuals": True,
    }


def nav_overlay(page_name: str) -> dict:
    """Transparent blank button for a card that must be clickable (cards cannot carry a reliable
    page-navigation action). Lay it exactly over the card, above it in z order."""
    return {
        "visualType": "actionButton",
        "objects": {
            "icon": [{"properties": {"shapeType": text("blank")}, "selector": {"id": "default"}}],
            "fill": [
                {"properties": {"show": lit("true")}},
                {"properties": {"fillColor": solid(NAVY), "transparency": lit("100D")}, "selector": {"id": "default"}},
            ],
            "outline": [{"properties": {"show": lit("false")}}],
        },
        "visualContainerObjects": {
            **BARE,
            "visualLink": [
                {
                    "properties": {
                        "show": lit("true"),
                        "type": text("PageNavigation"),
                        "navigationSection": text(page_name),
                    }
                }
            ],
        },
        "drillFilterOtherVisuals": True,
    }


def textbox(paragraphs: list[tuple[str, int, str, bool]]) -> dict:
    """Textbox from (text, font size pt, colour, bold) paragraphs. Keeps the theme card around it."""
    paras = []
    for value, size, colour, bold in paragraphs:
        style = {"fontSize": f"{size}pt", "color": colour}
        if bold:
            style["fontWeight"] = "bold"
        paras.append({"textRuns": [{"value": value, "textStyle": style}]})
    return {
        "visualType": "textbox",
        "objects": {"general": [{"properties": {"paragraphs": paras}}]},
        "visualContainerObjects": container(None),
    }


def footnote(value: str) -> dict:
    return textbox([(value, 9, TEXT_MUTED, False)])


def source_colours() -> dict[str, str]:
    """display_name -> colour from the seed (doc 04 §3.2), so charts bind colour to the source."""
    with (ROOT / "seed" / "dim_source.csv").open(encoding="utf-8-sig", newline="") as fh:
        return {row["display_name"]: row["color_hex"] for row in csv.DictReader(fh)}


def series_selector(table: str, column: str, value: str) -> dict:
    """Selector for one series/category value (scopeId comparison on the column)."""
    return {
        "data": [
            {
                "scopeId": {
                    "Comparison": {
                        "ComparisonKind": 0,
                        "Left": column_ref(table, column),
                        "Right": {"Literal": {"Value": "'" + value.replace("'", "''") + "'"}},
                    }
                }
            }
        ]
    }


def series_colours(table: str, column: str, colours: dict[str, str]) -> list[dict]:
    """dataPoint fills per series value, so a filtered-out source never shifts the palette."""
    return [
        {"properties": {"fill": solid(hex_colour)}, "selector": series_selector(table, column, value)}
        for value, hex_colour in colours.items()
    ]


def highlight_colours(table: str, column: str, value: str, highlight: str = NAVY, others: str = PEER_MUTED) -> list[dict]:
    """Default fill for every series/category (muted) plus one highlighted value (doc 04 §3.3)."""
    return [
        {"properties": {"fill": solid(others)}},
        {"properties": {"fill": solid(highlight)}, "selector": series_selector(table, column, value)},
    ]


def measure_colours(colours: dict[str, str]) -> list[dict]:
    """dataPoint fills per measure (multi-measure charts), keyed by queryRef."""
    return [
        {"properties": {"fill": solid(hex_colour)}, "selector": {"metadata": f"_Measures.{measure}"}}
        for measure, hex_colour in colours.items()
    ]


# ---------- slicers and field parameters ----------
# A field-parameter column in a value well: Desktop binds the hidden "<name> Fields" column and keeps
# the parameter name as the display name. Flip to False to bind the visible "<name>" column instead.
PARAM_WELL_USES_FIELDS_COLUMN = True


def param_projection(table: str) -> dict:
    """Projection of a field parameter ('Mix Unit', 'ASEAN Metric') for a chart's value well."""
    prop = f"{table} Fields" if PARAM_WELL_USES_FIELDS_COLUMN else table
    return {**projection(column_ref(table, prop)), "displayName": table}


def in_filter(table: str, column: str, values: list[str], name_seed: str) -> dict:
    """Saved slicer selection: Categorical filter `column IN values` (Desktop's shape)."""
    return {
        "filters": [
            {
                "name": filter_name(name_seed),
                "field": column_ref(table, column),
                "type": "Categorical",
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "s", "Entity": table, "Type": 0}],
                    "Where": [
                        {
                            "Condition": {
                                "In": {
                                    "Expressions": [
                                        {"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": column}}
                                    ],
                                    "Values": [[{"Literal": {"Value": "'" + v.replace("'", "''") + "'"}}] for v in values],
                                }
                            }
                        }
                    ],
                },
            }
        ]
    }


def slicer(
    table: str,
    column: str,
    header: str,
    mode: str = "Dropdown",
    single: bool = False,
    sync_group: str | None = None,
    horizontal: bool = False,
) -> dict:
    """Slicer body. mode: 'Dropdown', 'Basic' (list/tiles) or 'Between' (numeric range)."""
    objects: dict = {
        "data": [{"properties": {"mode": text(mode)}}],
        "header": [{"properties": {"show": lit("true"), "text": text(header), "fontSize": lit("9D")}}],
    }
    if mode != "Between":
        objects["selection"] = [{"properties": {"singleSelect": lit("true" if single else "false")}}]
    if horizontal:
        objects["general"] = [{"properties": {"orientation": lit("1L")}}]  # 0 = vertical, 1 = horizontal
    body: dict = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [projection(column_ref(table, column), True)]}}},
        "objects": objects,
        "drillFilterOtherVisuals": True,
    }
    if sync_group:
        body["syncGroup"] = {"groupName": sync_group, "fieldChanges": True, "filterChanges": True}
    return body


def year_range_slicer(header: str = "Years") -> dict:
    """Synced year-range slicer (doc 03 A4: synced across P2, P3, P5 and D1)."""
    return slicer("dim_year", "year", header, mode="Between", sync_group="year_range")


# ---------- page frame ----------
def frame(
    page_name: str,
    title_measure: str,
    subtitle_measure: str,
    footnote_text: str | None,
    footnote_measure: str | None = None,
) -> list[dict]:
    """Nav rail, takeaway title, scope/as-of subtitle and footnote strip (doc 03 A3, doc 04 §4).

    The footnote is static text, or bound to a measure (a boxed text shape) when `footnote_measure` is set.
    """
    visuals = [
        visual("frame_rail", 0, 0, 176, 720, 0, shape(NAVY), tab=False),
        visual(
            "frame_brand",
            12,
            HEADER_Y,
            156,
            56,
            1,
            shape(None, text("Malaysia Energy Transition"), 11, NAV_TEXT, "Segoe UI Semibold", v_align="top"),
            tab=False,
        ),
    ]
    existing = [(label, name) for label, name in NAV if (PAGES / name).is_dir()]
    for i, (label, name) in enumerate(existing):
        y = BODY_Y + i * 48
        visuals.append(visual(f"frame_nav_{i}", 8, y, 160, 44, 2 + i, nav_button(label, name, name == page_name)))
        if name == page_name:
            visuals.append(visual("frame_nav_selected", 0, y + 6, 4, 32, 20, shape(NAV_SELECTED_BAR), tab=False))
    if footnote_measure:
        footnote_body = shape(
            None, {"expr": measure_ref(footnote_measure)}, 9, TEXT_MUTED, v_align="top", boxed=True, left_margin=4
        )
    else:
        footnote_body = footnote(footnote_text or "")
    visuals += [
        visual(
            "frame_title",
            CONTENT_X,
            HEADER_Y,
            840,
            44,
            30,
            shape(None, {"expr": measure_ref(title_measure)}, 20, TEXT_PRIMARY, "Segoe UI Semibold"),
        ),
        visual(
            "frame_subtitle",
            CONTENT_X,
            HEADER_Y + 44,
            840,
            28,
            31,
            shape(None, {"expr": measure_ref(subtitle_measure)}, 11, TEXT_SECONDARY),
        ),
        visual("frame_footnote", CONTENT_X, FOOTNOTE_Y, CONTENT_W, 44, 99, footnote_body),
    ]
    return visuals


def write_page(
    page_name: str,
    display_name: str,
    visuals: list[dict],
    page_extra: dict | None = None,
    width: int = 1280,
    height: int = 720,
) -> None:
    """Rebuild one page's visuals from scratch and register the page in pages.json."""
    page_dir = PAGES / page_name
    visuals_dir = page_dir / "visuals"
    if visuals_dir.exists():
        shutil.rmtree(visuals_dir)
    for v in visuals:
        target = visuals_dir / v["name"] / "visual.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

    page_file = page_dir / "page.json"
    page = json.loads(page_file.read_text(encoding="utf-8")) if page_file.exists() else {"$schema": PAGE_SCHEMA}
    page.update({"name": page_name, "displayName": display_name, "displayOption": "FitToPage", "width": width, "height": height})
    page.update(page_extra or {})
    page_file.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")

    meta_file = PAGES / "pages.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if page_name not in meta["pageOrder"]:
        meta["pageOrder"].append(page_name)
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def set_page_order(order: list[str]) -> None:
    """Fix pages.json order (visible pages first, hidden pages last); the active page stays the first one."""
    meta_file = PAGES / "pages.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    known = [p for p in order if (PAGES / p).is_dir()]
    meta["pageOrder"] = known + [p for p in meta["pageOrder"] if p not in known]
    meta["activePageName"] = known[0]
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
