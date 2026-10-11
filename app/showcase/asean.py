"""Pure functions behind the ASEAN page (report page P5, with the Country Deep Dive D1 and the T2 country tooltip, M6
step 5).

They take the snapshot frames (`data.frames()`) and the page's selection and return plain values or frames, so the page
only draws and the numbers are unit-testable without Streamlit. Each one names the report measure it translates
(`report/EnergyTransition.SemanticModel/definition/tables/_Measures.tmdl`). The ranks come from the step 3 port
`metrics.ranking` (sql/showcase/03) and the deep dive reuses the Malaysia functions of `annual.py`, which take the
country in context (`focus_on` points the Malaysia-only ports at it).
"""

from __future__ import annotations

from typing import NamedTuple

import pandas as pd

from showcase import annual, metrics

Frames = metrics.Frames
FOCUS = annual.FOCUS
# The 'ASEAN Metric' field parameter: slicer label -> ([Country RE Share (%)] etc. as the country_annual column, decimals)
METRICS = {
    "RE share (%)": ("re_share_gen_pct", 1),  # [Country RE Share (%)]
    "Carbon intensity (gCO2e/kWh)": ("emissions_intensity_gco2e_kwh", 0),  # [Country Carbon Intensity (gCO2e/kWh)]
    "Emissions (MtCO2e)": ("emissions_mtco2e", 1),  # [Country Emissions (MtCO2e)]
}
DEFAULT_METRIC = "RE share (%)"


def countries(f: Frames) -> list[str]:
    """The 'Compare Country' list: the ASEAN countries in the report's order, never the ASEAN aggregate."""
    dc = f["dim_country"]
    return list(dc[dc["area_type"] == "COUNTRY"].sort_values("display_order")["name"])


def default_peers(f: Frames) -> list[str]:
    dc = f["dim_country"]
    return list(dc[(dc["area_type"] == "COUNTRY") & dc["is_default_peer"]].sort_values("display_order")["name"])


def compared(f: Frames, selection: list[str]) -> list[str]:
    """DAX [Is Compared]: the countries the slicer picked, else the default peers (none ticked = the 6 peers)."""
    if not selection:
        return default_peers(f)
    return [n for n in countries(f) if n in set(selection)]


# ----------------------------------------------------------------------------- ranks, titles, footnote


class Comparison(NamedTuple):
    """The compared set at the range's last year, as the ASEAN measures read it."""

    names: list[str]  # [Is Compared]
    rows: pd.DataFrame  # sql/showcase/03 for this set: values, ranks, years (one row per country with a value)
    label: str  # DAX [Rank Label]
    title: str  # DAX [ASEAN Title]
    year: int | None  # DAX [Comparison Year] = [Common Latest Year]
    per_capita_year: int | None  # DAX [Common Per Capita Year]


def comparison(f: Frames, selection: list[str], first: int, last: int) -> Comparison:
    """DAX [Common Latest Year], [Common Per Capita Year], [Focus RE Share Rank], [Focus Intensity Rank], [Countries
    Compared], [Rank Label] and [ASEAN Title] for the selection and the year range.

    `metrics.ranking` (the SQL twin) does the ranking on frames whose peer flag is the compared set and whose year
    range is the slicer's: its latest year is the MINX over the compared countries, capped at the range's last year
    (ALLSELECTED(dim_year)). A country with no value at that year has no row, as in COUNTROWS(FILTER(... NOT ISBLANK)).
    """
    names = compared(f, selection)
    dc = f["dim_country"].assign(is_default_peer=lambda d: d["name"].isin(names))
    dy = f["dim_year"][f["dim_year"]["year"].between(first, last)]
    label, rows = annual.rank_summary({**f, "dim_country": dc, "dim_year": dy}, last)
    year = per_capita_year = None
    if len(rows):
        year = int(rows["comparison_year"].iloc[0])
        known = rows["per_capita_year"].dropna()
        per_capita_year = int(known.iloc[0]) if len(known) else None
    mine = rows[rows["name"] == FOCUS] if len(rows) else rows
    title = label
    if len(rows) >= 2 and not mine.empty and pd.notna(mine["re_share_rank"].iloc[0]):
        ir = mine["intensity_rank"].iloc[0]
        title = (
            f"{FOCUS}: {int(mine['re_share_rank'].iloc[0])} of {len(rows)} on renewable share, "
            f"{'' if pd.isna(ir) else int(ir)} of {len(rows)} on carbon intensity ({year})"
        )
    return Comparison(names, rows, label, title, year, per_capita_year)


def subtitle(first: int, last: int, as_of: str) -> str:
    """DAX [ASEAN Subtitle]."""
    return f"ASEAN peers · {first}–{last} · {as_of}"


def footnote(c: Comparison) -> str:
    """DAX [ASEAN Footnote]. A year that cannot be worked out (no country has a value) reads "n/a"."""
    year = "n/a" if c.year is None else c.year
    pc = "n/a" if c.per_capita_year is None else c.per_capita_year
    return (
        f"Ranking, scatter and intensity bars use {year}, the latest year all selected countries report; per-capita "
        f"demand uses {pc} (OWID population). With no country selected, the six default peers are compared. "
        "Sources: Ember (CC BY 4.0), OWID (CC BY 4.0)."
    )


# ----------------------------------------------------------------------------- chart data


def trend(f: Frames, names: list[str], metric: str, first: int, last: int) -> pd.DataFrame:
    """The trend line's rows: DAX [Country RE Share (%)], [Country Carbon Intensity (gCO2e/kWh)] or [Country Emissions
    (MtCO2e)] (the 'ASEAN Metric' choice) for each compared country and year of the range. One country and one year
    only, never a sum; a year without a value has no row (a gap, not a zero)."""
    col = METRICS[metric][0]
    dc = f["dim_country"][["country_key", "name", "display_order"]]
    t = f["country_annual"].merge(dc, on="country_key")
    t = t[t["name"].isin(names) & t["year"].between(first, last) & t[col].notna()]
    t = t.sort_values(["display_order", "year"]).rename(columns={"name": "country", col: "value"})
    return t[["country", "year", "value"]].reset_index(drop=True)


class Tip(NamedTuple):
    """The T2 country tooltip for one country at the comparison year."""

    title: str  # DAX [T2 Title]: "Malaysia · 2025"
    re_share: float | None  # [RE Share at Comparison Year (%)] (t2_card_0)
    intensity: float | None  # [Intensity at Comparison Year (gCO2e/kWh)] (t2_card_1)
    mix: list[tuple[str, float]]  # [T2 Generation Share (%)] by source, in the report's order (t2_mix_bar)

    def hover(self, *header: str) -> str:
        """The tooltip as Plotly hover text: the chart's own `header` lines, then the T2 page's fields."""
        re = "no data" if self.re_share is None else f"{annual.fmt(self.re_share)}%"
        co2 = "no data" if self.intensity is None else f"{annual.fmt(self.intensity, 0, grouping=True)} gCO2e/kWh"
        lines = [
            *header,
            *([""] if header else []),
            f"<b>{self.title}</b>",
            f"RE share: {re}",
            f"Carbon intensity: {co2}",
        ]
        shown = [f"{s} {annual.fmt(p)}%" for s, p in self.mix if p > 0]  # a 0% segment is invisible in the bar
        if shown:
            lines.append("Generation mix (% of the year's total):")
            lines += [" · ".join(shown[i : i + 3]) for i in range(0, len(shown), 3)]
        return "<br>".join(lines)

    @property
    def html(self) -> str:
        return self.hover()


def tooltip(f: Frames, name: str, year: int | None) -> Tip:
    """The T2 page for `name` at `year` (the comparison year): DAX [T2 Title], [RE Share at Comparison Year (%)],
    [Intensity at Comparison Year (gCO2e/kWh)] and [T2 Generation Share (%)] = the source's generation over the
    country's total that year (REMOVEFILTERS on dim_source for the total). The report's tooltip always uses the
    comparison year, not the hovered year."""
    if year is None:
        return Tip(name, None, None, [])
    dc = f["dim_country"]
    key = int(dc.loc[dc["name"] == name, "country_key"].iloc[0])
    ca = f["country_annual"]
    row = ca[(ca["country_key"] == key) & (ca["year"] == year)]
    share = intensity = None
    if len(row):
        share = None if pd.isna(row["re_share_gen_pct"].iloc[0]) else float(row["re_share_gen_pct"].iloc[0])
        v = row["emissions_intensity_gco2e_kwh"].iloc[0]
        intensity = None if pd.isna(v) else float(v)
    ga = f["generation_annual"].merge(f["dim_source"], on="source_key")
    g = ga[(ga["country_key"] == key) & (ga["year"] == year)].sort_values("sort_order")
    total = g["generation_twh"].sum(min_count=1)
    mix = []
    if pd.notna(total) and total != 0:
        mix = [(r.display_name, 100 * r.generation_twh / total) for r in g.itertuples() if pd.notna(r.generation_twh)]
    return Tip(f"{name} · {year}", share, intensity, mix)


def snapshot(f: Frames, c: Comparison) -> pd.DataFrame:
    """The compared countries at the comparison year: the scatter's three measures (DAX [RE Share at Comparison Year
    (%)], [Intensity at Comparison Year (gCO2e/kWh)], [Demand at Comparison Year (TWh)]), per-capita demand at its
    common year, and the T2 mix by source. The page's "Show data" tables."""
    ca = f["country_annual"].merge(f["dim_country"][["country_key", "name"]], on="country_key")
    sources = list(f["dim_source"].sort_values("sort_order")["display_name"])
    out = []
    for r in c.rows.itertuples():
        demand = ca[(ca["name"] == r.name) & (ca["year"] == r.comparison_year)]["demand_twh"]
        mix = dict(tooltip(f, r.name, c.year).mix)
        out.append(
            {
                "Country": r.name,
                "Year": r.comparison_year,
                "RE share (%)": r.re_share_gen_pct,
                "Carbon intensity (gCO2e/kWh)": r.emissions_intensity_gco2e_kwh,
                "Demand (TWh)": demand.iloc[0] if len(demand) else None,
                "Per-capita year": r.per_capita_year,
                "Demand per capita (MWh)": r.demand_per_capita_mwh,
                **{s: mix.get(s) for s in sources},
            }
        )
    columns = [
        "Country",
        "Year",
        "RE share (%)",
        "Carbon intensity (gCO2e/kWh)",
        "Demand (TWh)",
        "Per-capita year",
        "Demand per capita (MWh)",
        *sources,
    ]
    table = pd.DataFrame(out, columns=columns)
    for col in ("RE share (%)", "Carbon intensity (gCO2e/kWh)", "Demand (TWh)", "Demand per capita (MWh)", *sources):
        table[col] = pd.to_numeric(table[col])  # a blank is NaN, never an object None
    return table


def spread(values: list[float], gap: float) -> list[float]:
    """Label heights at least `gap` apart, in the order of `values` (the direct labels at the line ends, doc 04 §3.3).
    Labels that are too close move apart around their shared centre; a label with room stays where it is."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    pos = [float(values[i]) for i in order]
    for _ in range(200):
        moved = False
        for a in range(len(pos) - 1):
            short = gap - (pos[a + 1] - pos[a])
            if short > 1e-9:
                pos[a] -= short / 2
                pos[a + 1] += short / 2
                moved = True
        if not moved:
            break
    out = [0.0] * len(values)
    for rank, i in enumerate(order):
        out[i] = pos[rank]
    return out


def focus_on(f: Frames, country: str) -> Frames:
    """The frames with `country` as the focus, so the Malaysia-only ports (`metrics.trends`, `metrics.yoy_lag`) and the
    `annual` helpers describe it: the deep dive's [Context Country Key] (the drilled country, else the focus)."""
    return {**f, "dim_country": f["dim_country"].assign(is_focus=lambda d: d["name"] == country)}


# ----------------------------------------------------------------------------- text summaries (alt text and captions)


def _ordinal(rank: int) -> str:
    return f"{rank}{'th' if 10 <= rank % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(rank % 10, 'th')}"


def trend_summary(t: pd.DataFrame, metric: str) -> str:
    if t.empty:
        return "No data for the selected countries and years."
    digits = METRICS[metric][1]
    latest = t.sort_values("year").groupby("country").tail(1).sort_values("value", ascending=False)
    parts = "; ".join(
        f"{r.country} {annual.fmt(r.value, digits, grouping=True)} ({r.year})" for r in latest.itertuples()
    )
    return f"{metric}, latest value in the selected years, highest first: {parts}."


def scatter_summary(snap: pd.DataFrame, year: int | None) -> str:
    d = snap.dropna(subset=["RE share (%)", "Carbon intensity (gCO2e/kWh)"])
    if d.empty or year is None:
        return "No country has both a renewable share and a carbon intensity to compare."
    best = d.loc[d["RE share (%)"].idxmax()]
    cleanest = d.loc[d["Carbon intensity (gCO2e/kWh)"].idxmin()]
    share = f"the highest renewable share ({annual.fmt(best['RE share (%)'])}%)"
    clean = f"the lowest carbon intensity ({annual.fmt(cleanest['Carbon intensity (gCO2e/kWh)'], 0, grouping=True)} gCO2e/kWh)"
    if best["Country"] == cleanest["Country"]:
        text = f"In {year}, {best['Country']} has both {share} and {clean}."
    else:
        text = f"In {year}, {best['Country']} has {share} and {cleanest['Country']} {clean}."
    mine = d[d["Country"] == FOCUS]
    if not mine.empty:
        m = mine.iloc[0]
        text += (
            f" {FOCUS}: {annual.fmt(m['RE share (%)'])}% and "
            f"{annual.fmt(m['Carbon intensity (gCO2e/kWh)'], 0, grouping=True)} gCO2e/kWh."
        )
    return text


def bar_summary(
    snap: pd.DataFrame, column: str, year: int | None, what: str, unit: str, digits: int, *, low_first: bool
) -> str:
    """One sentence for a ranked bar: its range from first to last and where Malaysia stands."""
    d = snap.dropna(subset=[column])
    if d.empty or year is None:
        return f"No {what} to show for the selected countries."
    d = d.sort_values(column, ascending=low_first)
    top, bottom = d.iloc[0], d.iloc[-1]

    def show(v: float) -> str:
        return annual.fmt(v, digits, grouping=True)

    text = f"{what.capitalize()} in {year} runs from {show(top[column])} {unit} ({top['Country']}) to {show(bottom[column])} ({bottom['Country']})."
    if FOCUS in set(d["Country"]):
        place = list(d["Country"]).index(FOCUS) + 1
        text += f" {FOCUS} is {_ordinal(place)} of {len(d)}: {show(d[d['Country'] == FOCUS][column].iloc[0])}."
    return text


def demand_summaries(d: pd.DataFrame, country: str, first: int, last: int) -> tuple[str, str]:
    """The deep dive's demand and growth summaries; a country with no demand in the range says so."""
    if d.empty:
        none = f"No demand is reported for {country} in {first}–{last}."
        return none, none
    return annual.demand_summary(d), annual.growth_summary(d)
