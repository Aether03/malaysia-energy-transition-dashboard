"""Rebuild every report page in order (M2 steps 8-10, M5 step 4): Overview, Generation, Regions, State reliability, Grid load, Forecast, ASEAN, About, Data quality, then hidden pages.

The nav rail lists only pages that exist, so the builders run twice: the first pass creates every
page folder, the second draws the complete rail on each page.

    .venv/Scripts/python tools/build_report.py
"""

from __future__ import annotations

import build_d1_page
import build_overview_page
import build_p2_page
import build_p3_page
import build_p3b_page
import build_p4_page
import build_p4b_page
import build_p5_page
import build_p6_page
import build_p6b_page
import build_tooltips
import report_builder as rb

BUILDERS = (
    build_overview_page,
    build_p2_page,
    build_p3_page,
    build_p3b_page,
    build_p4_page,
    build_p4b_page,
    build_p5_page,
    build_p6_page,
    build_p6b_page,
    build_d1_page,
    build_tooltips,
)
ORDER = [
    rb.OVERVIEW_PAGE,
    build_p2_page.PAGE,
    build_p3_page.PAGE,
    build_p3b_page.PAGE,
    build_p4_page.PAGE,
    build_p4b_page.PAGE,
    build_p5_page.PAGE,
    build_p6_page.PAGE,
    build_p6b_page.PAGE,
    build_d1_page.PAGE,
    build_tooltips.T2_PAGE,
]


def main() -> None:
    for _ in range(2):
        for builder in BUILDERS:
            builder.main()
    rb.set_page_order(ORDER)
    print("Page order:", ", ".join(ORDER))


if __name__ == "__main__":
    main()
