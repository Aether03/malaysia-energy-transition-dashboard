"""Build the P3 Regions page as PBIR visual definitions (M4 step 11, doc 03 P3 as amended by the M4 plan Q5/Q9).

Layout (1280x720 frame, doc 04 §4): header (takeaway title, subtitle); row 1 = three region cards
(Peninsular, Sabah, Sarawak: installed MW, available MW, consumption GWh, use per person, SAIFI, each
with the years it is for); row 2 = installed-capacity mix by region (100% stacked column) | consumption
by year; row 3 = SAIFI by region with the Sabah / Peninsular ratio in its title | supply interruptions
by year; a note strip with the Q4 disclosures. Region cards neither filter nor navigate (plan Q9).

Q1 licence rules: no table or matrix, no data labels (values are in the hover), every chart adds
something derived. Re-running rebuilds the page.

    .venv/Scripts/python tools/build_p3_page.py
"""

from __future__ import annotations

import csv

import build_p4_page as p4
import report_builder as rb
from report_builder import column_ref, lit, measure_ref, projection, text, visual

PAGE = "p3_regions"

# --- geometry (1280x720 frame; limits are Desktop 2.158's, from the M3 GUI rounds)
# GUI round 1: five callouts in one row were truncated, so the cards use a 3-column table layout whose
# second tile row needs height: cards 168 px (title, years subtitle, two tile rows).
CARDS_Y, CARDS_H = rb.BODY_Y, 168
ROW_GAP = rb.GAP
# The plan budgets rows 2 and 3 at 200 px each; the cards and the note strip take the rest. Legends need
# ~140 px, charts ~120 px: 168 is fine.
ROW2_Y, ROW_H = CARDS_Y + CARDS_H + ROW_GAP, 168  # 288
ROW3_Y = ROW2_Y + ROW_H + ROW_GAP  # 472
NOTE_Y = ROW3_Y + ROW_H + 4  # 644
NOTE_H = 20  # one 9 pt line at 1056 px; ends at y 664, 8 px above the footnote strip
COL_W = (rb.CONTENT_W - rb.GAP) / 2  # 520
COL2_X = rb.CONTENT_X + COL_W + rb.GAP
# Three cards across 1056 px with two 16 px gaps: 341 + 342 + 341 = 1024, plus 32 = 1056.
CARD_WIDTHS = (341, 342, 341)

# Region series colours (all P3 charts, bound per region so a filter never shifts them).
# Distinct from the 7 energy-source hues of doc 04 §3.2 (they share the page): the source palette
# has no magenta and no neutral, so the regions use plum, orchid and text.secondary charcoal.
# Checked with CIEDE2000 (and Machado CVD simulations) against the seven source colours: every region
# colour is >= 18.6 apart from every source colour for normal vision and >= 10.3 under protan, deutan
# and tritan; pairwise between regions >= 16.3 under every simulation; all three reach >= 3.8:1 on
# surface.card, so lines and bars pass the 3:1 graphics rule.
REGION_COLOURS = {"Peninsular Malaysia": "#730d62", "Sabah": "#bc629e", "Sarawak": rb.TEXT_SECONDARY}


def region_names() -> list[tuple[str, str]]:
    """(region_code, name) from the seed, in display order."""
    with (rb.ROOT / "seed" / "dim_region.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = sorted(csv.DictReader(fh), key=lambda r: int(r["display_order"]))
    return [(r["region_code"], r["name"]) for r in rows]


def region_colours() -> dict[str, str]:
    names = [name for _, name in region_names()]
    assert set(names) == set(REGION_COLOURS), f"REGION_COLOURS out of step with seed/dim_region.csv: {names}"
    return REGION_COLOURS


# ---------- row 1: region cards ----------
# (measure, callout label). New card (template card_new.json, cardVisual): every callout is a field of the
# Data role; the label sits under the value.
# GUI round 2: labels over ~10 characters truncate in a 3-column tile, so the capacity unit (MW) moved
# into the card subtitle ([Region Card Note]).
CALLOUTS = [
    ("Region Installed (MW)", "Installed"),
    ("Region Available (MW)", "Available"),
    ("Region Consumption (GWh)", "Use GWh"),
    ("Region Use per Person (kWh)", "kWh/head"),
    ("Region SAIFI", "SAIFI"),
]


def region_card(name: str) -> dict:
    """One region's card. Title = region name; the subtitle is [Region Card Note], the years each value
    is for, evaluated in the card's own region filter (a text shape could not see that filter)."""
    return {
        "visualType": "cardVisual",
        "query": {
            "queryState": {
                "Data": {"projections": [{**projection(measure_ref(m)), "displayName": label} for m, label in CALLOUTS]}
            }
        },
        "objects": {
            # Desktop-captured (GUI round 1): `value` fontSize and `label` objects were accepted. One `value`
            # entry per callout (labelDisplayUnits 1 = none) stops "29K" auto units; the 3-column table layout
            # stops the five callouts truncating in one row.
            "value": [
                {"properties": {"fontSize": lit("14D")}},
                *(
                    {"properties": {"labelDisplayUnits": lit("1D")}, "selector": {"metadata": f"_Measures.{m}"}}
                    for m, _ in CALLOUTS
                ),
            ],
            "label": [{"properties": {"fontSize": lit("8D"), "color": rb.solid(rb.TEXT_SECONDARY)}}],
            # orientation 0 = Grid (Desktop-captured, GUI round 2): wraps to 3 + 2 tiles. Without it the
            # table stays one horizontal row that scrolls and hides the last two callouts.
            "layout": [{"properties": {"style": lit("'Table'"), "columnCount": lit("3L"), "orientation": lit("0D")}}],
        },
        "visualContainerObjects": rb.container(name, subtitle_measure="Region Card Note"),
        "drillFilterOtherVisuals": True,
    }


# ---------- charts ----------
def legend_top() -> list[dict]:
    return [{"properties": {"show": lit("true"), "position": text("Top")}}]


# Fuel groups present in the capacity tables, in doc 04 stacking order (no wind in Malaysia's tables).
CAPACITY_SOURCES = ("Coal", "Other fossil", "Gas", "Hydro", "Bioenergy", "Solar")


def capacity_mix() -> dict:
    """Installed capacity by fuel group, horizontal 100% stacked bars; colours bound per source (doc 04 §3.2).

    GUI rounds 1-2 at 168 px: with the built-in legend on top, the bars scroll (one or two of three visible);
    as columns, Desktop hides the region axis for lack of height ("Peninsular Malaysia" wraps); the legend
    refuses a side position at this size. Without the legend all three bars fit, so the legend is drawn
    by `capacity_legend()` on the title line instead.
    """
    return {
        "visualType": "hundredPercentStackedBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_region", "name"), True)]},
                "Series": {"projections": [projection(column_ref("dim_source", "display_name"))]},
                "Y": {"projections": [projection(measure_ref("Region Installed by Fuel (MW)"))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("false")}}],
            "dataPoint": rb.series_colours("dim_source", "display_name", rb.source_colours()),
        },
        "visualContainerObjects": rb.container("Capacity mix, 2021"),
        "drillFilterOtherVisuals": True,
    }


def capacity_legend() -> dict:
    """Static legend for capacity_mix: one right-aligned paragraph of coloured squares and source names."""
    colours = rb.source_colours()
    runs = []
    for name in CAPACITY_SOURCES:
        runs.append({"value": "■ ", "textStyle": {"fontSize": "9pt", "color": colours[name]}})
        runs.append({"value": f"{name}  ", "textStyle": {"fontSize": "8pt", "color": rb.TEXT_SECONDARY}})
    return {
        "visualType": "textbox",
        "objects": {
            "general": [{"properties": {"paragraphs": [{"textRuns": runs, "horizontalTextAlignment": "right"}]}}]
        },
        "visualContainerObjects": rb.BARE,
    }


def region_line(measure: str, title: str) -> dict:
    """One line per region on dim_year[year], explicit colour per region (line series ignore a default)."""
    return {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_year", "year"), True)]},
                "Series": {"projections": [projection(column_ref("dim_region", "name"))]},
                "Y": {"projections": [projection(measure_ref(measure))]},
            }
        },
        "objects": {
            "legend": legend_top(),
            "dataPoint": rb.series_colours("dim_region", "name", region_colours()),
            "lineStyles": [{"properties": {"strokeWidth": lit("2D")}}],
            # labelDisplayUnits 1 = none: ticks read in full with separators, not "0.1M" (GUI round 1).
            "valueAxis": [{"properties": {"labelDisplayUnits": lit("1D")}}],
        },
        "visualContainerObjects": rb.container(title),
        "drillFilterOtherVisuals": True,
    }


def saifi_bar() -> dict:
    """SAIFI by region at each region's latest year; the title carries the Sabah / Peninsular ratio.
    No data labels (plan Q1): the values and the year are in the hover."""
    body = {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_region", "name"), True)]},
                "Y": {"projections": [projection(measure_ref("Region SAIFI"))]},
            }
        },
        "objects": {
            "legend": [{"properties": {"show": lit("false")}}],
            "dataPoint": rb.series_colours("dim_region", "name", region_colours()),
        },
        "visualContainerObjects": rb.container(None, "P3 SAIFI Bar Title"),
        "drillFilterOtherVisuals": True,
    }
    rb.tooltip_fields(body, ["Region SAIFI Year"])
    for p in body["query"]["queryState"]["Tooltips"]["projections"]:
        p["displayName"] = "Year"
    return body


def build() -> list[dict]:
    visuals = rb.frame(PAGE, "P3 Title", "P3 Subtitle", None, footnote_measure="P3 Footnote", title_size=16)

    # --- row 1: one card per region, each filtered by region_code (cards don't filter or navigate, plan Q9)
    x = rb.CONTENT_X
    for i, ((code, name), w) in enumerate(zip(region_names(), CARD_WIDTHS)):
        visuals.append(
            visual(
                f"p3_card_{code.lower()}",
                x,
                CARDS_Y,
                w,
                CARDS_H,
                50 + i,
                region_card(name),
                filter_config=rb.in_filter("dim_region", "region_code", [code], f"p3_card_{code}"),
                alt=f"Card: {name} at a glance, with installed and available capacity, consumption, use per person and SAIFI, each for its latest year",
            )
        )
        x += w + rb.GAP

    # --- row 2: capacity mix | consumption by year
    visuals.append(
        visual(
            "p3_capacity_mix",
            rb.CONTENT_X,
            ROW2_Y,
            COL_W,
            ROW_H,
            60,
            capacity_mix(),
            alt="100% stacked bar chart: installed capacity by fuel group for each of the three regions; one colour per fuel group",
        )
    )
    # On the chart's title line, right of the ~150 px title (GUI round 2: at 312 px "Solar" wrapped); above the chart in z order.
    visuals.append(
        visual(
            "p3_capacity_legend",
            rb.CONTENT_X + 176,
            ROW2_Y + 6,
            COL_W - 184,
            28,
            66,
            capacity_legend(),
            tab=False,
            alt="Legend: the colour of each fuel group in the capacity mix chart",
        )
    )
    visuals.append(
        visual(
            "p3_consumption_line",
            COL2_X,
            ROW2_Y,
            COL_W,
            ROW_H,
            61,
            region_line("Region Consumption by Year (GWh)", "Electricity consumption by region (GWh)"),
            alt="Line chart: electricity consumption per year in GWh, one line per region",
        )
    )

    # --- row 3: SAIFI by region | supply interruptions by year
    visuals.append(
        visual(
            "p3_saifi_bar",
            rb.CONTENT_X,
            ROW3_Y,
            COL_W,
            ROW_H,
            62,
            saifi_bar(),
            alt="Bar chart: SAIFI (supply interruptions per customer) for each region at its latest year",
        )
    )
    visuals.append(
        visual(
            "p3_interruptions_line",
            COL2_X,
            ROW3_Y,
            COL_W,
            ROW_H,
            63,
            region_line("Region Interruptions by Year", "Supply interruptions by region (number per year)"),
            alt="Line chart: number of supply interruptions per year, one line per region",
        )
    )

    # --- note strip: the Q4 disclosures moved out of the footnote (the footnote keeps source + consent)
    visuals.append(
        visual(
            "p3_note",
            rb.CONTENT_X,
            NOTE_Y,
            rb.CONTENT_W,
            NOTE_H,
            64,
            p4.note("P3 Note"),
            alt="Note: disclosures about how the regional figures are defined",
        )
    )
    return visuals


def main() -> None:
    visuals = build()
    rb.write_page(PAGE, "Regions", visuals)
    print(f"Wrote {len(visuals)} visuals to the Regions page")


if __name__ == "__main__":
    main()
