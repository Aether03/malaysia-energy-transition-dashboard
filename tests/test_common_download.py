"""`_common.download` and `parse_number` (M3 Python review M1, M2, M6, L2, L3): no network."""

import pytest
import requests

from pipeline.sources import _common
from pipeline.sources._common import InvalidDownloadError


class _Response:
    def __init__(self, status=200, body=b"data", headers=None):
        self.status_code = status
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def iter_content(self, chunk_size):
        yield self.body


class _Getter:
    """Plays back a list of responses (or exceptions) and counts calls."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0
        self.user_agents = []

    def __call__(self, url, stream, timeout, headers):
        self.calls += 1
        self.user_agents.append(headers["User-Agent"])
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(_common.time, "sleep", lambda s: None)


def _reject_bad(path):
    if path.read_bytes() == b"bad":
        raise InvalidDownloadError("bad body")


def test_downloads_and_reuses_the_same_folder_file(tmp_path, monkeypatch):
    getter = _Getter(_Response(body=b"good", headers={"Last-Modified": "Mon"}))
    monkeypatch.setattr(_common.requests, "get", getter)
    path, version = _common.download("u", "src", "f.csv", folder=tmp_path)
    assert path.read_bytes() == b"good" and version == "Mon"
    again, version2 = _common.download("u", "src", "f.csv", folder=tmp_path)
    assert again == path and version2 == "Mon" and getter.calls == 1
    assert "github.com/Aether03" in getter.user_agents[0]


def test_a_404_fails_at_once_without_retries(tmp_path, monkeypatch):
    getter = _Getter(_Response(status=404))
    monkeypatch.setattr(_common.requests, "get", getter)
    with pytest.raises(requests.HTTPError):
        _common.download("u", "src", "f.csv", folder=tmp_path)
    assert getter.calls == 1


def test_a_503_is_retried(tmp_path, monkeypatch):
    getter = _Getter(_Response(status=503), _Response(body=b"ok"))
    monkeypatch.setattr(_common.requests, "get", getter)
    path, _ = _common.download("u", "src", "f.csv", folder=tmp_path)
    assert path.read_bytes() == b"ok" and getter.calls == 2


def test_invalid_body_is_deleted_and_retried_never_cached(tmp_path, monkeypatch):
    getter = _Getter(_Response(body=b"bad"), _Response(body=b"good"))
    monkeypatch.setattr(_common.requests, "get", getter)
    path, _ = _common.download("u", "src", "f.csv", folder=tmp_path, validate=_reject_bad)
    assert path.read_bytes() == b"good" and getter.calls == 2


def test_invalid_body_on_every_attempt_raises_and_leaves_no_file(tmp_path, monkeypatch):
    getter = _Getter(*(_Response(body=b"bad") for _ in range(3)))
    monkeypatch.setattr(_common.requests, "get", getter)
    with pytest.raises(InvalidDownloadError):
        _common.download("u", "src", "f.csv", folder=tmp_path, validate=_reject_bad)
    assert not (tmp_path / "f.csv").exists()


def test_a_cached_file_that_fails_validation_is_downloaded_again(tmp_path, monkeypatch):
    (tmp_path / "f.csv").write_bytes(b"bad")
    getter = _Getter(_Response(body=b"good"))
    monkeypatch.setattr(_common.requests, "get", getter)
    path, _ = _common.download("u", "src", "f.csv", folder=tmp_path, validate=_reject_bad)
    assert path.read_bytes() == b"good" and getter.calls == 1


@pytest.mark.parametrize(("text", "expected"), [("", None), ("  ", None), ("0", 0.0), ("-3.5", -3.5), ("1e3", 1000.0)])
def test_parse_number_accepts_plain_numbers_and_blanks(text, expected):
    assert _common.parse_number(text) == expected


@pytest.mark.parametrize("text", ["nan", "inf", "-Infinity", "1_000", "#N/A", "NA", "1.2.3", "12 MW"])
def test_parse_number_rejects_everything_else(text):
    with pytest.raises(ValueError):
        _common.parse_number(text)
