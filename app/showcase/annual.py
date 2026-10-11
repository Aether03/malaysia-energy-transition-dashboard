"""Pure functions behind the Overview and Generation pages (report pages P1 and P2, M6 step 4).

They take the snapshot frames (`data.frames()`) and the page's selection and return plain values or frames, so the
pages only draw and the numbers are unit-testable without Streamlit. Each one names the report measure it translates
(`report/EnergyTransition.SemanticModel/definition/tables/_Measures.tmdl`). Where a step 3 port in `metrics.py` gives
the number (`yoy_lag`, `ranking`, `trends`, `capacity_factor`) it is reused, so the page shows what the SQL twin gives.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

import pandas as pd

from showcase import metrics

Frames = metrics.Frames
FOCUS = "Malaysia"  # the report's titles spell the focus country out
ACCENT_BLUE = "#256abf"  # doc 04 accent.blue: the official-basis bar and the growth columns
BLANK_CF = {"CAPACITY_NOT_REPORTED", "CF_ABOVE_100"}  # the blank reasons the Capacity Factor Note names


def fmt(x, digits: int = 1, *, grouping: bool = False) -> str:
    """DAX FORMAT(x, "0.0" / "#,0.0"): rounds half away from zero (not half to even); blank gives ''."""
    if x is None or pd.isna(x):
        return ""
    q = Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return f"{q:,.{digits}f}" if grouping else f"{q:.{digits}f}"


def _num(x) -> float | None:
    return None if x is None or pd.isna(x) else float(x)


def _focus(f: Frames) -> int:
    dc = f["dim_country"]
    return int(dc.loc[dc["is_focus"], "country_key"].iloc[0])


def _focus_annual(f: Frames) -> pd.DataFrame:
    ca = f["country_annual"]
    return ca[ca["country_key"] == _focus(f)].set_index("year")


def _country_annual(f: Frames, country: str) -> pd.DataFrame:
    """One country's `country_annual` rows by name, indexed by year (the ASEAN deep dive's country in context)."""
    dc = f["dim_country"]
    ca = f["country_annual"]
    return ca[ca["country_key"] == int(dc.loc[dc["name"] == country, "country_key"].iloc[0])].set_index("year")


def years(f: Frames) -> list[int]:
    return sorted(int(y) for y in f["dim_year"]["year"])


def latest_complete_year(f: Frames) -> int:
    """DAX [Latest Complete Year]: the year slicer's default (a partial latest year is never the default)."""
    dy = f["dim_year"]
    return int(dy.loc[dy["is_complete"], "year"].max())


# ----------------------------------------------------------------------------- P1 Overview


def overview_title(f: Frames, year: int) -> str:
    """DAX [Overview Title]: "Renewables supplied 20.4% of Malaysia's electricity in 2025"."""
    ca = _focus_annual(f)
    re_share = ca["re_share_gen_pct"].get(year)
    return f"Renewables supplied {fmt(re_share)}% of {FOCUS}'s electricity in {year}"


def overview_subtitle(year: int, as_of: str) -> str:
    """DAX [Overview Subtitle]."""
    return f"{FOCUS} · {year} · {as_of}"


def no_data_message(f: Frames, year: int) -> str | None:
    """DAX [No Data Message]: shown when the selected year has no total generation (doc 03 P1 empty state)."""
    total = _focus_annual(f)["total_generation_twh"].get(year)
    return f"No data for {year}" if total is None or pd.isna(total) else None


class Kpi(NamedTuple):
    """One KPI card: the value, the delta label the report shows, and a word for it (nothing by colour alone)."""

    label: str  # the card's category label, the measure's name
    value: str
    delta: str  # DAX "<kpi> Delta Label": "▲ 0.6 pp vs 2024", or "—"
    word: str  # "up, good" / "down, bad" / "up"
    tone: str  # "good" | "bad" | "neutral": only the three KPIs the report colours are ever judged
    help: str  # the report's T1 tooltip: definition, formula, source

    @property
    def text(self) -> str:
        return f"{self.delta} · {self.word}" if self.word else self.delta

    @property
    def markdown(self) -> str:
        colour = {"good": "green", "bad": "red"}.get(self.tone)
        return f":{colour}[{self.text}]" if colour else self.text


# (kpi_code, measure name, decimals, thousands separator, the report colours its delta by polarity)
_CARDS = [
    ("TOTAL_GENERATION", "Total Generation (TWh)", 1, True, False),
    ("RE_SHARE_GEN", "RE Share (%)", 1, False, True),
    ("FOSSIL_SHARE_GEN", "Fossil Share (%)", 1, False, True),
    ("CARBON_INTENSITY", "Carbon Intensity (gCO2e/kWh)", 0, True, True),
    ("DEMAND_PER_CAPITA", "Demand per Capita (MWh)", 2, False, False),
]


def overview_kpis(f: Frames, year: int) -> list[Kpi]:
    """The five KPI cards and their YoY deltas for the selected year.

    DAX: [Total Generation (TWh)], [RE Share (%)], [Fossil Share (%)], [Carbon Intensity (gCO2e/kWh)], [Demand per
    Capita (MWh)] and their "<kpi> Delta Label" measures. The change and its direction come from `metrics.yoy_lag`
    (sql/showcase/02). A missing value or a missing previous year gives "—", never 0. The direction is rounded
    first, like the SQL twin: a change that rounds to 0.0 reads "▲ 0.0" with the word "up" and no verdict.
    """
    yoy = pd.DataFrame(metrics.yoy_lag(f))
    ds = f["data_source"].set_index("data_source_code")["credit_text"]
    kpi = f["kpi"].set_index("kpi_code")
    cards = []
    for code, label, digits, grouping, judged in _CARDS:
        r = yoy[(yoy["kpi_code"] == code) & (yoy["year"] == year)]
        value = _num(r["value"].iloc[0]) if len(r) else None
        change = _num(r["change"].iloc[0]) if len(r) else None
        if change is None:
            delta, word, tone = "—", "", "neutral"
        else:
            unit = " pp" if r["change_unit"].iloc[0] == "pp" else "%"
            delta = f"{'▲' if change >= 0 else '▼'} {fmt(abs(change))}{unit} vs {year - 1}"
            word, tone = ("up" if change >= 0 else "down"), "neutral"
            direction = r["direction"].iloc[0]
            if judged and direction in ("GOOD", "BAD"):
                tone = direction.lower()
                word += f", {tone}"
        k = kpi.loc[code]
        tip = f"{k['name']} ({k['unit']}). {k['definition']} Formula: {k['formula']}. Source: {ds[k['data_source_code']]}."
        cards.append(Kpi(label, fmt(value, digits, grouping=grouping) or "—", delta, word, tone, tip))
    return cards


class Netr(NamedTuple):
    """The NETR panel for a year: both capacity-share bases beside the next target."""

    ember: float | None  # DAX [RE Capacity Share (%)]: Ember grid basis
    official: float | None  # [Official RE Capacity Share (%)]: latest official point up to the year
    official_year: int | None  # [Official RE Capacity Year]
    official_source: str | None
    target: float | None  # [NETR Target (%)]: the next target on or after the year
    target_year: int | None  # [NETR Target Year]
    target_source: str | None
    gap: float | None  # [NETR Gap (pp)] = ember - target; None when either is missing
    label: str  # [NETR Progress Label]


def netr_progress(f: Frames, year: int) -> Netr:
    """DAX [RE Capacity Share (%)], [Official RE Capacity Share (%)], [NETR Target (%)], [NETR Gap (pp)] and
    [NETR Progress Label]. A blank Ember share reads "not reported" (the DAX would print "Ember grid basis %")."""
    ember = _num(_focus_annual(f)["re_share_capacity_pct"].get(year))
    off = f["re_capacity_official"]
    off = off[off["year"] <= year].sort_values("year")
    official = official_year = official_source = None
    if len(off):
        o = off.iloc[-1]
        official, official_year, official_source = float(o["re_capacity_share_pct"]), int(o["year"]), o["source_name"]
    tg = f["netr_target"]
    tg = tg[tg["target_year"] >= year].sort_values("target_year")
    target = target_year = target_source = None
    if len(tg):
        t = tg.iloc[0]
        target, target_year, target_source = float(t["re_capacity_share_pct"]), int(t["target_year"]), t["source_name"]
    label = "Ember grid basis " + (f"{fmt(ember)}%" if ember is not None else "not reported")
    if official is not None:
        label += f" · official {fmt(official, 0)}% (incl. off-grid and rooftop, {official_year})"
    if target is not None:
        label += f" · target {fmt(target, 0)}% by {target_year}"
    gap = None if ember is None or target is None else ember - target
    return Netr(ember, official, official_year, official_source, target, target_year, target_source, gap, label)


def netr_table(n: Netr, year: int) -> pd.DataFrame:
    """The NETR panel as a table (the "Show data" view): each measure of the bar chart, the gap and the sources."""
    rows = [
        ("RE Capacity Share (%), Ember grid basis", n.ember, year, "Ember Yearly Electricity Data"),
        ("Official RE Capacity Share (%)", n.official, n.official_year, n.official_source),
        ("NETR Target (%)", n.target, n.target_year, n.target_source),
        ("NETR Gap (pp)", n.gap, None, None),
    ]
    return pd.DataFrame(rows, columns=["Measure", "Value", "Year", "Source"])


def netr_summary(n: Netr) -> str:
    gap = (
        ""
        if n.gap is None
        else f" The Ember-basis gap to the target is {'-' if n.gap < 0 else '+'}{fmt(abs(n.gap))} pp."
    )
    return n.label + "." + gap


def rank_summary(f: Frames, year: int) -> tuple[str, pd.DataFrame]:
    """DAX [Rank Label] on P1 and the table behind it. [Comparison Year] is the latest year up to the selected one that
    every default peer reports, so the year range is capped at the selected year (ALLSELECTED on the single-year
    slicer); `metrics.ranking` (sql/showcase/03) ranks within it."""
    capped = {**f, "dim_year": f["dim_year"][f["dim_year"]["year"] <= year]}
    rows = pd.DataFrame(metrics.ranking(capped))
    if len(rows) < 2:
        return "Select at least two countries to compare", rows
    mine = rows[rows["name"] == FOCUS]
    if mine.empty or pd.isna(mine["re_share_rank"].iloc[0]):
        return f"{FOCUS} is not in the current selection", rows
    rank, n, comparison = int(mine["re_share_rank"].iloc[0]), len(rows), int(rows["comparison_year"].iloc[0])
    return f"{FOCUS} ranks {rank} of {n} on renewable share ({comparison})", rows


def rank_table(rows: pd.DataFrame) -> pd.DataFrame:
    cols = {
        "name": "Country",
        "comparison_year": "Year",
        "re_share_gen_pct": "RE share (%)",
        "re_share_rank": "RE share rank (1 = highest)",
        "emissions_intensity_gco2e_kwh": "Carbon intensity (gCO2e/kWh)",
        "intensity_rank": "Intensity rank (1 = lowest)",
    }
    return rows[list(cols)].rename(columns=cols) if len(rows) else pd.DataFrame(columns=list(cols.values()))


def mix_trend(f: Frames) -> pd.DataFrame:
    """DAX [Focus Generation (TWh)] by source and year, all years (sql/showcase/01 via `metrics.trends`), with the
    share of the year's whole mix and each source's colour (dim_source.color_hex)."""
    t = pd.DataFrame(metrics.trends(f))
    colours = f["dim_source"].set_index("display_name")["color_hex"]
    t["color"] = t["source"].map(colours)
    return t


def mix_summary(t: pd.DataFrame) -> str:
    totals = t.groupby("year")["generation_twh"].sum()
    y0, y1 = int(totals.index.min()), int(totals.index.max())
    last = t[t["year"] == y1].sort_values("generation_twh", ascending=False).iloc[0]
    return (
        f"{FOCUS}'s generation went from {fmt(totals[y0])} TWh in {y0} to {fmt(totals[y1])} TWh in {y1}; "
        f"{last['source']} supplied the most in {y1} ({fmt(last['share_of_mix_pct'])}% of the mix)."
    )


# ----------------------------------------------------------------------------- P2 Generation


def generation_title(f: Frames, last_year: int, country: str = FOCUS) -> str:
    """DAX [Generation Title]: the fossil share at the last year of the selected range, for [Context Country]."""
    fossil = _country_annual(f, country)["fossil_share_gen_pct"].get(last_year)
    return f"{country}: fossil fuels supplied {fmt(fossil)}% of electricity in {last_year}"


def generation_subtitle(first: int, last: int, as_of: str, country: str = FOCUS) -> str:
    """DAX [Generation Subtitle]."""
    return f"{country} · {first}–{last} · {as_of}"


def mix_series(f: Frames, first: int, last: int, sources: list[str]) -> pd.DataFrame:
    """DAX [Ctx Generation (TWh)] and [Ctx Generation Share (%)] per source and year of the range, for the selected
    sources (all when none is selected). The share is of the year's whole mix, so a source slicer never inflates it."""
    t = mix_trend(f)
    t = t[t["year"].between(first, last)]
    return t[t["source"].isin(sources)] if sources else t


def no_source_message(f: Frames, first: int, last: int, sources: list[str]) -> str | None:
    """DAX [No Source Generation Message]: a source filter whose generation is blank (not 0) in the range."""
    if not sources:
        return None
    if not pd.isna(mix_series(f, first, last, sources)["generation_twh"].sum(min_count=1)):
        return None
    order = f["dim_source"].sort_values("sort_order")["display_name"]
    names = [s for s in order if s in sources]
    return f"No {' or '.join(names)} generation in this period"


def generation_mix_summary(series: pd.DataFrame, unit: str) -> str:
    if series.empty or series["generation_twh"].isna().all():
        return "No generation to show for the selected sources and years."
    y1 = int(series["year"].max())
    col = "generation_twh" if unit == "TWh" else "share_of_mix_pct"
    top = series[series["year"] == y1].sort_values(col, ascending=False).iloc[0]
    value = f"{fmt(top[col])} TWh" if unit == "TWh" else f"{fmt(top[col])}% of the year's total"
    return f"In {y1}, {top['source']} was the largest source shown at {value}."


def capacity_factors(f: Frames, year: int, sources: list[str], country: str = FOCUS) -> pd.DataFrame:
    """DAX [Ctx Capacity Factor (%)] per source at `year` for `country` (sql/showcase/05 via `metrics.capacity_factor`):
    blank, never 0, with the reason, when capacity is not reported or implies a factor above 100%."""
    r = pd.DataFrame(metrics.capacity_factor(f))
    r = r[(r["name"] == country) & (r["year"] == year)].rename(columns={"blank_reason": "reason"})
    r = r[r["source"].isin(sources)] if sources else r
    order = {s: i for i, s in enumerate(f["dim_source"].sort_values("sort_order")["display_name"])}
    r = r.sort_values("source", key=lambda s: s.map(order))
    for col in ("generation_twh", "capacity_gw", "capacity_factor_pct"):
        r[col] = pd.to_numeric(r[col])
    colours = f["dim_source"].set_index("display_name")["color_hex"]
    r["color"] = r["source"].map(colours)
    cols = ["source", "color", "generation_twh", "capacity_gw", "hours_in_year", "capacity_factor_pct", "reason"]
    return r[cols].reset_index(drop=True)


def capacity_factor_title(year: int) -> str:
    """DAX [Capacity Factor Title]."""
    return f"Capacity factor by source, {year} (%)"


def capacity_factor_note(rows: pd.DataFrame, year: int) -> str | None:
    """DAX [Capacity Factor Note]: the sources that generated but whose capacity is missing, zero or inconsistent."""
    blank = rows[(rows["generation_twh"] > 0) & rows["reason"].isin(BLANK_CF)]
    if blank.empty:
        return None
    return (
        f"Capacity not reported or inconsistent with generation for {', '.join(blank['source'])} in {year}, "
        "so shown blank, not 0. CF = generation ÷ (capacity × hours in year)."
    )


def capacity_factor_summary(rows: pd.DataFrame, year: int) -> str:
    have = rows.dropna(subset=["capacity_factor_pct"])
    if have.empty:
        return f"No capacity factor can be shown for the selected sources in {year}."
    lo, hi = have.loc[have["capacity_factor_pct"].idxmin()], have.loc[have["capacity_factor_pct"].idxmax()]
    return (
        f"Capacity factor in {year} ranged from {fmt(lo['capacity_factor_pct'])}% ({lo['source']}) "
        f"to {fmt(hi['capacity_factor_pct'])}% ({hi['source']})."
    )


def demand_series(f: Frames, first: int, last: int) -> pd.DataFrame:
    """DAX [Ctx Demand (TWh)] and [Ctx Demand Growth (%)] per year of the range. Growth looks one year back even past
    the range's first year, and is blank when either year is (the SQL twin is sql/showcase/02, `metrics.yoy_lag`)."""
    g = pd.DataFrame(metrics.yoy_lag(f))
    g = g[g["kpi_code"] == "DEMAND_GROWTH"].rename(columns={"value": "demand_twh", "change": "growth_pct"})
    g = g[g["year"].between(first, last)].sort_values("year")
    out = g[["year", "demand_twh", "growth_pct"]].reset_index(drop=True)
    return out.astype({"demand_twh": float, "growth_pct": float})


def demand_summary(d: pd.DataFrame) -> str:
    a, b = d.iloc[0], d.iloc[-1]
    return f"Demand went from {fmt(a['demand_twh'])} TWh in {int(a['year'])} to {fmt(b['demand_twh'])} TWh in {int(b['year'])}."


def growth_summary(d: pd.DataFrame) -> str:
    g = d.dropna(subset=["growth_pct"])
    if g.empty:
        return "There is no earlier year to compare the first year with."
    lo, hi = g.loc[g["growth_pct"].idxmin()], g.loc[g["growth_pct"].idxmax()]
    return (
        f"Year-on-year demand growth ranged from {fmt(lo['growth_pct'])}% ({int(lo['year'])}) "
        f"to {fmt(hi['growth_pct'])}% ({int(hi['year'])})."
    )


def target_axis(f: Frames) -> pd.DataFrame:
    """The 'Target Axis' table with DAX [Axis RE Capacity Share (%)], [Axis Official (%)] and [Axis Target (%)]: the
    data years plus the target years, from 2000, always whatever the year range (the report's NoFilter interaction)."""
    tg, off = f["netr_target"].set_index("target_year"), f["re_capacity_official"].set_index("year")
    ember = _focus_annual(f)["re_share_capacity_pct"]
    axis = sorted({*years(f), *tg.index} - set(range(2000)))
    rows = [
        {
            "year": y,
            "ember": _num(ember.get(y)),
            "official": _num(off["re_capacity_share_pct"].get(y)),
            "official_source": off["source_name"].get(y),
            "target": _num(tg["re_capacity_share_pct"].get(y)),
            "target_source": tg["source_name"].get(y),
        }
        for y in axis
    ]
    return pd.DataFrame(rows)


def target_summary(axis: pd.DataFrame) -> str:
    have = axis.dropna(subset=["ember"])
    latest = have.iloc[-1]
    targets = "; ".join(f"{fmt(t.target, 0)}% by {t.year}" for t in axis.dropna(subset=["target"]).itertuples())
    return f"Ember-basis renewable share of capacity was {fmt(latest['ember'])}% in {int(latest['year'])}. Targets: {targets}."
