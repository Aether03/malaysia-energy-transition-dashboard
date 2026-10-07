"""The FINAL / replay / DEV machinery of `pipeline.forecast.run`, on fakes (MLE review H1, M1, M7).

No database: the SQL helpers are replaced, and the backtest runs a small real LightGBM on a
synthetic Jan-Apr 2024 series under a stand-in protocol (dev Feb 2024, final Mar-Apr 2024).
"""

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from pipeline.forecast import features, protocol, run

HASH_P = "a" * 40
HASH_H = "b" * 40
GRID = run.Grid(grid_key=1, grid_code="TH_EGAT", utc_offset_min=420, data_source_code="DTH", holiday_country="TH")
HOLIDAYS = {date(2024, 1, 1), date(2024, 2, 24), date(2024, 4, 6)}


def _raw():
    return {
        "features": list(features.FEATURE_COLUMNS),
        "data_start": "2024-01-08",
        "es_days": 7,
        "dev": {"first_month": "2024-02", "last_month": "2024-02"},
        "final": {"first_month": "2024-03", "last_month": "2024-04"},
        "lightgbm": {"objective": "l2", "learning_rate": 0.1, "num_leaves": 7, "min_data_in_leaf": 5,
                     "n_estimators": 30, "verbose": -1},
        "seed": 3,
        "num_threads": 1,
        "bootstrap": {"n_boot": 50, "level": 0.95, "block_days": 7},
    }  # fmt: skip


def _series():
    idx = pd.date_range("2024-01-01", "2024-04-30 23:00", freq="h")
    rng = np.random.default_rng(1)
    values = 20000 + 3000 * np.sin(2 * np.pi * idx.hour / 24) + 800 * idx.weekday + rng.normal(0, 150, len(idx))
    return pd.Series(values, index=idx)


class _FakeConn:
    def close(self):
        pass


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Fakes for every outside dependency; returns a dict the tests inspect and adjust."""
    state = {
        "demand": _series(),
        "untils": [],
        "saved": [],
        "db_final": None,
        "fail_save": False,
        "protocol": protocol.protocol_from_dict(_raw()),
        "changed": [],
    }

    def load_demand(conn, grid, until):
        state["untils"].append(until)
        return state["demand"].loc[:until]

    def save_run(conn, grid, row, results):
        if state["fail_save"]:
            raise RuntimeError("database down")
        state["saved"].append((row, results))
        return 100 + len(state["saved"])

    monkeypatch.setattr(run.db, "connect", lambda *a, **k: _FakeConn())
    monkeypatch.setattr(run, "load_grid", lambda conn, code: GRID)
    monkeypatch.setattr(run, "load_demand", load_demand)
    monkeypatch.setattr(run, "load_holidays", lambda conn, grid: set(HOLIDAYS))
    monkeypatch.setattr(run, "save_run", save_run)
    monkeypatch.setattr(run, "final_run_metrics", lambda conn, grid: state["db_final"])
    monkeypatch.setattr(run, "committed_protocol", lambda: (HASH_P, HASH_H))
    monkeypatch.setattr(run, "load_protocol", lambda: state["protocol"])
    monkeypatch.setattr(run, "protocol_at_commit", lambda commit: protocol.protocol_from_dict(_raw()))
    monkeypatch.setattr(run, "changed_since", lambda commit: list(state["changed"]))
    monkeypatch.setattr(run, "RECORD_PATH", tmp_path / "forecast_final.json")
    return state


def _stored_from(entry, model_run_id=101):
    return {"model_run_id": model_run_id, **entry["metrics"]}


# --- FINAL ---------------------------------------------------------------------------------


def test_run_final_records_then_stores_a_current_final_run(env):
    outcome = run.run_final("TH_EGAT", load_run_id=9)
    record = run.read_record()
    entry = record["TH_EGAT"]
    assert entry["protocol_commit"] == HASH_P
    assert entry["git_commit"] == HASH_H
    assert entry["protocol"] == _raw()
    assert entry["forecast_sha256"] == run.forecast_sha256(outcome.results)
    assert entry["fingerprint"] == run.input_fingerprint(env["demand"].loc[:"2024-04-30 23:00"], HOLIDAYS)
    assert set(entry["metrics"]) == set(run.COMPARED)

    ((row, results),) = env["saved"]
    assert row["run_kind"] == "FINAL"
    assert row["is_current"] == 1
    assert row["protocol_commit"] == HASH_P
    assert row["load_run_id"] == 9
    assert {c: str(row[c]) for c in run.COMPARED} == entry["metrics"]
    assert results.index.min() == pd.Timestamp("2024-03-01") and results.index.max() == pd.Timestamp("2024-04-30 23:00")
    assert env["untils"] == [pd.Timestamp("2024-04-30 23:00")]
    assert json.loads(row["metrics_json"])["fingerprint"] == entry["fingerprint"]


def test_run_final_writes_the_record_before_the_database_commit(env):
    env["fail_save"] = True
    with pytest.raises(RuntimeError):
        run.run_final("TH_EGAT", None)
    assert "TH_EGAT" in run.read_record()  # recoverable: the next replay stores the run


def test_a_second_final_is_refused_when_the_record_has_the_grid(env):
    run.write_record({"TH_EGAT": {"metrics": {}}})
    with pytest.raises(run.ForecastError, match="once only"):
        run.run_final("TH_EGAT", None)
    assert env["untils"] == []  # no demand was even read
    assert env["saved"] == []


def test_a_second_final_is_refused_when_the_database_has_one(env):
    env["db_final"] = {"model_run_id": 5}
    with pytest.raises(run.ForecastError, match="once only"):
        run.run_final("TH_EGAT", None)
    assert env["untils"] == []
    assert env["saved"] == []


def test_run_final_stops_at_the_gate(env, monkeypatch):
    def refuse():
        raise protocol.ProtocolError("uncommitted changes")

    monkeypatch.setattr(run, "committed_protocol", refuse)
    with pytest.raises(protocol.ProtocolError):
        run.run_final("TH_EGAT", None)
    assert env["untils"] == [] and not run.RECORD_PATH.exists()


def test_a_second_grid_runs_under_the_same_settings_and_code(env, monkeypatch):
    run.run_final("TH_EGAT", None)
    monkeypatch.setattr(run, "load_grid", lambda conn, code: run.Grid(3, "SG_EMA", 480, "DSG", "SG"))
    run.run_final("SG_EMA", None)
    assert set(run.read_record()) == {"TH_EGAT", "SG_EMA"}
    assert not run.RECORD_PATH.with_name(run.RECORD_PATH.name + ".tmp").exists()  # written atomically


def test_a_second_grid_with_edited_settings_is_refused(env):
    run.run_final("TH_EGAT", None)
    env["untils"].clear()
    raw = _raw()
    raw["lightgbm"]["num_leaves"] = 31  # tweaked after seeing the first grid's result
    env["protocol"] = protocol.protocol_from_dict(raw)
    with pytest.raises(run.ForecastError, match="settings differ"):
        run.run_final("SG_EMA", None)
    assert env["untils"] == []


def test_a_second_grid_after_a_code_change_is_refused(env):
    run.run_final("TH_EGAT", None)
    env["untils"].clear()
    env["changed"] = ["pipeline/forecast/features.py"]
    with pytest.raises(run.ForecastError, match="changed since"):
        run.run_final("SG_EMA", None)
    assert env["untils"] == []


# --- replay --------------------------------------------------------------------------------


def _recorded(env):
    run.run_final("TH_EGAT", None)
    env["saved"].clear()
    env["untils"].clear()
    return run.read_record()["TH_EGAT"]


def test_replay_is_identical_to_the_stored_final_run_and_stores_nothing(env):
    entry = _recorded(env)
    env["db_final"] = _stored_from(entry)
    message = run.replay("TH_EGAT", entry, None)
    assert message == "replay identical to FINAL run 101"
    assert env["saved"] == []


def test_replay_into_an_empty_database_stores_the_final_run(env):
    entry = _recorded(env)
    message = run.replay("TH_EGAT", entry, 12)
    assert "stored as FINAL run" in message
    ((row, _),) = env["saved"]
    assert row["run_kind"] == "FINAL" and row["is_current"] == 1
    assert row["protocol_commit"] == HASH_P and row["git_commit"] == HASH_H  # the record's commits
    assert {c: str(row[c]) for c in run.COMPARED} == entry["metrics"]


def test_a_replay_mismatch_fails_and_names_fields_but_never_the_new_values(env):
    entry = _recorded(env)
    real = entry["metrics"]["mape_model"]
    entry["metrics"]["mape_model"] = "99.999"
    with pytest.raises(run.ForecastError) as caught:
        run.replay("TH_EGAT", entry, None)
    assert "mape_model" in str(caught.value)
    assert real not in str(caught.value)
    assert env["saved"] == []


def test_a_replay_with_a_different_forecast_vector_fails(env):
    entry = _recorded(env)
    entry["forecast_sha256"] = "0" * 64
    with pytest.raises(run.ForecastError, match="forecast_sha256"):
        run.replay("TH_EGAT", entry, None)


def test_a_replay_on_changed_inputs_stops_before_backtesting(env, monkeypatch):
    entry = _recorded(env)
    env["demand"] = env["demand"].copy()
    env["demand"].iloc[100] += 1.0  # a re-extract changed one hour
    monkeypatch.setattr(run, "backtest_grid", lambda *a, **k: pytest.fail("backtest must not run"))
    with pytest.raises(run.ForecastError, match="demand_sha256"):
        run.replay("TH_EGAT", entry, None)


def test_a_replay_on_a_different_holiday_calendar_or_library_version_stops(env, monkeypatch):
    entry = _recorded(env)
    monkeypatch.setattr(run, "load_holidays", lambda conn, grid: HOLIDAYS | {date(2024, 3, 15)})
    with pytest.raises(run.ForecastError, match="holidays_sha256"):
        run.replay("TH_EGAT", entry, None)
    monkeypatch.setattr(run, "load_holidays", lambda conn, grid: set(HOLIDAYS))
    entry["fingerprint"]["versions"]["lightgbm"] = "0.0.1"
    with pytest.raises(run.ForecastError, match="versions"):
        run.replay("TH_EGAT", entry, None)


def test_a_replay_whose_settings_differ_from_the_committed_protocol_stops(env):
    entry = _recorded(env)
    entry["protocol"]["seed"] = 4
    with pytest.raises(run.ForecastError, match="committed"):
        run.replay("TH_EGAT", entry, None)


def test_a_stored_final_that_differs_from_the_record_fails(env):
    entry = _recorded(env)
    env["db_final"] = {**_stored_from(entry), "mape_model": "1.234"}
    with pytest.raises(run.ForecastError, match="differs from the record"):
        run.replay("TH_EGAT", entry, None)


# --- DEV -----------------------------------------------------------------------------------


def test_a_dev_run_may_not_reach_past_2023_whatever_the_protocol_says(env):
    # the stand-in protocol's dev month is Feb 2024
    with pytest.raises(run.ForecastError, match="DEV run may not go past"):
        run.run_dev("TH_EGAT", None)
    assert env["untils"] == []


def test_a_dev_run_inside_2023_reads_only_up_to_its_last_dev_hour(env):
    raw = _raw()
    raw.update(data_start="2023-01-08", dev={"first_month": "2023-02", "last_month": "2023-02"},
               final={"first_month": "2024-03", "last_month": "2024-04"})  # fmt: skip
    env["protocol"] = protocol.protocol_from_dict(raw)
    idx = pd.date_range("2023-01-01", "2023-03-31 23:00", freq="h")
    noise = np.random.default_rng(2).normal(0, 150, len(idx))  # an exact weekly cycle would make the baseline perfect
    env["demand"] = pd.Series(20000 + 3000 * np.sin(2 * np.pi * idx.hour / 24) + 500 * idx.weekday + noise, index=idx)
    run.run_dev("TH_EGAT", None)
    assert env["untils"] == [pd.Timestamp("2023-02-28 23:00")]
    ((row, _),) = env["saved"]
    assert row["run_kind"] == "DEV" and row["is_current"] == 0 and row["protocol_commit"] is None


# --- SQL helpers on a fake cursor -----------------------------------------------------------


def _ts(text):
    """A naive datetime, as the SQL driver returns DATETIME2."""
    return pd.Timestamp(text).to_pydatetime()


class _Cursor:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _Conn:
    def __init__(self, rows):
        self.cur = _Cursor(rows)

    def cursor(self):
        return self.cur


def test_load_demand_passes_the_cutoff_to_sql_and_rejects_a_later_row():
    until = pd.Timestamp("2023-12-31 23:00")
    ok = _Conn([(_ts("2023-12-31 22:00"), 100.0), (_ts("2023-12-31 23:00"), 101.0)])
    demand = run.load_demand(ok, GRID, until)
    assert list(demand) == [100.0, 101.0]
    sql, params = ok.cur.calls[0]
    assert "ts_local <= ?" in sql and params == (1, until.to_pydatetime())

    leaked = _Conn([(_ts("2023-12-31 23:00"), 101.0), (_ts("2024-01-01 00:00"), 102.0)])
    with pytest.raises(run.ForecastError, match="after"):
        run.load_demand(leaked, GRID, until)


@pytest.mark.parametrize(("iso3", "country"), [("THA", "TH"), ("SGP", "SG"), ("MYS", "MY")])
def test_each_grid_uses_its_own_countrys_holidays(iso3, country):
    grid = run.load_grid(_Conn([(3, 480, "DSG", iso3)]), "X")
    assert grid.holiday_country == country


def test_a_grid_in_a_country_without_a_calendar_is_refused():
    with pytest.raises(run.ForecastError, match="no holiday calendar"):
        run.load_grid(_Conn([(3, 480, "DSG", "VNM")]), "X")
