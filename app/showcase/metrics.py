"""Pandas ports of the report's numbers, computed from the exported views (M6 plan Q4).

Contract: each function reproduces one `sql/showcase` query from the snapshot frames (`data.frames()`, keyed by
view name) and returns rows with the query's column names, row set and rounding. `tests/test_app_metrics.py`
compares the result with `exports/expected.json[<query>]`: text, dates and integers exactly, other numbers within
the twin tolerance max(0.05, 0.1%) (`tools/dax_twin_check.py`). The SQL file is the specification; where its
comments describe a choice (a year window, a blank reason, a rounding), the port makes the same one.

The pages build their charts from these results or from the same frames, so a number on the web page is the
number the SQL twin, and therefore the Power BI measure, gives.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pandas as pd

Frames = Mapping[str, pd.DataFrame]


def trends(f: Frames) -> list[dict]:
    """sql/showcase/01_trends.sql: Malaysia's generation by source (TWh) and share of the mix, every year."""
    raise NotImplementedError


def yoy_lag(f: Frames) -> list[dict]:
    """sql/showcase/02_yoy_lag.sql: year-on-year change of each headline KPI, with its polarity (P1 deltas)."""
    raise NotImplementedError


def ranking(f: Frames) -> list[dict]:
    """sql/showcase/03_ranking.sql: Malaysia's rank among its ASEAN peers on RE share, intensity, per-capita demand."""
    raise NotImplementedError


def rolling_avg(f: Frames) -> list[dict]:
    """sql/showcase/04_rolling_avg.sql: each country's RE share and its 3-year rolling average."""
    raise NotImplementedError


def capacity_factor(f: Frames) -> list[dict]:
    """sql/showcase/05_capacity_factor.sql: capacity factor by country, year and source, with blank reasons."""
    raise NotImplementedError


def re_growth_decomposition(f: Frames) -> list[dict]:
    """sql/showcase/06_re_growth_decomposition.sql: which renewable sources drove Malaysia's rising RE share."""
    raise NotImplementedError


def emissions_vs_demand(f: Frames) -> list[dict]:
    """sql/showcase/07_emissions_vs_demand.sql: demand, generation, intensity and emissions, base vs latest year."""
    raise NotImplementedError


def grid_load(f: Frames) -> list[dict]:
    """sql/showcase/08_grid_load.sql: peak hourly demand, when, mean and load factor per grid, year and month."""
    raise NotImplementedError


def forecast_metrics(f: Frames) -> list[dict]:
    """sql/showcase/09_forecast_metrics.sql: MAPE and MAE of the model and the seasonal-naive baseline per grid."""
    raise NotImplementedError


def load_curves(f: Frames) -> list[dict]:
    """sql/showcase/10_load_curves.sql: mean demand by local hour, per grid, season and day type."""
    raise NotImplementedError


def interconnector_flows(f: Frames) -> list[dict]:
    """sql/showcase/11_interconnector_flows.sql: Thailand-Malaysia border flows by direction, per year."""
    raise NotImplementedError


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
