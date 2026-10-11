"""Pure functions behind the Grid load (P4) and Forecast (P4b) pages (M6 step 4).

They take the snapshot frames (`data.frames()`) and the page's selection and return the strings and tables the pages
draw, so they are unit-tested without Streamlit. Each function names the DAX measure it translates (in
`report/EnergyTransition.SemanticModel/definition/tables/_Measures.tmdl`). Peaks and flows come from the step 3
ports in `metrics.py` (`rows` below are their results); the rest is computed from the frames here.

The report's page filter keeps 2023 and 2024 on P4 (`YEARS`). A DAX BLANK becomes None, so a state the report
leaves empty stays empty here.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

import numpy as np
import pandas as pd

from showcase import annual

Frames = Mapping[str, pd.DataFrame]
YEARS = (2023, 2024)  # P4's page filter on dim_date[year]
ERROR_STATE = "Forecast not generated in latest run — see About page"  # [Forecast Error State]


# ---------------------------------------------------------------- DAX FORMAT
def num(x: float, digits: int = 0, *, thousands: bool = False) -> str:
    """DAX FORMAT(x, "0.0" or "#,0"): `annual.fmt`, the one implementation (halves away from zero, no "-0")."""
    return annual.fmt(x, digits, grouping=thousands)


def date_text(d: date | datetime, *, weekday: bool = False) -> str:
    """FORMAT(d, "d mmm yyyy") or, with `weekday`, "ddd d mmm yyyy"."""
    return (f"{d:%a} " if weekday else "") + f"{d.day} {d:%b %Y}"


def _blank(v) -> bool:
    return v is None or bool(pd.isna(v))


def _day(v) -> date:
    return date.fromisoformat(str(v)[:10])


# ---------------------------------------------------------------- the grid selector and the shared text
def grid_names(f: Frames) -> list[str]:
    """dim_grid[name] in display order: the grid slicer's options."""
    return list(f["dim_grid"].sort_values("display_order")["name"])


def grid_row(f: Frames, name: str) -> dict:
    return f["dim_grid"].set_index("name").loc[name].to_dict() | {"name": name}


def banner(grid: dict) -> str:
    """[Grid Banner]."""
    return f"Showing: {grid['name']} · {grid['banner_note']}"


def load_subtitle(grid: dict, as_of: str) -> str:
    """[P4 Subtitle]."""
    return f"{grid['demand_label']} · hourly, 2023–24 · local time · {as_of}"


def forecast_subtitle(grid: dict, as_of: str) -> str:
    """[P4 Forecast Subtitle]."""
    return f"{grid['demand_label']} · day-ahead backtest, 2024 · local time · {as_of}"


# ---------------------------------------------------------------- P4 Grid load
def _hours(f: Frames, grid_key: int) -> pd.DataFrame:
    """The grid's hourly demand under the page filter."""
    h = f["grid_hourly"]
    return h[(h["grid_key"] == grid_key) & h["year"].isin(YEARS)]


def _peaks(rows: list[dict], code: str, year: int | None = None) -> list[dict]:
    """The whole-year rows (month None) of `metrics.grid_load` for the grid, under the page filter."""
    return [
        r
        for r in rows
        if r["grid_code"] == code
        and r["month"] is None
        and r["year"] in YEARS
        and (year is None or r["year"] == year)
        and not _blank(r["peak_mw"])
    ]


def load_factor(f: Frames, grid_key: int, year: int) -> float | None:
    """[Load Factor (%)] = 100 * DIVIDE(AVERAGE(demand), MAX(demand)), unrounded: the twin's 2-place rounding would
    flip 3 of the 48 monthly 1-place values the report shows."""
    d = f["grid_hourly"]
    d = d[(d["grid_key"] == grid_key) & (d["year"] == year)]["demand_mw"]
    return None if d.empty or d.max() == 0 else float(100 * d.mean() / d.max())


def load_title(grid: dict, f: Frames, rows: list[dict]) -> str:
    """[P4 Load Title]: the 2024 peak (from the port) and load factor of the chosen grid."""
    peak = _peaks(rows, grid["grid_code"], 2024)
    if not peak:
        return "Grid load"
    lf = load_factor(f, grid["grid_key"], 2024)
    return (
        f"{grid['country_name']}: demand peaked at {num(peak[0]['peak_mw'], 0, thousands=True)} MW in 2024; "
        f"load factor {'' if lf is None else num(lf)}%"
    )


def peak_text(rows: list[dict], code: str) -> str | None:
    """[Peak Text]: the highest hour over 2023-24 and, of tied hours, the earliest ("Peak 35,560 MW on 29 Apr 2024, 21:00")."""
    peaks = _peaks(rows, code)
    if not peaks:
        return None
    top = max(r["peak_mw"] for r in peaks)
    at = datetime.fromisoformat(min(r["peak_at"] for r in peaks if r["peak_mw"] == top))
    return f"Peak {num(top, 0, thousands=True)} MW on {date_text(at)}, {at.hour}:00"


def heatmap(f: Frames, grid_key: int) -> pd.DataFrame:
    """[Avg Load (GW)] by month (rows, January first) and hour (columns 0-23), over 2023-24."""
    months = f["dim_date"][["date_key", "month", "month_name"]]
    d = _hours(f, grid_key)[["date_key", "hour", "demand_mw"]].merge(months, on="date_key")
    z = d.groupby(["month", "month_name", "hour"])["demand_mw"].mean().div(1000).unstack("hour")
    z.index = z.index.get_level_values("month_name")
    return z.reindex(columns=range(24)).rename_axis(index="Month", columns="hour")


def season_options(f: Frames, grid_key: int) -> list[str]:
    """season_pick[season] for the grid, by season_order: the season slicer's options."""
    pick = f["season_pick"]
    return list(pick[pick["grid_key"] == grid_key].sort_values("season_order")["season"])


def load_curve(f: Frames, grid_key: int, seasons: list[str]) -> pd.DataFrame:
    """[Avg Load Curve (MW)] by day type and hour: TREATAS(VALUES(season_pick[season]), grid_hourly[season]).

    Nothing picked means every season season_pick lists for the grid, so hours of an unlisted season drop out.
    """
    listed = season_options(f, grid_key)
    chosen = [s for s in seasons if s in listed] or listed
    h = _hours(f, grid_key)
    h = h[h["season"].isin(chosen)]
    out = h.groupby(["day_type", "hour"], as_index=False)["demand_mw"].mean()
    return out.rename(columns={"demand_mw": "mean_mw"})


def monthly(f: Frames, grid: dict, rows: list[dict]) -> pd.DataFrame:
    """[Peak Load (MW)] (from the port) and [Load Factor (%)] per year and month, with the month's name."""
    code = grid["grid_code"]
    peaks = [
        {"year": r["year"], "month": r["month"], "peak_mw": r["peak_mw"]}
        for r in rows
        if r["grid_code"] == code and r["year"] in YEARS and r["month"] is not None
    ]
    cols = ["year", "month", "month_name", "peak_mw", "load_factor_pct"]
    if not peaks:
        return pd.DataFrame(columns=cols)
    mean = _hours(f, grid["grid_key"]).groupby(["year", "month"])["demand_mw"].mean().rename("mean_mw").reset_index()
    out = pd.DataFrame(peaks).astype({"month": int}).merge(mean, on=["year", "month"])
    out["load_factor_pct"] = 100 * out["mean_mw"] / out["peak_mw"].replace(0, np.nan)
    names = f["dim_date"].drop_duplicates("month").set_index("month")["month_name"]
    out["month_name"] = out["month"].map(names)
    return out.sort_values(["year", "month"])[cols].reset_index(drop=True)


def by_month(m: pd.DataFrame, column: str, digits: int) -> pd.DataFrame:
    """One column of `monthly` as a Month x year table."""
    t = m.pivot(index="month", columns="year", values=column).round(digits)
    t.index = m.drop_duplicates("month").set_index("month").loc[t.index, "month_name"]
    t.columns = [str(c) for c in t.columns]
    return t.rename_axis("Month").reset_index()


def flow_daily(f: Frames, grid_key: int) -> pd.DataFrame:
    """[Daily Net Flow (MW)]: the mean net flow with Malaysia per day, 2023-24; days without data stay NaN gaps."""
    fd = f["grid_flow_daily"]
    fd = fd[(fd["grid_key"] == grid_key) & (fd["counterparty"] == "MY") & fd["year"].isin(YEARS)]
    if fd.empty:
        return pd.DataFrame({"date": pd.to_datetime([]), "net_flow_mw": []})
    s = fd.assign(date=pd.to_datetime(fd["date"])).groupby("date")["net_flow_mw"].mean()
    return s.reindex(pd.date_range(s.index.min(), s.index.max())).rename_axis("date").reset_index()


def flow_note(rows: list[dict], code: str) -> str:
    """[Flow Subtitle]: annual export and import totals (from `metrics.interconnector_flows`), or the no-flows line."""
    by = {r["year"]: r for r in rows if r["grid_code"] == code}

    def gwh(year: int, field: str) -> str:
        v = by.get(year, {}).get(field)
        return "" if _blank(v) else num(v, 1, thousands=True)

    if _blank(by.get(2023, {}).get("export_gwh")) and _blank(by.get(2024, {}).get("export_gwh")):
        return "No Malaysia interconnector flows are published for this grid"
    return (
        f"Exported {gwh(2023, 'export_gwh')} GWh to Malaysia and imported {gwh(2023, 'import_gwh')} GWh in 2023; "
        f"{gwh(2024, 'export_gwh')} and {gwh(2024, 'import_gwh')} GWh in 2024. Above 0 = Thailand exports"
    )


# One-sentence text summaries of the charts (alt text and caption, doc 04 section 7).
def heatmap_summary(z: pd.DataFrame) -> str:
    s = z.stack()
    if s.empty:
        return "No hourly load is published for this grid."
    (hi_m, hi_h), (lo_m, lo_h) = s.idxmax(), s.idxmin()
    return (
        f"Average load is highest at {num(s.max(), 1)} GW ({hi_m}, {hi_h}:00) and lowest at "
        f"{num(s.min(), 1)} GW ({lo_m}, {lo_h}:00)."
    )


def curve_summary(curve: pd.DataFrame, seasons: list[str]) -> str:
    parts = []
    for day_type, c in curve.groupby("day_type"):
        hi, lo = c.loc[c["mean_mw"].idxmax()], c.loc[c["mean_mw"].idxmin()]
        parts.append(
            f"{day_type.lower()} load runs from {num(lo['mean_mw'], 0, thousands=True)} MW at {int(lo['hour'])}:00 to "
            f"{num(hi['mean_mw'], 0, thousands=True)} MW at {int(hi['hour'])}:00"
        )
    scope = ", ".join(seasons) if seasons else "all seasons"
    return f"On a typical day ({scope}), " + "; ".join(parts) + "." if parts else "No hourly load for these seasons."


def monthly_summary(m: pd.DataFrame, column: str, unit: str) -> str:
    if m.empty:
        return "No monthly values are published for this grid."
    hi, lo = m.loc[m[column].idxmax()], m.loc[m[column].idxmin()]
    digits = 0 if unit == "MW" else 1
    label = "monthly peak" if unit == "MW" else "load factor"
    sep = "" if unit == "%" else " "
    return (
        f"The highest {label} is {num(hi[column], digits, thousands=True)}{sep}{unit} ({hi['month_name']} {hi['year']}) "
        f"and the lowest {num(lo[column], digits, thousands=True)}{sep}{unit} ({lo['month_name']} {lo['year']})."
    )


def flow_summary(flow: pd.DataFrame) -> str:
    s = flow.dropna()
    hi, lo = s.loc[s["net_flow_mw"].idxmax()], s.loc[s["net_flow_mw"].idxmin()]
    return (
        f"Daily mean net flow runs from {num(lo['net_flow_mw'], 0, thousands=True)} MW ({date_text(lo['date'])}) to "
        f"{num(hi['net_flow_mw'], 0, thousands=True)} MW ({date_text(hi['date'])}); above 0 Thailand exports."
    )


# ---------------------------------------------------------------- P4b Forecast
def run_row(f: Frames, grid_key: int) -> dict | None:
    """The grid's row of forecast_run_current; None unless exactly one (DAX SELECTEDVALUE is blank otherwise)."""
    r = f["forecast_run_current"]
    r = r[r["grid_key"] == grid_key]
    return r.iloc[0].to_dict() if len(r) == 1 else None


def forecast_title(grid: dict, run: dict | None) -> str:
    """[P4 Title]: the whole-percent improvement over the baseline, or the plain fallbacks."""
    impr = None if run is None else run.get("improvement_pct")
    country = grid["country_name"]
    if _blank(impr):
        return f"{country}: hourly grid load"
    if impr > 0:
        return f"{country}: day-ahead forecast cuts hourly error by {num(impr)}%"
    return f"{country}: day-ahead forecast does not beat the baseline"


def improvement_ci(run: dict | None) -> str | None:
    """[Backtest Improvement CI]."""
    if run is None or _blank(run.get("improvement_ci_low")):
        return None
    return f"95% CI {num(run['improvement_ci_low'], 1)} to {num(run['improvement_ci_high'], 1)}"


def backtest_window(run: dict | None) -> str | None:
    """[Backtest Window]."""
    if run is None or _blank(run.get("model_run_id")):
        return None
    return (
        f"Backtest {date_text(_day(run['test_start']))} – {date_text(_day(run['test_end']))} · "
        f"{num(run['scored_hours'], 0, thousands=True)} hours scored, {num(run['excluded_hours'], 0, thousands=True)} excluded"
    )


def verdict(run: dict | None) -> tuple[bool, str] | None:
    """[Forecast Verdict]: (beats the baseline?, sentence); None (BLANK) without a run."""
    if run is None or _blank(run.get("beats_baseline")):
        return None
    if run["beats_baseline"]:
        pct = num(run["improvement_pct"], 1)
        return True, f"Beats the seasonal-naive baseline: {pct}% lower MAPE ({improvement_ci(run) or ''})"
    return False, "WARN: does not beat the seasonal-naive baseline (the 95% CI includes 0); results kept as recorded"


def secondary(run: dict | None) -> str | None:
    """[Forecast Secondary]: the pre-declared comparison with the weekday-aware naive rule."""
    if run is None or _blank(run.get("improvement_weekday_ci_low")):
        return None
    lo, hi = run["improvement_weekday_ci_low"], run["improvement_weekday_ci_high"]
    ci = f"95% CI {num(lo, 1)} to {num(hi, 1)}"
    if lo > 0:
        return f"Also beats a weekday-aware naive rule: {num(run['improvement_weekday_pct'], 1)}% lower MAPE ({ci})"
    return f"Its edge over a simple weekday-aware naive rule is not established ({ci} includes 0)"


def cards(run: dict | None) -> list[tuple[str, str, str]]:
    """The five backtest cards as (label, value, tooltip): [Backtest MAPE Model/Baseline (%)] 0.00, [Backtest
    Improvement (%)] 0.0, [Backtest MAE Model/Baseline (MW)] #,0. The tooltip lists the window, the CI and the MAE
    pair, each card leaving out its own measure (the report's Tooltips field well)."""
    spec = [
        ("Model MAPE (%)", "mape_model", 2, "Backtest MAPE Model (%)"),
        ("Baseline MAPE (%)", "mape_baseline", 2, "Backtest MAPE Baseline (%)"),
        ("Improvement (%)", "improvement_pct", 1, "Backtest Improvement (%)"),
        ("Model MAE (MW)", "mae_model", 0, "Backtest MAE Model (MW)"),
        ("Baseline MAE (MW)", "mae_baseline", 0, "Backtest MAE Baseline (MW)"),
    ]

    def fmt(field: str, digits: int) -> str:
        return "" if run is None or _blank(run.get(field)) else num(run[field], digits, thousands=True)

    others = [
        ("Backtest Window", backtest_window(run)),
        ("Backtest Improvement CI", improvement_ci(run)),
        ("Backtest MAE Model (MW)", fmt("mae_model", 0)),
        ("Backtest MAE Baseline (MW)", fmt("mae_baseline", 0)),
    ]
    return [
        (label, fmt(field, digits), "\n\n".join(f"{n}: {v}" for n, v in others if v and n != measure))
        for label, field, digits, measure in spec
    ]


def forecast_dates(f: Frames) -> list[date]:
    """forecast_date[date]: the backtest days the date slicer offers."""
    return [_day(d) for d in sorted(f["forecast_date"]["date"])]


def default_day(f: Frames, grid_key: int) -> date | None:
    """[Forecast Default Day]: the day of the grid's highest actual hour (the earliest, if tied)."""
    d = f["load_forecast_current"]
    d = d[(d["grid_key"] == grid_key) & d["actual_mw"].notna()]
    if d.empty:
        return None
    return _day(d.sort_values(["actual_mw", "ts_local"], ascending=[False, True]).iloc[0]["ts_local"])


def day_series(f: Frames, grid_key: int, day: date) -> pd.DataFrame:
    """[Day Actual / Model / Baseline (MW)] for the 24 hours of `day`; hours without a row stay NaN."""
    d = f["load_forecast_current"]
    d = d[(d["grid_key"] == grid_key) & (d["date_key"] == day.year * 10000 + day.month * 100 + day.day)]
    cols = ["actual_mw", "forecast_mw", "baseline_mw"]
    out = d.groupby("hour")[cols].sum(min_count=1).reindex(range(24))
    return out.rename(columns={"forecast_mw": "model_mw"}).rename_axis("hour").reset_index()


def day_title(day: date, *, picked: bool) -> str:
    """[Forecast Day Title]."""
    return f"Forecast vs actual, {date_text(day, weekday=True)}" + ("" if picked else " (2024 peak day)")


def empty_state(run: dict | None, day: date) -> str | None:
    """[Forecast Empty State]: the day is outside the backtest window."""
    if run is None or _blank(run.get("test_start")):
        return None
    start, end = _day(run["test_start"]), _day(run["test_end"])
    if start <= day <= end:
        return None
    return f"Forecast available for {date_text(start)} – {date_text(end)}"


def error_state(f: Frames, grid_key: int) -> str | None:
    """[Forecast Error State]: the forecast step did not succeed (a blank status is not "SUCCESS" either)."""
    s = f["forecast_status"]
    s = s[s["grid_key"] == grid_key]["status"]
    return None if len(s) == 1 and s.iloc[0] == "SUCCESS" else ERROR_STATE


def day_summary(series: pd.DataFrame) -> str:
    """One sentence for the day chart: peak actual vs what the model and baseline gave at that hour."""
    s = series.dropna(subset=["actual_mw"])
    if s.empty:
        return "No hourly values for this day."
    peak = s.loc[s["actual_mw"].idxmax()]
    return (
        f"Actual demand peaks at {num(peak['actual_mw'], 0, thousands=True)} MW at {int(peak['hour'])}:00, when the "
        f"model forecast {num(peak['model_mw'], 0, thousands=True)} MW and the baseline "
        f"{num(peak['baseline_mw'], 0, thousands=True)} MW."
    )
