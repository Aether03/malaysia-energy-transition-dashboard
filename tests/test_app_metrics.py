"""The web showcase's numbers equal the SQL twins (M6 plan Q4): each port in app/showcase/metrics.py reproduces
its sql/showcase query from the exported views; exports/expected.json holds the SQL results at export time."""

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from showcase import data, metrics

EXPECTED = data.expected() if (data.EXPORTS / "expected.json").exists() else {}


def test_every_exported_showcase_result_has_a_port():
    assert set(EXPECTED) <= set(metrics.SHOWCASE)


def assert_rows_match(got: list[dict], want: list[dict]) -> None:
    """Same columns and rows; text, dates and integers exact, other numbers equal up to float noise (1e-9)."""
    g, w = pd.DataFrame(got), pd.DataFrame(want)
    assert list(g.columns) == list(w.columns)
    assert len(g) == len(w)
    keys = [c for c in w.columns if not pd.api.types.is_float_dtype(w[c])]
    g = g.sort_values(keys, na_position="first").reset_index(drop=True)
    w = w.sort_values(keys, na_position="first").reset_index(drop=True)
    for col in w.columns:
        for i, (a, b) in enumerate(zip(g[col], w[col], strict=True)):
            if isinstance(b, float) and not math.isnan(b):
                assert a is not None and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), f"{col} row {i}: {a} vs {b}"
            else:
                assert (pd.isna(a) and pd.isna(b)) or a == b, f"{col} row {i}: {a!r} vs {b!r}"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_port_matches_its_sql_twin(name):
    want = EXPECTED[name]
    if name == "09_forecast_metrics":
        # The month rows' *_diff compare with the per-month MAPEs in dw.forecast_run.metrics_json, a self-check the
        # export does not carry and the report never shows (Amirul, 2026-10-11): the port leaves them None.
        diffs = dict.fromkeys(("mape_model_diff", "mape_baseline_diff"))
        want = [{**r, **diffs} if r["month"] is not None else r for r in want]
    assert_rows_match(metrics.SHOWCASE[name](data.frames()), want)


def test_the_comparison_catches_a_wrong_number():
    # The ports reproduce the SQL rounding exactly, so the comparison allows float noise only (M6 review M3): a
    # number one rounding step off fails, which max(0.05, 0.1%) would have let through.
    want = [{"grid_code": "TH_EGAT", "mape": 4.56}]
    assert_rows_match([{"grid_code": "TH_EGAT", "mape": 4.56 + 1e-12}], want)
    for wrong in (4.57, 4.6):
        with pytest.raises(AssertionError):
            assert_rows_match([{"grid_code": "TH_EGAT", "mape": wrong}], want)


# --- edge cases the real data does not exercise, on small synthetic frames ---

NAN = float("nan")


def by_key(rows: list[dict], key: str) -> dict:
    return {r[key]: r for r in rows}


def test_decimal_cast_rounds_half_away_from_zero():
    f = {
        "dim_grid": pd.DataFrame({"grid_key": [1], "grid_code": ["TH_EGAT"]}),
        "grid_flow_daily": pd.DataFrame(
            {
                "grid_key": 1,
                "counterparty": ["MY", "MY", "KH"],
                "year": [2023, 2024, 2023],
                "hours_present": 24,
                "export_mwh": [250.0, 0.0, 9999.0],  # 0.25 GWh: numpy rounds it to 0.2, SQL Server to 0.3
                "import_mwh": [0.0, 250.0, 9999.0],
                "net_flow_mw": [10.4, -10.4, 0.0],
            }
        ),
    }
    got = by_key(metrics.interconnector_flows(f), "year")
    assert [got[2023][k] for k in ("export_gwh", "import_gwh", "net_export_gwh")] == [0.3, 0.0, 0.3]
    assert [got[2024][k] for k in ("export_gwh", "import_gwh", "net_export_gwh")] == [0.0, 0.3, -0.3]
    assert set(got) == {2023, 2024}  # the Cambodia row is another counterparty


def test_yoy_change_is_none_without_a_previous_value_and_neutral_when_it_rounds_to_zero():
    ca = pd.DataFrame({"country_key": 1, "year": [2020, 2021, 2022, 2023]})
    for col in ("demand_twh", "fossil_share_gen_pct", "demand_per_capita_mwh"):
        ca[col] = NAN
    ca["total_generation_twh"] = [0.0, 10.0, 10.00000001, 11.0]  # previous 0 -> NULLIF -> NULL; then a 1e-7 % change
    ca["re_share_gen_pct"] = [10.0, 12.0, 11.0, 11.0]
    ca["emissions_intensity_gco2e_kwh"] = [500.0, 400.0, 400.0, 400.0]
    codes = ["TOTAL_GENERATION", "DEMAND_GROWTH", "RE_SHARE_GEN", "FOSSIL_SHARE_GEN", "CARBON_INTENSITY"]
    f = {
        "country_annual": ca,
        "dim_country": pd.DataFrame({"country_key": [1], "is_focus": [True]}),
        "kpi": pd.DataFrame({"kpi_code": [*codes, "DEMAND_PER_CAPITA"], "polarity": [1, 1, 1, -1, -1, 1]}),
    }
    got = metrics.yoy_lag(f)

    def by(code: str) -> list[tuple]:
        return [(r["year"], r["change"], r["direction"]) for r in got if r["kpi_code"] == code]

    assert by("TOTAL_GENERATION") == [
        (2020, None, "NEUTRAL"),  # no previous year
        (2021, None, "NEUTRAL"),  # previous value 0: a divide by zero is NULL, not infinity
        (2022, 0.0, "NEUTRAL"),  # rounds to 0.000 first
        (2023, 10.0, "GOOD"),
    ]
    assert by("RE_SHARE_GEN") == [
        (2020, None, "NEUTRAL"),
        (2021, 2.0, "GOOD"),
        (2022, -1.0, "BAD"),
        (2023, 0.0, "NEUTRAL"),
    ]
    assert by("CARBON_INTENSITY")[1] == (2021, -20.0, "GOOD")  # polarity -1: down is good


def test_capacity_factor_blank_reasons_and_leap_hours():
    cases = [  # (generation TWh, capacity GW, year)
        (NAN, 1.0, 2023),
        (1.0, NAN, 2023),
        (1.0, 0.0, 2023),
        (0.0, 0.0, 2023),
        (10.0, 1.0, 2023),  # 10 TWh from 1 GW over 8,760 h would be 114%
        (4.38, 1.0, 2023),
        (4.392, 1.0, 2024),  # 2024 is a leap year: 8,784 h
    ]
    keys = list(range(len(cases)))
    f = {
        "generation_annual": pd.DataFrame(
            {
                "country_key": 1,
                "source_key": keys,
                "year": [c[2] for c in cases],
                "generation_twh": [c[0] for c in cases],
                "capacity_gw": [c[1] for c in cases],
            }
        ),
        "dim_source": pd.DataFrame({"source_key": keys, "display_name": list("abcdefg"), "sort_order": keys}),
        "dim_country": pd.DataFrame(
            {"country_key": [1], "name": ["Malaysia"], "area_type": ["COUNTRY"], "display_order": [1]}
        ),
        "dim_year": pd.DataFrame({"year": [2023, 2024], "hours_in_year": [8760, 8784]}),
    }
    got = metrics.capacity_factor(f)
    assert [(r["capacity_factor_pct"], r["blank_reason"]) for r in got] == [
        (None, "GENERATION_NOT_REPORTED"),
        (None, "CAPACITY_NOT_REPORTED"),
        (None, "CAPACITY_NOT_REPORTED"),  # generation from zero reported capacity: the capacity is missing
        (None, "NO_CAPACITY"),
        (None, "CF_ABOVE_100"),
        (50.0, None),
        (50.0, None),
    ]


def test_ranking_ties_share_a_rank_and_a_peer_without_per_capita_keeps_its_row():
    peers = ["A", "B", "C", "D"]
    f = {
        "dim_country": pd.DataFrame({"country_key": [1, 2, 3, 4], "name": peers, "is_default_peer": True}),
        "dim_year": pd.DataFrame({"year": [2023, 2025]}),
        "country_annual": pd.DataFrame(
            {
                "country_key": [1, 2, 3, 4, 1, 2, 3],
                "year": [2025, 2025, 2025, 2025, 2023, 2023, 2023],
                "re_share_gen_pct": [30.0, 30.0, 10.0, 5.0, 1.0, 1.0, 1.0],
                "emissions_intensity_gco2e_kwh": [400.0, 500.0, 600.0, 700.0, 1.0, 1.0, 1.0],
                # C has no per-capita value for 2025 and D never does, so the common year is 2023
                "demand_per_capita_mwh": [8.0, 9.0, NAN, NAN, 7.0, 8.0, 6.0],
            }
        ),
    }
    got = by_key(metrics.ranking(f), "name")
    assert [got[n]["re_share_rank"] for n in peers] == [1, 1, 3, 4]  # tie: 1, 1, then 3
    assert [got[n]["per_capita_rank"] for n in peers] == [2, 1, 3, None]
    assert got["D"]["per_capita_year"] is None and got["A"]["per_capita_year"] == 2023
    assert {r["countries_compared"] for r in got.values()} == {4}


def test_rolling_average_needs_three_values_and_restarts_per_country():
    shares = {1: [10.0, 20.0, NAN, 40.0, 50.0, 60.0], 2: [3.0, 6.0, 9.0], 3: [99.0] * 3}
    ca = pd.concat(
        [
            pd.DataFrame({"country_key": k, "year": range(2020, 2020 + len(v)), "re_share_gen_pct": v})
            for k, v in shares.items()
        ]
    )
    f = {
        "country_annual": ca,
        "dim_country": pd.DataFrame(
            {
                "country_key": [1, 2, 3],
                "name": ["A", "B", "ASEAN"],
                "area_type": ["COUNTRY", "COUNTRY", "REGION"],
                "display_order": [1, 2, 3],
            }
        ),
    }
    got = metrics.rolling_avg(f)
    assert [r["re_share_3yr_avg_pct"] for r in got if r["name"] == "A"] == [None, None, None, None, None, 50.0]
    avg_b = [r["re_share_3yr_avg_pct"] for r in got if r["name"] == "B"]
    assert avg_b == [None, None, 6.0]  # B does not borrow A's years
    assert {r["name"] for r in got} == {"A", "B"}  # the region row is not a country


def test_grid_load_peak_tie_takes_the_earliest_hour_and_the_year_row_has_no_month():
    h = pd.DataFrame(
        {
            "grid_key": 1,
            "ts_local": ["2023-01-05T10:00:00", "2023-01-02T09:00:00", "2023-02-01T00:00:00", "2022-12-31T23:00:00"],
            "year": [2023, 2023, 2023, 2022],
            "month": [1, 1, 2, 12],
            "demand_mw": [100.0, 100.0, 50.0, 999.0],  # the 2022 hour is outside the complete years
        }
    )
    f = {"grid_hourly": h, "dim_grid": pd.DataFrame({"grid_key": [1], "grid_code": ["X"], "display_order": [1]})}
    got = metrics.grid_load(f)
    assert [(r["month"], r["hours"], r["peak_at"], r["mean_mw"], r["load_factor_pct"]) for r in got] == [
        (None, 3, "2023-01-02T09:00:00", 83.3, 83.33),
        (1, 2, "2023-01-02T09:00:00", 100.0, 100.0),
        (2, 1, "2023-02-01T00:00:00", 50.0, 100.0),
    ]
