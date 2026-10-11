"""Streamlit-cached access to the snapshots, for the pages (the metric ports stay plain functions)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from showcase import data


@st.cache_data
def frames() -> dict[str, pd.DataFrame]:
    return data.frames()


@st.cache_data
def manifest() -> dict:
    return data.manifest()
