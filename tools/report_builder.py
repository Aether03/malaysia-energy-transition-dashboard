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
    ("State reliability", "p3b_state_reliability"),
    ("Grid load", "p4_grid_load"),
    ("Forecast", "p4b_forecast"),
    ("ASEAN", "p5_asean"),
    ("About", "p6_about"),
    ("Data quality", "p6b_data_quality"),
)
# The ⓘ button sits at the foot of the nav rail, level with the footnote: in the header it cut the
# longest takeaway titles to 800 px (M5 GUI round 1). White on the navy rail.
TITLE_W = 840
INFO_X, INFO_Y, INFO_SIZE = 12, FOOTNOTE_Y + 6, 32
BADGE_SIZE = 20
TAB_ORDER_TOP = 1000  # above every z in use (footnotes are 99)
ABOUT_PAGE = "p6_about"
DQ_PAGE = "p6b_data_quality"
INFO_TOOLTIP = "About the data: sources, licences and data quality"
# Visuals that carry no information (background and selection bars, an arrow glyph): no alt text, and not
# in the tab order. Every other visual must have alt text (tools/validate_report.py).
DECORATIVE = frozenset({"frame_rail", "frame_nav_selected", "p1_rank_arrow"})


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


def container(title: str | None, title_measure: str | None = None, subtitle_measure: str | None = None) -> dict:
    """Title block. `title_measure` binds the title text to a measure (e.g. 'Capacity Factor Title').

    `subtitle_measure` shows a measure-bound subtitle under the title (9 pt, muted). It is evaluated in
    the visual's own filter context, so a per-region card can carry per-region years (P3).
    """
    # Subtitles are auto-generated from field names ("X by year and display_name"): hidden unless a
    # measure is bound on purpose.
    hidden_subtitle = [{"properties": {"show": lit("false")}}]
    if subtitle_measure:
        hidden_subtitle = [
            {
                "properties": {
                    "show": lit("true"),
                    "text": {"expr": measure_ref(subtitle_measure)},
                    "fontSize": lit("9D"),
                    "fontColor": solid(TEXT_MUTED),
                }
            }
        ]
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
    alt: str | None = None,
) -> dict:
    """One visual container. `alt` is the screen-reader description (visualContainerObjects.general.altText,
    the shape Desktop writes: tools/templates/table_status_chip_alt_tooltip.json). Describe what the visual
    shows and its encoding, never data values. Only the names in DECORATIVE go without."""
    if alt:
        # A new dict: `body["visualContainerObjects"]` may be the shared BARE constant.
        body["visualContainerObjects"] = {
            **body.get("visualContainerObjects", {}),
            "general": [{"properties": {"altText": text(alt)}}],
        }
    position = {"x": x, "y": y, "z": z, "width": w, "height": h}
    if tab:
        # Desktop focuses the HIGHEST tabOrder first (its Tab order pane lists it as 1; M5 GUI round 2), so
        # reading order = ascending z is written as a descending tabOrder.
        position["tabOrder"] = TAB_ORDER_TOP - z
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


def tooltip_fields(body: dict, measures: list[str]) -> dict:
    """Add measures to a visual's built-in tooltip (the Tooltips well), skipping any already bound.

    For visuals without a report-page tooltip (P3, P3b, P4b cards). Report-page tooltips do render when
    written the way Desktop writes them (see tooltip_page; M5 step 1), so a visual with a tooltip page
    uses that instead and keeps no built-in fields.
    """
    state = body["query"]["queryState"]
    bound = {p["queryRef"] for role in state.values() for p in role.get("projections", [])}
    extra = [projection(measure_ref(m)) for m in measures if f"_Measures.{m}" not in bound]
    if extra:
        state.setdefault("Tooltips", {"projections": []})["projections"].extend(extra)
    return body


def tooltip_page(body: dict, page_name: str) -> dict:
    """Assign a report-page tooltip to a visual (visualContainerObjects.visualTooltip).

    Desktop writes only `show` and `section` (tools/templates/table_status_chip_alt_tooltip.json, M5 step 1).
    An extra `type: 'ReportPage'` property, which the M2 builds wrote, is what stopped the tooltip page
    rendering. The page replaces the visual's built-in tooltip.
    """
    body["visualContainerObjects"] = {
        **body.get("visualContainerObjects", {}),
        "visualTooltip": [{"properties": {"show": lit("true"), "section": text(page_name)}}],
    }
    return body


# ---------- components ----------
# Invisible in every button state: without hover/press entries Desktop paints the theme's first
# colour (coal brown) on hover (GUI round 7).
CLEAR_BUTTON_FILL = [
    {"properties": {"show": lit("true")}},
    *(
        {"properties": {"fillColor": solid(NAVY), "transparency": lit("100D")}, "selector": {"id": state}}
        for state in ("default", "hover", "press")
    ),
]

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
    fill_measure: str | None = None,
    tile: str = "rectangle",
) -> dict:
    """Rectangle or oval (templates: shape_measure_title.json, shape_fill_measure.json). `text_value` is
    text() or a measure expr; `fill_measure` binds the fill colour to a measure returning a hex string.

    `boxed` keeps the theme's card background and border on the container (instead of BARE) so a
    text shape reads as a card; the shape fill itself stays transparent.
    """
    objects: dict = {
        "shape": [{"properties": {"tileShape": text(tile)}}],
        "rotation": [{"properties": {"shapeAngle": lit("0L")}}],
        # `show` goes in a selector-free entry and colours in the {"id": "default"} state entry,
        # as Desktop writes them; a `show` inside the state entry is ignored (P1 test, M2 step 6).
        "fill": [
            {"properties": {"show": lit("true")}},
            {
                "properties": {
                    "fillColor": {"solid": {"color": {"expr": measure_ref(fill_measure)}}}
                    if fill_measure
                    else solid(fill or SURFACE_CARD),
                    "transparency": lit("0D" if fill or fill_measure else "100D"),
                },
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
            "fill": CLEAR_BUTTON_FILL,
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


def nav_overlay(page_name: str, tooltip: str | None = None) -> dict:
    """Transparent blank button for a card that must be clickable (cards cannot carry a reliable
    page-navigation action). Lay it exactly over the card, above it in z order. `tooltip` is the
    button's hover text (it covers the card, so the card's own tooltip can't show)."""
    return {
        "visualType": "actionButton",
        "objects": {
            "icon": [{"properties": {"shapeType": text("blank")}, "selector": {"id": "default"}}],
            "fill": CLEAR_BUTTON_FILL,
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
                        **({"enabledTooltip": text(tooltip)} if tooltip else {}),
                    }
                }
            ],
        },
        "drillFilterOtherVisuals": True,
    }


def info_button(page_name: str, tooltip: str) -> dict:
    """ⓘ button with a page-navigation action (the icon from tools/templates/button_info_weburl.json,
    the action from nav_overlay: Desktop wrote 'WebUrl' there, here it is 'PageNavigation')."""
    body = nav_overlay(page_name, tooltip)
    body["objects"]["icon"] = [
        {"properties": {"shapeType": text("information"), "lineColor": solid(NAV_TEXT)}, "selector": {"id": "default"}}
    ]
    return body


def fail_badge(page_name: str) -> dict:
    """20 x 20 oval over the Data quality nav button: fill = [DQ Fail Badge Fill] (rail navy when nothing
    fails, so it vanishes), text = [DQ Fail Badge Text] (blank at 0). A click on it navigates like the button."""
    body = shape(
        None,
        {"expr": measure_ref("DQ Fail Badge Text")},
        9,
        NAV_TEXT,
        "Segoe UI Semibold",
        align="center",
        fill_measure="DQ Fail Badge Fill",
        tile="oval",
    )
    body["visualContainerObjects"] = {
        **BARE,
        "visualLink": [{"properties": {"show": lit("true"), "type": text("PageNavigation"), "navigationSection": text(page_name)}}],
    }
    return body


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


def table(
    title: str,
    columns: list[tuple[dict, str, int]],
    sort: list[tuple[dict, str]] | None = None,
    extra_values: list[dict] | None = None,
    font_size: int = 9,
) -> dict:
    """Table visual `tableEx` (shape: tools/templates/table_status_chip_alt_tooltip.json, M5 step 1).

    `columns` = (field, header text, width px); the width goes in objects.columnWidth keyed by the
    projection's queryRef. `sort` = (field, "Ascending" | "Descending"). `extra_values` are selector
    entries appended to objects.values (conditional formats). Header and cells are `font_size` pt
    (Desktop's header minimum is 8 pt), totals are off, and the container padding is 4 px: the theme's
    14-16 px padding would cost a table 30 px of height. Long cell text wraps, so a table scrolls.
    """
    projections = [{**projection(field), "displayName": header} for field, header, _ in columns]
    query: dict = {"queryState": {"Values": {"projections": projections}}}
    if sort:
        query["sortDefinition"] = {"sort": [{"field": f, "direction": d} for f, d in sort]}
    return {
        "visualType": "tableEx",
        "query": query,
        "objects": {
            "columnWidth": [
                {"properties": {"value": lit(f"{width}D")}, "selector": {"metadata": proj["queryRef"]}}
                for proj, (_, _, width) in zip(projections, columns)
            ],
            "columnHeaders": [{"properties": {"fontSize": lit(f"{font_size}D")}}],
            # `urlIcon` shows a WebUrl column as a link icon (a long URL would wrap over many lines).
            "values": [{"properties": {"fontSize": lit(f"{font_size}D"), "urlIcon": lit("true")}}, *(extra_values or [])],
            "grid": [{"properties": {"rowPadding": lit("3D")}}],
            "total": [{"properties": {"totals": lit("false")}}],
        },
        "visualContainerObjects": {
            **container(title),
            "padding": [{"properties": {side: lit("4D") for side in ("left", "top", "right", "bottom")}}],
        },
        "drillFilterOtherVisuals": True,
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
    """Default fill for every series/category (muted) plus one highlighted value (doc 04 §3.3).

    Line series ignore the selector-free default (GUI round 5), so every country in the seed
    also gets its own explicit muted entry.
    """
    with (ROOT / "seed" / "dim_country.csv").open(encoding="utf-8-sig", newline="") as fh:
        names = [row["name"] for row in csv.DictReader(fh) if row["area_type"] == "COUNTRY" and row["name"] != value]
    return [
        {"properties": {"fill": solid(others)}},
        *({"properties": {"fill": solid(others)}, "selector": series_selector(table, column, n)} for n in names),
        {"properties": {"fill": solid(highlight)}, "selector": series_selector(table, column, value)},
    ]


def measure_colours(colours: dict[str, str]) -> list[dict]:
    """dataPoint fills per measure (multi-measure charts), keyed by queryRef."""
    return [
        {"properties": {"fill": solid(hex_colour)}, "selector": {"metadata": f"_Measures.{measure}"}}
        for measure, hex_colour in colours.items()
    ]


# ---------- slicers and field parameters ----------
def param_role(table: str, default_measure: str, default_label: str) -> dict:
    """A chart value well driven by a field parameter ('Mix Unit', 'ASEAN Metric').

    Desktop's shape (saved in M2 GUI round 4): the projection is the currently selected measure,
    and `fieldParameters` points at the parameter column. Binding the parameter column itself
    fails with "Can't determine relationships between the fields".
    """
    return {
        "projections": [{**projection(measure_ref(default_measure)), "nativeQueryRef": default_label, "displayName": default_label}],
        "fieldParameters": [{"parameterExpr": column_ref(table, table), "index": 0, "length": 1}],
    }


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
    default: list[str] | None = None,
) -> dict:
    """Slicer body. mode: 'Dropdown', 'Basic' (list/tiles) or 'Between' (numeric range).

    `default` is the saved selection, stored in objects.general.filter like Desktop does. A filter in
    the slicer's own filterConfig would hide the other options instead (M2 GUI round 3).
    """
    objects: dict = {
        "data": [{"properties": {"mode": text(mode)}}],
        "header": [{"properties": {"show": lit("true"), "text": text(header), "fontSize": lit("9D")}}],
    }
    if mode != "Between":
        objects["selection"] = [{"properties": {"singleSelect": lit("true" if single else "false")}}]
    general: dict = {}
    if horizontal:
        general["orientation"] = lit("1L")  # 0 = vertical, 1 = horizontal
    if default:
        general["filter"] = {"filter": in_filter(table, column, default, f"{table}.{column}")["filters"][0]["filter"]}
    if general:
        objects["general"] = [{"properties": general}]
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


BOOKMARKS = ROOT / "report" / "EnergyTransition.Report" / "definition" / "bookmarks"


def page_bookmark(page_name: str) -> str | None:
    """Name of the "Reset ..." bookmark Amirul created in Desktop for this page (doc 03 A4), if any."""
    for path in sorted(BOOKMARKS.glob("*.bookmark.json")):
        b = json.loads(path.read_text(encoding="utf-8"))
        if b.get("displayName", "").startswith("Reset") and b.get("explorationState", {}).get("activeSection") == page_name:
            return b["name"]
    return None


def reset_button(bookmark_name: str) -> dict:
    """Nav-rail button that applies the page's Reset bookmark (default slicers and filters)."""
    body = nav_button("↺  Reset filters", "", False)
    body["visualContainerObjects"]["visualLink"] = [
        {"properties": {"show": lit("true"), "type": text("Bookmark"), "bookmark": text(bookmark_name)}}
    ]
    return body


# ---------- page frame ----------
def frame(
    page_name: str,
    title_measure: str | None,
    subtitle_measure: str | None,
    footnote_text: str | None,
    footnote_measure: str | None = None,
    title_size: int = 20,
    title_text: str | None = None,
    subtitle_text: str | None = None,
) -> list[dict]:
    """Nav rail, takeaway title, scope/as-of subtitle, footnote strip, the ⓘ button and the Fail badge
    (doc 03 A3, doc 04 §4).

    The footnote is static text, or bound to a measure (a boxed text shape) when `footnote_measure` is set.
    `title_size` (pt) lets a page with a long takeaway title (P3, P3b) drop to 16 pt, so two lines fit the 44 px box.
    `title_text` / `subtitle_text` give a static title or subtitle (About and Data quality have no measure for them).

    z order = tab order (the tab=True visuals): nav buttons 2-10, Reset 15, title 30, subtitle 31, the ⓘ button
    32, page content from 40, footnote 99. The badge (z 16) sits above its nav button and is not a tab stop.
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
            alt="Report name: Malaysia Energy Transition",
        ),
    ]
    existing = [(label, name) for label, name in NAV if (PAGES / name).is_dir()]
    bookmark = page_bookmark(page_name)
    if bookmark:
        y = BODY_Y + len(existing) * 48 + 24
        visuals.append(
            visual("frame_reset", 8, y, 160, 44, 15, reset_button(bookmark), alt="Button: reset this page's filters and slicers to their defaults")
        )
    for i, (label, name) in enumerate(existing):
        y = BODY_Y + i * 48
        here = name == page_name
        visuals.append(
            visual(
                f"frame_nav_{i}", 8, y, 160, 44, 2 + i, nav_button(label, name, here),
                alt=f"Navigation button: {label} page" + (" (the current page)" if here else ""),
            )
        )
        if here:
            visuals.append(visual("frame_nav_selected", 0, y + 6, 4, 32, 20, shape(NAV_SELECTED_BAR), tab=False))
        if name == DQ_PAGE:
            visuals.append(
                visual(
                    "frame_nav_badge", 8 + 160 - BADGE_SIZE - 4, y + (44 - BADGE_SIZE) / 2, BADGE_SIZE, BADGE_SIZE, 16,
                    fail_badge(name), tab=False,
                    alt="Badge on the Data quality button: how many data-quality rules failed in the latest run; empty when none failed",
                )
            )
    if footnote_measure:
        footnote_body = shape(
            None, {"expr": measure_ref(footnote_measure)}, 9, TEXT_MUTED, v_align="top", boxed=True, left_margin=4
        )
    else:
        footnote_body = footnote(footnote_text or "")
    title_value = text(title_text) if title_text else {"expr": measure_ref(title_measure)}
    subtitle_value = text(subtitle_text) if subtitle_text else {"expr": measure_ref(subtitle_measure)}
    visuals += [
        visual(
            "frame_title",
            CONTENT_X,
            HEADER_Y,
            TITLE_W,
            44,
            30,
            shape(None, title_value, title_size, TEXT_PRIMARY, "Segoe UI Semibold"),
            alt="Page title: the main takeaway of this page as one sentence",
        ),
        visual(
            "frame_subtitle",
            CONTENT_X,
            HEADER_Y + 44,
            TITLE_W,
            28,
            31,
            shape(None, subtitle_value, 11, TEXT_SECONDARY),
            alt="Page scope line: what this page covers and when the data was refreshed",
        ),
        visual(
            "frame_info", INFO_X, INFO_Y, INFO_SIZE, INFO_SIZE, 32, info_button(ABOUT_PAGE, INFO_TOOLTIP),
            alt="Button: open the About page, with sources, licences and data quality",
        ),
        visual(
            "frame_footnote", CONTENT_X, FOOTNOTE_Y, CONTENT_W, 44, 99, footnote_body,
            alt="Footnote: sources, licences and caveats for this page",
        ),
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


REPORT_DIR = ROOT / "report" / "EnergyTransition.Report"
REGISTERED_RESOURCES = REPORT_DIR / "StaticResources" / "RegisteredResources"
REPORT_JSON = REPORT_DIR / "definition" / "report.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register_shape_map(source: Path, file_name: str) -> dict:
    """Register a TopoJSON as a Shape Map resource (M4 step 11; the layout Desktop 2.158 itself writes).

    Copies `source` byte-identically to StaticResources/RegisteredResources/<file_name> (SHA-256 asserted
    equal) and adds {"name", "path", "type": "ShapeMap"} to the report.json "RegisteredResources" package.
    Idempotent: nothing is rewritten when the copy and the entry already exist. Returns the entry.
    """
    target = REGISTERED_RESOURCES / file_name
    if not target.exists() or _sha256(target) != _sha256(source):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    assert _sha256(target) == _sha256(source), f"{file_name} is not byte-identical to {source.name}"

    entry = {"name": file_name, "path": file_name, "type": "ShapeMap"}
    raw = REPORT_JSON.read_bytes()
    report = json.loads(raw.decode("utf-8"))
    package = next(p for p in report["resourcePackages"] if p["name"] == "RegisteredResources")
    if not any(item["name"] == file_name for item in package["items"]):
        package["items"].append(entry)
        out = json.dumps(report, indent=2, ensure_ascii=False)
        if b"\r\n" in raw:  # keep the file's own CRLF line endings (and its missing final newline)
            out = out.replace("\n", "\r\n")
        REPORT_JSON.write_bytes(out.encode("utf-8"))
    return entry


def set_page_order(order: list[str]) -> None:
    """Fix pages.json order (visible pages first, hidden pages last); the active page stays the first one."""
    meta_file = PAGES / "pages.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    known = [p for p in order if (PAGES / p).is_dir()]
    meta["pageOrder"] = known + [p for p in meta["pageOrder"] if p not in known]
    meta["activePageName"] = known[0]
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
