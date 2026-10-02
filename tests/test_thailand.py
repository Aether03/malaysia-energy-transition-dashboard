import csv
import math
import pathlib
import shutil

import pandas as pd
import pytest

from pipeline.sources import thailand
from pipeline.sources._common import SchemaMismatchError, assert_unique_keys

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "thailand"
F2023 = FIXTURES / "system_2023.csv"
F2024 = FIXTURES / "system_2024.csv"

HEADER_2023 = [
    "datetime", "north_generation", "north_demand", "south_generation", "south_demand",
    "metropolitan_generation", "metropolitan_demand", "central_generation", "central_demand",
    "northeast_generation", "northeast_demand", "malaysia_IMP", "malaysia_EXP", "EDL_IMP",
    "EDL_EXP", "hongsa_IMP", "cambodia_EXP",
]  # fmt: skip
HEADER_2024 = [
    "datetime", "north_generation", "north_demand", "south_generation", "south_demand",
    "metropolitan_generation", "metropolitan_demand", "central_generation", "central_demand",
    "northeast_generation", "northeast_demand", "hongsa_IMP", "malaysia_EXP", "malaysia_IMP",
    "laos_IMP", "laos_EXP", "cambodia_EXP",
]  # fmt: skip

# Fixture files: 6 data rows each, 16 series (every column except datetime).
ROWS_PER_FILE = 6
SERIES_PER_ROW = 16


# --- helpers -----------------------------------------------------------------------------


def _load_fixture(path):
    """Return (header, rows) of a fixture as plain lists of str (BOM stripped)."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def _write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def _by_ts_series(records):
    """Index records by (ts_text, series) -> value. Assumes one file's records (unique keys)."""
    return {(r[2], r[3]): r[4] for r in records}


def _records(path):
    return thailand.to_raw_records(thailand.read_file(path), path.name)


# --- module constants --------------------------------------------------------------------


def test_constants():
    assert thailand.GRID_CODE == "TH_EGAT"
    assert thailand.FILES == ("system_2023.csv", "system_2024.csv")
    assert thailand.RAW_COLUMNS == ("grid_code", "file_name", "ts_text", "series", "value")
    assert thailand.KEY_COLUMNS == ("grid_code", "file_name", "ts_text", "series")


def test_header_variants_are_the_two_published_column_sets():
    variants = thailand.HEADER_VARIANTS
    assert isinstance(variants, tuple)
    assert len(variants) == 2
    assert all(isinstance(v, frozenset) for v in variants)
    assert set(variants) == {frozenset(HEADER_2023), frozenset(HEADER_2024)}


# --- read_file: accepts the real fixtures ------------------------------------------------


@pytest.mark.parametrize(
    ("path", "header"),
    [(F2023, HEADER_2023), (F2024, HEADER_2024)],
    ids=["2023", "2024"],
)
def test_read_file_accepts_fixture_with_columns_as_published(path, header):
    df = thailand.read_file(path)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == header
    assert len(df) == ROWS_PER_FILE


@pytest.mark.parametrize("path", [F2023, F2024], ids=["2023", "2024"])
def test_read_file_strips_bom_from_first_column_name(path):
    assert path.read_bytes().startswith(b"\xef\xbb\xbf"), "fixture is expected to carry a UTF-8 BOM"
    df = thailand.read_file(path)
    assert df.columns[0] == "datetime"
    assert not any("﻿" in c for c in df.columns)


@pytest.mark.parametrize("path", [F2023, F2024], ids=["2023", "2024"])
def test_read_file_returns_all_strings_with_blanks_as_empty_string(path):
    df = thailand.read_file(path)
    for column in df.columns:
        assert all(isinstance(v, str) for v in df[column]), column
    # Blank cells stay "" (not NaN, not "nan", not None).
    assert "cambodia_EXP" in df.columns
    assert set(df["cambodia_EXP"]) == {""}


def test_read_file_keeps_datetime_text_exactly_as_published():
    df = thailand.read_file(F2023)
    assert list(df["datetime"]) == [
        "01/01/2023 0:05", "01/01/2023 1:00", "01/01/2023 2:00",
        "07/06/2023 0:00", "01/01/2024 22:00", "01/01/2024 23:00",
    ]  # fmt: skip
    df = thailand.read_file(F2024)
    assert list(df["datetime"]) == [
        "01/01/2024 0:05", "01/01/2024 0:00", "02/01/2024 0:00",
        "27/07/2024 5:00", "01/01/2025 22:00", "01/01/2025 23:00",
    ]  # fmt: skip


def test_read_file_accepts_a_path_object_or_string():
    assert len(thailand.read_file(str(F2023))) == ROWS_PER_FILE
    assert len(thailand.read_file(F2023)) == ROWS_PER_FILE


# --- read_file: schema checks ------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "column"),
    [(F2023, "malaysia_EXP"), (F2024, "laos_IMP"), (F2024, "datetime")],
    ids=["2023-malaysia_EXP", "2024-laos_IMP", "2024-datetime"],
)
def test_read_file_raises_schema_mismatch_for_missing_column(tmp_path, fixture, column):
    header, rows = _load_fixture(fixture)
    idx = header.index(column)
    new_header = [c for i, c in enumerate(header) if i != idx]
    new_rows = [[v for i, v in enumerate(r) if i != idx] for r in rows]
    bad = _write_csv(tmp_path / "missing.csv", new_header, new_rows)

    with pytest.raises(SchemaMismatchError):
        thailand.read_file(bad)


@pytest.mark.parametrize("fixture", [F2023, F2024], ids=["2023", "2024"])
def test_read_file_raises_schema_mismatch_for_extra_column(tmp_path, fixture):
    header, rows = _load_fixture(fixture)
    bad = _write_csv(tmp_path / "extra.csv", header + ["vietnam_IMP"], [r + ["1.0"] for r in rows])

    with pytest.raises(SchemaMismatchError):
        thailand.read_file(bad)


@pytest.mark.parametrize("fixture", [F2023, F2024], ids=["2023", "2024"])
def test_read_file_raises_schema_mismatch_for_renamed_column(tmp_path, fixture):
    header, rows = _load_fixture(fixture)
    new_header = ["malaysia_imp" if c == "malaysia_IMP" else c for c in header]
    assert new_header != header
    bad = _write_csv(tmp_path / "renamed.csv", new_header, rows)

    with pytest.raises(SchemaMismatchError):
        thailand.read_file(bad)


def test_read_file_raises_schema_mismatch_for_a_mix_of_both_variants(tmp_path):
    """2023 header with one 2024-only column swapped in is neither variant."""
    header, rows = _load_fixture(F2023)
    new_header = ["laos_IMP" if c == "EDL_IMP" else c for c in header]
    bad = _write_csv(tmp_path / "mixed.csv", new_header, rows)

    with pytest.raises(SchemaMismatchError):
        thailand.read_file(bad)


def test_schema_mismatch_error_is_the_shared_common_error():
    from pipeline.sources import _common

    assert SchemaMismatchError is _common.SchemaMismatchError


@pytest.mark.parametrize(
    ("fixture", "header"),
    [(F2023, HEADER_2023), (F2024, HEADER_2024)],
    ids=["2023", "2024"],
)
def test_read_file_accepts_valid_variant_in_different_column_order(tmp_path, fixture, header):
    """Order may differ (datetime kept first); the column SET is what is checked."""
    src_header, rows = _load_fixture(fixture)
    assert src_header == header
    order = [0] + list(reversed(range(1, len(header))))
    new_header = [header[i] for i in order]
    new_rows = [[r[i] for i in order] for r in rows]
    assert new_header != header
    shuffled = _write_csv(tmp_path / "shuffled.csv", new_header, new_rows)

    df = thailand.read_file(shuffled)

    assert set(df.columns) == set(header)
    assert len(df) == ROWS_PER_FILE
    # Values are carried by name: records from the shuffled copy equal records from the original.
    original = _by_ts_series(_records(fixture))
    reordered = _by_ts_series(thailand.to_raw_records(df, fixture.name))
    assert reordered == original


# --- to_raw_records: shape and counts ----------------------------------------------------


@pytest.mark.parametrize("path", [F2023, F2024], ids=["2023", "2024"])
def test_to_raw_records_count_is_rows_times_16_series(path):
    records = _records(path)
    assert isinstance(records, list)
    assert len(records) == ROWS_PER_FILE * SERIES_PER_ROW == 96
    assert all(isinstance(r, tuple) and len(r) == len(thailand.RAW_COLUMNS) for r in records)


@pytest.mark.parametrize(
    ("path", "header"),
    [(F2023, HEADER_2023), (F2024, HEADER_2024)],
    ids=["2023", "2024"],
)
def test_to_raw_records_has_every_series_for_every_timestamp(path, header):
    records = _records(path)
    expected_series = set(header) - {"datetime"}
    assert len(expected_series) == SERIES_PER_ROW

    per_ts = {}
    for _grid, _file, ts_text, series, _value in records:
        per_ts.setdefault(ts_text, []).append(series)
    assert len(per_ts) == ROWS_PER_FILE
    for ts_text, series_list in per_ts.items():
        assert len(series_list) == SERIES_PER_ROW, ts_text
        assert set(series_list) == expected_series, ts_text
    assert "datetime" not in {r[3] for r in records}


@pytest.mark.parametrize("path", [F2023, F2024], ids=["2023", "2024"])
def test_to_raw_records_field_types(path):
    for grid_code, file_name, ts_text, series, value in _records(path):
        assert isinstance(grid_code, str)
        assert isinstance(file_name, str)
        assert isinstance(ts_text, str)
        assert isinstance(series, str)
        assert value is None or isinstance(value, float)


def test_to_raw_records_tuple_order_follows_raw_columns():
    records = _records(F2023)
    first = next(r for r in records if r[2] == "01/01/2023 0:05" and r[3] == "north_generation")
    assert first == ("TH_EGAT", "system_2023.csv", "01/01/2023 0:05", "north_generation", pytest.approx(1991.4))
    assert thailand.RAW_COLUMNS.index("value") == 4


def test_to_raw_records_uses_the_file_name_argument_as_given():
    df = thailand.read_file(F2023)
    records = thailand.to_raw_records(df, "whatever.csv")
    assert {r[1] for r in records} == {"whatever.csv"}


# --- exact preservation ------------------------------------------------------------------


def test_ts_text_preserved_exactly_in_2023_file():
    ts = {r[2] for r in _records(F2023)}
    assert ts == {
        "01/01/2023 0:05", "01/01/2023 1:00", "01/01/2023 2:00",
        "07/06/2023 0:00", "01/01/2024 22:00", "01/01/2024 23:00",
    }  # fmt: skip
    # 2023 file starts at 0:05 and there is no 0:00 for that day; spill into 2024 is kept.
    assert "01/01/2023 0:00" not in ts
    assert "01/01/2024 22:00" in ts


def test_ts_text_preserved_exactly_in_2024_file():
    ts = {r[2] for r in _records(F2024)}
    assert ts == {
        "01/01/2024 0:05", "01/01/2024 0:00", "02/01/2024 0:00",
        "27/07/2024 5:00", "01/01/2025 22:00", "01/01/2025 23:00",
    }  # fmt: skip


def test_ts_text_not_normalised_or_deduplicated():
    ts_2024 = [r[2] for r in _records(F2024) if r[3] == "north_generation"]
    # Out of order as published, both 0:05 and 0:00 kept, no zero-padded hour.
    assert ts_2024[:2] == ["01/01/2024 0:05", "01/01/2024 0:00"]
    assert "27/07/2024 5:00" in ts_2024
    assert "27/07/2024 05:00" not in ts_2024
    assert not any(t.startswith("2024-") or "T" in t for t in ts_2024)
    # Rows come out in file order.
    assert ts_2024 == [
        "01/01/2024 0:05", "01/01/2024 0:00", "02/01/2024 0:00",
        "27/07/2024 5:00", "01/01/2025 22:00", "01/01/2025 23:00",
    ]  # fmt: skip


# --- series naming as published ----------------------------------------------------------


def test_2023_records_use_edl_names_not_laos():
    series = {r[3] for r in _records(F2023)}
    assert "EDL_IMP" in series
    assert "EDL_EXP" in series
    assert "laos_IMP" not in series
    assert "laos_EXP" not in series
    assert "hongsa_IMP" in series
    assert "cambodia_EXP" in series


def test_2024_records_use_laos_names_not_edl():
    series = {r[3] for r in _records(F2024)}
    assert "laos_IMP" in series
    assert "laos_EXP" in series
    assert "EDL_IMP" not in series
    assert "EDL_EXP" not in series
    assert "hongsa_IMP" in series
    assert "cambodia_EXP" in series


# --- values by name, not position --------------------------------------------------------


def test_2024_values_by_name_row_0000():
    values = _by_ts_series(_records(F2024))
    assert values[("01/01/2024 0:00", "hongsa_IMP")] == pytest.approx(1007.8)
    assert values[("01/01/2024 0:00", "malaysia_EXP")] == pytest.approx(29.2)
    assert values[("01/01/2024 0:00", "malaysia_IMP")] is None
    assert values[("01/01/2024 0:00", "laos_IMP")] == pytest.approx(0.7)
    assert values[("01/01/2024 0:00", "laos_EXP")] == pytest.approx(235.3)


def test_2024_row_0005_is_distinct_from_row_0000():
    values = _by_ts_series(_records(F2024))
    assert values[("01/01/2024 0:05", "hongsa_IMP")] == pytest.approx(1000.0)
    assert values[("01/01/2024 0:05", "north_generation")] == pytest.approx(3257.6)
    assert values[("01/01/2024 0:00", "north_generation")] == pytest.approx(3275.6)


def test_2023_values_by_name_spillover_row_2024_2200():
    values = _by_ts_series(_records(F2023))
    assert values[("01/01/2024 22:00", "hongsa_IMP")] == pytest.approx(1003.8)
    assert values[("01/01/2024 22:00", "EDL_EXP")] == pytest.approx(317.9)
    assert values[("01/01/2024 22:00", "EDL_IMP")] == pytest.approx(5.7)
    assert values[("01/01/2024 22:00", "malaysia_EXP")] == pytest.approx(29.2)
    assert values[("01/01/2024 22:00", "malaysia_IMP")] is None


def test_zero_is_a_value_not_a_blank():
    values = _by_ts_series(_records(F2023))
    assert values[("01/01/2023 0:05", "EDL_IMP")] == 0.0
    assert values[("01/01/2023 0:05", "EDL_IMP")] is not None


# --- blanks -> None ----------------------------------------------------------------------


def test_blank_cambodia_exp_is_none_in_2023():
    values = _by_ts_series(_records(F2023))
    assert values[("01/01/2023 0:05", "cambodia_EXP")] is None


def test_blank_cells_are_none_not_nan_or_empty_string():
    for path in (F2023, F2024):
        for record in _records(path):
            value = record[4]
            assert value != ""
            if value is not None:
                assert not math.isnan(value), f"NaN leaked into {record}"


def test_exactly_one_of_malaysia_imp_exp_is_blank_per_row():
    for path in (F2023, F2024):
        values = _by_ts_series(_records(path))
        for ts_text in {ts for ts, _series in values}:
            blanks = [values[(ts_text, s)] is None for s in ("malaysia_IMP", "malaysia_EXP")]
            assert sum(blanks) == 1, (path.name, ts_text)


# --- identity columns --------------------------------------------------------------------


@pytest.mark.parametrize("path", [F2023, F2024], ids=["2023", "2024"])
def test_grid_code_and_bare_file_name_on_every_record(path):
    records = thailand.records_from(FIXTURES)
    own = [r for r in records if r[1] == path.name]
    assert len(own) == ROWS_PER_FILE * SERIES_PER_ROW
    assert {r[0] for r in records} == {"TH_EGAT"}
    assert {r[1] for r in records} == {"system_2023.csv", "system_2024.csv"}
    assert all("/" not in r[1] and "\\" not in r[1] for r in records)


# --- records_from ------------------------------------------------------------------------


def _folder_with_both(tmp_path):
    folder = tmp_path / "th"
    folder.mkdir()
    shutil.copy(F2023, folder / "system_2023.csv")
    shutil.copy(F2024, folder / "system_2024.csv")
    return folder


def test_records_from_reads_both_files_2023_first(tmp_path):
    folder = _folder_with_both(tmp_path)
    records = thailand.records_from(folder)

    assert isinstance(records, list)
    assert len(records) == 2 * ROWS_PER_FILE * SERIES_PER_ROW == 192
    names = [r[1] for r in records]
    assert names[:96] == ["system_2023.csv"] * 96
    assert names[96:] == ["system_2024.csv"] * 96


def test_records_from_equals_concatenated_per_file_records(tmp_path):
    folder = _folder_with_both(tmp_path)
    expected = _records(F2023) + _records(F2024)
    assert thailand.records_from(folder) == expected


def test_records_from_follows_files_order_regardless_of_directory_listing(tmp_path):
    folder = tmp_path / "th"
    folder.mkdir()
    # Create 2024 first so any naive listing order would differ.
    shutil.copy(F2024, folder / "system_2024.csv")
    shutil.copy(F2023, folder / "system_2023.csv")
    records = thailand.records_from(folder)
    assert records[0][1] == "system_2023.csv"
    assert records[-1][1] == "system_2024.csv"


def test_records_from_accepts_the_fixture_folder_directly():
    assert len(thailand.records_from(FIXTURES)) == 192


def test_records_from_missing_file_raises(tmp_path):
    folder = tmp_path / "th"
    folder.mkdir()
    shutil.copy(F2023, folder / "system_2023.csv")  # system_2024.csv absent
    with pytest.raises(FileNotFoundError):
        thailand.records_from(folder)


def test_records_from_propagates_schema_mismatch(tmp_path):
    folder = _folder_with_both(tmp_path)
    header, rows = _load_fixture(F2024)
    bad_header = ["malaysia_imp" if c == "malaysia_IMP" else c for c in header]
    _write_csv(folder / "system_2024.csv", bad_header, rows)

    with pytest.raises(SchemaMismatchError):
        thailand.records_from(folder)


# --- key uniqueness ----------------------------------------------------------------------


def test_assert_unique_keys_passes_for_both_files_together(tmp_path):
    folder = _folder_with_both(tmp_path)
    records = thailand.records_from(folder)
    assert assert_unique_keys(records, (0, 1, 2, 3)) is None


@pytest.mark.parametrize("path", [F2023, F2024], ids=["2023", "2024"])
def test_assert_unique_keys_passes_for_each_file_alone(path):
    assert assert_unique_keys(_records(path), (0, 1, 2, 3)) is None


def test_full_key_is_unique_and_a_duplicate_is_caught():
    """Every (grid_code, file_name, ts_text, series) is distinct; a repeated record is rejected."""
    records = thailand.records_from(FIXTURES)
    assert len({r[:4] for r in records}) == len(records)
    # And a deliberate duplicate is caught by the shared helper.
    with pytest.raises(ValueError):
        assert_unique_keys(records + [records[0]], (0, 1, 2, 3))


# --- checksum pin (added by the implementer) ---------------------------------------------


def test_verify_checksum_rejects_a_revised_file(tmp_path):
    revised = tmp_path / "system_2023.csv"
    shutil.copy(F2023, revised)  # an excerpt, so its md5 can't match the published file
    with pytest.raises(SchemaMismatchError, match="revised"):
        thailand.verify_checksum(revised)
