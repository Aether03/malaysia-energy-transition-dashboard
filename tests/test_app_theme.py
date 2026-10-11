"""Dark mode (M6 step 6): charts and coloured text stay readable on the dark theme (doc 04 dark slots, WCAG)."""

import json
import re
import sys
import tomllib
from pathlib import Path

import plotly.graph_objects as go
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from showcase import theme

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
DARK_PAGE = "#1a1a19"
# doc 04 §3.2: the energy-source slots, light -> dark
SOURCE_SLOTS = {
    "#a0522d": "#a0522d",
    "#4a3aa7": "#9085e9",
    "#eb6834": "#d95926",
    "#2a78d6": "#3987e5",
    "#008300": "#008300",
    "#1baf7a": "#1ca3a6",
    "#eda100": "#c98500",
}


def contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        c = [int(h.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_to_dark_uses_doc_04s_dark_slots_and_readable_text():
    fig = go.Figure()
    for light in SOURCE_SLOTS:
        fig.add_scatter(y=[1], line={"color": light})
    fig.add_bar(y=[1], marker_color=theme.MALAYSIA)
    fig.add_annotation(text="x", font={"color": theme.TEXT_SECONDARY})
    dark = theme.to_dark(fig)
    assert [t.line.color for t in dark.data[:7]] == list(SOURCE_SLOTS.values())
    assert contrast(dark.data[7].marker.color, DARK_PAGE) >= 3  # the Malaysia highlight stays visible
    assert contrast(dark.layout.annotations[0].font.color, DARK_PAGE) >= 4.5
    assert fig.data[7].marker.color == theme.MALAYSIA  # the input is not changed


def hard_coded_colours() -> set[str]:
    files = [*(ROOT / "app" / "pages").glob("*.py")] + [
        ROOT / "app" / "showcase" / f"{m}.py" for m in ("annual", "grid", "asean", "theme")
    ]
    found = set()
    for f in files:
        found |= {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}\b", f.read_text(encoding="utf-8"))}
    return found


def test_every_chart_colour_is_readable_on_the_dark_page_after_to_dark():
    """A guard: a new hard-coded light colour must get a dark mapping or already pass on the dark page."""
    surfaces = {"#fcfcfb", "#f4f3ef", "#ffffff", DARK_PAGE}  # backgrounds, never marks or text
    sequential = {"#cde2fb", "#5a91d6"}  # the heatmap's fill ramp: cells carry their values in text and hover
    decorative = {"#e4e3df"}  # grid and axis lines (WCAG exempts decoration; doc 04 border.subtle)
    status = {c for c, _ in theme.STATUS.values()}  # only filled chips with their own text colour (meta.CHIP_COLOURS)
    weak = {
        h: round(contrast(theme.DARK.get(h, h), DARK_PAGE), 2)
        for h in hard_coded_colours() - surfaces - sequential - decorative - status - set(theme.DARK.values())
        if contrast(theme.DARK.get(h, h), DARK_PAGE) < 3
    }
    assert not weak, f"below 3:1 on the dark page after to_dark: {weak}"


def test_coloured_delta_text_passes_aa_in_both_themes():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    for mode in ("light", "dark"):
        t = config["theme"][mode]
        for key in ("greenTextColor", "redTextColor"):
            assert contrast(t[key], t["backgroundColor"]) >= 4.5, f"{mode} {key}"


def page() -> None:
    import plotly.graph_objects as go
    from showcase import theme, ui

    ui.chart(
        go.Figure(go.Bar(y=[1], marker_color=theme.MALAYSIA)), "One bar.", __import__("pandas").DataFrame(), key="c"
    )


def spec(at) -> dict:
    return json.loads(at.get("plotly_chart")[0].proto.spec)


def test_chart_follows_the_viewers_theme(monkeypatch):
    from showcase import ui

    light = spec(AppTest.from_function(page, default_timeout=30).run())
    assert light["data"][0]["marker"]["color"] == theme.MALAYSIA
    monkeypatch.setattr(ui, "is_dark", lambda: True)
    dark = spec(AppTest.from_function(page, default_timeout=30).run())
    assert dark["data"][0]["marker"]["color"] == theme.DARK[theme.MALAYSIA]
    assert dark["layout"]["template"]["layout"]["font"]["color"] == "#f4f3ef"


def test_bar_values_sit_outside_the_bars():
    """Plotly colours in-bar text by itself (#444 or white), which falls below 4.5:1 on mid-tone fills in both themes;
    outside the bar the value takes the template's text colour."""
    for page in (ROOT / "app" / "pages").glob("*.py"):
        assert 'textposition="auto"' not in page.read_text(encoding="utf-8"), page.name
        assert 'textposition="inside"' not in page.read_text(encoding="utf-8"), page.name
