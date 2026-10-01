"""DAX vs SQL twin check (M2 step 7, doc 06 task 2.2): every report measure must equal its
SQL showcase twin.

Each twin asks the same question twice: once in DAX against the model open in Power BI
Desktop (via tools/dax_query.ps1) and once in SQL against the mart views. Rows are matched
on a key, and values must agree within max(0.05, 0.1% of the SQL value). A value blank on
one side must be blank (NULL) on the other.

    (open report/EnergyTransition.pbip in Desktop first)
    .venv/Scripts/python tools/dax_twin_check.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config, db

SHOWCASE = config.ROOT / "sql" / "showcase"
PEERS = "TREATAS ( { TRUE () }, dim_country[is_default_peer] )"
FIVE = 'TREATAS ( { "Malaysia", "Indonesia", "Thailand", "Vietnam", "Philippines" }, dim_country[name] )'


@dataclass(frozen=True)
class Twin:
    name: str
    dax: str
    sql: str  # SQL text; may reference a showcase file via {file:NAME}
    key: tuple[str, ...]  # columns that identify a row (same names on both sides)
    values: tuple[str, ...]  # columns compared numerically


def _showcase(name: str) -> str:
    return (SHOWCASE / f"{name}.sql").read_text(encoding="utf-8")


def _wrap(name: str, select: str) -> str:
    """Run a showcase query as a derived table, so a twin can pick and rename its columns."""
    body = _showcase(name).strip().rstrip(";")
    body = re.sub(r"\nORDER BY[^\n]*$", "", body)  # ORDER BY is not allowed in a derived table
    if body.lstrip().upper().startswith("WITH"):
        raise ValueError(f"{name}: CTE queries are wrapped by the twin's own SQL, not here")
    return select.replace("{q}", f"({body}) AS q")


TWINS = (
    Twin(
        "P1 KPIs and YoY, Malaysia 2025",
        """EVALUATE SUMMARIZECOLUMNS ( TREATAS ( { 2025 }, dim_year[year] ),
            "TOTAL_GENERATION", [Total Generation (TWh)], "RE_SHARE_GEN", [RE Share (%)], "FOSSIL_SHARE_GEN", [Fossil Share (%)],
            "CARBON_INTENSITY", [Carbon Intensity (gCO2e/kWh)], "DEMAND_PER_CAPITA", [Demand per Capita (MWh)],
            "TOTAL_GENERATION_chg", [Total Generation YoY (%)] * 100, "RE_SHARE_GEN_chg", [RE Share YoY (pp)],
            "FOSSIL_SHARE_GEN_chg", [Fossil Share YoY (pp)], "CARBON_INTENSITY_chg", [Carbon Intensity YoY (%)] * 100,
            "DEMAND_PER_CAPITA_chg", [Demand per Capita YoY (%)] * 100 )""",
        "{file:02_yoy_lag:pivot2025}",
        (),
        ("TOTAL_GENERATION", "RE_SHARE_GEN", "FOSSIL_SHARE_GEN", "CARBON_INTENSITY", "DEMAND_PER_CAPITA",
         "TOTAL_GENERATION_chg", "RE_SHARE_GEN_chg", "FOSSIL_SHARE_GEN_chg", "CARBON_INTENSITY_chg", "DEMAND_PER_CAPITA_chg"),
    ),
    Twin(
        "P2 mix TWh and share by source, Malaysia 2025",
        """EVALUATE SUMMARIZECOLUMNS ( dim_source[display_name], TREATAS ( { 2025 }, dim_year[year] ),
            "twh", [Ctx Generation (TWh)], "share", [Ctx Generation Share (%)] )""",
        "SELECT source AS display_name, generation_twh AS twh, share_of_mix_pct AS share FROM {q} WHERE year = 2025",
        ("display_name",),
        ("twh", "share"),
    ),
    Twin(
        "D1 mix share by source, Vietnam 2020 (country in context)",
        """EVALUATE SUMMARIZECOLUMNS ( dim_source[display_name], TREATAS ( { 2020 }, dim_year[year] ),
            TREATAS ( { "Vietnam" }, dim_country[name] ), "share", [Ctx Generation Share (%)] )""",
        """SELECT s.display_name, CAST(100.0 * g.generation_twh / SUM(g.generation_twh) OVER () AS DECIMAL(9, 3)) AS share
           FROM mart.generation_annual AS g JOIN mart.dim_source AS s ON s.source_key = g.source_key
           JOIN mart.dim_country AS c ON c.country_key = g.country_key WHERE c.name = 'Vietnam' AND g.year = 2020""",
        ("display_name",),
        ("share",),
    ),
    Twin(
        "P2 demand growth, Malaysia, every year",
        """EVALUATE SUMMARIZECOLUMNS ( dim_year[year], "growth", [Ctx Demand Growth (%)] )""",
        "{file:02_yoy_lag:DEMAND_GROWTH}",
        ("year",),
        ("growth",),
    ),
    Twin(
        "P2 capacity factor by source, Malaysia 2024 (leap year) and 2025",
        """EVALUATE UNION (
            ADDCOLUMNS ( CALCULATETABLE ( SUMMARIZECOLUMNS ( dim_source[display_name], "cf", [Ctx Capacity Factor (%)] ), dim_year[year] = 2024 ), "year", 2024 ),
            ADDCOLUMNS ( CALCULATETABLE ( SUMMARIZECOLUMNS ( dim_source[display_name], "cf", [Ctx Capacity Factor (%)] ), dim_year[year] = 2025 ), "year", 2025 ) )""",
        "SELECT source AS display_name, year, capacity_factor_pct AS cf FROM {q} WHERE name = 'Malaysia' AND year IN (2024, 2025) AND capacity_factor_pct IS NOT NULL",
        ("display_name", "year"),
        ("cf",),
    ),
    Twin(
        "D1 capacity factor by source, Philippines 2023 (geothermal capacity gap)",
        """EVALUATE CALCULATETABLE ( SUMMARIZECOLUMNS ( dim_source[display_name], TREATAS ( { "Philippines" }, dim_country[name] ),
            "cf", [Ctx Capacity Factor (%)] ), dim_year[year] = 2023 )""",
        "SELECT source AS display_name, capacity_factor_pct AS cf FROM {q} WHERE name = 'Philippines' AND year = 2023 AND capacity_factor_pct IS NOT NULL",
        ("display_name",),
        ("cf",),
    ),
    Twin(
        "P5 values at the comparison year, 6 default peers",
        f"""EVALUATE SUMMARIZECOLUMNS ( dim_country[name], {PEERS},
            "re", [RE Share at Comparison Year (%)], "intensity", [Intensity at Comparison Year (gCO2e/kWh)],
            "per_capita", [Demand per Capita at Common Year (MWh)] )""",
        "{file:03_ranking:values}",
        ("name",),
        ("re", "intensity", "per_capita"),
    ),
    Twin(
        "P5 rank card, 6 default peers",
        f"""EVALUATE SUMMARIZECOLUMNS ( {PEERS}, "rank", [Focus RE Share Rank], "n", [Countries Compared],
            "year", [Common Latest Year], "per_capita_year", [Common Per Capita Year] )""",
        "{file:03_ranking:rank}",
        (),
        ("rank", "n", "year", "per_capita_year"),
    ),
    Twin(
        "P5 rank card, Singapore deselected (5 countries)",
        f"""EVALUATE SUMMARIZECOLUMNS ( {FIVE}, "rank", [Focus RE Share Rank], "n", [Countries Compared] )""",
        "{file:03_ranking:rank5}",
        (),
        ("rank", "n"),
    ),
    Twin(
        "P2 target chart: Ember basis, official and targets, 2000-2050",
        """EVALUATE SUMMARIZECOLUMNS ( 'Target Axis'[year], "ember", [Axis RE Capacity Share (%)],
            "official", [Axis Official (%)], "target", [Axis Target (%)] )""",
        """SELECT y.year, ca.re_share_capacity_pct AS ember, o.re_capacity_share_pct AS official, t.re_capacity_share_pct AS target
           FROM (SELECT year FROM mart.dim_year UNION SELECT target_year FROM mart.netr_target) AS y
           LEFT JOIN (SELECT a.year, a.re_share_capacity_pct FROM mart.country_annual AS a JOIN mart.dim_country AS c
                      ON c.country_key = a.country_key AND c.is_focus = 1) AS ca ON ca.year = y.year
           LEFT JOIN mart.re_capacity_official AS o ON o.year = y.year
           LEFT JOIN mart.netr_target AS t ON t.target_year = y.year
           WHERE y.year >= 2000 AND (ca.re_share_capacity_pct IS NOT NULL OR o.year IS NOT NULL OR t.target_year IS NOT NULL)""",
        ("year",),
        ("ember", "official", "target"),
    ),
)


def _sql_for(twin: Twin) -> str:
    match = re.fullmatch(r"\{file:(\w+):(\w+)\}", twin.sql.strip())
    if not match:
        return twin.sql if "{q}" not in twin.sql else _wrap(_file_for(twin), twin.sql)
    name, view = match.groups()
    if name == "02_yoy_lag":
        body = _showcase(name).strip().rstrip(";")
        if view == "DEMAND_GROWTH":
            return body.replace("ORDER BY ch.kpi_code, ch.year", "") .replace(
                "FROM changes AS ch", "FROM changes AS ch WHERE ch.kpi_code = 'DEMAND_GROWTH' AND ch.change IS NOT NULL"
            ).replace("SELECT\n    ch.year,\n    ch.kpi_code,\n    ch.value,\n    ch.change,", "SELECT\n    ch.year,\n    ch.kpi_code,\n    ch.value,\n    ch.change AS growth,")
        if view == "pivot2025":
            return body.replace("ORDER BY ch.kpi_code, ch.year", "").replace("FROM changes AS ch", "FROM changes AS ch WHERE ch.year = 2025")
    if name == "03_ranking":
        body = _showcase(name).strip().rstrip(";").replace("ORDER BY g.re_share_rank, g.name", "")
        if view == "rank5":
            body = body.replace(
                "WHERE c.is_default_peer = 1",
                "WHERE c.name IN ('Malaysia', 'Indonesia', 'Thailand', 'Vietnam', 'Philippines')",
            )
        return body
    raise ValueError(twin.sql)


def _file_for(twin: Twin) -> str:
    return {
        "P2 mix TWh and share by source, Malaysia 2025": "01_trends",
        "P2 capacity factor by source, Malaysia 2024 (leap year) and 2025": "05_capacity_factor",
        "D1 capacity factor by source, Philippines 2023 (geothermal capacity gap)": "05_capacity_factor",
    }[twin.name]


def run_dax(query: str) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as fh:
        fh.write(query)
        path = fh.name
    out = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(config.ROOT / "tools" / "dax_query.ps1"), "-QueryFile", path],
        capture_output=True, text=True, encoding="utf-8",
    )
    Path(path).unlink(missing_ok=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or out.stdout.strip())
    rows = json.loads(out.stdout or "[]")
    # DAX column names come back as "table[column]" or "[name]".
    return [{re.sub(r"^.*\[(.*)\]$", r"\1", k): v for k, v in row.items()} for row in rows]


def run_sql(cursor, query: str) -> list[dict]:
    cursor.execute(query)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _num(value):
    return None if value is None else float(value)


def _close(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= max(0.05, 0.001 * abs(b))


def _reshape_sql(twin: Twin, rows: list[dict]) -> list[dict]:
    if twin.name.startswith("P1 KPIs"):
        flat: dict = {}
        for r in rows:
            flat[r["kpi_code"]] = r["value"]
            flat[r["kpi_code"] + "_chg"] = r["change"]
        flat.pop("DEMAND_GROWTH", None)
        flat.pop("DEMAND_GROWTH_chg", None)
        return [flat]
    if twin.name.startswith("P5 values"):
        return [{"name": r["name"], "re": r["re_share_gen_pct"], "intensity": r["emissions_intensity_gco2e_kwh"],
                 "per_capita": r["demand_per_capita_mwh"]} for r in rows]
    if twin.name.startswith("P5 rank card"):
        my = next((r for r in rows if r["name"] == "Malaysia"), None)
        return [{"rank": my and my["re_share_rank"], "n": len(rows), "year": rows[0]["comparison_year"],
                 "per_capita_year": rows[0]["per_capita_year"]}]
    return rows


def check(twin: Twin, cursor) -> tuple[bool, list[str]]:
    dax_rows = run_dax(twin.dax)
    sql_rows = _reshape_sql(twin, run_sql(cursor, _sql_for(twin)))
    key = lambda r: tuple(str(int(r[k])) if isinstance(r[k], (int, float)) else str(r[k]) for k in twin.key)  # noqa: E731
    dax_by, sql_by = {key(r): r for r in dax_rows}, {key(r): r for r in sql_rows}
    problems = []
    for k in sorted(set(dax_by) | set(sql_by)):
        d, s = dax_by.get(k), sql_by.get(k)
        if d is None or s is None:
            problems.append(f"{k}: only in {'SQL' if d is None else 'DAX'}")
            continue
        for col in twin.values:
            if col not in s:
                continue  # e.g. the 5-country twin has no per-capita year
            if not _close(_num(d.get(col)), _num(s.get(col))):
                problems.append(f"{k} {col}: DAX {d.get(col)} vs SQL {s.get(col)}")
    return not problems, problems


def main() -> int:
    cursor = db.connect().cursor()
    failures = 0
    for twin in TWINS:
        try:
            ok, problems = check(twin, cursor)
        except Exception as exc:  # report and continue, so one bad twin doesn't hide the rest
            ok, problems = False, [f"error: {exc}"]
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {twin.name}")
        for p in problems[:10]:
            print(f"        {p}")
    print(f"\n{len(TWINS) - failures}/{len(TWINS)} twins pass")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
