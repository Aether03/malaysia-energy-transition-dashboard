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

TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font={"family": "Segoe UI, system-ui, sans-serif", "size": 13, "color": _THEME["foreground"]},
        colorway=SOURCE_COLORS,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"gridcolor": "#e4e3df", "linecolor": "#e4e3df", "tickfont": {"color": TEXT_SECONDARY}},
        yaxis={"gridcolor": "#e4e3df", "linecolor": "#e4e3df", "tickfont": {"color": TEXT_SECONDARY}},
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 8, "r": 8, "t": 32, "b": 8},
    )
)
pio.templates["energy_transition"] = TEMPLATE
