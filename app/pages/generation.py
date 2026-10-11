"""Generation (report page P2): Malaysia's generation by source, progress to the national capacity targets, capacity
factor by source and demand growth, for a year range, a unit and a source selection (see showcase/annual.py)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from showcase import annual, cache, theme, ui

FOOTNOTE = (  # frame_footnote, verbatim
    "Sources: Ember Yearly Electricity Data (CC BY 4.0). Capacity factor = generation ÷ (capacity × hours in the "
    "year; 8,784 h in leap years), shown at the last year of the selected range; blank, never 0, when capacity is "
    "not reported. Targets: 31% by 2025 and 40% by 2035 (12MP / SEDA MyRER, 2021); 35% by 2030 and 70% by 2050 "
    "(NETR). Ember counts grid capacity only; the official share also counts off-grid and rooftop capacity. The "
    "target chart always spans 2000-2050 and ignores the year range."
)
KEYS = ["generation_years", "generation_unit", "generation_sources"]
LEGEND_TOP = {"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0}  # room for the legend above the plot
TOP_MARGIN = {"l": 8, "r": 8, "t": 64, "b": 8}


def gaps(values) -> list:
    """NaN -> None, so a blank value is a gap in the chart (never a 0)."""
    return [None if pd.isna(v) else v for v in values]


f = cache.frames()
head = st.container()  # the title depends on the slicers below it

all_years = annual.years(f)
names = list(f["dim_source"].sort_values("sort_order")["display_name"])
pick_years, pick_unit, pick_source = st.columns([3, 2, 3])
first, last = pick_years.select_slider("Years", all_years, value=(all_years[0], all_years[-1]), key=KEYS[0])
unit = pick_unit.radio("Unit", ["TWh", "%"], horizontal=True, key=KEYS[1])
sources = pick_source.multiselect("Source", names, placeholder="All sources", key=KEYS[2])
ui.reset_button(KEYS)
with head:
    ui.header(annual.generation_title(f, last), annual.generation_subtitle(first, last, ui.data_as_of()))

if message := annual.no_source_message(f, first, last, sources):
    st.info(message)

# --- generation by source (p2_mix_area) ---
st.markdown("**Generation by source (TWh or % of the year's total, per the Unit toggle)**")
series = annual.mix_series(f, first, last, sources)
col, other = ("generation_twh", "share_of_mix_pct") if unit == "TWh" else ("share_of_mix_pct", "generation_twh")
hover = (
    "%{y:.1f} TWh · %{customdata:.1f}% of the year's mix<extra>%{fullData.name}</extra>"
    if unit == "TWh"
    else "%{y:.1f}% of the year's mix · %{customdata:.1f} TWh<extra>%{fullData.name}</extra>"
)
fig = go.Figure()
for source, g in series.groupby("source", sort=False):
    colour = g["color"].iloc[0]
    fig.add_scatter(
        x=g["year"].tolist(),
        y=gaps(g[col]),
        name=source,
        mode="lines",
        stackgroup="one",
        line={"color": colour, "width": 0.5},
        fillcolor=colour,
        customdata=g[other].tolist(),
        hovertemplate=hover,
    )
fig.update_layout(
    hovermode="x unified",
    height=320,
    yaxis_title="TWh" if unit == "TWh" else "% of the year's total",
    legend=LEGEND_TOP,
    margin=TOP_MARGIN,
)
table = series.pivot(index="year", columns="source", values=col).reset_index() if len(series) else series
ui.chart(fig, annual.generation_mix_summary(series, unit), table, key="generation_mix")

target_col, cf_col = st.columns(2)

# --- national targets (p2_target_line) ---
with target_col:
    st.markdown("**National RE capacity targets: share of installed capacity (%)**")
    axis = annual.target_axis(f)
    fig = go.Figure()
    ember = axis.dropna(subset=["ember"])
    fig.add_scatter(
        x=ember["year"].tolist(),
        y=ember["ember"].tolist(),
        name="Ember grid basis (%)",
        mode="lines",
        line={"color": theme.MALAYSIA, "width": 2.5},
        hovertext=[f"Actual, Ember grid basis, {r.year}: {annual.fmt(r.ember)}%" for r in ember.itertuples()],
        hoverinfo="text",
    )
    official = axis.dropna(subset=["official"])
    fig.add_scatter(
        x=official["year"].tolist(),
        y=official["official"].tolist(),
        name="Official (%)",
        mode="lines+markers",
        line={"color": annual.ACCENT_BLUE, "width": 2},
        hovertext=[
            f"Official, {r.year} (incl. off-grid and rooftop): {annual.fmt(r.official, 0)}%<br>{r.official_source}"
            for r in official.itertuples()
        ],
        hoverinfo="text",
    )
    targets = axis.dropna(subset=["target"])
    fig.add_scatter(
        x=targets["year"].tolist(),
        y=targets["target"].tolist(),
        name="Target (%)",
        mode="lines+markers",
        line={"color": theme.PEER, "width": 1.5, "dash": "dash"},
        hovertext=[f"Target {annual.fmt(r.target, 0)}% by {r.year}<br>{r.target_source}" for r in targets.itertuples()],
        hoverinfo="text",
    )
    fig.update_layout(height=320, yaxis={"range": [0, 100]}, legend=LEGEND_TOP, margin=TOP_MARGIN)
    table = axis.rename(
        columns={
            "year": "Year",
            "ember": "Ember grid basis (%)",
            "official": "Official (%)",
            "official_source": "Official source",
            "target": "Target (%)",
            "target_source": "Target source",
        }
    )
    ui.chart(fig, annual.target_summary(axis), table, key="generation_targets")

# --- capacity factor (p2_cf_bar, p2_cf_note) ---
with cf_col:
    st.markdown(f"**{annual.capacity_factor_title(last)}**")
    rows = annual.capacity_factors(f, last, sources)
    have = rows.dropna(subset=["capacity_factor_pct"])
    fig = go.Figure(
        go.Bar(
            y=have["source"].tolist(),
            x=have["capacity_factor_pct"].tolist(),
            orientation="h",
            marker_color=have["color"].tolist(),
            text=[annual.fmt(v) for v in have["capacity_factor_pct"]],
            textposition="auto",
            hovertext=[
                f"{r.source}: capacity factor {annual.fmt(r.capacity_factor_pct)}%<br>"
                f"= generation {annual.fmt(r.generation_twh, 2)} TWh ÷ (capacity {annual.fmt(r.capacity_gw, 2)} GW "
                f"× {r.hours_in_year:,} hours in {last})"
                for r in have.itertuples()
            ],
            hoverinfo="text",
        )
    )
    fig.update_layout(height=320, xaxis={"range": [0, 100]}, yaxis={"autorange": "reversed"}, showlegend=False)
    table = rows.drop(columns="color").rename(
        columns={
            "source": "Source",
            "generation_twh": "Generation (TWh)",
            "capacity_gw": "Capacity (GW)",
            "hours_in_year": "Hours in year",
            "capacity_factor_pct": "Capacity factor (%)",
            "reason": "Why blank",
        }
    )
    ui.chart(fig, annual.capacity_factor_summary(rows, last), table, key="generation_cf")
    if note := annual.capacity_factor_note(rows, last):
        st.caption(note)

# --- demand and growth (p2_demand_cols, p2_growth_cols) ---
demand = annual.demand_series(f, first, last)
demand_col, growth_col = st.columns(2)

with demand_col:
    st.markdown("**Electricity demand (TWh)**")
    fig = go.Figure(go.Bar(x=demand["year"].tolist(), y=demand["demand_twh"].tolist(), marker_color=theme.MALAYSIA))
    fig.update_layout(height=240, showlegend=False)
    ui.chart(
        fig,
        annual.demand_summary(demand),
        demand[["year", "demand_twh"]].rename(columns={"demand_twh": "Demand (TWh)"}),
        key="generation_demand",
    )

with growth_col:
    st.markdown("**Demand growth, year on year (%)**")
    fig = go.Figure(go.Bar(x=demand["year"].tolist(), y=gaps(demand["growth_pct"]), marker_color=annual.ACCENT_BLUE))
    fig.update_layout(height=240, showlegend=False)
    ui.chart(
        fig,
        annual.growth_summary(demand),
        demand[["year", "growth_pct"]].rename(columns={"growth_pct": "Demand growth (%)"}),
        key="generation_growth",
    )

ui.footer(FOOTNOTE, ["D1"])
