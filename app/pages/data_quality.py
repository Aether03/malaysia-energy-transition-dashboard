"""Data quality (report page P6b): every rule of the latest pipeline run with its result as icon and word, a
Pass/Warn/Fail slicer, the rows table that narrows the rules to one source, and the expected-warnings note.
Numbers and text are the report's (see showcase/meta.py); 'click' became 'select' and the button became the sidebar."""

import streamlit as st
from showcase import cache, meta, ui

SUBTITLE = "Results of the most recent run · pass, warn or fail · select a source to see its rules"
# frame_footnote, verbatim except the nav button (now the sidebar notice) and 'click' (now 'select').
FOOTNOTE = (
    "Rules run on every pipeline run; the notice in the sidebar counts rules that FAIL. The four WARNs above are "
    "expected differences between sources, not pipeline faults (docs/reconciliation.md). Select a source in the table "
    "to see only its rules; select it again to clear. Rules with no source check the grid data."
)
WARN_NOTE = [  # p6b_warn_note, verbatim
    "OWID_GEN_WITHIN_5PCT: OWID uses a different upstream vintage than Ember.",
    "DOSM_SUPPLY_WITHIN_10PCT: DOSM's supply is a net balance below Ember's gross generation, and Ember revised 2021 on.",
    "CF_AT_MOST_1: Ember's capacity is too small for the generation it reports.",
    "STALE_COUNTRY_YEARS: Brunei, Laos and Myanmar end in 2024.",
]
NO_MATCH = "No rules match the selected result and source."
# The sources whose loads the rows table lists; the footer credits them as the other pages do.
CREDITED = ["D1", "D2", "D3", "D5", "DSG", "DTH"]

f = cache.frames()
ui.header("Every data-quality rule, checked on each pipeline run", SUBTITLE)

run_col, summary_col = st.columns([3, 2])
run_col.markdown(meta.run_summary(f))  # p6b_run_summary = [Run Summary]
summary_col.markdown(f"**{meta.dq_summary(f)}**")  # p6b_dq_summary = [DQ Summary]: the whole run, whatever is picked

left, right = st.columns([3, 2])

with left:
    picked = st.pills(  # p6b_status_slicer: none picked shows every rule
        "Result", meta.STATUSES, selection_mode="multi", format_func=meta.status_label, key="dq_status"
    )
    st.markdown("**Rows per source (select one to filter the rules)**")  # p6b_sources
    loads = meta.source_loads(f)
    event = st.dataframe(loads, hide_index=True, on_select="rerun", selection_mode="single-row", key="dq_source_pick")
    rows = event.selection.rows
    source = loads.iloc[rows[0]]["Code"] if rows and rows[0] < len(loads) else None

with right:
    st.markdown("**Expected WARNs (docs/reconciliation.md)**")  # p6b_warn_note
    st.markdown("\n".join(f"- {line}" for line in WARN_NOTE))

# The rules at full width: seven columns, some long, don't fit beside the source list.
st.markdown("**Data-quality rules**")  # p6b_dq_table
shown = meta.dq_rules(f, picked or (), source)
if message := meta.dq_empty_message(f):  # p6b_dq_empty = [DQ Empty Message]
    st.info(message)
elif shown.empty:
    st.info(NO_MATCH)  # the web's own: the report's slicer only lists results the run has
else:
    styled = shown.set_index("Rule").style.map(meta.chip_css, subset=["Result"]).format(na_rep="")
    st.table(styled, height=504)

ui.footer(FOOTNOTE, CREDITED)
