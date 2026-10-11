"""Every page of the web showcase renders without an exception (M6 step 2; content checks join in steps 4-5)."""

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
PAGES = sorted((APP / "pages").glob("*.py"))


def test_the_navigation_lists_every_page_file():
    entry = (APP / "streamlit_app.py").read_text(encoding="utf-8")
    assert {p.name for p in PAGES} == {
        name.split("/")[-1] for name in __import__("re").findall(r'"(pages/\w+\.py)"', entry)
    }


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_page_renders(page):
    at = AppTest.from_file(str(page), default_timeout=30).run()
    assert not at.exception
    assert at.title, "every page has a title"


def test_the_cloud_installs_the_versions_the_tests_run():
    """Community Cloud installs only app/requirements.txt (M6 plan Q8); each pin there must equal the root pin that
    local runs and CI's main job test with, so a drift can't ship untested."""

    def pins(path: Path) -> dict[str, str]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return dict(line.split("==") for line in lines if "==" in line and not line.startswith("#"))

    app, root = pins(APP / "requirements.txt"), pins(APP.parent / "requirements.txt")
    assert set(app) == {"streamlit", "plotly", "pandas", "pyarrow"}
    assert {name: root.get(name) for name in app} == app
