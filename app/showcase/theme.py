"""Plotly styling from the report's theme (report/.../energy-transition.json) and doc 04's tokens (M6 plan Q6)."""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

_THEME = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "report/EnergyTransition.Report/StaticResources/RegisteredResources/energy-transition.json"
    ).read_text(encoding="utf-8")
)

SOURCE_COLORS = _THEME["dataColors"]  # doc 04 §3.2, light slots 1-7; per source, use dim_source.color_hex
MALAYSIA = "#104281"  # accent.navy: Malaysia highlight
PEER = "#8a8984"  # peer.muted: the other countries
TEXT_SECONDARY = "#52514e"
STATUS = {"PASS": ("#087a08", "✓ Pass"), "WARN": ("#8a5a00", "! Warn"), "FAIL": ("#d03b3b", "✕ Fail")}  # doc 04 §3.4

# Dark mode (M6 step 6): doc 04's dark source slots, and text, grid and highlight colours measured against the dark
# page #1a1a19 (text >= 4.5:1, marks >= 3:1). Pages hard-code light colours; `to_dark` swaps them, so a page never
# needs a dark branch. #86b6ef moves to #5598e7 so it stays distinct from the navy it replaces (P4's 2023 vs 2024).
DARK = {
    "#4a3aa7": "#9085e9",  # other fossil
    "#eb6834": "#d95926",  # gas
    "#2a78d6": "#3987e5",  # hydro
    "#1baf7a": "#1ca3a6",  # wind & other renewables
    "#eda100": "#c98500",  # solar
    "#0b0b0b": "#f4f3ef",  # text.primary (15.7:1)
    "#52514e": "#b5b3ac",  # text.secondary (8.3:1)
    "#6b6a66": "#a3a19a",  # text.muted (6.7:1)
    "#104281": "#86b6ef",  # accent.navy, the Malaysia highlight (8.3:1)
    "#86b6ef": "#5598e7",  # the light blue beside navy (5.8:1)
    "#256abf": "#5598e7",  # accent.blue (5.8:1)
    "#e4e3df": "#3a3a37",  # border.subtle: grid and axis lines, decorative
}


def _template(text: str, secondary: str, grid: str) -> go.layout.Template:
    # automargin: the tight margins below grow to fit tick labels instead of clipping them
    axis = {"gridcolor": grid, "linecolor": grid, "tickfont": {"color": secondary}, "automargin": True}
    return go.layout.Template(
        layout=go.Layout(
            font={"family": "Segoe UI, system-ui, sans-serif", "size": 13, "color": text},
            colorway=SOURCE_COLORS,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=axis,
            yaxis=axis,
            legend={"orientation": "h", "y": -0.2},
            margin={"l": 8, "r": 8, "t": 32, "b": 8},
        )
    )


TEMPLATE = _template(_THEME["foreground"], TEXT_SECONDARY, "#e4e3df")
DARK_TEMPLATE = _template(DARK["#0b0b0b"], DARK[TEXT_SECONDARY], DARK["#e4e3df"])
DARK_TEMPLATE.layout.colorway = [DARK.get(c.lower(), c) for c in SOURCE_COLORS]
pio.templates["energy_transition"] = TEMPLATE
pio.templates["energy_transition_dark"] = DARK_TEMPLATE


def to_dark(fig: go.Figure) -> go.Figure:
    """A copy of `fig` with every light colour in `DARK` swapped for its dark value (marks, lines, text, shapes)."""

    def swap(node):
        if isinstance(node, dict):
            return {k: swap(v) for k, v in node.items()}
        if isinstance(node, list):
            return [swap(v) for v in node]
        if isinstance(node, str):
            return DARK.get(node.lower(), node)
        return node

    return go.Figure(swap(fig.to_dict()))
