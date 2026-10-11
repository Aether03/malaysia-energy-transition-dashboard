"""Forecast: the web form of the report's P4b (M6 step 4). Text and numbers come from `showcase.grid`."""

import plotly.graph_objects as go
import streamlit as st
from showcase import cache, grid, ui

NOTE = (
    "Forecast: LightGBM issued at local midnight for the next 24 h, monthly rolling-origin backtest over 2024, run once "
    "under a locked protocol (docs/forecast.md). Baseline = the same hour last week; improvement = 1 − MAPE model ÷ MAPE "
    "baseline, 95% CI from a 7-day block bootstrap. Pick a day; none picked = the grid's 2024 peak day."
)
# The report's lines (doc 04 section 5): actual black, model navy, baseline dashed grey.
LINES = [
    ("actual_mw", "Day Actual (MW)", "#0b0b0b", "solid", 2),
    ("model_mw", "Day Model (MW)", "#104281", "solid", 2),
    ("baseline_mw", "Day Baseline (MW)", "#52514e", "dash", 1.5),
]

f = cache.frames()
head = st.container()  # filled once the grid is chosen, so the title can follow the selector

names = grid.grid_names(f)
shared = st.session_state.get("grid_name", names[0])  # the Grid load page's grid slicer is synced with this one
name = st.selectbox("Grid", names, index=names.index(shared) if shared in names else 0, key="p4b_grid_widget")
st.session_state["grid_name"] = name
g = grid.grid_row(f, name)
key = g["grid_key"]
run = grid.run_row(f, key)

with head:
    ui.header(grid.forecast_title(g, run), grid.forecast_subtitle(g, ui.data_as_of()))
st.info(grid.banner(g), icon=":material/info:")

left, right = st.columns([1, 3])
with left:
    picked = st.selectbox(
        "Backtest day",
        grid.forecast_dates(f),
        index=None,
        placeholder="None picked: the 2024 peak day",
        format_func=lambda d: grid.date_text(d, weekday=True),
        key="p4b_day",
    )
    verdict = grid.verdict(run)
    if verdict:
        beats, sentence = verdict
        (st.success if beats else st.warning)(
            sentence, icon=":material/check_circle:" if beats else ":material/warning:"
        )
    for text in (grid.secondary(run), grid.backtest_window(run)):
        if text:
            st.markdown(text)

with right:
    day = picked or grid.default_day(f, key)
    if error := grid.error_state(f, key):
        st.warning(error, icon=":material/warning:")
    if day is not None and (empty := grid.empty_state(run, day)):
        st.info(empty, icon=":material/info:")
    elif day is not None:
        series = grid.day_series(f, key, day)
        fig = go.Figure()
        for column, label, colour, dash, width in LINES:
            fig.add_scatter(
                x=series["hour"],
                y=series[column],
                name=label,
                mode="lines",
                line={"color": colour, "dash": dash, "width": width},
                hovertemplate="%{x}:00 " + label + ": %{y:,.0f}<extra></extra>",
            )
        title = grid.day_title(day, picked=picked is not None)
        fig.update_layout(title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 15}}, height=440)
        fig.update_layout(margin={"t": 56})
        fig.update_xaxes(title="Hour of day (local time)", dtick=3)
        fig.update_yaxes(title="MW")
        table = series.rename(columns={column: label for column, label, *_ in LINES}).rename(columns={"hour": "Hour"})
        ui.chart(fig, grid.day_summary(series), table, key="p4b_fc_line")

for col, (label, value, tip) in zip(st.columns(5), grid.cards(run), strict=True):
    col.metric(label, value or "–", help=tip or None, border=True)

ui.footer(NOTE, ["DTH", "DSG"])
