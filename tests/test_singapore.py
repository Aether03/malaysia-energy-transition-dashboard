import math
import pathlib
import shutil
from datetime import date, timedelta
from itertools import pairwise

import numpy as np
import pandas as pd
import pytest

from pipeline.sources import singapore
from pipeline.sources._common import (
    InvalidDownloadError,
    SchemaMismatchError,
    assert_unique_keys,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "singapore"
F1226 = FIXTURES / "20221226.xls"  # week Mon 2022-12-26 .. Sun 2023-01-01
F0102 = FIXTURES / "20230102.xls"  # week Mon 2023-01-02 .. Sun 2023-01-08

SERIES = ("System Demand (Actual)", "NEM Demand (Actual)", "NEM Demand (Forecast)")
PERIODS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)][1:] + ["00:00"]  # 00:30 .. 23:30, 00:00

DAYS = 7
PERIODS_PER_DAY = 48
RECORDS_PER_FILE = DAYS * PERIODS_PER_DAY * len(SERIES)  # 1008

# Layout of the published sheet (0-based, read with header=None).
ROW_DATE, ROW_WEEKDAY, ROW_SERIES, ROW_FIRST_PERIOD = 1, 2, 4, 5
ROW_LAST_PERIOD = ROW_FIRST_PERIOD + PERIODS_PER_DAY - 1  # 52, the 00:00 (midnight at the END of the day) row
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# --- helpers -----------------------------------------------------------------------------


def _sheet(path):
    """The published sheet as the module sees it: header=None, every cell text, NA detection
    off, so blanks are '' and only Excel error cells are NaN (M3 Python review H4)."""
    return pd.read_excel(path, header=None, dtype=str, keep_default_na=False, na_filter=False)


def _col(day, series=0):
    """Column of `series` (0..2) for `day` (0 = Monday .. 6 = Sunday)."""
    return 1 + 3 * day + series


def _raw(df, row, day, series=0):
    """The raw published cell as a float."""
    return float(df.iloc[row, _col(day, series)])


def _records(path):
    return singapore.to_raw_records(path)


def _by_ts_series(records):
    """Index records by (ts_text, series) -> value. Assumes one file's records (unique keys)."""
    return {(r[2], r[3]): r[4] for r in records}


def _index(day, period, series):
    """Position of a record in the documented (day, period, series) order."""
    return (day * PERIODS_PER_DAY + period) * len(SERIES) + series


def _monday(path):
    return date.fromisoformat(f"{path.stem[:4]}-{path.stem[4:6]}-{path.stem[6:]}")


def _ts(path, day, period):
    return f"{(_monday(path) + timedelta(days=day)).isoformat()}|{PERIODS[period]}"


def _folder_with_both(tmp_path, reverse=False):
    folder = tmp_path / "sg"
    folder.mkdir()
    for src in (F0102, F1226) if reverse else (F1226, F0102):
        shutil.copy(src, folder / src.name)
    return folder


# --- module constants and calendar helpers -----------------------------------------------


def test_constants():
    assert singapore.GRID_CODE == "SG_EMA"
    assert singapore.SERIES == SERIES
    assert singapore.RAW_COLUMNS == ("grid_code", "file_name", "ts_text", "series", "value")
    assert singapore.KEY_COLUMNS == ("grid_code", "file_name", "ts_text", "series")
    assert singapore.FIRST_WEEK == date(2022, 12, 26)
    assert singapore.LAST_WEEK == date(2024, 12, 30)


def test_first_and_last_week_are_mondays():
    assert singapore.FIRST_WEEK.weekday() == 0
    assert singapore.LAST_WEEK.weekday() == 0


def test_week_starts_covers_the_published_range_with_106_mondays():
    weeks = singapore.week_starts(singapore.FIRST_WEEK, singapore.LAST_WEEK)
    assert isinstance(weeks, list)
    assert len(weeks) == 106
    assert weeks[0] == date(2022, 12, 26)
    assert weeks[-1] == date(2024, 12, 30)
    assert all(isinstance(w, date) for w in weeks)


def test_week_starts_are_all_mondays_seven_days_apart():
    weeks = singapore.week_starts(date(2022, 12, 26), date(2024, 12, 30))
    assert {w.weekday() for w in weeks} == {0}
    assert all(b - a == timedelta(days=7) for a, b in pairwise(weeks))


def test_week_starts_includes_both_ends_when_last_is_a_monday():
    assert singapore.week_starts(date(2023, 1, 2), date(2023, 1, 16)) == [
        date(2023, 1, 2),
        date(2023, 1, 9),
        date(2023, 1, 16),
    ]


def test_week_starts_single_week():
    assert singapore.week_starts(date(2023, 1, 2), date(2023, 1, 2)) == [date(2023, 1, 2)]


def test_week_starts_stops_at_the_last_monday_not_after_a_mid_week_last_day():
    # 2023-01-12 is a Thursday: Mondays 2 Jan and 9 Jan only (16 Jan is after `last`).
    assert singapore.week_starts(date(2023, 1, 2), date(2023, 1, 12)) == [date(2023, 1, 2), date(2023, 1, 9)]


@pytest.mark.parametrize("first", [date(2023, 1, 3), date(2023, 1, 1), date(2022, 12, 31)], ids=["Tue", "Sun", "Sat"])
def test_week_starts_raises_value_error_when_first_is_not_a_monday(first):
    with pytest.raises(ValueError):
        singapore.week_starts(first, date(2023, 3, 1))


def test_file_names_are_the_106_weekly_workbooks():
    names = singapore.file_names()
    assert isinstance(names, list)
    assert len(names) == 106
    assert len(set(names)) == 106
    assert names[0] == "20221226.xls"
    assert names[-1] == "20241230.xls"
    assert names[1] == "20230102.xls"


def test_file_names_follow_the_yyyymmdd_xls_pattern_in_week_order():
    names = singapore.file_names()
    weeks = singapore.week_starts(singapore.FIRST_WEEK, singapore.LAST_WEEK)
    assert names == [f"{w:%Y%m%d}.xls" for w in weeks]
    assert names == sorted(names)


# --- fixtures: the layout the tests rely on (guards against a changed fixture) -----------


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_fixture_layout_is_the_documented_one(path):
    df = _sheet(path)
    assert df.iloc[ROW_DATE, 0] == "Date"
    assert df.iloc[ROW_WEEKDAY, 0] == "Period Ending Time"
    assert [df.iloc[ROW_WEEKDAY, _col(d)] for d in range(DAYS)] == WEEKDAYS
    assert list(df.iloc[ROW_FIRST_PERIOD : ROW_LAST_PERIOD + 1, 0]) == PERIODS
    assert [c.strip() for c in df.iloc[ROW_SERIES, 1:22]] == list(SERIES) * DAYS
    assert pd.Timestamp(df.iloc[ROW_DATE, _col(0)]).date() == _monday(path)


# --- to_raw_records: shape, types, identity ----------------------------------------------


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_to_raw_records_count_is_7_days_x_48_periods_x_3_series(path):
    records = _records(path)
    assert isinstance(records, list)
    assert len(records) == RECORDS_PER_FILE == 1008
    assert all(isinstance(r, tuple) and len(r) == len(singapore.RAW_COLUMNS) for r in records)


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_to_raw_records_field_types(path):
    for grid_code, file_name, ts_text, series, value in _records(path):
        assert isinstance(grid_code, str)
        assert isinstance(file_name, str)
        assert isinstance(ts_text, str)
        assert isinstance(series, str)
        assert isinstance(value, float)  # the fixtures have no blank cells


def test_to_raw_records_tuple_order_follows_raw_columns():
    first = _records(F0102)[0]
    assert first == (
        "SG_EMA",
        "20230102.xls",
        "2023-01-02|00:30",
        "System Demand (Actual)",
        pytest.approx(5760.359344156905, abs=1e-9),
    )
    assert singapore.RAW_COLUMNS.index("value") == 4


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_grid_code_and_bare_file_name_on_every_record(path):
    records = _records(path)
    assert {r[0] for r in records} == {"SG_EMA"}
    assert {r[1] for r in records} == {path.name}
    assert all("/" not in r[1] and "\\" not in r[1] for r in records)


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_series_names_are_the_trimmed_published_names(path):
    # The published header cells carry a leading space (" System Demand (Actual)"); raw keeps the clean name.
    series = {r[3] for r in _records(path)}
    assert series == set(SERIES)
    assert all(s == s.strip() for s in series)


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_records_come_out_in_day_period_series_order(path):
    records = _records(path)
    expected = [
        (_ts(path, d, p), SERIES[s]) for d in range(DAYS) for p in range(PERIODS_PER_DAY) for s in range(len(SERIES))
    ]
    assert [(r[2], r[3]) for r in records] == expected


# --- ts_text: composite of the two published cells, not normalised -----------------------


def test_ts_text_first_record_is_monday_0030():
    assert _records(F0102)[0][2] == "2023-01-02|00:30"
    assert _records(F1226)[0][2] == "2022-12-26|00:30"


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_ts_text_is_iso_date_pipe_period_label_as_published(path):
    for record in _records(path):
        day_text, sep, label = record[2].partition("|")
        assert sep == "|"
        assert label in PERIODS
        assert date.fromisoformat(day_text)  # plain YYYY-MM-DD, no time part
        assert len(day_text) == 10
        assert "T" not in record[2]
        assert " " not in record[2]


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_ts_text_dates_are_seven_consecutive_days_from_the_file_monday(path):
    days = sorted({r[2].split("|")[0] for r in _records(path)})
    monday = _monday(path)
    assert days == [(monday + timedelta(days=i)).isoformat() for i in range(DAYS)]


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_last_record_of_each_day_is_the_0000_label_with_that_same_days_date(path):
    records = _records(path)
    monday = _monday(path)
    for d in range(DAYS):
        day_records = records[_index(d, 0, 0) : _index(d + 1, 0, 0)]
        assert len(day_records) == PERIODS_PER_DAY * len(SERIES)
        day_iso = (monday + timedelta(days=d)).isoformat()
        assert {r[2].split("|")[0] for r in day_records} == {day_iso}
        assert [r[2] for r in day_records[-3:]] == [f"{day_iso}|00:00"] * 3
        assert [r[3] for r in day_records[-3:]] == list(SERIES)


def test_ts_text_is_not_normalised_midnight_row_keeps_its_own_date():
    ts = {r[2] for r in _records(F0102)}
    assert "2023-01-02|00:00" in ts  # midnight at the END of Monday stays on Monday
    assert "2023-01-09|00:00" not in ts  # NOT rolled to the next day
    assert "2023-01-03|00:00" in ts
    assert "2023-01-02|24:00" not in ts
    assert "2023-01-02|23:30" in ts
    assert "2023-01-02|00:30" in ts


# --- the midnight trap -------------------------------------------------------------------


def test_midnight_trap_monday_0000_is_the_last_row_not_the_first():
    df = _sheet(F0102)
    values = _by_ts_series(_records(F0102))
    last_row = _raw(df, ROW_LAST_PERIOD, day=0)
    first_row = _raw(df, ROW_FIRST_PERIOD, day=0)

    assert df.iloc[ROW_LAST_PERIOD, 0] == "00:00"
    assert last_row == pytest.approx(5885.135573949379, abs=1e-9)
    assert first_row == pytest.approx(5760.359344156905, abs=1e-9)

    assert values[("2023-01-02|00:00", "System Demand (Actual)")] == pytest.approx(5885.135573949379, abs=1e-9)
    assert values[("2023-01-02|00:00", "System Demand (Actual)")] == pytest.approx(last_row, abs=1e-9)
    assert values[("2023-01-02|00:00", "System Demand (Actual)")] != pytest.approx(first_row, abs=1e-6)
    # ...and the 00:30 period is the first row.
    assert values[("2023-01-02|00:30", "System Demand (Actual)")] == pytest.approx(first_row, abs=1e-9)


def test_midnight_trap_applies_to_all_three_series_and_all_days():
    df = _sheet(F0102)
    values = _by_ts_series(_records(F0102))
    for d in range(DAYS):
        for s, name in enumerate(SERIES):
            expected = _raw(df, ROW_LAST_PERIOD, d, s)
            assert values[(_ts(F0102, d, PERIODS_PER_DAY - 1), name)] == pytest.approx(expected, abs=1e-9), (d, name)
            assert values[(_ts(F0102, d, 0), name)] == pytest.approx(_raw(df, ROW_FIRST_PERIOD, d, s), abs=1e-9), (
                d,
                name,
            )


def test_midnight_trap_monday_other_series_values():
    values = _by_ts_series(_records(F0102))
    assert values[("2023-01-02|00:00", "NEM Demand (Actual)")] == pytest.approx(5760.4)
    assert values[("2023-01-02|00:00", "NEM Demand (Forecast)")] == pytest.approx(5813.7)
    assert values[("2023-01-02|00:30", "NEM Demand (Actual)")] == pytest.approx(5632.6)
    assert values[("2023-01-02|00:30", "NEM Demand (Forecast)")] == pytest.approx(5662.4)


# --- full precision ----------------------------------------------------------------------


def test_system_demand_keeps_full_precision():
    values = _by_ts_series(_records(F1226))
    assert values[("2022-12-26|00:30", "System Demand (Actual)")] == pytest.approx(5602.11676031169, abs=1e-9)
    assert values[("2022-12-27|00:30", "System Demand (Actual)")] == pytest.approx(5643.947137036133, abs=1e-9)
    # Not rounded to 1 or 2 decimal places.
    assert values[("2022-12-26|00:30", "System Demand (Actual)")] != round(5602.11676031169, 2)
    assert values[("2022-12-26|00:30", "System Demand (Actual)")] != round(5602.11676031169, 1)


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_every_value_equals_its_raw_cell_to_1e_9(path):
    df = _sheet(path)
    records = _records(path)
    for d in range(DAYS):
        for p in range(PERIODS_PER_DAY):
            for s in range(len(SERIES)):
                record = records[_index(d, p, s)]
                expected = float(df.iloc[ROW_FIRST_PERIOD + p, _col(d, s)])
                assert record[4] == pytest.approx(expected, abs=1e-9), (record[2], record[3])


def test_system_demand_values_have_more_than_two_decimals():
    values = [r[4] for r in _records(F0102) if r[3] == "System Demand (Actual)"]
    long_decimals = [v for v in values if abs(v * 100 - round(v * 100)) > 1e-6]
    assert len(long_decimals) > len(values) * 0.9


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_no_nan_and_all_positive_in_fixtures(path):
    for record in _records(path):
        assert record[4] is not None
        assert not math.isnan(record[4])
        assert record[4] > 0


# --- week boundary: 20221226.xls holds 1 Jan 2023 ----------------------------------------


def test_20221226_ends_on_sunday_2023_01_01():
    records = _records(F1226)
    days = sorted({r[2].split("|")[0] for r in records})
    assert days[0] == "2022-12-26"
    assert days[-1] == "2023-01-01"
    assert days == [
        "2022-12-26", "2022-12-27", "2022-12-28", "2022-12-29", "2022-12-30", "2022-12-31", "2023-01-01",
    ]  # fmt: skip
    jan1 = [r for r in records if r[2].startswith("2023-01-01|")]
    assert len(jan1) == PERIODS_PER_DAY * len(SERIES)
    assert not any(r[2].startswith("2023-01-02|") for r in records)


def test_20221226_sunday_values_come_from_the_seventh_day_columns():
    df = _sheet(F1226)
    values = _by_ts_series(_records(F1226))
    assert values[("2023-01-01|00:30", "System Demand (Actual)")] == pytest.approx(5752.102642295732, abs=1e-9)
    assert values[("2023-01-01|00:00", "System Demand (Actual)")] == pytest.approx(5831.513656573605, abs=1e-9)
    assert values[("2023-01-01|00:00", "NEM Demand (Actual)")] == pytest.approx(5705.9)
    assert values[("2023-01-01|00:00", "NEM Demand (Forecast)")] == pytest.approx(5685.2)
    assert values[("2023-01-01|00:00", "System Demand (Actual)")] == pytest.approx(
        _raw(df, ROW_LAST_PERIOD, 6), abs=1e-9
    )


def test_the_two_weeks_do_not_overlap_in_ts_text():
    a = {r[2] for r in _records(F1226)}
    b = {r[2] for r in _records(F0102)}
    assert a.isdisjoint(b)
    assert len(a) == len(b) == DAYS * PERIODS_PER_DAY


# --- counts per series and per timestamp -------------------------------------------------


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_every_series_appears_7_x_48_times(path):
    counts = {}
    for record in _records(path):
        counts[record[3]] = counts.get(record[3], 0) + 1
    assert counts == {name: DAYS * PERIODS_PER_DAY for name in SERIES}
    assert DAYS * PERIODS_PER_DAY == 336


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_each_date_period_has_exactly_three_records_one_per_series(path):
    per_ts = {}
    for _grid, _file, ts_text, series, _value in _records(path):
        per_ts.setdefault(ts_text, []).append(series)
    assert len(per_ts) == DAYS * PERIODS_PER_DAY
    for ts_text, series_list in per_ts.items():
        assert series_list == list(SERIES), ts_text


# --- parse_sheet: blanks and equivalence with to_raw_records -----------------------------


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_parse_sheet_matches_to_raw_records(path):
    assert singapore.parse_sheet(_sheet(path), path.name) == _records(path)


def test_parse_sheet_uses_the_file_name_argument_for_the_file_name_column():
    df = _sheet(F0102)
    records = singapore.parse_sheet(df, "20230102.xls")
    assert {r[1] for r in records} == {"20230102.xls"}


def test_blank_cell_becomes_none_not_nan():
    df = _sheet(F0102)
    df.iloc[ROW_FIRST_PERIOD + 10, _col(2, 1)] = ""  # Wed 05:30 NEM Demand (Actual), blank
    records = singapore.parse_sheet(df, "20230102.xls")
    values = _by_ts_series(records)
    assert len(records) == RECORDS_PER_FILE
    assert values[("2023-01-04|05:30", "NEM Demand (Actual)")] is None
    assert values[("2023-01-04|05:30", "System Demand (Actual)")] is not None
    assert [v for v in (r[4] for r in records) if v is not None and math.isnan(v)] == []
    assert sum(1 for r in records if r[4] is None) == 1


def test_excel_error_cell_stops_the_run_instead_of_becoming_null():
    """With NA detection off, NaN can only be an Excel error cell (#N/A, #DIV/0!)."""
    df = _sheet(F0102)
    df.iloc[ROW_FIRST_PERIOD + 10, _col(2, 1)] = np.nan
    with pytest.raises(SchemaMismatchError, match="error cell"):
        singapore.parse_sheet(df, "20230102.xls")


@pytest.mark.parametrize("text", ["NA", "N/A", "null", "nan", "#N/A", "inf"])
def test_text_in_a_data_cell_stops_the_run(text):
    df = _sheet(F0102)
    df.iloc[ROW_FIRST_PERIOD, _col(0, 0)] = text
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_content_right_of_the_seven_days_stops_the_run():
    df = _sheet(F0102)
    df[df.shape[1]] = ""
    df.iloc[ROW_FIRST_PERIOD, df.shape[1] - 1] = "123.4"
    with pytest.raises(SchemaMismatchError, match="right of"):
        singapore.parse_sheet(df, "20230102.xls")


def test_fixture_files_carry_the_xls_signature():
    for path in (F1226, F0102):
        singapore.verify_signature(path)


def test_non_xls_body_is_rejected(tmp_path):
    page = tmp_path / "20230102.xls"
    page.write_text("<html>security check</html>", encoding="utf-8")
    with pytest.raises(InvalidDownloadError):
        singapore.verify_signature(page)


def test_zero_is_a_value_not_a_blank():
    df = _sheet(F0102)
    df.iloc[ROW_FIRST_PERIOD, _col(0, 2)] = "0"
    values = _by_ts_series(singapore.parse_sheet(df, "20230102.xls"))
    assert values[("2023-01-02|00:30", "NEM Demand (Forecast)")] == 0.0
    assert values[("2023-01-02|00:30", "NEM Demand (Forecast)")] is not None


# --- schema checks (modified copies of the header=None frame) ----------------------------


def test_schema_mismatch_error_is_the_shared_common_error():
    from pipeline.sources import _common

    assert SchemaMismatchError is _common.SchemaMismatchError


def test_parse_sheet_accepts_the_untouched_fixture():
    # Guards the schema tests below: each one changes exactly one thing in an otherwise valid frame.
    assert len(singapore.parse_sheet(_sheet(F0102), "20230102.xls")) == RECORDS_PER_FILE


def test_renamed_series_header_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_SERIES, _col(0, 1)] = " NEM Demand (Actuals)"
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_renamed_series_header_on_the_last_day_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_SERIES, _col(6, 2)] = " NEM Demand (Forecasts)"
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_series_header_in_the_wrong_order_raises_schema_mismatch():
    df = _sheet(F0102)
    a, b = _col(0, 1), _col(0, 2)
    df.iloc[ROW_SERIES, [a, b]] = df.iloc[ROW_SERIES, [b, a]].to_numpy()
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_blank_series_header_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_SERIES, _col(3, 0)] = np.nan
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_missing_period_row_raises_schema_mismatch():
    df = _sheet(F0102)
    df = df.drop(index=ROW_FIRST_PERIOD + 20).reset_index(drop=True)  # drop the 10:30 row; later rows shift up
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_missing_last_period_row_raises_schema_mismatch():
    df = _sheet(F0102)
    df = df.drop(index=ROW_LAST_PERIOD).reset_index(drop=True)  # no 00:00 row
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_period_labels_out_of_order_raise_schema_mismatch():
    df = _sheet(F0102)
    r1, r2 = ROW_FIRST_PERIOD + 4, ROW_FIRST_PERIOD + 5
    df.iloc[[r1, r2], 0] = df.iloc[[r2, r1], 0].to_numpy()
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_period_label_that_is_start_not_end_convention_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_LAST_PERIOD, 0] = "24:00"
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_period_labels_that_start_at_0000_raise_schema_mismatch():
    # A sheet that begins at 00:00 (period-start convention) must not be read as period-ending.
    df = _sheet(F0102)
    labels = ["00:00"] + PERIODS[:-1]
    df.iloc[ROW_FIRST_PERIOD : ROW_LAST_PERIOD + 1, 0] = labels
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_wrong_date_sequence_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_DATE, _col(3)] = "2023-01-06 00:00:00"  # Thu cell jumps to 6 Jan: 4 Jan, 6 Jan skips a day
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_repeated_date_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_DATE, _col(4)] = df.iloc[ROW_DATE, _col(3)]
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_dates_out_of_order_raise_schema_mismatch():
    df = _sheet(F0102)
    d1, d2 = _col(1), _col(2)
    df.iloc[ROW_DATE, [d1, d2]] = df.iloc[ROW_DATE, [d2, d1]].to_numpy()
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_blank_date_cell_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_DATE, _col(5)] = np.nan
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


@pytest.mark.parametrize(
    "file_name", ["20230109.xls", "20221226.xls", "20230103.xls"], ids=["next-Mon", "prev-Mon", "Tue"]
)
def test_file_name_monday_that_mismatches_the_sheet_dates_raises_schema_mismatch(file_name):
    # The sheet is the 2023-01-02 week; the name claims a different Monday (or not a Monday at all).
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(_sheet(F0102), file_name)


def test_sheet_dates_that_start_a_day_after_the_file_name_monday_raise_schema_mismatch():
    # Whole sheet shifted by one day (Tue..Mon) while the file name still says Monday 2023-01-02.
    df = _sheet(F0102)
    for d in range(DAYS):
        df.iloc[ROW_DATE, _col(d)] = f"2023-01-{3 + d:02d} 00:00:00"
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_missing_date_label_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_DATE, 0] = np.nan
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_wrong_date_label_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_DATE, 0] = "Day"
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_missing_period_ending_time_label_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_WEEKDAY, 0] = np.nan
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_wrong_period_ending_time_label_raises_schema_mismatch():
    df = _sheet(F0102)
    df.iloc[ROW_WEEKDAY, 0] = "Period Starting Time"
    with pytest.raises(SchemaMismatchError):
        singapore.parse_sheet(df, "20230102.xls")


def test_parse_sheet_does_not_mutate_its_input():
    df = _sheet(F0102)
    before = df.copy()
    singapore.parse_sheet(df, "20230102.xls")
    pd.testing.assert_frame_equal(df, before)


# --- records_from ------------------------------------------------------------------------


def test_records_from_reads_the_named_files_in_the_order_given(tmp_path):
    folder = _folder_with_both(tmp_path)
    records = singapore.records_from(folder, names=["20221226.xls", "20230102.xls"])

    assert isinstance(records, list)
    assert len(records) == 2 * RECORDS_PER_FILE == 2016
    names = [r[1] for r in records]
    assert names[:RECORDS_PER_FILE] == ["20221226.xls"] * RECORDS_PER_FILE
    assert names[RECORDS_PER_FILE:] == ["20230102.xls"] * RECORDS_PER_FILE


def test_records_from_equals_concatenated_per_file_records(tmp_path):
    folder = _folder_with_both(tmp_path)
    expected = _records(F1226) + _records(F0102)
    assert singapore.records_from(folder, names=["20221226.xls", "20230102.xls"]) == expected


def test_records_from_keeps_the_names_order_not_the_directory_or_calendar_order(tmp_path):
    folder = _folder_with_both(tmp_path, reverse=True)  # 20230102 copied first
    records = singapore.records_from(folder, names=["20230102.xls", "20221226.xls"])
    assert len(records) == 2016
    assert records[0][1] == "20230102.xls"
    assert records[-1][1] == "20221226.xls"
    assert records == _records(F0102) + _records(F1226)


def test_records_from_a_single_named_file(tmp_path):
    folder = _folder_with_both(tmp_path)
    assert singapore.records_from(folder, names=["20230102.xls"]) == _records(F0102)


def test_records_from_accepts_the_fixture_folder_directly():
    assert len(singapore.records_from(FIXTURES, names=["20221226.xls", "20230102.xls"])) == 2016


def test_records_from_missing_named_file_raises_file_not_found(tmp_path):
    folder = tmp_path / "sg"
    folder.mkdir()
    shutil.copy(F1226, folder / "20221226.xls")  # 20230102.xls absent
    with pytest.raises(FileNotFoundError):
        singapore.records_from(folder, names=["20221226.xls", "20230102.xls"])


def test_records_from_default_names_are_file_names_so_a_missing_first_file_raises(tmp_path):
    folder = tmp_path / "sg"
    folder.mkdir()
    shutil.copy(F0102, folder / "20230102.xls")  # the default list starts at 20221226.xls, which is absent
    with pytest.raises(FileNotFoundError):
        singapore.records_from(folder)


def test_records_from_propagates_schema_mismatch_for_a_file_name_that_disagrees_with_its_sheet(tmp_path):
    folder = tmp_path / "sg"
    folder.mkdir()
    shutil.copy(F0102, folder / "20230109.xls")  # the 2023-01-02 week saved under the wrong Monday
    with pytest.raises(SchemaMismatchError):
        singapore.records_from(folder, names=["20230109.xls"])


# --- key uniqueness ----------------------------------------------------------------------


def test_records_are_unique_on_the_first_four_columns_for_both_files(tmp_path):
    folder = _folder_with_both(tmp_path)
    records = singapore.records_from(folder, names=["20221226.xls", "20230102.xls"])
    assert len(records) == 2016
    assert assert_unique_keys(records, (0, 1, 2, 3)) is None
    assert len({r[:4] for r in records}) == len(records)


@pytest.mark.parametrize("path", [F1226, F0102], ids=["20221226", "20230102"])
def test_records_are_unique_on_the_key_columns_for_each_file_alone(path):
    assert assert_unique_keys(_records(path), range(len(singapore.KEY_COLUMNS))) is None


def test_a_deliberate_duplicate_is_caught_by_the_shared_helper():
    records = _records(F0102)
    with pytest.raises(ValueError):
        assert_unique_keys([*records, records[0]], (0, 1, 2, 3))
