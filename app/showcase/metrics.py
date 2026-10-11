"""Pandas ports of the report's numbers, computed from the exported views (M6 plan Q4).

Contract: each function reproduces one `sql/showcase` query from the snapshot frames (`data.frames()`, keyed by
view name) and returns rows with the query's column names, row set and rounding. `tests/test_app_metrics.py`
compares the result with `exports/expected.json[<query>]`: text, dates and integers exactly, other numbers up to
float noise (1e-9; the twins' max(0.05, 0.1%) was loosened slack, M6 review). The SQL file is the specification; where its
comments describe a choice (a year window, a blank reason, a rounding), the port makes the same one.

The pages build their charts from these results or from the same frames, so a number on the web page is the
number the SQL twin, and therefore the Power BI measure, gives.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np
import pandas as pd

Frames = Mapping[str, pd.DataFrame]


def _round(x, digits: int):
    """CAST(x AS DECIMAL(p, digits)): SQL Server rounds half away from zero, numpy rounds half to even.

    The scaled value is trimmed to 9 places first, so a float that is a .5 tie in decimal (65.4499999...) still ties.
    """
    scaled = np.round(x * 10**digits, 9)
    return np.sign(scaled) * np.floor(np.abs(scaled) + 0.5) / 10**digits


def _pct_change(cur, prev):
    """100 * (cur - prev) / NULLIF(prev, 0), as float."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return 100.0 * (cur - prev) / np.where(np.asarray(prev) == 0, np.nan, prev)


def _records(df: pd.DataFrame) -> list[dict]:
    """Rows as plain Python values, with NaN and <NA> as None (the SQL NULLs of expected.json)."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def _focus_keys(f: Frames) -> pd.Series:
    return f["dim_country"].loc[f["dim_country"]["is_focus"], "country_key"]


def trends(f: Frames) -> list[dict]:
    """sql/showcase/01_trends.sql: Malaysia's generation by source (TWh) and share of the mix, every year."""
    g = f["generation_annual"].merge(f["dim_source"], on="source_key")
    g = g[g["country_key"].isin(_focus_keys(f))].sort_values(["year", "sort_order"])
    total = g.groupby("year")["generation_twh"].transform("sum", min_count=1).replace(0, np.nan)

    def group_share(group: str) -> pd.Series:  # 100 * SUM(CASE WHEN group_name = ... END) OVER (PARTITION BY year)
        in_group = g["generation_twh"].where(g["group_name"] == group)
        return _round(100.0 * in_group.groupby(g["year"]).transform("sum", min_count=1) / total, 3)

    out = pd.DataFrame(
        {
            "year": g["year"],
            "source": g["display_name"],
            "group_name": g["group_name"],
            "generation_twh": g["generation_twh"],
            "share_of_mix_pct": _round(100.0 * g["generation_twh"] / total, 3),
            "re_share_pct": group_share("RENEWABLE"),
            "fossil_share_pct": group_share("FOSSIL"),
        }
    )
    return _records(out)


def yoy_lag(f: Frames) -> list[dict]:
    """sql/showcase/02_yoy_lag.sql: year-on-year change of each headline KPI, with its polarity (P1 deltas)."""
    ca = f["country_annual"]
    ca = ca[ca["country_key"].isin(_focus_keys(f))].sort_values("year")  # LAG(...) OVER (ORDER BY year)
    # (kpi_code, column, change is in percentage points): shares move in pp, the rest in percent
    kpis = [
        ("TOTAL_GENERATION", "total_generation_twh", False),
        ("DEMAND_GROWTH", "demand_twh", False),
        ("RE_SHARE_GEN", "re_share_gen_pct", True),
        ("FOSSIL_SHARE_GEN", "fossil_share_gen_pct", True),
        ("CARBON_INTENSITY", "emissions_intensity_gco2e_kwh", False),
        ("DEMAND_PER_CAPITA", "demand_per_capita_mwh", False),
    ]
    parts = []
    for code, col, is_pp in kpis:
        value, prev = ca[col], ca[col].shift()
        change = _round(value - prev if is_pp else _pct_change(value, prev), 3)
        unit = "pp" if is_pp else "%"
        parts.append(
            pd.DataFrame({"year": ca["year"], "kpi_code": code, "value": value, "change": change, "change_unit": unit})
        )
    out = pd.concat(parts).merge(f["kpi"][["kpi_code", "polarity"]], on="kpi_code")
    # direction judges the rounded change: one that rounds to 0.000 is NEUTRAL, as is the first year's NULL
    good = np.sign(out["change"]) == out["polarity"]
    out["direction"] = np.where(out["change"].isna() | (out["change"] == 0), "NEUTRAL", np.where(good, "GOOD", "BAD"))
    return _records(out.drop(columns="polarity").sort_values(["kpi_code", "year"]))


def ranking(f: Frames) -> list[dict]:
    """sql/showcase/03_ranking.sql: Malaysia's rank among its ASEAN peers on RE share, intensity, per-capita demand."""
    dc, ca = f["dim_country"], f["country_annual"]
    peers = dc.loc[dc["is_default_peer"], ["country_key", "name"]]
    d = peers.merge(ca[ca["year"] <= f["dim_year"]["year"].max()], on="country_key")  # range_end = the full range
    # the latest year every peer has the metric for: MIN over peers of each one's latest year
    gen_year = d.loc[d["re_share_gen_pct"].notna()].groupby("country_key")["year"].max().min()
    per_capita_year = d.loc[d["demand_per_capita_mwh"].notna()].groupby("country_key")["year"].max().min()

    g = d[(d["year"] == gen_year) & d["re_share_gen_pct"].notna()].copy()
    # RANK(): ties share a rank and leave a gap. SQL Server sorts NULL first under ASC, so a missing intensity ranks 1.
    g["re_share_rank"] = g["re_share_gen_pct"].rank(method="min", ascending=False)
    g["intensity_rank"] = g["emissions_intensity_gco2e_kwh"].rank(method="min", na_option="top")
    pc = d[(d["year"] == per_capita_year) & d["demand_per_capita_mwh"].notna()].copy()
    pc["per_capita_rank"] = pc["demand_per_capita_mwh"].rank(method="min", ascending=False)

    ranked = ["name", "year", "re_share_gen_pct", "re_share_rank", "emissions_intensity_gco2e_kwh", "intensity_rank"]
    r = (
        g[ranked]
        .rename(columns={"year": "comparison_year"})
        .merge(
            pc.rename(columns={"year": "per_capita_year"})[
                ["name", "per_capita_year", "demand_per_capita_mwh", "per_capita_rank"]
            ],
            on="name",
            how="left",  # a peer without a per-capita value keeps its row, with NULLs
        )
    )
    r["countries_compared"] = len(r)
    for col in ("re_share_rank", "intensity_rank", "per_capita_year", "per_capita_rank"):
        r[col] = r[col].astype("Int64")
    cols = [
        "name",
        "comparison_year",
        "re_share_gen_pct",
        "re_share_rank",
        "emissions_intensity_gco2e_kwh",
        "intensity_rank",
        "per_capita_year",
        "demand_per_capita_mwh",
        "per_capita_rank",
        "countries_compared",
    ]
    return _records(r.sort_values(["re_share_rank", "name"])[cols])


def rolling_avg(f: Frames) -> list[dict]:
    """sql/showcase/04_rolling_avg.sql: each country's RE share and its 3-year rolling average."""
    c = f["dim_country"]
    d = f["country_annual"].merge(c[c["area_type"] == "COUNTRY"], on="country_key")
    d = d.sort_values(["display_order", "year"])
    # reported only when all three rows of the frame have a value (COUNT = 3), never on a partial window
    roll = d.groupby("country_key")["re_share_gen_pct"].transform(lambda s: s.rolling(3, min_periods=3).mean())
    d["re_share_3yr_avg_pct"] = _round(roll, 3)
    return _records(d[["name", "year", "re_share_gen_pct", "re_share_3yr_avg_pct"]])


def capacity_factor(f: Frames) -> list[dict]:
    """sql/showcase/05_capacity_factor.sql: capacity factor by country, year and source, with blank reasons."""
    c = f["dim_country"]
    d = (
        f["generation_annual"]
        .merge(f["dim_source"], on="source_key")
        .merge(c[c["area_type"] == "COUNTRY"], on="country_key")
        .merge(f["dim_year"], on="year")
        .sort_values(["display_order", "year", "sort_order"])
    )
    gen, cap = d["generation_twh"], d["capacity_gw"]
    max_gwh = cap * d["hours_in_year"]  # what the fleet would generate running flat out
    reasons = [
        (gen.isna(), "GENERATION_NOT_REPORTED"),
        (cap.isna(), "CAPACITY_NOT_REPORTED"),
        ((cap == 0) & (gen > 0), "CAPACITY_NOT_REPORTED"),
        (cap == 0, "NO_CAPACITY"),
        (1000 * gen > max_gwh, "CF_ABOVE_100"),
    ]
    blank = np.select([c for c, _ in reasons], [r for _, r in reasons], default="")
    d["blank_reason"] = pd.Series(blank, index=d.index).replace("", None)
    d["capacity_factor_pct"] = _round(100.0 * 1000 * gen / max_gwh, 2).where((cap > 0) & (1000 * gen <= max_gwh))
    d = d.rename(columns={"display_name": "source"})
    cols = ["name", "year", "source", "generation_twh", "capacity_gw", "hours_in_year"]
    return _records(d[[*cols, "capacity_factor_pct", "blank_reason"]])


def re_growth_decomposition(f: Frames) -> list[dict]:
    """sql/showcase/06_re_growth_decomposition.sql: which renewable sources drove Malaysia's rising RE share."""
    latest = f["dim_year"].loc[f["dim_year"]["is_complete"], "year"].max()
    g = f["generation_annual"].merge(f["dim_source"], on="source_key")
    g = g[g["country_key"].isin(_focus_keys(f)) & (g["group_name"] == "RENEWABLE")]
    parts = []
    for base in (2015, 2017):  # 2015 sits just before large hydro ramped up (audit HIGH-1)
        sub = g[g["year"].isin([base, latest])]
        by_source = [sub["display_name"], sub["sort_order"]]
        r = pd.DataFrame(
            {
                "base_twh": sub["generation_twh"].where(sub["year"] == base).groupby(by_source).sum(min_count=1),
                "latest_twh": sub["generation_twh"].where(sub["year"] == latest).groupby(by_source).sum(min_count=1),
            }
        ).reset_index()
        r = r.rename(columns={"display_name": "source"}).assign(base_year=base, latest_year=latest)
        r["increase_twh"] = _round(r["latest_twh"] - r["base_twh"], 4)  # DECIMAL(12, 4) subtraction is exact in SQL
        total = r["increase_twh"].sum(min_count=1)
        r["share_of_increase_pct"] = _round(100.0 * r["increase_twh"] / (np.nan if total == 0 else total), 1)
        parts.append(r.sort_values(["increase_twh", "sort_order"], ascending=[False, True], na_position="last"))
    cols = ["base_year", "latest_year", "source", "base_twh", "latest_twh", "increase_twh", "share_of_increase_pct"]
    return _records(pd.concat(parts)[cols])


def emissions_vs_demand(f: Frames) -> list[dict]:
    """sql/showcase/07_emissions_vs_demand.sql: demand, generation, intensity and emissions, base vs latest year."""
    base, latest = 2015, f["dim_year"].loc[f["dim_year"]["is_complete"], "year"].max()
    focus = _focus_keys(f)
    ca = f["country_annual"][f["country_annual"]["country_key"].isin(focus)]
    ga = f["generation_annual"].merge(f["dim_source"], on="source_key")
    ga = ga[ga["country_key"].isin(focus)]

    def pick(df: pd.DataFrame, col: str, year: int, **where: str) -> float:
        """SUM(CASE WHEN year = ... [AND ...] THEN col END): NULL, not 0, when no row matches."""
        mask = df["year"] == year
        for key, value in where.items():
            mask &= df[key] == value
        return df.loc[mask, col].sum(min_count=1)

    def fossil_intensity(year: int) -> float:
        gen = pick(ga, "generation_twh", year, group_name="FOSSIL")
        return 1000 * pick(ga, "emissions_mtco2e", year, group_name="FOSSIL") / (np.nan if gen == 0 else gen)

    out: dict = {"base_year": base, "latest_year": latest}

    def pair(name: str, df: pd.DataFrame, col: str, change_name: str | None = None, **where: str) -> None:
        """Add `<name>_base` and `<name>_latest`, and `<change_name>_change_pct` when the query reports one."""
        out[f"{name}_base"], out[f"{name}_latest"] = pick(df, col, base, **where), pick(df, col, latest, **where)
        if change_name:
            out[f"{change_name}_change_pct"] = _round(_pct_change(out[f"{name}_latest"], out[f"{name}_base"]), 1)

    pair("demand", ca, "demand_twh", "demand")
    pair("gen", ca, "total_generation_twh", "generation")
    pair("intensity", ca, "emissions_intensity_gco2e_kwh", "intensity")
    pair("emissions", ca, "emissions_mtco2e", "emissions")
    pair("coal", ga, "generation_twh", "coal", source_code="COAL")
    pair("gas", ga, "generation_twh", source_code="GAS")
    out["fossil_intensity_base"] = _round(fossil_intensity(base), 1)
    out["fossil_intensity_latest"] = _round(fossil_intensity(latest), 1)
    return _records(pd.DataFrame([out]))


def grid_load(f: Frames) -> list[dict]:
    """sql/showcase/08_grid_load.sql: peak hourly demand, when, mean and load factor per grid, year and month."""
    h = f["grid_hourly"].merge(f["dim_grid"][["grid_key", "grid_code", "display_order"]], on="grid_key")
    h = h[h["year"].isin([2023, 2024])]
    by_year = ["grid_code", "display_order", "year"]
    parts = []
    for keys in (by_year, [*by_year, "month"]):  # the whole-year rows have month NULL
        demand = h.groupby(keys)["demand_mw"]
        # ROW_NUMBER() ... ORDER BY demand_mw DESC, ts_local: of tied peaks, the earliest hour
        peak_at = h[h["demand_mw"] == demand.transform("max")].groupby(keys)["ts_local"].min()
        stats = {"hours": demand.size(), "peak_mw": demand.max(), "peak_at": peak_at, "mean": demand.mean()}
        parts.append(pd.DataFrame(stats).reset_index())
    r = pd.concat(parts)
    r["month"] = r["month"].astype("Int64")
    r["mean_mw"] = _round(r["mean"], 1)
    r["load_factor_pct"] = _round(100.0 * r["mean"] / r["peak_mw"].replace(0, np.nan), 2)
    r = r.sort_values(["display_order", "year", "month"], na_position="first")
    return _records(r[["grid_code", "year", "month", "hours", "peak_mw", "peak_at", "mean_mw", "load_factor_pct"]])


def forecast_metrics(f: Frames) -> list[dict]:
    """sql/showcase/09_forecast_metrics.sql: MAPE and MAE of the model and the seasonal-naive baseline per grid.

    The month rows' `*_diff` columns compare with the per-month values in `dw.forecast_run.metrics_json`, which the
    export does not carry (`forecast_run_current` has only the whole-run metrics), so they are None here.
    """
    fc = f["load_forecast_current"]
    d = fc[fc["is_scored"]].merge(f["dim_date"][["date_key", "month"]], on="date_key")
    for name in ("model", "baseline"):
        d[f"ae_{name}"] = (d["actual_mw"] - d[f"{'forecast' if name == 'model' else name}_mw"]).abs()
        d[f"pe_{name}"] = d[f"ae_{name}"] / d["actual_mw"]
    parts = []
    for keys in (["grid_key"], ["grid_key", "month"]):  # GROUPING SETS ((grid_key, month), (grid_key))
        gb = d.groupby(keys)
        stats = {
            "scored_hours": gb.size(),
            "mape_model": 100.0 * gb["pe_model"].mean(),
            "mape_baseline": 100.0 * gb["pe_baseline"].mean(),
            "mae_model": gb["ae_model"].mean(),
            "mae_baseline": gb["ae_baseline"].mean(),
        }
        parts.append(pd.DataFrame(stats).reset_index())
    r = pd.concat(parts)
    r["month"] = r["month"].astype("Int64")
    stored = f["forecast_run_current"][["grid_key", "mape_model", "mape_baseline"]]
    r = r.merge(stored, on="grid_key", suffixes=("", "_stored"))
    r = r.merge(f["dim_grid"][["grid_key", "grid_code", "display_order"]], on="grid_key")
    r["improvement_pct"] = _round(100.0 * (1 - r["mape_model"] / r["mape_baseline"].replace(0, np.nan)), 3)
    whole_run = r["month"].isna()
    r["mape_model_diff"] = _round(r["mape_model"] - r["mape_model_stored"], 4).where(whole_run)
    r["mape_baseline_diff"] = _round(r["mape_baseline"] - r["mape_baseline_stored"], 4).where(whole_run)
    for col in ("mape_model", "mape_baseline", "mae_model", "mae_baseline"):
        r[col] = _round(r[col], 3)
    r = r.sort_values(["display_order", "month"], na_position="first")
    cols = ["grid_code", "month", "scored_hours", "mape_model", "mape_baseline", "mae_model", "mae_baseline"]
    return _records(r[[*cols, "improvement_pct", "mape_model_diff", "mape_baseline_diff"]])


def load_curves(f: Frames) -> list[dict]:
    """sql/showcase/10_load_curves.sql: mean demand by local hour, per grid, season and day type."""
    h = f["grid_hourly"].merge(f["dim_grid"][["grid_key", "grid_code", "display_order"]], on="grid_key")
    h = h[h["year"].isin([2023, 2024])]
    keys = ["grid_code", "display_order", "season", "season_order", "day_type", "hour"]
    demand = h.groupby(keys)["demand_mw"]
    r = pd.DataFrame({"hours": demand.size(), "mean_mw": _round(demand.mean(), 1)}).reset_index()
    r = r.sort_values(["display_order", "season_order", "day_type", "hour"], ascending=[True, True, False, True])
    return _records(r[["grid_code", "season", "season_order", "day_type", "hour", "hours", "mean_mw"]])


def interconnector_flows(f: Frames) -> list[dict]:
    """sql/showcase/11_interconnector_flows.sql: Thailand-Malaysia border flows by direction, per year."""
    fd = f["grid_flow_daily"].merge(f["dim_grid"][["grid_key", "grid_code"]], on="grid_key")
    fd = fd[(fd["counterparty"] == "MY") & fd["year"].isin([2023, 2024])]
    gb = fd.groupby(["grid_code", "counterparty", "year"])
    export, import_ = gb["export_mwh"].sum(min_count=1), gb["import_mwh"].sum(min_count=1)
    r = pd.DataFrame(
        {
            "days": gb.size(),
            "hours_present": gb["hours_present"].sum(min_count=1),
            "export_gwh": _round(export / 1000.0, 1),
            "import_gwh": _round(import_ / 1000.0, 1),
            "net_export_gwh": _round((export - import_) / 1000.0, 1),
            "mean_daily_net_mw": _round(gb["net_flow_mw"].mean(), 1),
        }
    ).reset_index()
    return _records(r.sort_values("year"))


# Query name (exports/expected.json key) -> its port.
SHOWCASE: dict[str, Callable[[Frames], list[dict]]] = {
    "01_trends": trends,
    "02_yoy_lag": yoy_lag,
    "03_ranking": ranking,
    "04_rolling_avg": rolling_avg,
    "05_capacity_factor": capacity_factor,
    "06_re_growth_decomposition": re_growth_decomposition,
    "07_emissions_vs_demand": emissions_vs_demand,
    "08_grid_load": grid_load,
    "09_forecast_metrics": forecast_metrics,
    "10_load_curves": load_curves,
    "11_interconnector_flows": interconnector_flows,
}
