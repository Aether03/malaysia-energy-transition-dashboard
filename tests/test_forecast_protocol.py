"""Tests for the locked forecast protocol: parsing `docs/forecast.md` and the `--final` git gate.

The git tests build a throwaway repository under `tmp_path` and configure it locally; nothing here
touches the real repository or any global git configuration.
"""

import json
import re
import shutil
import subprocess

import pandas as pd
import pytest

from pipeline.forecast import features, protocol
from pipeline.forecast.protocol import ProtocolError

# --- helpers -----------------------------------------------------------------------------


def _raw():
    return {
        "features": list(features.FEATURE_COLUMNS),
        "data_start": "2023-01-08",
        "es_days": 28,
        "dev": {"first_month": "2023-10", "last_month": "2023-12"},
        "final": {"first_month": "2024-01", "last_month": "2024-12"},
        "lightgbm": {"objective": "l2", "learning_rate": 0.05, "num_leaves": 31},
        "seed": 20231008,
        "num_threads": 1,
        "bootstrap": {"n_boot": 2000, "level": 0.95, "block_days": 7},
    }


def _doc(block=None, *, before="", pre_block="", between="", after=""):
    """A protocol document. `block` is the JSON text of the protocol block (default: the valid one)."""
    block = json.dumps(_raw(), indent=2) if block is None else block
    return (
        "# Forecast\n\nSome introduction — with a dash.\n\n" + before
        + "## Protocol\n\nThe settings below are locked before the run.\n\n" + pre_block
        + f"```json\n{block}\n```\n\n" + between
        + "More prose about the protocol.\n\n" + after
        + "## Results\n\nNot run yet.\n"
    )  # fmt: skip


def _doc_with(mutate):
    raw = _raw()
    mutate(raw)
    return _doc(json.dumps(raw, indent=2))


# --- constants ---------------------------------------------------------------------------


def test_protocol_paths():
    assert protocol.PROTOCOL_REL == "docs/forecast.md"
    assert protocol.RECORD_REL == "docs/forecast_final.json"
    assert protocol.GUARDED_REL == (
        "docs/forecast.md", "docs/forecast_final.json", "pipeline/forecast", "pipeline/cli.py",
        "pipeline/public_holidays.py", "pipeline/seeds.py", "seed/holiday_override.csv", "requirements.txt",
        "sql/views/R__stg_grid.sql", "sql/transform/050_fact_grid_hourly.sql",
    )  # fmt: skip
    assert issubclass(ProtocolError, RuntimeError)


# --- parse_protocol: the valid document --------------------------------------------------


def test_parse_protocol_reads_every_field():
    parsed = protocol.parse_protocol(_doc())
    assert parsed.features == tuple(features.FEATURE_COLUMNS)
    assert isinstance(parsed.data_start, pd.Timestamp)
    assert parsed.data_start == pd.Timestamp("2023-01-08")
    assert parsed.es_days == 28
    assert (parsed.dev_first_month, parsed.dev_last_month) == ("2023-10", "2023-12")
    assert (parsed.final_first_month, parsed.final_last_month) == ("2024-01", "2024-12")
    assert parsed.lightgbm == {"objective": "l2", "learning_rate": 0.05, "num_leaves": 31}
    assert parsed.seed == 20231008
    assert parsed.num_threads == 1
    assert parsed.n_boot == 2000
    assert parsed.level == 0.95
    assert parsed.block_days == 7
    assert parsed.raw == _raw()


def test_parse_protocol_takes_the_first_json_block_inside_the_protocol_section():
    other = _raw()
    other["seed"] = 1
    decoy = f"```json\n{json.dumps(other)}\n```\n\n"
    text = _doc(
        before=decoy,  # in the introduction, before the heading
        pre_block="```text\nnot json at all\n```\n\n",  # a fenced block of another language is skipped
        between=decoy,  # a second json block after the real one is ignored
    )
    assert protocol.parse_protocol(text).seed == 20231008


def test_parse_protocol_section_continues_through_a_level_three_heading():
    text = _doc(between="### Details\n\nA sub-heading does not end the section.\n\n")
    assert protocol.parse_protocol(text).seed == 20231008
    # and a block that only appears under that sub-heading still counts
    sub_only = (
        "# Forecast\n\n## Protocol\n\nProse.\n\n### Settings\n\n```json\n" + json.dumps(_raw()) + "\n```\n\n## Results\n"
    )
    assert protocol.parse_protocol(sub_only).es_days == 28


# --- parse_protocol: structure errors ----------------------------------------------------


def test_no_protocol_section():
    text = "# Forecast\n\n## Method\n\n```json\n" + json.dumps(_raw()) + "\n```\n"
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(text)


def test_a_level_three_protocol_heading_is_not_the_protocol_section():
    text = "# Forecast\n\n### Protocol\n\n```json\n" + json.dumps(_raw()) + "\n```\n"
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(text)


def test_protocol_section_without_a_json_block():
    prose_only = "# Forecast\n\n## Protocol\n\nJust prose, no settings.\n\n## Results\n\nNone.\n"
    other_language = "# Forecast\n\n## Protocol\n\n```python\nx = 1\n```\n\n## Results\n"
    for text in (prose_only, other_language):
        with pytest.raises(ProtocolError):
            protocol.parse_protocol(text)


@pytest.mark.parametrize("heading", ["## Results", "# Appendix"])
def test_a_json_block_only_after_the_next_heading_does_not_count(heading):
    text = (
        "# Forecast\n\n## Protocol\n\nProse only here.\n\n"
        + f"{heading}\n\n```json\n{json.dumps(_raw())}\n```\n"
    )  # fmt: skip
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(text)


def test_invalid_json():
    for broken in ('{"features": [', "not json", "{'single': 'quotes'}", ""):
        with pytest.raises(ProtocolError):
            protocol.parse_protocol(_doc(broken))


def test_json_that_is_not_an_object():
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(_doc("[1, 2, 3]"))


# --- parse_protocol: content errors ------------------------------------------------------


@pytest.mark.parametrize(
    "key", ["features", "data_start", "es_days", "dev", "final", "lightgbm", "seed", "num_threads", "bootstrap"]
)
def test_a_missing_top_level_key(key):
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(_doc_with(lambda raw: raw.pop(key)))


@pytest.mark.parametrize(
    ("section", "key"),
    [("dev", "first_month"), ("dev", "last_month"), ("final", "first_month"), ("final", "last_month"),
     ("bootstrap", "n_boot"), ("bootstrap", "level"), ("bootstrap", "block_days")],
)  # fmt: skip
def test_a_missing_nested_key(section, key):
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(_doc_with(lambda raw: raw[section].pop(key)))


@pytest.mark.parametrize(
    ("key", "wrong"),
    [("es_days", "28"), ("seed", "20231008"), ("num_threads", "1"), ("lightgbm", ["l2"]), ("features", "hour"),
     ("dev", "2023-10"), ("bootstrap", 2000)],
)  # fmt: skip
def test_a_value_of_the_wrong_type(key, wrong):
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(_doc_with(lambda raw: raw.__setitem__(key, wrong)))


def _reordered(raw):
    raw["features"][0], raw["features"][1] = raw["features"][1], raw["features"][0]


def _one_missing(raw):
    raw["features"].pop()


def _one_extra(raw):
    raw["features"].append("temperature")


@pytest.mark.parametrize("mutate", [_reordered, _one_missing, _one_extra], ids=["reordered", "missing", "extra"])
def test_features_must_equal_the_code_feature_columns(mutate):
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(_doc_with(mutate))


@pytest.mark.parametrize("bad", ["2024-1", "2024-13", "2024-00", "24-01", "2024/01", "Jan 2024", ""])
@pytest.mark.parametrize(
    ("section", "key"), [("final", "first_month"), ("final", "last_month"), ("dev", "first_month"), ("dev", "last_month")]
)
def test_a_month_must_be_yyyy_mm(section, key, bad):
    with pytest.raises(ProtocolError):
        protocol.parse_protocol(_doc_with(lambda raw: raw[section].__setitem__(key, bad)))


def test_a_first_month_after_its_last_month():
    def dev_backwards(raw):
        raw["dev"] = {"first_month": "2023-12", "last_month": "2023-10"}

    def final_backwards(raw):
        raw["final"] = {"first_month": "2024-12", "last_month": "2024-01"}

    for mutate in (dev_backwards, final_backwards):
        with pytest.raises(ProtocolError):
            protocol.parse_protocol(_doc_with(mutate))


@pytest.mark.parametrize("dev_last", ["2024-01", "2024-03", "2025-01"], ids=["equal", "inside_final", "after_final"])
def test_dev_months_must_end_before_the_final_period(dev_last):
    def reach_in(raw):
        raw["dev"] = {"first_month": "2023-10", "last_month": dev_last}

    with pytest.raises(ProtocolError):
        protocol.parse_protocol(_doc_with(reach_in))


def test_dev_may_end_the_month_before_final_starts_and_single_month_periods_are_fine():
    def tight(raw):
        raw["dev"] = {"first_month": "2023-12", "last_month": "2023-12"}
        raw["final"] = {"first_month": "2024-01", "last_month": "2024-01"}

    parsed = protocol.parse_protocol(_doc_with(tight))
    assert parsed.dev_first_month == parsed.dev_last_month == "2023-12"
    assert parsed.final_first_month == parsed.final_last_month == "2024-01"


# --- load_protocol -----------------------------------------------------------------------


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_load_protocol_reads_a_utf8_file(tmp_path, newline):
    path = tmp_path / "forecast.md"
    path.write_bytes(_doc().replace("\n", newline).encode("utf-8"))
    parsed = protocol.load_protocol(path)
    assert parsed.raw == _raw()
    assert parsed.data_start == pd.Timestamp("2023-01-08")


def test_load_protocol_of_a_missing_file(tmp_path):
    with pytest.raises(ProtocolError):
        protocol.load_protocol(tmp_path / "does_not_exist.md")


# --- committed_protocol: the git gate ----------------------------------------------------

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
HEX40 = re.compile(r"[0-9a-f]{40}")


def _git(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(
        repo, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
        "commit", "-q", "-m", message,
    )  # fmt: skip


def _new_repo(root, files):
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "core.autocrlf", "false")  # this repository only
    for rel, text in files.items():
        _write(root, rel, text)
    _commit(root, "initial")
    return root


@pytest.fixture(scope="module")
def template_repo(tmp_path_factory):
    """One committed repository, built once; each test works on its own copy."""
    return _new_repo(
        tmp_path_factory.mktemp("template") / "repo",
        {"docs/forecast.md": "# Forecast\n", "pipeline/forecast/x.py": "X = 1\n", "README.md": "readme\n"},
    )


@pytest.fixture
def repo(template_repo, tmp_path):
    copy = tmp_path / "repo"
    shutil.copytree(template_repo, copy)
    return copy


def _head(repo):
    return _git(repo, "rev-parse", "HEAD")


def _last_protocol_commit(repo):
    return _git(repo, "log", "-1", "--format=%H", "--", "docs/forecast.md")


@needs_git
def test_clean_repo_returns_the_protocol_and_head_commits(repo):
    result = protocol.committed_protocol(repo)
    assert isinstance(result, tuple)
    protocol_commit, head_commit = result
    assert HEX40.fullmatch(protocol_commit)
    assert HEX40.fullmatch(head_commit)
    assert protocol_commit == _last_protocol_commit(repo)
    assert head_commit == _head(repo)
    assert protocol_commit == head_commit  # one commit so far


@needs_git
def test_protocol_commit_stays_put_while_head_moves(repo):
    first = _head(repo)
    _write(repo, "README.md", "readme, edited\n")
    _commit(repo, "readme")
    _write(repo, "pipeline/forecast/x.py", "X = 2\n")
    _commit(repo, "code")
    protocol_commit, head_commit = protocol.committed_protocol(repo)
    assert protocol_commit == first == _last_protocol_commit(repo)
    assert head_commit == _head(repo)
    assert head_commit != first

    _write(repo, "docs/forecast.md", "# Forecast\n\nlocked settings\n")
    _commit(repo, "protocol")
    protocol_commit, head_commit = protocol.committed_protocol(repo)
    assert protocol_commit == head_commit == _head(repo)
    assert protocol_commit != first


def _readme_unstaged(repo):
    _write(repo, "README.md", "readme, edited\n")


def _readme_staged(repo):
    _write(repo, "README.md", "readme, edited\n")
    _git(repo, "add", "README.md")


def _untracked_elsewhere(repo):
    _write(repo, "notes.txt", "scratch\n")


def _untracked_in_docs(repo):
    _write(repo, "docs/other.md", "another document\n")


def _untracked_in_pipeline(repo):
    _write(repo, "pipeline/other.py", "Y = 1\n")


def _untracked_sibling_with_the_same_prefix(repo):
    _write(repo, "pipeline/forecast_old/y.py", "Y = 1\n")


@needs_git
@pytest.mark.parametrize(
    "touch",
    [_readme_unstaged, _readme_staged, _untracked_elsewhere, _untracked_in_docs, _untracked_in_pipeline,
     _untracked_sibling_with_the_same_prefix],
    ids=["readme_unstaged", "readme_staged", "untracked_elsewhere", "untracked_in_docs", "untracked_in_pipeline",
         "untracked_sibling_prefix"],
)  # fmt: skip
def test_uncommitted_changes_outside_the_guarded_paths_are_allowed(repo, touch):
    touch(repo)
    protocol_commit, head_commit = protocol.committed_protocol(repo)
    assert protocol_commit == head_commit == _head(repo)


def _protocol_unstaged(repo):
    _write(repo, "docs/forecast.md", "# Forecast\n\nedited\n")


def _protocol_staged(repo):
    _protocol_unstaged(repo)
    _git(repo, "add", "docs/forecast.md")


def _protocol_deleted(repo):
    (repo / "docs" / "forecast.md").unlink()


def _code_unstaged(repo):
    _write(repo, "pipeline/forecast/x.py", "X = 99\n")


def _code_staged(repo):
    _code_unstaged(repo)
    _git(repo, "add", "pipeline/forecast/x.py")


def _code_deleted(repo):
    (repo / "pipeline" / "forecast" / "x.py").unlink()


def _code_untracked(repo):
    _write(repo, "pipeline/forecast/new.py", "Z = 1\n")


def _code_untracked_nested(repo):
    _write(repo, "pipeline/forecast/sub/deeper.py", "Z = 1\n")


def _code_added_not_committed(repo):
    _code_untracked(repo)
    _git(repo, "add", "pipeline/forecast/new.py")


@needs_git
@pytest.mark.parametrize(
    "touch",
    [_protocol_unstaged, _protocol_staged, _protocol_deleted, _code_unstaged, _code_staged, _code_deleted,
     _code_untracked, _code_untracked_nested, _code_added_not_committed],
    ids=["protocol_unstaged", "protocol_staged", "protocol_deleted", "code_unstaged", "code_staged", "code_deleted",
         "code_untracked", "code_untracked_nested", "code_added_not_committed"],
)  # fmt: skip
def test_an_uncommitted_change_in_a_guarded_path_is_refused(repo, touch):
    touch(repo)
    with pytest.raises(ProtocolError):
        protocol.committed_protocol(repo)


@needs_git
def test_a_protocol_file_that_was_never_added_is_refused(tmp_path):
    root = _new_repo(tmp_path / "fresh", {"pipeline/forecast/x.py": "X = 1\n", "README.md": "readme\n"})
    _write(root, "docs/forecast.md", "# Forecast\n")  # on disk, untracked
    with pytest.raises(ProtocolError):
        protocol.committed_protocol(root)


@needs_git
def test_a_repo_without_a_protocol_file_is_refused(tmp_path):
    root = _new_repo(tmp_path / "bare", {"pipeline/forecast/x.py": "X = 1\n", "README.md": "readme\n"})
    with pytest.raises(ProtocolError):
        protocol.committed_protocol(root)


@needs_git
def test_a_directory_that_is_not_a_git_repo_is_refused(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "docs").mkdir()
    (plain / "docs" / "forecast.md").write_text("# Forecast\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))  # never discover a repository above it
    with pytest.raises(ProtocolError):
        protocol.committed_protocol(plain)


# --- MLE review additions: hidden edits, the record under the gate, protocol at a commit ---


@needs_git
@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_an_edit_hidden_from_git_status_is_refused(repo, flag):
    _git(repo, "update-index", flag, "pipeline/forecast/x.py")
    _write(repo, "pipeline/forecast/x.py", "X = 99\n")
    assert _git(repo, "status", "--porcelain") == ""  # git status no longer shows the edit
    with pytest.raises(ProtocolError, match="hidden"):
        protocol.committed_protocol(repo)


@needs_git
def test_the_record_is_guarded_once_it_exists(repo):
    _write(repo, "docs/forecast_final.json", "{}\n")  # written by a FINAL run, not yet committed
    with pytest.raises(ProtocolError):
        protocol.committed_protocol(repo)
    _commit(repo, "record")
    protocol.committed_protocol(repo)  # committed: the next grid may run
    (repo / "docs" / "forecast_final.json").unlink()  # deleting it to allow a second FINAL
    with pytest.raises(ProtocolError):
        protocol.committed_protocol(repo)


@needs_git
@pytest.mark.parametrize("rel", ["requirements.txt", "seed/holiday_override.csv", "sql/views/R__stg_grid.sql"])
def test_an_uncommitted_input_file_is_refused(repo, rel):
    _write(repo, rel, "changed\n")
    with pytest.raises(ProtocolError):
        protocol.committed_protocol(repo)


@needs_git
def test_protocol_at_commit_reads_the_protocol_as_committed_then(repo):
    _write(repo, "docs/forecast.md", _doc())
    _commit(repo, "protocol v1")
    first = _head(repo)
    _write(repo, "docs/forecast.md", _doc_with(lambda raw: raw.__setitem__("seed", 99)))
    _commit(repo, "protocol v2")
    assert protocol.protocol_at_commit(first, repo).seed == 20231008
    assert protocol.protocol_at_commit(_head(repo), repo).seed == 99
    with pytest.raises(ProtocolError):
        protocol.protocol_at_commit("not-a-hash", repo)
