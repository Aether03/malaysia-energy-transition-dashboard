"""DAX vs SQL twin check (M2 step 7, doc 06 task 2.2): every report measure must equal its
SQL showcase twin.

Each twin asks the same question twice: once in DAX against the model open in Power BI
Desktop (via tools/dax_query.ps1) and once in SQL against the mart views, mostly by running
the sql/showcase queries themselves. Rows are matched on a key. Measured values must agree
within max(0.05, 0.1% of the SQL value); years, ranks and counts must match exactly. A value
blank on one side must be blank (NULL) on the other, and a missing column is a failure.

    (open report/EnergyTransition.pbip in Desktop first, and only that file)
    .venv/Scripts/python tools/dax_twin_check.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config, db

SHOWCASE = config.ROOT / "sql" / "showcase"
PEERS6 = ("Malaysia", "Indonesia", "Thailand", "Vietnam", "Philippines", "Singapore")


# ---------- SQL side: the showcase queries, with the twin's filter applied ----------
def _body(name: str) -> str:
    return (SHOWCASE / f"{name}.sql").read_text(encoding="utf-8").strip().rstrip(";")


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"expected exactly one {old!r} in the showcase query")
    return text.replace(old, new)


def _derived(name: str, select: str) -> str:
    """Use a non-CTE showcase query as a derived table `q`."""
    body = re.sub(r"\nORDER BY[^\n]*$", "", _body(name))
    return select.replace("{q}", f"({body}) AS q")


def yoy_sql(year: int, kpi: str | None = None) -> str:
    body = _replace_once(_body("02_yoy_lag"), "ORDER BY ch.kpi_code, ch.year", "")
    where = f"WHERE ch.year = {year}" if kpi is None else f"WHERE ch.kpi_code = '{kpi}' AND ch.change IS NOT NULL"
    return _replace_once(body, "JOIN mart.kpi AS k ON k.kpi_code = ch.kpi_code", f"JOIN mart.kpi AS k ON k.kpi_code = ch.kpi_code\n{where}")


def ranking_sql(names: tuple[str, ...] | None = None, last_year: int | None = None) -> str:
    body = _replace_once(_body("03_ranking"), "ORDER BY g.re_share_rank, g.name", "")
    if names is not None:
        listed = ", ".join(f"'{n}'" for n in names)
        body = _replace_once(body, "WHERE c.is_default_peer = 1", f"WHERE c.name IN ({listed})")
    if last_year is not None:
        body = _replace_once(body, "SELECT MAX(year) AS last_year FROM mart.dim_year", f"SELECT {last_year} AS last_year")
    return body


# ---------- reshaping SQL rows into the DAX twin's shape ----------
def kpis_flat(rows: list[dict]) -> list[dict]:
    flat: dict = {}
    for r in rows:
        if r["kpi_code"] != "DEMAND_GROWTH":
            flat[r["kpi_code"]] = r["value"]
            flat[r["kpi_code"] + "_chg"] = r["change"]
    return [flat]


def rank_card(rows: list[dict]) -> list[dict]:
    my = next((r for r in rows if r["name"] == "Malaysia"), None)
    return [{
        "rank": my["re_share_rank"] if my else None,
        "intensity_rank": my["intensity_rank"] if my else None,
        "n": len(rows),
        "year": rows[0]["comparison_year"] if rows else None,
        "per_capita_year": rows[0]["per_capita_year"] if rows else None,
    }]


def peer_values(rows: list[dict]) -> list[dict]:
    return [{"name": r["name"], "re": r["re_share_gen_pct"], "intensity": r["emissions_intensity_gco2e_kwh"],
             "per_capita": r["demand_per_capita_mwh"]} for r in rows]


@dataclass(frozen=True)
class Twin:
    name: str
    dax: str
    sql: str
    key: tuple[str, ...]
    values: tuple[str, ...]
    exact: tuple[str, ...] = ()  # whole numbers (years, ranks, counts): must match exactly
    reshape: Callable[[list[dict]], list[dict]] = field(default=lambda rows: rows)


def _names(names: tuple[str, ...]) -> str:
    return "TREATAS ( { " + ", ".join(f'"{n}"' for n in names) + " }, 'Compare Country'[name] )"


KPI_DAX = """EVALUATE SUMMARIZECOLUMNS ( TREATAS ( {{ {y} }}, dim_year[year] ),
    "TOTAL_GENERATION", [Total Generation (TWh)], "RE_SHARE_GEN", [RE Share (%)], "FOSSIL_SHARE_GEN", [Fossil Share (%)],
    "CARBON_INTENSITY", [Carbon Intensity (gCO2e/kWh)], "DEMAND_PER_CAPITA", [Demand per Capita (MWh)],
    "TOTAL_GENERATION_chg", [Total Generation YoY (%)] * 100, "RE_SHARE_GEN_chg", [RE Share YoY (pp)],
    "FOSSIL_SHARE_GEN_chg", [Fossil Share YoY (pp)], "CARBON_INTENSITY_chg", [Carbon Intensity YoY (%)] * 100,
    "DEMAND_PER_CAPITA_chg", [Demand per Capita YoY (%)] * 100 )"""
KPI_COLS = ("TOTAL_GENERATION", "RE_SHARE_GEN", "FOSSIL_SHARE_GEN", "CARBON_INTENSITY", "DEMAND_PER_CAPITA",
            "TOTAL_GENERATION_chg", "RE_SHARE_GEN_chg", "FOSSIL_SHARE_GEN_chg", "CARBON_INTENSITY_chg", "DEMAND_PER_CAPITA_chg")
RANK_DAX = 'EVALUATE SUMMARIZECOLUMNS ( {filters}"rank", [Focus RE Share Rank], "intensity_rank", [Focus Intensity Rank], "n", [Countries Compared], "year", [Common Latest Year], "per_capita_year", [Common Per Capita Year] )'

TWINS = (
    Twin("P1 KPIs and YoY, Malaysia 2025", KPI_DAX.format(y=2025), yoy_sql(2025), (), KPI_COLS, reshape=kpis_flat),
    Twin("P1 KPIs and YoY, Malaysia 2015 (slicer honoured, not the default year)", KPI_DAX.format(y=2015), yoy_sql(2015), (), KPI_COLS, reshape=kpis_flat),
    Twin(
        "P2 mix TWh and share by source, Malaysia 2025",
        'EVALUATE SUMMARIZECOLUMNS ( dim_source[display_name], TREATAS ( { 2025 }, dim_year[year] ), "twh", [Ctx Generation (TWh)], "share", [Ctx Generation Share (%)] )',
        _derived("01_trends", "SELECT source AS display_name, generation_twh AS twh, share_of_mix_pct AS share FROM {q} WHERE year = 2025"),
        ("display_name",), ("twh", "share"),
    ),
    Twin(
        "D1 mix share by source, Vietnam 2020 (country in context)",
        'EVALUATE SUMMARIZECOLUMNS ( dim_source[display_name], TREATAS ( { 2020 }, dim_year[year] ), TREATAS ( { "Vietnam" }, dim_country[name] ), "share", [Ctx Generation Share (%)] )',
        """SELECT s.display_name, CAST(100.0 * g.generation_twh / SUM(g.generation_twh) OVER () AS DECIMAL(9, 3)) AS share
           FROM mart.generation_annual AS g JOIN mart.dim_source AS s ON s.source_key = g.source_key
           JOIN mart.dim_country AS c ON c.country_key = g.country_key WHERE c.name = 'Vietnam' AND g.year = 2020""",
        ("display_name",), ("share",),
    ),
    Twin(
        "P2 demand growth, Malaysia, every year",
        'EVALUATE SUMMARIZECOLUMNS ( dim_year[year], "growth", [Ctx Demand Growth (%)] )',
        yoy_sql(0, "DEMAND_GROWTH"),  # a CTE query can't be a derived table, so reshape in Python
        ("year",), ("growth",),
        reshape=lambda rows: [{"year": r["year"], "growth": r["change"]} for r in rows],
    ),
    Twin(
        "P2 capacity factor by source, Malaysia 2024 (leap year) and 2025",
        """EVALUATE UNION (
            ADDCOLUMNS ( CALCULATETABLE ( SUMMARIZECOLUMNS ( dim_source[display_name], "cf", [Ctx Capacity Factor (%)] ), dim_year[year] = 2024 ), "year", 2024 ),
            ADDCOLUMNS ( CALCULATETABLE ( SUMMARIZECOLUMNS ( dim_source[display_name], "cf", [Ctx Capacity Factor (%)] ), dim_year[year] = 2025 ), "year", 2025 ) )""",
        _derived("05_capacity_factor", "SELECT source AS display_name, year, capacity_factor_pct AS cf FROM {q} WHERE name = 'Malaysia' AND year IN (2024, 2025) AND capacity_factor_pct IS NOT NULL"),
        ("display_name", "year"), ("cf",),
    ),
    Twin(
        "D1 capacity factor by source, Philippines 2023 (geothermal capacity gap)",
        'EVALUATE CALCULATETABLE ( SUMMARIZECOLUMNS ( dim_source[display_name], TREATAS ( { "Philippines" }, dim_country[name] ), "cf", [Ctx Capacity Factor (%)] ), dim_year[year] = 2023 )',
        _derived("05_capacity_factor", "SELECT source AS display_name, capacity_factor_pct AS cf FROM {q} WHERE name = 'Philippines' AND year = 2023 AND capacity_factor_pct IS NOT NULL"),
        ("display_name",), ("cf",),
    ),
    Twin(
        "P5 values at the comparison year, 6 default peers (no selection)",
        """EVALUATE FILTER ( SUMMARIZECOLUMNS ( dim_country[name], "re", [RE Share at Comparison Year (%)],
            "intensity", [Intensity at Comparison Year (gCO2e/kWh)], "per_capita", [Demand per Capita at Common Year (MWh)],
            "compared", [Is Compared] ), [compared] = 1 )""",
        ranking_sql(), ("name",), ("re", "intensity", "per_capita"), reshape=peer_values,
    ),
    Twin("P5 rank card, 6 default peers (no selection)", RANK_DAX.format(filters=""), ranking_sql(), (), (),
         exact=("rank", "intensity_rank", "n", "year", "per_capita_year"), reshape=rank_card),
    Twin("P5 rank card, Singapore deselected (5 countries)", RANK_DAX.format(filters=_names(PEERS6[:5]) + ", "),
         ranking_sql(PEERS6[:5]), (), (), exact=("rank", "intensity_rank", "n", "year"), reshape=rank_card),
    Twin("P5 rank card, Brunei added (common year falls to 2024)", RANK_DAX.format(filters=_names(PEERS6 + ("Brunei",)) + ", "),
         ranking_sql(PEERS6 + ("Brunei",)), (), (), exact=("rank", "intensity_rank", "n", "year", "per_capita_year"), reshape=rank_card),
    Twin("P5 rank card, year range 2015-2020", RANK_DAX.format(filters="TREATAS ( GENERATESERIES ( 2015, 2020, 1 ), dim_year[year] ), "),
         ranking_sql(last_year=2020), (), (), exact=("rank", "intensity_rank", "n", "year", "per_capita_year"), reshape=rank_card),
    Twin("P1 rank card, 2024 selected", RANK_DAX.format(filters="TREATAS ( { 2024 }, dim_year[year] ), "),
         ranking_sql(last_year=2024), (), (), exact=("rank", "intensity_rank", "n", "year"), reshape=rank_card),
    Twin(
        "P2 target chart: Ember basis, official and targets, 2000-2050",
        'EVALUATE SUMMARIZECOLUMNS ( \'Target Axis\'[year], "ember", [Axis RE Capacity Share (%)], "official", [Axis Official (%)], "target", [Axis Target (%)] )',
        """SELECT y.year, ca.re_share_capacity_pct AS ember, o.re_capacity_share_pct AS official, t.re_capacity_share_pct AS target
           FROM (SELECT year FROM mart.dim_year UNION SELECT target_year FROM mart.netr_target) AS y
           LEFT JOIN (SELECT a.year, a.re_share_capacity_pct FROM mart.country_annual AS a JOIN mart.dim_country AS c
                      ON c.country_key = a.country_key AND c.is_focus = 1) AS ca ON ca.year = y.year
           LEFT JOIN mart.re_capacity_official AS o ON o.year = y.year
           LEFT JOIN mart.netr_target AS t ON t.target_year = y.year
           WHERE y.year >= 2000 AND (ca.re_share_capacity_pct IS NOT NULL OR o.year IS NOT NULL OR t.target_year IS NOT NULL)""",
        ("year",), ("ember", "official", "target"),
    ),
)


# ---------- P4 Grid load & forecast (M3 step 11) ----------
TH, YEARS = 'TREATAS ( { "TH_EGAT" }, dim_grid[grid_code] )', "TREATAS ( { 2023, 2024 }, dim_date[year] )"


def _pick(rename: dict[str, str], keep: Callable[[dict], bool]) -> Callable[[list[dict]], list[dict]]:
    """Filter a CTE showcase query's rows in Python (a CTE can't be a derived table) and rename columns."""
    return lambda rows: [{rename.get(k, k): v for k, v in r.items()} for r in rows if keep(r)]


def _day_sql(grid: str, date_key: int) -> str:
    return f"""SELECT f.hour, f.actual_mw AS actual, f.forecast_mw AS model, f.baseline_mw AS baseline, f.date_key AS day
               FROM mart.load_forecast_current AS f JOIN mart.dim_grid AS g ON g.grid_key = f.grid_key
               WHERE g.grid_code = '{grid}' AND f.date_key = {date_key}"""


DAY_COLS = '"actual", [Day Actual (MW)], "model", [Day Model (MW)], "baseline", [Day Baseline (MW)], "day", [Forecast Day Key]'

P4_TWINS = (
    Twin(
        "P4 peak and load factor by month, Thailand 2023-24",
        f'EVALUATE SUMMARIZECOLUMNS ( dim_date[year], dim_date[month], {TH}, {YEARS}, "peak", [Peak Load (MW)], "lf", [Load Factor (%)] )',
        _body("08_grid_load"), ("year", "month"), ("peak", "lf"),
        reshape=_pick({"peak_mw": "peak", "load_factor_pct": "lf"}, lambda r: r["grid_code"] == "TH_EGAT" and r["month"] is not None),
    ),
    Twin(
        "P4 annual peak and load factor, both grids",
        f'EVALUATE SUMMARIZECOLUMNS ( dim_grid[grid_code], dim_date[year], {YEARS}, "peak", [Peak Load (MW)], "lf", [Load Factor (%)] )',
        _body("08_grid_load"), ("grid_code", "year"), ("peak", "lf"),
        reshape=_pick({"peak_mw": "peak", "load_factor_pct": "lf"}, lambda r: r["month"] is None),
    ),
    Twin(
        "P4 load curves, both grids, every season x day type x hour (288 points)",
        f'EVALUATE SUMMARIZECOLUMNS ( dim_grid[grid_code], grid_hourly[season], grid_hourly[day_type], dim_hour[hour], {YEARS}, "mw", [Avg Load (MW)] )',
        _derived("10_load_curves", "SELECT grid_code, season, day_type, hour, mean_mw AS mw FROM {q}"),
        ("grid_code", "season", "day_type", "hour"), ("mw",),
    ),
    Twin(
        "P4 load-curve season toggle, Thailand Hot season picked (curve only)",
        f'EVALUATE SUMMARIZECOLUMNS ( grid_hourly[day_type], dim_hour[hour], {TH}, {YEARS}, '
        'TREATAS ( { "Hot (Mar–May)" }, season_pick[season] ), "mw", [Avg Load Curve (MW)] )',
        _derived("10_load_curves", "SELECT day_type, hour, mean_mw AS mw FROM {q} WHERE grid_code = 'TH_EGAT' AND season_order = 1"),
        ("day_type", "hour"), ("mw",),
    ),
    Twin(
        "P4 backtest metric cards, both grids (SQL recomputes MAPE/MAE from the facts)",
        'EVALUATE SUMMARIZECOLUMNS ( dim_grid[grid_code], "mape_model", [Backtest MAPE Model (%)], "mape_baseline", [Backtest MAPE Baseline (%)], '
        '"mae_model", [Backtest MAE Model (MW)], "mae_baseline", [Backtest MAE Baseline (MW)], "improvement", [Backtest Improvement (%)] )',
        _body("09_forecast_metrics"), ("grid_code",), ("mape_model", "mape_baseline", "mae_model", "mae_baseline", "improvement"),
        reshape=_pick({"improvement_pct": "improvement"}, lambda r: r["month"] is None),
    ),
    Twin(
        "P4 forecast day, Thailand, no pick (defaults to the 2024 peak day, 29 Apr)",
        f"EVALUATE SUMMARIZECOLUMNS ( dim_hour[hour], {TH}, {DAY_COLS} )",
        _day_sql("TH_EGAT", 20240429), ("hour",), ("actual", "model", "baseline"), exact=("day",),
    ),
    Twin(
        "P4 forecast day, Singapore, 10 Feb 2024 picked (Chinese New Year)",
        'EVALUATE SUMMARIZECOLUMNS ( dim_hour[hour], TREATAS ( { "SG_EMA" }, dim_grid[grid_code] ), '
        f"TREATAS ( {{ DATE ( 2024, 2, 10 ) }}, forecast_date[date] ), {DAY_COLS} )",
        _day_sql("SG_EMA", 20240210), ("hour",), ("actual", "model", "baseline"), exact=("day",),
    ),
    Twin(
        "P4 day MAPE, Thailand 7 Dec 2024 (a published gap hour is left out)",
        f'EVALUATE SUMMARIZECOLUMNS ( {TH}, TREATAS ( {{ DATE ( 2024, 12, 7 ) }}, forecast_date[date] ), '
        '"model", [Day MAPE Model (%)], "baseline", [Day MAPE Baseline (%)] )',
        """SELECT 100.0 * AVG(ABS(CAST(f.actual_mw AS FLOAT) - CAST(f.forecast_mw AS FLOAT)) / CAST(f.actual_mw AS FLOAT)) AS model,
                  100.0 * AVG(ABS(CAST(f.actual_mw AS FLOAT) - CAST(f.baseline_mw AS FLOAT)) / CAST(f.actual_mw AS FLOAT)) AS baseline
           FROM mart.load_forecast_current AS f JOIN mart.dim_grid AS g ON g.grid_key = f.grid_key
           WHERE g.grid_code = 'TH_EGAT' AND f.date_key = 20241207 AND f.is_scored = 1""",
        (), ("model", "baseline"),
    ),
    Twin(
        "P4 Thailand-Malaysia flows by year (export and import GWh)",
        f'EVALUATE SUMMARIZECOLUMNS ( dim_date[year], {TH}, {YEARS}, "exp", [Flow Export (GWh)], "imp", [Flow Import (GWh)] )',
        _derived("11_interconnector_flows", "SELECT year, export_gwh AS exp, import_gwh AS imp FROM {q}"),
        ("year",), ("exp", "imp"),
    ),
)
TWINS = TWINS + P4_TWINS


# M4 P3 / P3b: handbook values compare EXACTLY (SAIFI is ~1, so the 0.05 tolerance would hide a
# wrong cell); only derived ratios use the tolerance. Twins hold no handbook value (plan Q1).
_STATE_SQL = """SELECT d.state_code, f.saifi, f.saidi_min,
                       RANK() OVER (ORDER BY f.saifi) AS saifi_rank, RANK() OVER (ORDER BY f.saidi_min) AS saidi_rank,
                       f.saidi_min - b.saidi_min AS saidi_chg
                FROM mart.state_reliability AS f JOIN mart.dim_state AS d ON d.state_key = f.state_key
                JOIN mart.state_reliability AS b ON b.state_key = f.state_key AND b.year = 2015
                WHERE f.year = {year}"""
_REGION_SQL = """SELECT g.region_code, a.year, a.metric_code, a.value
                 FROM mart.region_annual AS a JOIN mart.dim_region AS g ON g.region_key = a.region_key"""


def _latest(metric: str, out: str) -> str:
    return f"""SELECT x.region_code, x.value AS {out} FROM ({_REGION_SQL}) AS x
               WHERE x.metric_code = '{metric}' AND x.year = (SELECT MAX(y.year) FROM ({_REGION_SQL}) AS y
                                                              WHERE y.metric_code = '{metric}' AND y.region_code = x.region_code)"""


P3_TWINS = (
    Twin(
        "P3b default view: SAIFI 2022 by state, value and rank (no picks)",
        'EVALUATE SUMMARIZECOLUMNS ( dim_state[state_code], "saifi", [Reliability Value], "saifi_rank", [Reliability Rank] )',
        _STATE_SQL.format(year=2022), ("state_code",), (), exact=("saifi", "saifi_rank"),
    ),
    Twin(
        "P3b SAIDI toggle + 2015 picked: value, rank, change since 2015 (zero)",
        'EVALUATE SUMMARIZECOLUMNS ( dim_state[state_code], TREATAS ( { "SAIDI" }, reliability_metric[metric_code] ), '
        'TREATAS ( { 2015 }, reliability_year[year] ), "saidi_min", [Reliability Value], "saidi_rank", [Reliability Rank], '
        '"saidi_chg", [Reliability Change Since 2015] )',
        _STATE_SQL.format(year=2015), ("state_code",), (), exact=("saidi_min", "saidi_rank", "saidi_chg"),
    ),
    Twin(
        "P3b SAIDI change since 2015, 2022 picked",
        'EVALUATE SUMMARIZECOLUMNS ( dim_state[state_code], TREATAS ( { "SAIDI" }, reliability_metric[metric_code] ), '
        'TREATAS ( { 2022 }, reliability_year[year] ), "saidi_chg", [Reliability Change Since 2015] )',
        _STATE_SQL.format(year=2022), ("state_code",), ("saidi_chg",),
    ),
    Twin(
        "P3b trend: Johor clicked vs Peninsular, SAIFI by year",
        'EVALUATE SUMMARIZECOLUMNS ( dim_year[year], TREATAS ( { "JHR" }, dim_state[state_code] ), '
        '"sel", [Reliability Selected State], "pen", [Reliability Peninsular] )',
        """SELECT f.year, f.saifi AS sel, p.value AS pen
           FROM mart.state_reliability AS f JOIN mart.dim_state AS d ON d.state_key = f.state_key AND d.state_code = 'JHR'
           JOIN mart.region_annual AS p ON p.year = f.year AND p.metric_code = 'SAIFI'
           JOIN mart.dim_region AS g ON g.region_key = p.region_key AND g.region_code = 'PEN'""",
        ("year",), (), exact=("sel", "pen"),
    ),
    Twin(
        "P3 region cards: installed and available MW, latest consumption, use per person and SAIFI",
        'EVALUATE SUMMARIZECOLUMNS ( dim_region[region_code], "inst", [Region Installed (MW)], "avail", [Region Available (MW)], '
        '"gwh", [Region Consumption (GWh)], "kwh", [Region Use per Person (kWh)], "saifi", [Region SAIFI], '
        '"saifi_year", [Region SAIFI Year] )',
        f"""SELECT i.region_code, i.inst, a.avail, c.gwh, k.kwh, s.saifi,
                   (SELECT MAX(y.year) FROM ({_REGION_SQL}) AS y WHERE y.metric_code = 'SAIFI' AND y.region_code = i.region_code) AS saifi_year
            FROM ({_latest('INSTALLED_MW', 'inst')}) AS i JOIN ({_latest('AVAILABLE_MW', 'avail')}) AS a ON a.region_code = i.region_code
            JOIN ({_latest('ELEC_CONSUMPTION_GWH', 'gwh')}) AS c ON c.region_code = i.region_code
            JOIN ({_latest('ELEC_PER_CAPITA_KWH', 'kwh')}) AS k ON k.region_code = i.region_code
            JOIN ({_latest('SAIFI', 'saifi')}) AS s ON s.region_code = i.region_code""",
        ("region_code",), (), exact=("inst", "avail", "gwh", "kwh", "saifi", "saifi_year"),
    ),
    Twin(
        "P3 headline: Sabah vs Peninsular SAIFI in Sabah's latest year",
        'EVALUATE ROW ( "ratio", [Sabah vs Peninsular SAIFI] )',
        f"""SELECT CAST(s.value AS FLOAT) / p.value AS ratio FROM ({_REGION_SQL}) AS s JOIN ({_REGION_SQL}) AS p
                ON p.year = s.year AND p.metric_code = 'SAIFI' AND p.region_code = 'PEN'
            WHERE s.metric_code = 'SAIFI' AND s.region_code = 'SAB'
              AND s.year = (SELECT MAX(year) FROM ({_REGION_SQL}) AS y WHERE y.metric_code = 'SAIFI' AND y.region_code = 'SAB')""",
        (), ("ratio",),
    ),
    Twin(
        "P3 capacity mix: installed MW by region and fuel group (31 Dec 2021)",
        'EVALUATE SUMMARIZECOLUMNS ( dim_region[region_code], dim_source[source_code], "mw", [Region Installed by Fuel (MW)] )',
        """SELECT g.region_code, s.source_code, c.installed_mw AS mw FROM mart.region_capacity AS c
           JOIN mart.dim_region AS g ON g.region_key = c.region_key JOIN mart.dim_source AS s ON s.source_key = c.source_key
           WHERE c.installed_mw IS NOT NULL""",
        ("region_code", "source_code"), (), exact=("mw",),
    ),
    Twin(
        "P3 consumption and interruptions by region and year",
        'EVALUATE SUMMARIZECOLUMNS ( dim_region[region_code], dim_year[year], "gwh", [Region Consumption by Year (GWh)], '
        '"cuts", [Region Interruptions by Year] )',
        f"""SELECT region_code, year, MAX(CASE WHEN metric_code = 'ELEC_CONSUMPTION_GWH' THEN value END) AS gwh,
                   MAX(CASE WHEN metric_code = 'SUPPLY_INTERRUPTIONS' THEN value END) AS cuts
            FROM ({_REGION_SQL}) AS x WHERE metric_code IN ('ELEC_CONSUMPTION_GWH', 'SUPPLY_INTERRUPTIONS') GROUP BY region_code, year""",
        ("region_code", "year"), (), exact=("gwh", "cuts"),
    ),
)
TWINS = TWINS + P3_TWINS


# ---------- running and comparing ----------
def run_dax(query: str) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as fh:
        fh.write(query)
        path = fh.name
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(config.ROOT / "tools" / "dax_query.ps1"), "-QueryFile", path],
            capture_output=True, text=True, encoding="utf-8",
        )
    finally:
        Path(path).unlink(missing_ok=True)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout).strip().splitlines()[0])
    rows = json.loads(out.stdout or "[]")
    # DAX column names come back as "table[column]" or "[name]".
    return [{re.sub(r"^.*\[(.*)\]$", r"\1", k): v for k, v in row.items()} for row in rows]


def run_sql(cursor, query: str) -> list[dict]:
    cursor.execute(query)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _num(value):
    return None if value is None else float(value)


def _same(a, b, exact: bool) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return a == b if exact else abs(a - b) <= max(0.05, 0.001 * abs(b))


def check(twin: Twin, cursor) -> list[str]:
    dax_rows = run_dax(twin.dax)
    sql_rows = twin.reshape(run_sql(cursor, twin.sql))

    def key(r):
        return tuple(str(int(r[k])) if isinstance(r[k], (int, float)) else str(r[k]) for k in twin.key)

    dax_by, sql_by = {key(r): r for r in dax_rows}, {key(r): r for r in sql_rows}
    problems = []
    for k in sorted(set(dax_by) | set(sql_by)):
        d, s = dax_by.get(k), sql_by.get(k)
        if d is None or s is None:
            problems.append(f"{k}: only in {'SQL' if d is None else 'DAX'}")
            continue
        for col in twin.values + twin.exact:
            if col not in d or col not in s:
                problems.append(f"{k} {col}: missing on the {'DAX' if col not in d else 'SQL'} side")
            elif not _same(_num(d[col]), _num(s[col]), col in twin.exact):
                problems.append(f"{k} {col}: DAX {d[col]} vs SQL {s[col]}")
    return problems


def main() -> int:
    cursor = db.connect().cursor()
    failures = 0
    for twin in TWINS:
        try:
            problems = check(twin, cursor)
        except Exception as exc:  # report and continue, so one bad twin doesn't hide the rest
            problems = [f"error: {exc}"]
        failures += bool(problems)
        print(f"{'FAIL' if problems else 'PASS'}  {twin.name}")
        for p in problems[:10]:
            print(f"        {p}")
    print(f"\n{len(TWINS) - failures}/{len(TWINS)} twins pass")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
