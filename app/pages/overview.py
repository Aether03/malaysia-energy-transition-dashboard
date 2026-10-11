"""Overview (report page P1): the year's headline KPIs, the generation mix, progress to the national target and
Malaysia's rank among its ASEAN peers. Titles, numbers and notes are the report's (see showcase/annual.py)."""

import plotly.graph_objects as go
import streamlit as st
from showcase import annual, cache, theme, ui

FOOTNOTE = (  # frame_footnote, verbatim
    "Sources: Ember Yearly Electricity Data (CC BY 4.0); OWID population (CC BY 4.0). Targets: 31% by 2025 and 40% "
    "by 2035 (12MP / SEDA MyRER, 2021), 35% by 2030 (NETR pathway), 70% by 2050 (NETR, 2023). Ember counts grid "
    "capacity only; the official share also counts off-grid and rooftop capacity. Large hydro is renewable in both. "
    "KPIs describe Malaysia in the selected year."
)
FINDINGS = [  # p1_findings, verbatim: typed text in the report, checked against the data in tests/test_page_overview.py
    (
        "1. The renewable share roughly doubled (9.6% → 19.7%, 3-year averages), mostly in a 2015–17 hydro step; "
        "since 2017 hydro and solar share the growth."
    ),
    (
        "2. Each kWh got 9.5% cleaner, yet power-sector emissions rose 27%: generation grew 40%, and all the fossil "
        "growth was coal."
    ),
    (
        "3. Malaysia is 4th of 6 ASEAN peers on renewable share and 5th of 6 on carbon intensity (606 g/kWh, 2025): "
        "the coal-to-gas balance matters as much."
    ),
]
KEYS = ["overview_year"]
LEGEND_TOP = {"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0}  # room for the legend above the plot
TOP_MARGIN = {"l": 8, "r": 8, "t": 64, "b": 8}

f = cache.frames()
head = st.container()  # the title depends on the year slicer below it

options = sorted(annual.years(f), reverse=True)  # newest first; the report's dropdown lists oldest first
pick, reset = st.columns([2, 5], vertical_alignment="bottom")
year = pick.selectbox("Year", options, index=options.index(annual.latest_complete_year(f)), key=KEYS[0])
with reset:
    ui.reset_button(KEYS)
with head:
    ui.header(annual.overview_title(f, year), annual.overview_subtitle(year, ui.data_as_of()))

if message := annual.no_data_message(f, year):
    st.info(message)

for col, kpi in zip(st.columns(5), annual.overview_kpis(f, year), strict=True):
    with col:
        st.metric(kpi.label, kpi.value, help=kpi.help)
        st.markdown(kpi.markdown)

mix_col, netr_col = st.columns([8, 5])

with mix_col:
    st.markdown("**Malaysia's generation mix by source (TWh), all years**")
    trend = annual.mix_trend(f)
    fig = go.Figure()
    for source, g in trend.groupby("source", sort=False):
        colour = g["color"].iloc[0]
        fig.add_scatter(
            x=g["year"].tolist(),
            y=g["generation_twh"].tolist(),
            name=source,
            mode="lines",
            stackgroup="one",
            line={"color": colour, "width": 0.5},
            fillcolor=colour,
            customdata=g["share_of_mix_pct"].tolist(),
            hovertemplate="%{y:.1f} TWh · %{customdata:.1f}% of the mix<extra>%{fullData.name}</extra>",
        )
    fig.update_layout(hovermode="x unified", height=320, yaxis_title="TWh", legend=LEGEND_TOP, margin=TOP_MARGIN)
    ui.chart(
        fig,
        annual.mix_summary(trend),
        trend[["year", "source", "generation_twh", "share_of_mix_pct"]].rename(
            columns={"generation_twh": "TWh", "share_of_mix_pct": "Share of the year's mix (%)"}
        ),
        key="overview_mix",
    )

with netr_col:
    st.markdown("**Renewable share of installed capacity (%)**")
    n = annual.netr_progress(f, year)
    gap = "" if n.gap is None else f"<br>Gap to target: {'-' if n.gap < 0 else '+'}{annual.fmt(abs(n.gap))} pp"
    bars = [
        (
            "RE Capacity Share (%)",
            n.ember,
            theme.MALAYSIA,
            (
                f"Ember grid basis, {year}: {annual.fmt(n.ember)}%{gap}<br>Target {annual.fmt(n.target, 0)}% by "
                f"{n.target_year}: {n.target_source}"
            ),
        ),
        (
            "Official RE Capacity Share (%)",
            n.official,
            annual.ACCENT_BLUE,
            (
                f"Official, {n.official_year} (incl. off-grid and rooftop): {annual.fmt(n.official, 0)}%<br>"
                f"{n.official_source}"
            ),
        ),
        (
            "NETR Target (%)",
            n.target,
            theme.PEER,
            f"Target {annual.fmt(n.target, 0)}% by {n.target_year}<br>{n.target_source}",
        ),
    ]
    fig = go.Figure()
    for name, value, colour, hover in bars:
        if value is not None:  # a measure that is blank for the year has no bar, as in the report
            fig.add_bar(
                name=name,
                x=[value],
                y=[""],
                orientation="h",
                marker_color=colour,
                text=[annual.fmt(value)],
                textposition="auto",
                hovertext=hover,
                hoverinfo="text",
            )
    fig.update_layout(
        barmode="group",
        height=320,
        xaxis={"range": [0, 100]},
        yaxis={"visible": False},
        legend=LEGEND_TOP,
        margin=TOP_MARGIN,
    )
    ui.chart(fig, annual.netr_summary(n), annual.netr_table(n, year), key="overview_netr")
    st.caption(n.label)  # NETR Progress Label: both bases and the target in words

rank_col, findings_col = st.columns([5, 8])

with rank_col:
    label, ranked = annual.rank_summary(f, year)
    with st.container(border=True):
        st.markdown(f"### {label} →")
        st.caption("Rank among the six largest ASEAN power systems; the ASEAN page compares them in full.")
        with st.expander("Show data"):
            st.dataframe(annual.rank_table(ranked), hide_index=True)

with findings_col:
    st.markdown("**Headline findings (2015–2025, Ember basis; caveats in docs/findings.md)**")
    st.markdown("\n".join(FINDINGS))

ui.footer(FOOTNOTE, ["D1", "D2"])
