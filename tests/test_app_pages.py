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
