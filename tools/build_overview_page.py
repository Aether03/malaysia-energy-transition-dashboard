"""Build the P1 Overview page (thin, M1 step 9) as PBIR visual definitions.

Layout and styling follow doc 04 (1280x720 canvas, Segoe UI, measured colours); content
follows doc 03 P1. The query shapes mirror visuals saved by Power BI Desktop (commit
5efb683). Re-running rebuilds the page from scratch.

    .venv/Scripts/python tools/build_overview_page.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "report" / "EnergyTransition.Report" / "definition" / "pages"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"

TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED = "#0b0b0b", "#52514e", "#6b6a66"
NAVY, TARGET_RED = "#104281", "#d03b3b"


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


def container(title: str | None) -> dict:
    # Subtitles are auto-generated from field names ("X by year and display_name"): always hidden.
    hidden_subtitle = [{"properties": {"show": lit("false")}}]
    if title is None:
        return {"title": [{"properties": {"show": lit("false")}}], "subTitle": hidden_subtitle}
    return {
        "title": [
            {
                "properties": {
                    "show": lit("true"),
                    "text": text(title),
                    "fontSize": lit("12D"),
                    "fontColor": solid(TEXT_PRIMARY),
                }
            }
        ],
        "subTitle": hidden_subtitle,
    }


def visual(name: str, x: int, y: int, w: int, h: int, z: int, body: dict) -> dict:
    return {
        "$schema": SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": body,
    }


def card(measure: str, size: int, colour: dict, show_label: bool, title: str | None = None) -> dict:
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
        "visualContainerObjects": container(title),
        "drillFilterOtherVisuals": True,
    }


def build() -> list[dict]:
    visuals = [
        # Cards need about 40 px or more to render text; smaller boxes show blank (first Desktop test).
        visual("p1_title", 24, 6, 1010, 56, 1, card("Overview Title", 16, solid(TEXT_PRIMARY), False)),
        visual("p1_as_of", 24, 58, 400, 40, 2, card("Data As Of", 10, solid(TEXT_SECONDARY), False)),
    ]

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
    visuals.append(visual("p1_year_slicer", 1046, 12, 210, 64, 3, slicer))

    kpis = [  # (measure, delta label, delta colour measure or None)
        ("Total Generation (TWh)", "Total Generation Delta Label", None),
        ("RE Share (%)", "RE Share Delta Label", "RE Share Delta Color"),
        ("Fossil Share (%)", "Fossil Share Delta Label", "Fossil Share Delta Color"),
        ("Carbon Intensity (gCO2e/kWh)", "Carbon Intensity Delta Label", "Carbon Intensity Delta Color"),
    ]
    width, gap, x = 296, 16, 24
    for i, (measure, delta, colour_measure) in enumerate(kpis):
        kx = x + i * (width + gap)
        visuals.append(visual(f"p1_kpi_{i}", kx, 100, width, 104, 10 + i, card(measure, 28, solid(TEXT_PRIMARY), True)))
        delta_colour = {"solid": {"color": {"expr": measure_ref(colour_measure)}}} if colour_measure else solid(TEXT_SECONDARY)
        visuals.append(visual(f"p1_kpi_delta_{i}", kx, 204, width, 44, 20 + i, card(delta, 10, delta_colour, False)))

    area = {
        "visualType": "stackedAreaChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(column_ref("dim_year", "year"), True)]},
                "Series": {"projections": [projection(column_ref("dim_source", "display_name"))]},
                "Y": {"projections": [projection(measure_ref("Focus Generation (TWh)"))]},
            }
        },
        "objects": {"legend": [{"properties": {"show": lit("true"), "position": text("Top")}}]},
        "visualContainerObjects": container("Malaysia's generation mix by source (TWh), all years"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(visual("p1_mix_area", 24, 260, 800, 380, 30, area))

    gauge = {
        "visualType": "gauge",
        "query": {
            "queryState": {
                "Y": {"projections": [projection(measure_ref("RE Capacity Share (%)"))]},
                "TargetValue": {"projections": [projection(measure_ref("NETR Target (%)"))]},
            }
        },
        "objects": {
            "axis": [{"properties": {"min": lit("0D"), "max": lit("100D")}}],
            "dataPoint": [{"properties": {"fill": solid(NAVY), "target": solid(TARGET_RED)}}],
        },
        "visualContainerObjects": container("Renewable capacity share vs NETR target (%)"),
        "drillFilterOtherVisuals": True,
    }
    visuals.append(visual("p1_netr_gauge", 840, 260, 416, 280, 31, gauge))
    visuals.append(
        visual("p1_netr_label", 840, 540, 416, 100, 32, card("NETR Progress Label", 11, solid(TEXT_SECONDARY), False))
    )

    footnote = {
        "visualType": "textbox",
        "objects": {
            "general": [
                {
                    "properties": {
                        "paragraphs": [
                            {
                                "textRuns": [
                                    {
                                        "value": (
                                            "Sources: Ember Yearly Electricity Data (CC BY 4.0); NETR targets via MIDA/IEA. "
                                            "Large hydro counted as renewable capacity (to be verified against the NETR text). "
                                            "KPIs describe Malaysia in the selected year."
                                        ),
                                        "textStyle": {"fontSize": "9pt", "color": TEXT_MUTED},
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        },
        "visualContainerObjects": container(None),
    }
    visuals.append(visual("p1_footnote", 24, 652, 1232, 48, 40, footnote))
    return visuals


def main() -> None:
    page_dir = next(p for p in PAGES.iterdir() if p.is_dir())
    visuals_dir = page_dir / "visuals"
    if visuals_dir.exists():
        shutil.rmtree(visuals_dir)
    for v in build():
        target = visuals_dir / v["name"] / "visual.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

    page_file = page_dir / "page.json"
    page = json.loads(page_file.read_text(encoding="utf-8"))
    page.update({"displayName": "Overview", "width": 1280, "height": 720, "displayOption": "FitToPage"})
    # The mix chart shows every year; the year slicer must not filter it (doc 03 P1).
    page["visualInteractions"] = [{"source": "p1_year_slicer", "target": "p1_mix_area", "type": "NoFilter"}]
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Wrote {len(build())} visuals to {visuals_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
