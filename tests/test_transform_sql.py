"""Transform SQL text guards for the M5 LOW items (the DB-backed checks are in test_db_integration)."""

import re

from pipeline import config


def _sql(name):
    return (config.TRANSFORM_DIR / name).read_text(encoding="utf-8")


def _code(sql):
    return re.sub(r"--[^\n]*", "", sql)  # comments may mention the old behaviour


def test_dim_year_is_complete_uses_malaysia_local_time_not_utc():
    sql = _code(_sql("010_dim_year.sql"))
    assert "SYSUTCDATETIME" not in sql
    assert "AT TIME ZONE 'Singapore Standard Time'" in sql  # Windows zone id for UTC+8 (Malaysia has none)


def test_generation_facts_keep_a_source_that_has_capacity_but_no_generation():
    sql = _code(_sql("020_fact_generation_annual.sql"))
    assert "s.generation_twh IS NOT NULL OR s.capacity_gw > 0" in sql  # zero capacity carries no information
