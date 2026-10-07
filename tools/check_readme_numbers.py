"""README number check (M5 step 7, FR-16): every number in the README's findings must match the warehouse.

Each claim is rebuilt as the exact phrase the README uses, from the same sql/showcase queries the
findings cite (docs/findings.md), and must appear verbatim in README.md (bold markers ignored). A
missing phrase means the README and the warehouse have drifted apart: re-run after `pipeline run`.

    .venv/Scripts/python tools/check_readme_numbers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config, db

SHOWCASE = config.ROOT / "sql" / "showcase"
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}


def run(cursor, name: str) -> list[dict]:
    cursor.execute((SHOWCASE / f"{name}.sql").read_text(encoding="utf-8"))
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, (float(v) if hasattr(v, "is_finite") else v for v in row))) for row in cursor.fetchall()]


def claims(cursor) -> list[str]:
    rolling = {r["year"]: r for r in run(cursor, "04_rolling_avg") if r["name"] == "Malaysia"}
    e = run(cursor, "07_emissions_vs_demand")[0]
    ranks = {r["name"]: r for r in run(cursor, "03_ranking")}
    my = ranks["Malaysia"]
    forecast = {r["grid_code"]: r for r in run(cursor, "09_forecast_metrics") if r["month"] is None}
    if abs(e["gas_latest"] - e["gas_base"]) / e["gas_base"] >= 0.01:
        raise SystemExit("FAIL  gas output is no longer flat (>= 1% change): rewrite finding 2")
    return [
        (
            f"from {rolling[2015]['re_share_3yr_avg_pct']:.1f}% (2013–15 average) to "
            f"{rolling[2025]['re_share_3yr_avg_pct']:.1f}% (2023–25)"
        ),
        f"{my['re_share_gen_pct']:.1f}% in {my['comparison_year']}",
        f"fell {-e['intensity_change_pct']:.1f}% ({e['intensity_base']:.0f} → {e['intensity_latest']:.0f} gCO₂e/kWh)",
        f"generation grew {e['generation_change_pct']:.0f}%",
        f"emissions rose {e['emissions_change_pct']:.0f}%",
        f"coal output grew {e['coal_change_pct']:.0f}% while gas was flat",
        f"coal is now {100 * e['coal_latest'] / e['gen_latest']:.1f}% of generation",
        f"{ORDINAL[my['re_share_rank']]} of {my['countries_compared']} on renewable share",
        f"{ORDINAL[my['intensity_rank']]} of {my['countries_compared']} on carbon intensity",
        f"{forecast['TH_EGAT']['improvement_pct']:.1f}% for Thailand",
        f"{forecast['SG_EMA']['improvement_pct']:.1f}% for Singapore",
    ]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # the phrases hold → and en dashes; the Windows console default is cp1252
    readme = (config.ROOT / "README.md").read_text(encoding="utf-8").replace("**", "")
    conn = db.connect()
    try:
        phrases = claims(conn.cursor())
    finally:
        conn.close()
    missing = [p for p in phrases if p not in readme]
    for p in phrases:
        print(("FAIL  " if p in missing else "ok    ") + p)
    print(f"\n{len(phrases) - len(missing)}/{len(phrases)} README claims match the warehouse")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
