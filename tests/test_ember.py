import math
import pathlib

import pytest

from pipeline.sources.ember import (
    EXPECTED_COLUMNS,
    SchemaMismatchError,
    filter_asean,
    read_csv,
    to_raw_records,
    validate_header,
)


def fixture_path():
    return pathlib.Path(__file__).parent / "fixtures" / "ember_sample.csv"


def test_validate_header_accepts_expected_columns():
    columns = list(EXPECTED_COLUMNS)
    validate_header(columns)


def test_validate_header_rejects_missing_column():
    columns = list(EXPECTED_COLUMNS)
    columns.remove("Capacity (GW)")
    with pytest.raises(SchemaMismatchError) as exc_info:
        validate_header(columns)
    assert "Capacity (GW)" in str(exc_info.value)


def test_validate_header_rejects_extra_column():
    columns = list(EXPECTED_COLUMNS) + ["Foo"]
    with pytest.raises(SchemaMismatchError) as exc_info:
        validate_header(columns)
    assert "Foo" in str(exc_info.value)


def test_filter_asean_keeps_six_rows():
    df = read_csv(fixture_path())
    filtered = filter_asean(df)
    assert len(filtered) == 6


def test_filter_asean_keeps_net_imports():
    df = read_csv(fixture_path())
    filtered = filter_asean(df)
    net_imports = filtered[filtered["Electricity source"] == "Net imports"]
    assert len(net_imports) == 1


def test_to_raw_records_returns_six_tuples_of_length_24():
    df = read_csv(fixture_path())
    filtered = filter_asean(df)
    records = to_raw_records(filtered)
    assert len(records) == 6
    for record in records:
        assert len(record) == 24


def test_to_raw_records_asean_row_values():
    df = read_csv(fixture_path())
    filtered = filter_asean(df)
    records = to_raw_records(filtered)

    asean_record = next(r for r in records if r[0] == "ASEAN")
    assert asean_record[1] is None
    assert asean_record[2] == 2024
    assert asean_record[5] is False


def test_to_raw_records_malaysia_coal_values():
    df = read_csv(fixture_path())
    filtered = filter_asean(df)
    records = to_raw_records(filtered)

    malaysia_coal = next(r for r in records if r[0] == "Malaysia" and r[4] == "Coal")
    assert malaysia_coal[11] == 13.5
    assert malaysia_coal[23] is True


def test_to_raw_records_no_nan_values():
    df = read_csv(fixture_path())
    filtered = filter_asean(df)
    records = to_raw_records(filtered)

    for record in records:
        for value in record:
            assert not (isinstance(value, float) and math.isnan(value))
