import datetime
import pathlib

import pandas as pd
import pytest

from pipeline.sources._common import SchemaMismatchError, assert_unique_keys


def fixture_supply_path():
    return pathlib.Path(__file__).parent / "fixtures" / "dosm_supply_sample.csv"


def fixture_consumption_path():
    return pathlib.Path(__file__).parent / "fixtures" / "dosm_consumption_sample.csv"


class TestReadCSV:
    """Test read_csv function for both supply and consumption files."""

    def test_read_csv_supply_returns_dataframe_with_3_columns(self):
        """read_csv returns a DataFrame with exactly 3 columns: date, sector, supply."""
        from pipeline.sources.dosm import read_csv

        df = read_csv(fixture_supply_path(), "supply")
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) == 3
        assert list(df.columns) == ["date", "sector", "supply"]

    def test_read_csv_consumption_returns_dataframe_with_3_columns(self):
        """read_csv returns a DataFrame with exactly 3 columns: date, sector, consumption."""
        from pipeline.sources.dosm import read_csv

        df = read_csv(fixture_consumption_path(), "consumption")
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) == 3
        assert list(df.columns) == ["date", "sector", "consumption"]

    def test_read_csv_supply_returns_12_rows(self):
        """read_csv on the supply fixture returns exactly 12 rows (6 sectors x 2 dates)."""
        from pipeline.sources.dosm import read_csv

        df = read_csv(fixture_supply_path(), "supply")
        assert len(df) == 12

    def test_read_csv_consumption_returns_12_rows(self):
        """read_csv on the consumption fixture returns exactly 12 rows (6 sectors x 2 dates)."""
        from pipeline.sources.dosm import read_csv

        df = read_csv(fixture_consumption_path(), "consumption")
        assert len(df) == 12

    def test_read_csv_raises_schema_mismatch_when_measure_column_wrong(self, tmp_path):
        """read_csv raises SchemaMismatchError when the third column name doesn't match measure."""
        from pipeline.sources.dosm import read_csv

        # Create a temporary CSV with wrong measure column name
        fixture = pd.read_csv(fixture_supply_path(), dtype=str, keep_default_na=False)
        fixture = fixture.rename(columns={"supply": "wrong_column"})

        temp_csv = tmp_path / "bad_header.csv"
        fixture.to_csv(temp_csv, index=False)

        with pytest.raises(SchemaMismatchError) as exc_info:
            read_csv(temp_csv, "supply")
        assert "supply" in str(exc_info.value).lower() or "header" in str(exc_info.value).lower()

    def test_read_csv_raises_schema_mismatch_when_extra_column(self, tmp_path):
        """read_csv raises SchemaMismatchError when there's an extra column."""
        from pipeline.sources.dosm import read_csv

        # Create a temporary CSV with extra column
        fixture = pd.read_csv(fixture_supply_path(), dtype=str, keep_default_na=False)
        fixture["extra_col"] = "value"

        temp_csv = tmp_path / "extra_col.csv"
        fixture.to_csv(temp_csv, index=False)

        with pytest.raises(SchemaMismatchError) as exc_info:
            read_csv(temp_csv, "supply")
        assert "header" in str(exc_info.value).lower() or "column" in str(exc_info.value).lower()

    def test_read_csv_raises_value_error_when_measure_invalid(self):
        """read_csv raises ValueError when measure is not 'supply' or 'consumption'."""
        from pipeline.sources.dosm import read_csv

        with pytest.raises(ValueError) as exc_info:
            read_csv(fixture_supply_path(), "invalid_measure")
        assert "supply" in str(exc_info.value).lower() or "consumption" in str(exc_info.value).lower()


class TestToRawRecords:
    """Test to_raw_records function for converting DataFrames to tuples."""

    def test_to_raw_records_supply_returns_list_of_tuples(self):
        """to_raw_records returns a list of tuples for supply data."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_supply_path(), "supply")
        records = to_raw_records(df, "supply")
        assert isinstance(records, list)
        assert all(isinstance(r, tuple) for r in records)

    def test_to_raw_records_supply_returns_12_tuples(self):
        """to_raw_records on supply fixture returns exactly 12 tuples."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_supply_path(), "supply")
        records = to_raw_records(df, "supply")
        assert len(records) == 12

    def test_to_raw_records_consumption_returns_12_tuples(self):
        """to_raw_records on consumption fixture returns exactly 12 tuples."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_consumption_path(), "consumption")
        records = to_raw_records(df, "consumption")
        assert len(records) == 12

    def test_to_raw_records_tuple_length_is_4(self):
        """Each tuple has exactly 4 elements: (month, sector, measure, value_gwh)."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_supply_path(), "supply")
        records = to_raw_records(df, "supply")
        for record in records:
            assert len(record) == 4

    def test_to_raw_records_month_is_date(self):
        """Month field in each tuple is a datetime.date object."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_supply_path(), "supply")
        records = to_raw_records(df, "supply")
        for record in records:
            assert isinstance(record[0], datetime.date), f"Expected datetime.date, got {type(record[0])}"

    def test_to_raw_records_sector_is_str(self):
        """Sector field in each tuple is a string."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_supply_path(), "supply")
        records = to_raw_records(df, "supply")
        for record in records:
            assert isinstance(record[1], str), f"Expected str, got {type(record[1])}"

    def test_to_raw_records_measure_is_str(self):
        """Measure field in each tuple is a string."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_supply_path(), "supply")
        records = to_raw_records(df, "supply")
        for record in records:
            assert isinstance(record[2], str), f"Expected str, got {type(record[2])}"
            assert record[2] == "supply", f"Expected 'supply', got {record[2]}"

    def test_to_raw_records_value_gwh_is_float(self):
        """Value_gwh field in each tuple is a float."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_supply_path(), "supply")
        records = to_raw_records(df, "supply")
        for record in records:
            assert isinstance(record[3], float), f"Expected float, got {type(record[3])}"

    def test_to_raw_records_2023_01_01_supply_total_value(self):
        """Supply total for 2023-01-01 equals the fixture value."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_supply_path(), "supply")
        records = to_raw_records(df, "supply")
        # Find 2023-01-01 total
        record = next((r for r in records if r[0] == datetime.date(2023, 1, 1) and r[1] == "total"), None)
        assert record is not None
        assert record[3] == pytest.approx(14079.372866387892, rel=1e-9)

    def test_to_raw_records_2024_06_01_consumption_total_value(self):
        """Consumption total for 2024-06-01 equals the fixture value."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df = read_csv(fixture_consumption_path(), "consumption")
        records = to_raw_records(df, "consumption")
        # Find 2024-06-01 total
        record = next((r for r in records if r[0] == datetime.date(2024, 6, 1) and r[1] == "total"), None)
        assert record is not None
        assert record[3] == pytest.approx(15431.39970458838, rel=1e-9)

    def test_to_raw_records_blank_value_raises_value_error(self, tmp_path):
        """to_raw_records raises ValueError when a value field is blank."""
        from pipeline.sources.dosm import to_raw_records

        # Create a DataFrame with a blank value
        fixture = pd.read_csv(fixture_supply_path(), dtype=str, keep_default_na=False)
        fixture.loc[0, "supply"] = ""

        temp_csv = tmp_path / "blank_value.csv"
        fixture.to_csv(temp_csv, index=False)

        df = pd.read_csv(temp_csv, dtype=str, keep_default_na=False)
        with pytest.raises(ValueError) as exc_info:
            to_raw_records(df, "supply")
        assert (
            "blank" in str(exc_info.value).lower()
            or "empty" in str(exc_info.value).lower()
            or "2023-01-01" in str(exc_info.value)
        )


class TestRecordsFrom:
    """Test records_from function for reading both files from a folder."""

    def test_records_from_with_both_fixtures_returns_24_records(self, tmp_path):
        """records_from reads both supply and consumption from a folder and returns 24 records total."""
        import shutil

        from pipeline.sources.dosm import FILES, records_from

        # Copy both fixture files to a temporary folder with the expected names
        tmp_fixtures = tmp_path / "dosm_data"
        tmp_fixtures.mkdir()
        shutil.copy(fixture_supply_path(), tmp_fixtures / FILES["supply"])
        shutil.copy(fixture_consumption_path(), tmp_fixtures / FILES["consumption"])

        records = records_from(tmp_fixtures)
        assert len(records) == 24  # 12 supply + 12 consumption

    def test_records_from_supply_records_come_first(self, tmp_path):
        """records_from returns supply records before consumption records."""
        import shutil

        from pipeline.sources.dosm import FILES, records_from

        tmp_fixtures = tmp_path / "dosm_data"
        tmp_fixtures.mkdir()
        shutil.copy(fixture_supply_path(), tmp_fixtures / FILES["supply"])
        shutil.copy(fixture_consumption_path(), tmp_fixtures / FILES["consumption"])

        records = records_from(tmp_fixtures)
        # First 12 records should be supply
        for i in range(12):
            assert records[i][2] == "supply", f"Record {i} should have measure='supply'"
        # Last 12 records should be consumption
        for i in range(12, 24):
            assert records[i][2] == "consumption", f"Record {i} should have measure='consumption'"


class TestAssertUniqueKeys:
    """Test assert_unique_keys function for detecting duplicate keys."""

    def test_assert_unique_keys_passes_on_unique_records(self):
        """assert_unique_keys passes when records have unique (month, sector, measure) keys."""
        from pipeline.sources.dosm import read_csv, to_raw_records

        df_supply = read_csv(fixture_supply_path(), "supply")
        df_consumption = read_csv(fixture_consumption_path(), "consumption")
        records_supply = to_raw_records(df_supply, "supply")
        records_consumption = to_raw_records(df_consumption, "consumption")
        all_records = records_supply + records_consumption

        # Key positions: (0, 1, 2) = (month, sector, measure)
        # This should pass since all records should have unique keys
        assert assert_unique_keys(all_records, (0, 1, 2)) is None

    def test_assert_unique_keys_raises_on_duplicate_key(self):
        """assert_unique_keys raises ValueError on duplicate (month, sector, measure) keys."""
        # Create records with duplicate key
        records = [
            (datetime.date(2023, 1, 1), "total", "supply", 14079.372866387892),
            (datetime.date(2023, 1, 1), "total", "supply", 14079.372866387892),
        ]

        with pytest.raises(ValueError) as exc_info:
            assert_unique_keys(records, (0, 1, 2))
        assert "duplicate" in str(exc_info.value).lower()
