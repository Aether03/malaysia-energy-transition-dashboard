"""No information left behind (M6 plan Q1, Amirul): every item on the mirrored report pages that carries data or
text maps to an element of the web showcase in app/coverage.json ("<page folder>/<visual folder>": "where").

Layout is exempt: nav-rail buttons (page navigation, incl. the info button: st.navigation does that job), shapes
without text (frames, selected-state bars) and the rail's brand text (the app's page title)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "report" / "EnergyTransition.Report" / "definition" / "pages"
# P1, the Country Deep Dive, P2, P4, P4b, P5, P6, P6b and the T2 tooltip. P3/P3b wait on consent (plan Q2).
MIRRORED = (
    "59dacfc5089b163e62a0",
    "d1_country",
    "p2_generation",
    "p4_grid_load",
    "p4b_forecast",
    "p5_asean",
    "p6_about",
    "p6b_data_quality",
    "t2_country",
)


def is_layout(name: str, visual: dict) -> bool:
    text = json.dumps(visual)
    kind = visual.get("visual", {}).get("visualType")
    has_text = '"text"' in text or "paragraphs" in text
    if name == "frame_brand":
        return True
    if kind == "actionButton" and "PageNavigation" in text:
        return True
    return kind == "shape" and not has_text


def inventory() -> list[str]:
    items = []
    for page in MIRRORED:
        for path in sorted((PAGES / page / "visuals").glob("*/visual.json")):
            if not is_layout(path.parent.name, json.loads(path.read_text(encoding="utf-8"))):
                items.append(f"{page}/{path.parent.name}")
    return items


def test_layout_rules_keep_the_information():
    items = inventory()
    assert "59dacfc5089b163e62a0/p1_kpi_0" in items  # a KPI card
    assert "p6b_data_quality/p6b_status_slicer" in items  # a slicer
    assert "59dacfc5089b163e62a0/frame_footnote" in items  # the source credits
    assert "59dacfc5089b163e62a0/frame_nav_badge" in items  # the Fail badge is information, not layout
    assert "59dacfc5089b163e62a0/frame_nav_0" not in items


def test_every_item_maps_to_the_app():
    coverage = json.loads((ROOT / "app" / "coverage.json").read_text(encoding="utf-8"))
    missing = [i for i in inventory() if not coverage.get(i, "").strip()]
    assert not missing, f"{len(missing)} report items with no app element: {missing[:10]}"
