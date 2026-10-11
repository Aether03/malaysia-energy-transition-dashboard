"""About (report page P6): every data source with its credit, licence and consent, the KPI definitions, the method
notes, the data vintage and what this web version leaves out and why. Text and tables are the report's (see
showcase/meta.py); the last two sections are the web's own."""

import streamlit as st
from showcase import cache, meta, ui

REPO = "https://github.com/Aether03/malaysia-energy-transition-dashboard"
IMAGES = f"{REPO}/blob/main/docs/img"
# frame_footnote, verbatim except for the Power BI sentence ("Links open in your browser (Ctrl+click ...)").
FOOTNOTE = (
    "Credits are worded as each licence asks. Boundaries © OpenStreetMap contributors, via geoBoundaries (ODbL 1.0). "
    "A source marked REQUESTED needs written permission and is used locally only until it is granted. Licence texts: "
    "DATA_LICENSES.md in the repository."
)
NOT_HERE = (
    "The States and Sarawak notes describe the report's Regions and State reliability pages, which are not in this "
    "web version (see below)."
)
NOTES = [  # p6_notes, verbatim; NOT_HERE follows them
    (
        "Forecast: LightGBM issued at local midnight, scored once on a locked 2024 backtest against a seasonal-naive "
        "baseline (the same hour last week). The verdict is on the Forecast page."
    ),
    "Capacity factor = generation ÷ (capacity × hours in the year); blank if capacity is unreported.",
    (
        "States: handbook labels map to states through a reference table; reliability by state covers Peninsular "
        "states only, and Sabah includes Labuan."
    ),
    (
        "Sarawak: the 2023 handbook prints each Sarawak reliability year one year early, so the years are remapped "
        "(see docs/reconciliation.md)."
    ),
    (
        "Data lag: Ember runs to 2025 (Brunei, Laos and Myanmar to 2024); grid load covers 2023-24; DOSM supply ends "
        "in June 2024 and is a cross-check only."
    ),
]
# The sources the page draws on: every one the web version uses or links to (D5: the two adapted chart images).
# D4 is not used, and GEO's credit is already in the footnote.
CREDITED = ["D1", "D2", "D3", "D5", "D6", "DSG", "DTH"]

f = cache.frames()
manifest = cache.manifest()

ui.header("Where the data comes from, and on what terms", meta.run_summary(f))  # [Run Summary] is the subtitle

st.subheader("Sources and licences")
st.table(meta.sources_table(f).set_index("Source"))
if consent := meta.consent_summary(f):
    st.markdown(f"**Needs written permission:** {consent}")  # [Consent Summary]
st.link_button("Source code on GitHub", REPO)

st.subheader("KPI definitions")
st.table(meta.kpi_table(f).set_index("KPI"))

st.markdown("**Method notes**")
st.markdown("\n".join(f"- {note}" for note in NOTES))
st.caption(NOT_HERE)

st.subheader("Data vintage")
run = f"pipeline run {manifest['run']['run_id']}" if manifest.get("run") else "no pipeline run recorded"
st.markdown(f"These snapshots were exported on **{meta.exported_at(manifest)}** from {run}.")
st.table(meta.vintage_table(manifest, f).set_index("Source"))

st.subheader("What the web version leaves out, and why")
st.markdown(
    "The report's **Regions** and **State reliability** pages are not in this web version. The Energy Commission's "
    "written consent covers the handbook's charts as images (and a PDF and a video), not its data rows, and a web "
    "version has to ship the rows behind its charts. Those two pages stay as images, which you can open here:"
)
st.markdown(
    f"- [Regions]({IMAGES}/03_regions.png)\n- [State reliability]({IMAGES}/04_state_reliability.png)\n\n"
    "Charts adapted from the handbook with the Energy Commission's written permission (9 October 2026). "
    "Not endorsed by the Energy Commission."
)
st.markdown(
    "Every exported view is checked against its source's licence, and anything not cleared is left out. "
    "These are the ones left out of the latest export:"
)
st.table(meta.left_out(manifest).set_index("Left out"))

ui.footer(FOOTNOTE, CREDITED)
