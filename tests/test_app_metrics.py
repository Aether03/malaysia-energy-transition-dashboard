"""The web showcase's numbers equal the SQL twins (M6 plan Q4): each port in app/showcase/metrics.py reproduces
its sql/showcase query from the exported views; exports/expected.json holds the SQL results at export time."""

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from showcase import data, metrics

EXPECTED = data.expected() if (data.EXPORTS / "expected.json").exists() else {}


def test_every_exported_showcase_result_has_a_port():
    assert set(EXPECTED) <= set(metrics.SHOWCASE)


def assert_rows_match(got: list[dict], want: list[dict]) -> None:
    """Same columns and rows; text, dates and integers exact, other numbers within max(0.05, 0.1%)."""
    g, w = pd.DataFrame(got), pd.DataFrame(want)
    assert list(g.columns) == list(w.columns)
    assert len(g) == len(w)
    keys = [c for c in w.columns if not pd.api.types.is_float_dtype(w[c])]
    g = g.sort_values(keys, na_position="first").reset_index(drop=True)
    w = w.sort_values(keys, na_position="first").reset_index(drop=True)
    for col in w.columns:
        for i, (a, b) in enumerate(zip(g[col], w[col], strict=True)):
            if isinstance(b, float) and not math.isnan(b):
                assert a is not None and abs(a - b) <= max(0.05, 0.001 * abs(b)), f"{col} row {i}: {a} vs {b}"
            else:
                assert (pd.isna(a) and pd.isna(b)) or a == b, f"{col} row {i}: {a!r} vs {b!r}"


@pytest.mark.parametrize("name", sorted(EXPECTED))
@pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="ported in M6 step 3")
def test_port_matches_its_sql_twin(name):
    assert_rows_match(metrics.SHOWCASE[name](data.frames()), EXPECTED[name])


def test_the_comparison_catches_a_wrong_number():
    want = [{"grid_code": "TH_EGAT", "mape": 4.56}]
    assert_rows_match([{"grid_code": "TH_EGAT", "mape": 4.6}], want)
    with pytest.raises(AssertionError):
        assert_rows_match([{"grid_code": "TH_EGAT", "mape": 4.7}], want)
