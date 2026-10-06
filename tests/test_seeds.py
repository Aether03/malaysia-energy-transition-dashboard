"""Seed loader pure functions (M3 Python review M6, database review 12-13): no database."""

import pytest

from pipeline import config, seeds


def _spec(name):
    return next(s for s in seeds.SEEDS if s.csv_name == name)


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_every_real_seed_csv_passes_the_strict_header_check():
    for spec in seeds.SEEDS:
        _, rows = seeds._read_csv(spec, config.SEED_DIR)
        assert rows, spec.csv_name


def test_dim_grid_lookup_is_a_parameter_not_a_subquery():
    sql = seeds._merge_sql(_spec("dim_grid.csv"))
    assert "? AS country_key" in sql
    assert "SELECT country_key FROM" not in sql  # resolved in Python, with a clear error


def test_merge_sql_names_come_only_from_the_spec():
    spec = _spec("dim_hour.csv")
    sql = seeds._merge_sql(spec)
    assert sql.startswith("MERGE dw.dim_hour AS t USING (SELECT ? AS hour, ? AS label)")


def test_missing_column_is_rejected(tmp_path):
    _write(tmp_path, "dim_hour.csv", "hour\n0\n")
    with pytest.raises(ValueError, match="missing \\['label'\\]"):
        seeds._read_csv(_spec("dim_hour.csv"), tmp_path)


def test_unknown_column_is_rejected_so_it_never_reaches_sql(tmp_path):
    _write(tmp_path, "dim_hour.csv", "hour,label,x; DROP TABLE y--\n0,00:00,1\n")
    with pytest.raises(ValueError, match="unexpected"):
        seeds._read_csv(_spec("dim_hour.csv"), tmp_path)


def test_lookup_target_and_its_csv_column_together_are_rejected(tmp_path):
    header = "grid_code,name,country_iso3,country_key,utc_offset_min,data_source_code,is_published"
    _write(tmp_path, "dim_grid.csv", header + "\nTH_EGAT,x,THA,1,420,DTH,1\n")
    with pytest.raises(ValueError, match="unexpected \\['country_key'\\]"):
        seeds._read_csv(_spec("dim_grid.csv"), tmp_path)


def test_empty_csv_is_a_clear_error(tmp_path):
    _write(tmp_path, "dim_hour.csv", "")
    with pytest.raises(ValueError, match="empty"):
        seeds._read_csv(_spec("dim_hour.csv"), tmp_path)


def test_dq_rule_check_sql_must_be_a_query(tmp_path):
    header = "rule_code,description,data_source_code,severity,check_sql,is_active"
    _write(tmp_path, "dq_rule.csv", header + '\nBAD,x,,WARN,"DELETE FROM dw.fact_grid_hourly",1\n')
    with pytest.raises(ValueError, match="SELECT or WITH"):
        seeds._read_csv(_spec("dq_rule.csv"), tmp_path)


def test_lookup_needs_exactly_one_placeholder():
    with pytest.raises(ValueError, match="exactly one"):
        seeds.Lookup("a", "b", "SELECT 1")


def test_lookup_target_must_be_a_seeded_column():
    with pytest.raises(ValueError, match="not a seeded column"):
        seeds.SeedSpec("x.csv", "dw.x", "k", ("k",), (seeds.Lookup("iso", "nope", "SELECT 1 WHERE ? = 1"),))


class _Cursor:
    def __init__(self, result):
        self.result = result

    def execute(self, sql, params):
        self.params = params

    def fetchone(self):
        return self.result


def test_unknown_lookup_value_raises_a_clear_error():
    spec = _spec("dim_grid.csv")
    with pytest.raises(ValueError, match="unknown country_iso3 'XXX'"):
        seeds._resolve(_Cursor(None), spec, spec.lookups[0], "XXX")


def test_known_lookup_value_resolves():
    spec = _spec("dim_grid.csv")
    assert seeds._resolve(_Cursor((7,)), spec, spec.lookups[0], "THA") == 7


def _dq_rule(code):
    import csv

    with (config.SEED_DIR / "dq_rule.csv").open(encoding="utf-8", newline="") as handle:
        return next(row for row in csv.DictReader(handle) if row["rule_code"] == code)


def test_negative_generation_rule_has_a_rounding_tolerance():
    # Stored as DECIMAL(12,4) TWh, so one unit is 0.0001 TWh (0.1 GWh). The cut-off is 1 GWh: ten storage
    # units of slack for source rounding, far below any real negative (M5 Q4, transform review LOW).
    rule = _dq_rule("NO_NEGATIVE_GENERATION")
    assert "generation_twh < -0.001" in rule["check_sql"]
    assert "1 GWh" in rule["description"]
