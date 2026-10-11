"""Page parts every mirrored page shares, the web form of the report's frame (M6 plan Q1, Q6, Q7).

The report's frame items map here: `frame_title` / `frame_subtitle` -> `header`, `frame_footnote` -> `footer`,
`frame_nav_badge` -> `fail_badge`, `frame_reset` -> `reset_button`. Charts go through `chart`, so each has a text
summary and a "Show data" table and nothing relies on colour or hover alone (doc 04, NFR-04).
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from showcase import cache, theme


def data_as_of() -> str:
    """DAX [Data As Of]: "Data as of 7 Oct 2026", from the latest pipeline run (said so when none is recorded)."""
    finished = pd.to_datetime(cache.frames()["run_latest"]["finished_at"]).max()
    if pd.isna(finished):
        return "Data as of: no pipeline run recorded"
    return f"Data as of {finished.day} {finished:%b %Y}"


def header(title: str, subtitle: str) -> None:
    """The page's takeaway title (computed like its DAX title measure) and its subtitle line."""
    fail_badge()
    st.title(title)
    st.caption(subtitle)


def fail_badge() -> None:
    """DAX [DQ Fail Count] in the sidebar when any data-quality rule fails; nothing when none does."""
    dq = cache.frames()["dq_latest"]
    failing = int((dq["status"] == "FAIL").sum())
    if failing:
        st.sidebar.error(f"✕ {failing} data-quality rule{'s' if failing > 1 else ''} failing: see Data quality")


def reset_button(keys: Iterable[str]) -> None:
    """The report's "Reset filters" button: clears the page's widget state so the defaults come back."""
    if st.button("↺ Reset filters"):
        for key in keys:
            st.session_state.pop(key, None)
        st.rerun()


def is_dark() -> bool:
    """The viewer's theme. Streamlit infers it from the page background, so on a session's very first load it can
    report light for a dark viewer until the next rerun (any widget change); the charts then follow."""
    return st.context.theme.type == "dark"


def chart(fig: go.Figure, summary: str, data: pd.DataFrame, *, key: str) -> None:
    """A Plotly chart in the report's template, its one-sentence text summary, and a "Show data" table."""
    if is_dark():
        fig = theme.to_dark(fig)
    fig.update_layout(template="energy_transition_dark" if is_dark() else "energy_transition")
    st.plotly_chart(fig, theme=None, key=key, alt=summary)  # theme=None: the report's template, not Streamlit's
    st.caption(summary)
    with st.expander("Show data"):
        st.dataframe(data, hide_index=True)


def footer(note: str, source_codes: Iterable[str]) -> None:
    """The report's footnote (its caveats, `note`), then each source's credit as `data_source` words it."""
    st.divider()
    if note:
        st.caption(note)
    ds = cache.frames()["data_source"].set_index("data_source_code")
    credits = [f"[{ds.at[c, 'credit_text']}]({ds.at[c, 'url']})" for c in source_codes]
    st.caption("Credits: " + "; ".join(credits) + ".")  # the report's footnote already opens with "Sources:"
