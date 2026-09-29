from pipeline.db import split_batches


def test_splits_on_go_lines_and_drops_empty_batches():
    script = "CREATE SCHEMA a;\nGO\n\nGO\nCREATE SCHEMA b;\n"
    assert split_batches(script) == ["CREATE SCHEMA a;", "CREATE SCHEMA b;"]


def test_go_is_case_insensitive_and_allows_whitespace_and_trailing_comment():
    script = "SELECT 1;\n  go  \nSELECT 2;\nGo -- end of batch\nSELECT 3;"
    assert split_batches(script) == ["SELECT 1;", "SELECT 2;", "SELECT 3;"]


def test_go_must_stand_alone_on_its_line():
    script = "GOTO label;\nSELECT 'GO' AS word;\nSELECT 1 AS go_col;"
    assert split_batches(script) == [script]


def test_crlf_line_endings():
    script = "SELECT 1;\r\nGO\r\nSELECT 2;\r\n"
    assert split_batches(script) == ["SELECT 1;", "SELECT 2;"]


def test_script_without_go_is_one_batch():
    assert split_batches("SELECT 1;\nSELECT 2;") == ["SELECT 1;\nSELECT 2;"]
