"""ref.public_holiday generation (M3 plan step 3): package list + hand-checked overrides, no database."""

from datetime import date

import pytest

from pipeline import calendar, config


@pytest.fixture(scope="module")
def rows():
    return calendar.build_holidays(config.SEED_DIR)


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
    (tmp_path / calendar.OVERRIDE_FILE).write_text("country,date,name\nTH,2024-01-01,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        calendar.read_overrides(tmp_path)
