"""Pure functions behind the About (P6) and Data quality (P6b) pages (M6 step 5).

They take the snapshot frames (`data.frames()`) and the export manifest and return the strings and tables the pages
draw, so they are unit-tested without Streamlit. Each function names the DAX measure it translates (in
`report/EnergyTransition.SemanticModel/definition/tables/_Measures.tmdl`). Only metadata is read: `data_source`, `kpi`,
`run_latest`, `source_load_latest` and `dq_latest` (whose D5 rules have no detail by design).

A DAX BLANK becomes an empty cell here, so what the report leaves empty stays empty.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from showcase import theme

Frames = Mapping[str, pd.DataFrame]
NO_RUN = "No pipeline run recorded"
STATUSES = ("PASS", "WARN", "FAIL")  # the order of the report's sentence "pass, warn or fail"
CONSENT_WORDS = {"REQUESTED": "permission requested", "GRANTED": "permission granted", "REFUSED": "permission refused"}
# The Result column's conditional format in the report (p6b_dq_table): status -> (fill, text).
CHIP_COLOURS = {"PASS": ("#0ca30c", "#0b0b0b"), "WARN": ("#fab219", "#0b0b0b"), "FAIL": ("#d03b3b", "#ffffff")}


def _by_name(df: pd.DataFrame) -> pd.DataFrame:
    """Sorted ascending by `name`, ignoring case, as Power BI sorts a text column."""
    return df.sort_values("name", key=lambda s: s.str.casefold())


def _minutes(ts) -> str:
    """DAX FORMAT(x, "yyyy-mm-dd hh:nn")."""
    return f"{pd.Timestamp(ts):%Y-%m-%d %H:%M}"


def _blank_if_missing(s: pd.Series) -> pd.Series:
    return s.astype(object).where(s.notna(), None)


# ---------------------------------------------------------------- About (P6)
def run_summary(f: Frames) -> str:
    """[Run Summary]: the latest completed run, its status, start and finish (UTC)."""
    run = f["run_latest"]
    if run.empty:
        return NO_RUN
    started, finished = pd.to_datetime(run["started_at"]).max(), pd.to_datetime(run["finished_at"]).max()
    return f"Run {int(run['run_id'].max())} · {run['status'].max()} · started {_minutes(started)}, finished {_minutes(finished)} UTC"


def consent_summary(f: Frames) -> str:
    """[Consent Summary]: each source that needs written permission, with the status of the request (empty if none)."""
    ds = _by_name(f["data_source"])
    ds = ds[ds["consent_status"] != "OPEN"]
    return "; ".join(
        f"{r['name']}: {CONSENT_WORDS.get(r['consent_status'], r['consent_status'])}" for _, r in ds.iterrows()
    )


def sources_table(f: Frames) -> pd.DataFrame:
    """p6_sources: one row per `data_source` row, by name: what it provides, licence, credit, consent and link."""
    ds = _by_name(f["data_source"])
    return pd.DataFrame(
        {
            "Source": ds["name"],
            "What it provides": ds["provides"],
            "Licence": ds["licence"],
            "Credit": ds["credit_text"],
            "Consent": ds["consent_status"],
            "Link": ds["url"],
        }
    ).reset_index(drop=True)


def kpi_table(f: Frames) -> pd.DataFrame:
    """p6_kpis: every `kpi` row by name: definition, formula and unit."""
    kpi = _by_name(f["kpi"])
    return pd.DataFrame(
        {"KPI": kpi["name"], "Definition": kpi["definition"], "Formula": kpi["formula"], "Unit": kpi["unit"]}
    ).reset_index(drop=True)


def exported_at(manifest: Mapping) -> str:
    """When the snapshots were written (`manifest.exported_at`), in UTC to the minute."""
    ts = pd.Timestamp(manifest["exported_at"])
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return f"{ts:%Y-%m-%d %H:%M} UTC"


def vintage_table(manifest: Mapping, f: Frames) -> pd.DataFrame:
    """The data vintage per source (`manifest.data_vintage`): its latest load and the version of the file it read."""
    names = f["data_source"].set_index("data_source_code")["name"]
    rows = manifest["data_vintage"]
    return pd.DataFrame(
        {
            "Source": [names.get(v["data_source_code"], v["data_source_code"]) for v in rows],
            "Run": [v["run_id"] for v in rows],
            "Loaded": [_minutes(v["loaded_at"]) for v in rows],
            "Source version": [v["source_version"] for v in rows],
        }
    )


def left_out(manifest: Mapping) -> pd.DataFrame:
    """What the export left out and why (M6 plan Q3): the excluded views, then the excluded showcase queries."""
    kinds = (("Data view", manifest["excluded_views"]), ("Showcase query", manifest["excluded_showcase"]))
    rows = [(name, kind, why) for kind, excluded in kinds for name, why in sorted(excluded.items())]
    return pd.DataFrame(rows, columns=["Left out", "Kind", "Why"])


# ---------------------------------------------------------------- Data quality (P6b)
def status_label(status: str) -> str:
    """[DQ Status Label]: the status as icon and word (doc 04 section 3.5, never colour alone)."""
    return theme.STATUS[status][1]


def chip_css(label: str) -> str:
    """The report's fill and text colour for a Result cell; nothing for anything but the three labels."""
    for status, (fill, text) in CHIP_COLOURS.items():
        if label == status_label(status):
            return f"background-color: {fill}; color: {text}; font-weight: 600"
    return ""


def dq_summary(f: Frames) -> str:
    """[DQ Summary]: the whole run's counts (the measures remove the page's filters), or the empty message."""
    status = f["dq_latest"]["status"]
    if status.empty:
        return NO_RUN
    n = {s: int((status == s).sum()) for s in STATUSES}
    return f"{n['PASS']} pass · {n['WARN']} warn · {n['FAIL']} fail, of {len(status)} rules"


def dq_empty_message(f: Frames) -> str:
    """[DQ Empty Message]: shown when no rule was checked yet; blank otherwise."""
    return NO_RUN if f["dq_latest"].empty else ""


def dq_rules(f: Frames, statuses: Sequence[str] = (), source: str | None = None) -> pd.DataFrame:
    """p6b_dq_table: the rules, worst first (rows affected descending, then rule code).

    `statuses` is the Pass/Warn/Fail slicer (none picked = all); `source` is the code selected in the rows table,
    which keeps only that source's rules (a rule with no source never matches one).
    """
    dq = f["dq_latest"]
    if statuses:
        dq = dq[dq["status"].isin(statuses)]
    if source:
        dq = dq[dq["data_source_code"] == source]
    dq = dq.sort_values(["rows_affected", "rule_code"], ascending=[False, True])
    return pd.DataFrame(
        {
            "Rule": dq["rule_code"],
            "Source": _blank_if_missing(dq["data_source_code"]),
            "Severity": dq["severity"],
            "Result": dq["status"].map(status_label),
            "Rows affected": dq["rows_affected"],
            "What it checks": dq["description"],
            # the warehouse writes Python reprs; Decimal('202.7540') reads as 202.7540
            "Detail": _blank_if_missing(dq["detail"].str.replace(r"Decimal\('([^']*)'\)", r"\1", regex=True)),
        }
    ).reset_index(drop=True)


def source_loads(f: Frames) -> pd.DataFrame:
    """p6b_sources: each source's latest load by name. [Source Rows Read], [Source Rows Changed], [Source Last Loaded].

    The DAX leaves a source with no load blank, so it drops out of the table.
    """
    load = (
        f["source_load_latest"]
        .groupby("data_source_code", as_index=False)
        .agg(rows_in=("rows_in", "sum"), rows_merged=("rows_merged", "sum"), loaded_at=("loaded_at", "max"))
    )
    shown = _by_name(f["data_source"][["data_source_code", "name"]].merge(load, on="data_source_code"))
    return pd.DataFrame(
        {
            "Code": shown["data_source_code"],
            "Source": shown["name"],
            "Rows read": shown["rows_in"],
            "Rows changed": shown["rows_merged"],
            "Last loaded": pd.to_datetime(shown["loaded_at"]).dt.strftime("%Y-%m-%d"),
        }
    ).reset_index(drop=True)
