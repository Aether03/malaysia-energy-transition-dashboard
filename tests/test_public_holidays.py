"""ref.public_holiday generation (M3 plan step 3): package list + hand-checked overrides, no database."""

from datetime import date

import pytest

from pipeline import config, public_holidays


@pytest.fixture(scope="module")
def rows():
    return public_holidays.build_holidays(config.SEED_DIR)


def _days(rows, country):
    return {d for c, d, _, _ in rows if c == country}


def test_songkran_2024_and_its_in_lieu_day_are_holidays(rows):
    th = _days(rows, "TH")
    assert {date(2024, 4, 13), date(2024, 4, 14), date(2024, 4, 15), date(2024, 4, 16)} <= th


def test_cabinet_bridge_days_are_present(rows):
    th = _days(rows, "TH")
    bridges = {date(2023, 5, 5), date(2023, 7, 31), date(2023, 12, 29), date(2024, 4, 12), date(2024, 12, 30)}
    assert bridges <= th


def test_childrens_day_override_removes_the_observance(rows):
    th = _days(rows, "TH")
    assert date(2023, 1, 14) not in th and date(2024, 1, 13) not in th


def test_names_are_english_not_thai_script(rows):
    assert all(name.isascii() for _, _, name, _ in rows)


def test_origin_records_the_package_version(rows):
    origins = {origin for *_, origin in rows}
    assert any(o.startswith("holidays ") for o in origins)


def test_override_with_wrong_header_is_rejected(tmp_path):
    (tmp_path / public_holidays.OVERRIDE_FILE).write_text("country,date,name\nTH,2024-01-01,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        public_holidays.read_overrides(tmp_path)



def test_years_cover_every_hourly_grid_span():
    from datetime import timedelta

    from pipeline.sources import singapore

    first = min(singapore.FIRST_WEEK, date(2023, 1, 1))
    last = max(singapore.LAST_WEEK + timedelta(days=6), date(2025, 1, 1))  # TH spill-over day
    assert set(range(first.year, last.year + 1)) <= set(public_holidays.HOLIDAY_YEARS)


def test_singapore_christmas_observed_2022_is_present(rows):
    assert date(2022, 12, 26) in _days(rows, "SG")


def _write_overrides(tmp_path, body):
    header = "country_code,holiday_date,name,action\n"
    (tmp_path / public_holidays.OVERRIDE_FILE).write_text(header + body, encoding="utf-8")


def test_remove_of_a_date_the_package_lacks_stops_the_seed(tmp_path):
    _write_overrides(tmp_path, "TH,2024-03-03,not a holiday,REMOVE\n")
    with pytest.raises(ValueError, match="matches no package holiday"):
        public_holidays.build_holidays(tmp_path)


def test_duplicate_override_rows_stop_the_seed(tmp_path):
    _write_overrides(tmp_path, "TH,2024-01-13,a,REMOVE\nTH,2024-01-13,b,REMOVE\n")
    with pytest.raises(ValueError, match="duplicate"):
        public_holidays.read_overrides(tmp_path)


def test_override_with_blank_name_is_rejected(tmp_path):
    _write_overrides(tmp_path, "TH,2024-05-05, ,ADD\n")
    with pytest.raises(ValueError, match="bad row"):
        public_holidays.read_overrides(tmp_path)
