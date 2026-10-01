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
RANK_DAX = 'EVALUATE SUMMARIZECOLUMNS ( {filters}"rank", [Focus RE Share Rank], "n", [Countries Compared], "year", [Common Latest Year], "per_capita_year", [Common Per Capita Year] )'

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
         exact=("rank", "n", "year", "per_capita_year"), reshape=rank_card),
    Twin("P5 rank card, Singapore deselected (5 countries)", RANK_DAX.format(filters=_names(PEERS6[:5]) + ", "),
         ranking_sql(PEERS6[:5]), (), (), exact=("rank", "n", "year"), reshape=rank_card),
    Twin("P5 rank card, Brunei added (common year falls to 2024)", RANK_DAX.format(filters=_names(PEERS6 + ("Brunei",)) + ", "),
         ranking_sql(PEERS6 + ("Brunei",)), (), (), exact=("rank", "n", "year", "per_capita_year"), reshape=rank_card),
    Twin("P5 rank card, year range 2015-2020", RANK_DAX.format(filters="TREATAS ( GENERATESERIES ( 2015, 2020, 1 ), dim_year[year] ), "),
         ranking_sql(last_year=2020), (), (), exact=("rank", "n", "year", "per_capita_year"), reshape=rank_card),
    Twin("P1 rank card, 2024 selected", RANK_DAX.format(filters="TREATAS ( { 2024 }, dim_year[year] ), "),
         ranking_sql(last_year=2024), (), (), exact=("rank", "n", "year"), reshape=rank_card),
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
