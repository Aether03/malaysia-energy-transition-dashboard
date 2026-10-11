"""ASEAN (report page P5, with its Country Deep Dive drill-through D1 and the T2 country tooltip): Malaysia against its
ASEAN peers on renewable share, carbon intensity and demand, then one country's generation in depth. The drill-through
becomes the country selector below the comparison and the tooltip becomes the hover text (M6 plan Q1); titles, numbers
and notes are the report's (see showcase/asean.py and showcase/annual.py)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from showcase import annual, asean, cache, theme, ui

# frame_footnote of the Country Deep Dive, verbatim except its last sentence: the report says "Right-click a country on
# the ASEAN page to drill here; Back returns with its filters", which describes the drill-through the web page replaces.
DEEP_FOOTNOTE = (
    "Sources: Ember Yearly Electricity Data (CC BY 4.0); OWID population (CC BY 4.0). Capacity factor = generation ÷ "
    "(capacity × hours in year); blank, never 0, where Ember reports no capacity or capacity too small for the "
    "generation (e.g. Philippine and Indonesian geothermal, Thailand and Myanmar in every year). Choose the country "
    "with the deep-dive selector; Back returns to the comparison with its filters."
)
KEYS = ["asean_years", "asean_countries", "asean_metric", "asean_country", "asean_unit", "asean_sources"]
LEGEND_TOP = {"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0}  # room for the legend above the plot
TOP_MARGIN = {"l": 8, "r": 8, "t": 64, "b": 8}
NO_DATA = "No data for the selected countries and years."


def gaps(values) -> list:
    """NaN -> None, so a blank value is a gap in the chart (never a 0)."""
    return [None if pd.isna(v) else v for v in values]


def label(name: str) -> str:
    """The country's name as the charts print it: Malaysia in bold, as well as navy (nothing by colour alone)."""
    return f"<b>{name}</b>" if name == asean.FOCUS else name


def colour(name: str) -> str:
    return theme.MALAYSIA if name == asean.FOCUS else theme.PEER


def bars(names: list[str], values: list[float], hovers: list[str], digits: int) -> go.Figure:
    """A ranked horizontal bar (p5_intensity_bar, p5_percapita_bar): Malaysia navy and bold, peers muted, values on bars."""
    fig = go.Figure(
        go.Bar(
            y=names,
            x=values,
            orientation="h",
            marker_color=[colour(n) for n in names],
            text=[annual.fmt(v, digits, grouping=True) for v in values],
            textposition="outside",
            cliponaxis=False,
            hovertext=hovers,
            hoverinfo="text",
        )
    )
    fig.update_layout(
        height=300,
        showlegend=False,
        xaxis={"range": [0, max(values, default=1) * 1.18]},
        yaxis={"autorange": "reversed", "tickmode": "array", "tickvals": names, "ticktext": [label(n) for n in names]},
        margin={"l": 8, "r": 24, "t": 16, "b": 8},
    )
    return fig


f = cache.frames()
head = st.container()  # the title depends on the slicers below it
st.subheader("Compare the countries", anchor="compare-countries")

# --- P5 slicers (p5_country_slicer, p5_metric_slicer, p5_year_slicer) and reset (frame_reset) ---
all_years = annual.years(f)
pick_countries, pick_metric = st.columns([3, 2])
selection = pick_countries.multiselect(
    "Countries (none selected = the 6 default peers)",
    asean.countries(f),
    placeholder="Default: the 6 peers",
    key=KEYS[1],
)
metric = pick_metric.radio("Trend metric", list(asean.METRICS), key=KEYS[2])
pick_years, reset = st.columns([3, 2], vertical_alignment="bottom")
first, last = pick_years.select_slider("Years", all_years, value=(all_years[0], all_years[-1]), key=KEYS[0])
with reset:
    ui.reset_button(KEYS)

c = asean.comparison(f, selection, first, last)
with head:
    ui.header(c.title, asean.subtitle(first, last, ui.data_as_of()))

snap = asean.snapshot(f, c)
tips = {n: asean.tooltip(f, n, c.year) for n in c.names}  # the T2 tooltip page, as hover text on all four charts
digits = asean.METRICS[metric][1]

trend_col, intensity_col = st.columns(2)

# --- trend by country (p5_trend_line) ---
with trend_col:
    st.markdown(f"**Trend by country: {metric}** (Malaysia in navy and bold; choose the metric above)")
    t = asean.trend(f, c.names, metric, first, last)
    fig = go.Figure()
    ends = []
    for name, g in sorted(t.groupby("country", sort=False), key=lambda item: item[0] == asean.FOCUS):  # Malaysia on top
        mine = name == asean.FOCUS
        fig.add_scatter(
            x=g["year"].tolist(),
            y=g["value"].tolist(),
            name=name,
            mode="lines",
            line={"color": colour(name), "width": 2.5 if mine else 1.5},
            hovertemplate=tips[name].hover(f"<b>{name}</b> · %{{x}}: {metric} %{{y:,.{digits}f}}") + "<extra></extra>",
        )
        ends.append((name, int(g["year"].iloc[-1]), float(g["value"].iloc[-1])))
    if ends:  # direct labels at the line ends, nudged apart where lines finish close together (doc 04)
        heights = [y for _, _, y in ends]
        # The gap is set by the axis, not by the end values: an 11 px label needs about 7% of the 259 px plot height
        axis = (t["value"].max() - min(0.0, t["value"].min())) or 1.0
        for (name, x_end, _), y_label in zip(ends, asean.spread(heights, 0.07 * axis), strict=True):
            fig.add_annotation(
                x=x_end,
                y=y_label,
                text=label(name),
                showarrow=False,
                xanchor="left",
                xshift=6,
                font={"color": theme.MALAYSIA if name == asean.FOCUS else theme.TEXT_SECONDARY, "size": 11},
            )
    fig.update_layout(
        height=300,
        showlegend=False,
        yaxis_title=metric,
        margin={"l": 8, "r": 104, "t": 16, "b": 8},
    )
    table = t.pivot(index="year", columns="country", values="value").reset_index() if len(t) else t
    ui.chart(fig, asean.trend_summary(t, metric), table, key="asean_trend")

# --- carbon intensity bar (p5_intensity_bar) ---
with intensity_col:
    st.markdown("**Carbon intensity at the comparison year (gCO2e/kWh), lowest first**")
    d = snap.dropna(subset=["Carbon intensity (gCO2e/kWh)"]).sort_values("Carbon intensity (gCO2e/kWh)", kind="stable")
    fig = bars(
        list(d["Country"]),
        list(d["Carbon intensity (gCO2e/kWh)"]),
        [tips[n].hover() for n in d["Country"]],
        0,
    )
    ui.chart(
        fig,
        asean.bar_summary(
            snap, "Carbon intensity (gCO2e/kWh)", c.year, "carbon intensity", "gCO2e/kWh", 0, low_first=True
        ),
        d[["Country", "Year", "Carbon intensity (gCO2e/kWh)"]],
        key="asean_intensity",
    )

scatter_col, percapita_col = st.columns(2)

# --- RE share vs carbon intensity (p5_scatter) ---
with scatter_col:
    st.markdown("**RE share vs carbon intensity (bubble = demand, TWh)**")
    d = snap.dropna(subset=["RE share (%)", "Carbon intensity (gCO2e/kWh)"])
    names = list(d["Country"])
    sizes = d["Demand (TWh)"].fillna(0).tolist()
    fig = go.Figure(
        go.Scatter(
            x=d["RE share (%)"].tolist(),
            y=d["Carbon intensity (gCO2e/kWh)"].tolist(),
            mode="markers+text",
            text=[label(n) for n in names],
            textposition="top center",
            textfont={"size": 11},
            marker={
                "size": sizes,
                "sizemode": "area",
                "sizeref": 2.0 * max(sizes, default=1) / (36**2) or 1,
                "sizemin": 8,
                "color": [colour(n) for n in names],
                "symbol": ["diamond" if n == asean.FOCUS else "circle" for n in names],  # a shape as well as a colour
                "line": {"color": "#ffffff", "width": 1},
            },
            hovertext=[
                tips[n].hover(f"Demand: {annual.fmt(s, 1, grouping=True)} TWh (bubble size)")
                for n, s in zip(names, sizes, strict=True)
            ],
            hoverinfo="text",
        )
    )
    fig.update_layout(
        height=300,
        showlegend=False,
        xaxis_title="RE share of generation (%)",
        yaxis_title="Carbon intensity (gCO2e/kWh)",
        margin={"l": 8, "r": 16, "t": 16, "b": 8},
    )
    ui.chart(fig, asean.scatter_summary(snap, c.year), snap, key="asean_scatter")

# --- demand per capita bar (p5_percapita_bar) ---
with percapita_col:
    st.markdown("**Demand per capita at the common year (MWh)**")
    d = snap.dropna(subset=["Demand per capita (MWh)"]).sort_values(
        "Demand per capita (MWh)", ascending=False, kind="stable"
    )
    fig = bars(
        list(d["Country"]),
        list(d["Demand per capita (MWh)"]),
        [
            tips[n].hover(f"Demand per capita ({c.per_capita_year}): {annual.fmt(v, 2)} MWh")
            for n, v in zip(d["Country"], d["Demand per capita (MWh)"], strict=True)
        ],
        2,
    )
    ui.chart(
        fig,
        asean.bar_summary(
            snap, "Demand per capita (MWh)", c.per_capita_year, "demand per capita", "MWh", 2, low_first=False
        ),
        d[["Country", "Per-capita year", "Demand per capita (MWh)"]],
        key="asean_percapita",
    )

# --- rank card (p5_rank_card) ---
with st.container(border=True):
    st.markdown(f"### {c.label}")
    st.caption("Rank among the compared countries; 1 is the highest renewable share and the lowest carbon intensity.")
    with st.expander("Show data"):
        st.dataframe(annual.rank_table(c.rows), hide_index=True)

st.caption(asean.footnote(c))  # frame_footnote of P5: the DAX [ASEAN Footnote]

# =========================================================================== Country deep dive (D1)
st.divider()
names = asean.countries(f)
source_names = list(f["dim_source"].sort_values("sort_order")["display_name"])
pick_country, pick_unit, pick_source = st.columns([2, 2, 3])
country = pick_country.selectbox("Country deep dive", names, index=names.index(asean.FOCUS), key=KEYS[3])
unit = pick_unit.radio("Unit", ["TWh", "%"], horizontal=True, key=KEYS[4])
sources = pick_source.multiselect("Source", source_names, placeholder="All sources", key=KEYS[5])
deep = asean.focus_on(f, country)  # the Malaysia functions then describe the chosen country

st.subheader(annual.generation_title(f, last, country), anchor="country-deep-dive")  # d1 frame_title
st.caption(annual.generation_subtitle(first, last, ui.data_as_of(), country))  # d1 frame_subtitle
st.markdown("[↑ Back to the country comparison](#compare-countries)")  # d1_back: the page never left, filters kept

if message := annual.no_source_message(deep, first, last, sources):  # d1_empty_state
    st.info(message)

# --- generation by source (d1_mix_area) ---
st.markdown("**Generation by source (TWh or % of the year's total, per the Unit toggle)**")
series = annual.mix_series(deep, first, last, sources)
col, other = ("generation_twh", "share_of_mix_pct") if unit == "TWh" else ("share_of_mix_pct", "generation_twh")
hover = (
    "%{y:.1f} TWh · %{customdata:.1f}% of the year's mix<extra>%{fullData.name}</extra>"
    if unit == "TWh"
    else "%{y:.1f}% of the year's mix · %{customdata:.1f} TWh<extra>%{fullData.name}</extra>"
)
fig = go.Figure()
for source, g in series.groupby("source", sort=False):
    source_colour = g["color"].iloc[0]
    fig.add_scatter(
        x=g["year"].tolist(),
        y=gaps(g[col]),
        name=source,
        mode="lines",
        stackgroup="one",
        line={"color": source_colour, "width": 0.5},
        fillcolor=source_colour,
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
ui.chart(fig, annual.generation_mix_summary(series, unit), table, key="asean_deep_mix")

# --- capacity factor (d1_cf_bar, d1_cf_note) ---
st.markdown(f"**{annual.capacity_factor_title(last)}**")
rows = annual.capacity_factors(f, last, sources, country)
have = rows.dropna(subset=["capacity_factor_pct"])
fig = go.Figure(
    go.Bar(
        y=have["source"].tolist(),
        x=have["capacity_factor_pct"].tolist(),
        orientation="h",
        marker_color=have["color"].tolist(),
        text=[annual.fmt(v) for v in have["capacity_factor_pct"]],
        textposition="outside",
        cliponaxis=False,
        hovertext=[
            f"{r.source}: capacity factor {annual.fmt(r.capacity_factor_pct)}%<br>"
            f"= generation {annual.fmt(r.generation_twh, 2)} TWh ÷ (capacity {annual.fmt(r.capacity_gw, 2)} GW "
            f"× {r.hours_in_year:,} hours in {last})"
            for r in have.itertuples()
        ],
        hoverinfo="text",
    )
)
fig.update_layout(height=300, xaxis={"range": [0, 100]}, yaxis={"autorange": "reversed"}, showlegend=False)
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
ui.chart(fig, annual.capacity_factor_summary(rows, last), table, key="asean_deep_cf")
if note := annual.capacity_factor_note(rows, last):
    st.caption(note)

# --- demand and growth (d1_demand_cols, d1_growth_cols) ---
demand = annual.demand_series(deep, first, last)
demand_text, growth_text = asean.demand_summaries(demand, country, first, last)
demand_col, growth_col = st.columns(2)

with demand_col:
    st.markdown("**Electricity demand (TWh)**")
    fig = go.Figure(go.Bar(x=demand["year"].tolist(), y=gaps(demand["demand_twh"]), marker_color=theme.MALAYSIA))
    fig.update_layout(height=240, showlegend=False)
    ui.chart(
        fig,
        demand_text,
        demand[["year", "demand_twh"]].rename(columns={"demand_twh": "Demand (TWh)"}),
        key="asean_deep_demand",
    )

with growth_col:
    st.markdown("**Demand growth, year on year (%)**")
    fig = go.Figure(go.Bar(x=demand["year"].tolist(), y=gaps(demand["growth_pct"]), marker_color=annual.ACCENT_BLUE))
    fig.update_layout(height=240, showlegend=False)
    ui.chart(
        fig,
        growth_text,
        demand[["year", "growth_pct"]].rename(columns={"growth_pct": "Demand growth (%)"}),
        key="asean_deep_growth",
    )

ui.footer(DEEP_FOOTNOTE, ["D1", "D2"])
