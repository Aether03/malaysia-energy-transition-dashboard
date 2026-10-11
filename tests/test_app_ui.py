"""The shared page parts (app/showcase/ui.py) render, credit each source as data_source words it, and show the
data-quality badge only when a rule fails."""

import sys
from pathlib import Path

import pytest
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def page() -> None:
    import pandas as pd
    import plotly.graph_objects as go
    from showcase import ui

    ui.header("A takeaway title", ui.data_as_of())
    ui.chart(go.Figure(go.Bar(x=[1], y=[2])), "One bar of 2.", pd.DataFrame({"x": [1], "y": [2]}), key="c")
    ui.footer("A caveat.", ["D1", "DTH"])


def test_the_shared_parts_render_with_credits():
    at = AppTest.from_function(page, default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "A takeaway title"
    assert at.caption[0].value.startswith("Data as of ")
    captions = " ".join(c.value for c in at.caption)
    assert "One bar of 2." in captions and "A caveat." in captions
    assert "Ember (2026), Yearly Electricity Data, CC BY 4.0" in captions
    assert at.expander[0].label == "Show data"


def test_the_fail_badge_shows_only_when_a_rule_fails(monkeypatch):
    from showcase import data

    at = AppTest.from_function(page, default_timeout=30).run()
    assert not at.sidebar.error  # the exported DQ run has no FAIL

    real = data.frames

    def one_failing():
        f = real()
        f["dq_latest"] = f["dq_latest"].assign(status=["FAIL"] + ["PASS"] * (len(f["dq_latest"]) - 1))
        return f

    monkeypatch.setattr(data, "frames", one_failing)
    st.cache_data.clear()
    try:
        at = AppTest.from_function(page, default_timeout=30).run()
        assert "1 data-quality rule failing" in at.sidebar.error[0].value
    finally:
        st.cache_data.clear()  # later tests must not see the failing frames
