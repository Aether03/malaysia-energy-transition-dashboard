"""Grid load: the web form of the report's P4 (M6 step 4). Numbers come from `showcase.metrics` and `showcase.grid`."""

import plotly.graph_objects as go
import streamlit as st
from showcase import cache, grid, metrics, ui

NOTE = (
    "Thailand: sum of 5 regional demands, hourly means (published peaks are 2–4% higher). Singapore: EMA system demand, "
    "hourly mean of half-hours. Seasons are month-based. Gaps shown, never filled. Flows: Thailand's malaysia_EXP/IMP, "
    "daily means. Data: EGAT via Zenodo (CC BY 4.0); EMA (SODL v1.0)."
)
YEAR_COLOR = {2023: "#86b6ef", 2024: "#104281"}  # the report's per-year fills
YEAR_DASH = {2023: "dot", 2024: "solid"}  # a second cue besides colour
DAY_STYLE = {"Weekday": ("#104281", "solid"), "Weekend & holiday": ("#256abf", "dash")}
HEAT_SCALE = [[0, "#cde2fb"], [1, "#5a91d6"]]  # theme minimum to the visual's maximum (doc 04 section 3.4)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@st.cache_data
def _load_rows() -> list[dict]:
    return metrics.grid_load(cache.frames())


@st.cache_data
def _flow_rows() -> list[dict]:
    return metrics.interconnector_flows(cache.frames())


def titled(fig: go.Figure, title: str, height: int) -> go.Figure:
    """The visual's own title, left-aligned, as in the report."""
    fig.update_layout(title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 15}}, height=height)
    fig.update_layout(margin={"t": 56})
    return fig


f = cache.frames()
rows = _load_rows()
head = st.container()  # filled once the grid is chosen, so the title can follow the selector

names = grid.grid_names(f)
shared = st.session_state.get("grid_name", names[0])  # the Forecast page's grid slicer is synced with this one
name = st.selectbox("Grid", names, index=names.index(shared) if shared in names else 0, key="p4_grid_widget")
st.session_state["grid_name"] = name
g = grid.grid_row(f, name)
key, code = g["grid_key"], g["grid_code"]

with head:
    ui.header(grid.load_title(g, f, rows), grid.load_subtitle(g, ui.data_as_of()))
st.info(grid.banner(g), icon=":material/info:")

# Heatmap: month x hour, values in the cells and in the hover.
# Under 768 px the 24 columns are ~12 px wide, too narrow for the cell values: hide them there (hover and
# "Show data" keep every value).
st.html("<style>@media (max-width: 767px) { .heatmap-label { display: none; } }</style>")
z = grid.heatmap(f, key)
peak = grid.peak_text(rows, code)
if peak:
    st.caption(peak)
heat = go.Figure(
    go.Heatmap(
        z=z.to_numpy(),
        x=list(z.columns),
        y=list(z.index),
        colorscale=HEAT_SCALE,
        showscale=False,
        xgap=1,
        ygap=1,
        texttemplate="%{z:.1f}",
        textfont={"size": 10},
        hovertemplate="%{y}, %{x}:00<br>Average load %{z:.1f} GW<extra></extra>",
    )
)
heat.update_yaxes(autorange="reversed")
heat.update_xaxes(side="top", dtick=1)
shown = z.round(1).rename(columns=dict(zip(f["dim_hour"]["hour"], f["dim_hour"]["label"], strict=True)))
ui.chart(
    titled(heat, "Average load by month and hour (GW)", 420),
    grid.heatmap_summary(z),
    shown.reset_index(),
    key="p4_heatmap",
)

# Typical day (season slicer), monthly peak, load factor.
monthly = grid.monthly(f, g, rows)
col_curve, col_peak, col_lf = st.columns(3)

with col_curve:
    seasons = st.multiselect(
        "Season", grid.season_options(f, key), key=f"p4_season_{code}", help="None picked = every season"
    )
    curve = grid.load_curve(f, key, seasons)
    day_fig = go.Figure()
    for day_type, c in curve.groupby("day_type"):
        colour, dash = DAY_STYLE.get(day_type, ("#256abf", "solid"))
        c = c.set_index("hour").reindex(range(24))
        day_fig.add_scatter(
            x=list(c.index),
            y=c["mean_mw"],
            name=day_type,
            mode="lines",
            line={"color": colour, "dash": dash, "width": 2},
            hovertemplate="%{x}:00 " + day_type + ": %{y:,.0f} MW<extra></extra>",
        )
    ui.chart(
        titled(day_fig, "Typical day (MW)", 320),
        grid.curve_summary(curve, seasons),
        curve.pivot(index="hour", columns="day_type", values="mean_mw").round(1).reset_index(),
        key="p4_load_curve",
    )

with col_peak:
    peaks = go.Figure()
    for year, m in monthly.groupby("year"):
        peaks.add_bar(
            x=list(m["month_name"]),
            y=m["peak_mw"],
            name=str(year),
            marker_color=YEAR_COLOR.get(year),
            hovertemplate="%{x} " + str(year) + ": %{y:,.0f} MW<extra></extra>",
        )
    peaks.update_layout(barmode="group")
    peaks.update_xaxes(categoryorder="array", categoryarray=MONTHS)
    ui.chart(
        titled(peaks, "Monthly peak (MW)", 360),
        grid.monthly_summary(monthly, "peak_mw", "MW"),
        grid.by_month(monthly, "peak_mw", 0),
        key="p4_peak_cols",
    )

with col_lf:
    lf = go.Figure()
    for year, m in monthly.groupby("year"):
        lf.add_scatter(
            x=list(m["month_name"]),
            y=m["load_factor_pct"],
            name=str(year),
            mode="lines+markers",
            line={"color": YEAR_COLOR.get(year), "dash": YEAR_DASH.get(year, "solid"), "width": 2},
            hovertemplate="%{x} " + str(year) + ": %{y:.1f}%<extra></extra>",
        )
    lf.update_xaxes(categoryorder="array", categoryarray=MONTHS)
    ui.chart(
        titled(lf, "Load factor (%)", 360),
        grid.monthly_summary(monthly, "load_factor_pct", "%"),
        grid.by_month(monthly, "load_factor_pct", 1),
        key="p4_lf_line",
    )

# Interconnector flows: only the Thailand grid has any.
st.caption(grid.flow_note(_flow_rows(), code))
flow = grid.flow_daily(f, key)
if not flow.empty:
    flow_fig = go.Figure(
        go.Scatter(
            x=flow["date"],
            y=flow["net_flow_mw"],
            mode="lines",
            connectgaps=False,
            line={"color": "#104281", "width": 1.5},
            hovertemplate="%{x|%d %b %Y}: %{y:,.0f} MW<extra></extra>",
        )
    )
    flow_fig.add_hline(y=0, line={"color": "#52514e", "width": 1, "dash": "dot"})
    ui.chart(
        titled(flow_fig, "Thailand ↔ Malaysia daily net flow (MW)", 300),
        grid.flow_summary(flow),
        flow.assign(date=flow["date"].dt.strftime("%Y-%m-%d")).round(1),
        key="p4_flow_line",
    )

ui.footer(NOTE, ["DTH", "DSG"])
