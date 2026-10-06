import math
import pathlib

import pandas as pd
import pytest

from pipeline import config
from pipeline.sources._common import SchemaMismatchError, assert_unique_keys
from pipeline.sources.owid import (
    REQUIRED_COLUMNS,
    filter_asean,
    read_csv,
    to_raw_records,
)


def fixture_path():
    return pathlib.Path(__file__).parent / "fixtures" / "owid_sample.csv"


def test_required_columns_tuple():
    """REQUIRED_COLUMNS is a tuple of exactly 18 column names in the specified order."""
    assert isinstance(REQUIRED_COLUMNS, tuple)
    assert len(REQUIRED_COLUMNS) == 18
    assert REQUIRED_COLUMNS == (
        "country", "year", "iso_code", "population", "per_capita_electricity",
        "electricity_demand", "electricity_generation", "carbon_intensity_elec",
        "renewables_share_elec", "coal_electricity", "gas_electricity",
        "oil_electricity", "hydro_electricity", "solar_electricity",
        "wind_electricity", "biofuel_electricity", "other_renewable_electricity",
        "greenhouse_gas_emissions",
    )


def test_read_csv_returns_dataframe_with_18_columns():
    """read_csv returns a DataFrame with exactly 18 required columns in order."""
    df = read_csv(fixture_path())
    assert isinstance(df, pd.DataFrame)
    assert len(df.columns) == 18
    assert tuple(df.columns) == REQUIRED_COLUMNS


def test_read_csv_returns_10_rows():
    """read_csv on the fixture returns exactly 10 rows."""
    df = read_csv(fixture_path())
    assert len(df) == 10


def test_read_csv_raises_schema_mismatch_when_column_missing(tmp_path):
    """read_csv raises SchemaMismatchError when a required column is missing."""
    # Create a temporary CSV with population column removed
    fixture = pd.read_csv(fixture_path(), dtype=str, keep_default_na=False)
    cols_to_keep = [c for c in fixture.columns if c != "population"]
    fixture_no_pop = fixture[cols_to_keep]

    temp_csv = tmp_path / "no_population.csv"
    fixture_no_pop.to_csv(temp_csv, index=False)

    with pytest.raises(SchemaMismatchError) as exc_info:
        read_csv(temp_csv)
    assert "population" in str(exc_info.value).lower()


def test_filter_asean_keeps_only_asean_countries():
    """filter_asean keeps only rows whose iso_code is in config.ASEAN_ISO3."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)

    # Malaysia (2023, 2024, 2025), Singapore (1990, 2024), Indonesia (2024), Laos (1990): 7 rows
    assert len(filtered) == 7

    # Verify all iso_codes are in ASEAN
    for iso_code in filtered["iso_code"].unique():
        assert iso_code in config.ASEAN_ISO3


def test_filter_asean_drops_world_aggregate():
    """filter_asean drops World aggregate (iso_code blank or OWID_WRL)."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)

    # World should not be in the filtered data
    assert not (filtered["country"] == "World").any()


def test_filter_asean_drops_asia_aggregate():
    """filter_asean drops Asia aggregate (blank iso_code)."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)

    # Asia should not be in the filtered data
    assert not ((filtered["country"] == "Asia") & (filtered["iso_code"] == "")).any()


def test_filter_asean_drops_non_asean_country():
    """filter_asean drops non-ASEAN countries like India."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)

    # India should not be in the filtered data
    assert not (filtered["country"] == "India").any()


def test_filter_asean_keeps_Malaysia():
    """filter_asean keeps all Malaysia rows (2023, 2024, 2025)."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)

    mys_rows = filtered[filtered["country"] == "Malaysia"]
    assert len(mys_rows) == 3
    assert set(mys_rows["year"].astype(int)) == {2023, 2024, 2025}


def test_filter_asean_keeps_Singapore():
    """filter_asean keeps all Singapore rows (1990, 2024)."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)

    sgp_rows = filtered[filtered["country"] == "Singapore"]
    assert len(sgp_rows) == 2
    assert set(sgp_rows["year"].astype(int)) == {1990, 2024}


def test_filter_asean_keeps_Indonesia_and_Laos():
    """filter_asean keeps Indonesia 2024 and Laos 1990."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)

    kept = set(zip(filtered["iso_code"], filtered["year"].astype(int)))
    assert {("IDN", 2024), ("LAO", 1990)} <= kept


def test_filter_asean_resets_index():
    """filter_asean resets the index."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)

    # Index should be 0-based and continuous
    assert list(filtered.index) == list(range(len(filtered)))


def test_to_raw_records_returns_list_of_tuples():
    """to_raw_records returns a list of tuples."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    assert isinstance(records, list)
    assert all(isinstance(r, tuple) for r in records)


def test_to_raw_records_returns_one_tuple_per_row():
    """to_raw_records returns one tuple per row in the DataFrame."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    assert len(records) == 10


def test_to_raw_records_tuple_length_equals_required_columns():
    """Each tuple has length equal to REQUIRED_COLUMNS."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    for record in records:
        assert len(record) == len(REQUIRED_COLUMNS)


def test_to_raw_records_types_country_is_str():
    """country values are strings in tuples."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    for record in records:
        assert isinstance(record[0], str)  # country


def test_to_raw_records_types_iso_code_is_str():
    """iso_code values are strings for every ASEAN row (aggregates with a blank code are filtered out first)."""
    df = filter_asean(read_csv(fixture_path()))
    records = to_raw_records(df)

    for record in records:
        assert isinstance(record[2], str)  # iso_code


def test_to_raw_records_types_year_is_int():
    """year values are integers in tuples."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    for record in records:
        assert isinstance(record[1], int), f"year should be int, got {type(record[1])}"


def test_to_raw_records_types_population_is_int_or_none():
    """population values are integers or None in tuples."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    for record in records:
        pop = record[3]  # population
        assert pop is None or isinstance(pop, int), f"population should be int or None, got {type(pop)}"


def test_to_raw_records_types_floats_are_float_or_none():
    """Other numeric fields are floats or None."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    # Indices 4+ are floats (except population which is already tested)
    for record in records:
        for idx in range(4, len(record)):
            value = record[idx]
            assert value is None or isinstance(value, float), \
                f"Field {REQUIRED_COLUMNS[idx]} should be float or None, got {type(value)}"


def test_to_raw_records_malaysia_2025_year_is_int():
    """Malaysia 2025 year is 2025 (int)."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    mys_2025 = next(r for r in records if r[0] == "Malaysia" and r[1] == 2025)
    assert mys_2025[1] == 2025
    assert isinstance(mys_2025[1], int)


def test_to_raw_records_malaysia_2025_population_is_int():
    """Malaysia 2025 population is 35977834 (int)."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    mys_2025 = next(r for r in records if r[0] == "Malaysia" and r[1] == 2025)
    assert mys_2025[3] == 35977834
    assert isinstance(mys_2025[3], int)


def test_to_raw_records_malaysia_2025_electricity_demand_approx():
    """Malaysia 2025 electricity_demand is approximately 199.91."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    mys_2025 = next(r for r in records if r[0] == "Malaysia" and r[1] == 2025)
    # electricity_demand is index 5
    assert mys_2025[5] == pytest.approx(199.91, rel=1e-6)


def test_to_raw_records_malaysia_2025_carbon_intensity_approx():
    """Malaysia 2025 carbon_intensity_elec is approximately 601.97."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    mys_2025 = next(r for r in records if r[0] == "Malaysia" and r[1] == 2025)
    # carbon_intensity_elec is index 7
    assert mys_2025[7] == pytest.approx(601.97, rel=1e-4)


def test_to_raw_records_laos_1990_blank_fields_are_none():
    """Laos 1990 has a population but no electricity data: blanks become None, not 0."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    lao_1990 = next(r for r in records if r[2] == "LAO" and r[1] == 1990)
    assert lao_1990[3] == 4311960
    assert lao_1990[5] is None  # electricity_demand
    assert lao_1990[6] is None  # electricity_generation


def test_to_raw_records_float_string_population_converted_to_int():
    """A float-string population like '35977834.0' converts to int 35977834."""
    # Create a one-row DataFrame with population as float string
    data = {col: [""] for col in REQUIRED_COLUMNS}
    data["country"] = ["TestCountry"]
    data["year"] = ["2024"]
    data["iso_code"] = ["TST"]
    data["population"] = ["35977834.0"]

    test_df = pd.DataFrame(data)
    records = to_raw_records(test_df)

    assert len(records) == 1
    assert records[0][3] == 35977834
    assert isinstance(records[0][3], int)


def test_to_raw_records_no_nan_values():
    """to_raw_records never produces NaN float values (converts to None instead)."""
    df = read_csv(fixture_path())
    records = to_raw_records(df)

    for record in records:
        for value in record:
            if isinstance(value, float):
                assert not math.isnan(value), "NaN values should be converted to None"


def test_assert_unique_keys_passes_on_unique_keys():
    """assert_unique_keys passes when records have unique keys."""
    df = read_csv(fixture_path())
    filtered = filter_asean(df)
    records = to_raw_records(filtered)

    # Key positions: (2, 1) = (iso_code, year)
    # This should pass since all ASEAN records should have unique (iso_code, year)
    assert assert_unique_keys(records, (2, 1)) is None


def test_assert_unique_keys_raises_on_duplicate():
    """assert_unique_keys raises ValueError on duplicate keys."""
    # Create records with duplicate (iso_code, year)
    records = [
        ("Malaysia", 2024, "MYS", 35557670, 5400.0, 185.0, 190.0, 600.0, 20.0,
         85.0, 65.0, 2.0, 35.0, 4.0, 0.0, 1.5, 1.5, 120.0),
        ("Malaysia", 2024, "MYS", 35600000, 5500.0, 190.0, 195.0, 610.0, 21.0,
         90.0, 68.0, 2.5, 36.0, 5.0, 0.5, 2.0, 2.0, 125.0),
    ]

    with pytest.raises(ValueError):
        assert_unique_keys(records, (2, 1))


def test_assert_unique_keys_on_different_key_positions():
    """assert_unique_keys works with different key position tuples."""
    # Create records where (iso_code, country) is unique but (country, year) is not
    records = [
        ("Malaysia", 2024, "MYS", 35557670, 5400.0, 185.0, 190.0, 600.0, 20.0,
         85.0, 65.0, 2.0, 35.0, 4.0, 0.0, 1.5, 1.5, 120.0),
        ("Malaysia", 2024, "MYS", 35600000, 5500.0, 190.0, 195.0, 610.0, 21.0,
         90.0, 68.0, 2.5, 36.0, 5.0, 0.5, 2.0, 2.0, 125.0),
    ]

    # Using key (2, 0) = (iso_code, country) should raise because both rows have same iso_code + country
    with pytest.raises(ValueError):
        assert_unique_keys(records, (2, 0))


def test_read_csv_preserves_all_original_columns_internally():
    """read_csv reads the full file but returns only REQUIRED_COLUMNS."""
    # Read the full file for comparison
    full_df = pd.read_csv(fixture_path(), dtype=str, keep_default_na=False)
    result_df = read_csv(fixture_path())

    # Result should have fewer columns than the file
    assert len(result_df.columns) <= len(full_df.columns)
    assert len(result_df.columns) == len(REQUIRED_COLUMNS)
