"""Malaysia Energy Transition: the web showcase of the Power BI report (FR-21). Run from the repo root:

    streamlit run app/streamlit_app.py

It reads only exports/ (written by `python -m pipeline export`); see exports/README.md for the data's licences.
"""

import streamlit as st

st.set_page_config(page_title="Malaysia Energy Transition", page_icon="⚡", layout="wide")

PAGES = [
    st.Page("pages/overview.py", title="Overview", default=True),
    st.Page("pages/generation.py", title="Generation"),
    st.Page("pages/grid_load.py", title="Grid load"),
    st.Page("pages/forecast.py", title="Forecast"),
    st.Page("pages/asean.py", title="ASEAN"),
    st.Page("pages/about.py", title="About"),
    st.Page("pages/data_quality.py", title="Data quality"),
]

st.navigation(PAGES).run()
