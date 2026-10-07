# Walkthrough script (≤ 2 min)

Journey J2 from doc 03, without the Regions and State reliability pages (they stay out of every published export until the Energy Commission consents; M5 plan Q2). Recorded by Amirul as an MP4 with Snipping Tool, then uploaded through GitHub's README editor so it plays inline and stays out of git history (Q6).

**Target length:** 1:50. The narration is about 210 words, about 1:30 at a calm 140 words a minute; the pauses for hovers and page loads bring it to about 1:50.

## Before recording (not timed)

1. Close Discord and anything else heavy. Desktop needs the RAM.
2. Run `pipeline run` if the data is stale, then open `report/EnergyTransition.pbip` and click **Home → Refresh**.
3. Collapse the **Filters**, **Visualizations** and **Data** panes and set **View → Fit to page**, so the canvas fills the window.
4. On each page you will visit, Ctrl+click **Reset filters** once. Finish on **Overview**.
5. In Desktop, **buttons need Ctrl+click** (nav rail, KPI cards, Back, ⓘ). Slicers, hovers and right-click menus work with a plain click.
6. Snipping Tool → **Record** → select the Desktop window only. Do a dry run once with a stopwatch.

## Script

| Time | Page | Do (click by click) | Say |
|---|---|---|---|
| 0:00–0:14 | Overview | Mouse still on the title. Then hover the **RE Share (%)** card until its hover text appears | "How fast is Malaysia's electricity getting cleaner, and how does it compare with its neighbours? Renewables supplied 20.4% in 2025. Every card explains its own formula and source on hover." |
| 0:14–0:18 | Overview → Generation | Ctrl+click the **RE Share** card | "Clicking a card opens the detail." |
| 0:18–0:36 | Generation | Click **%** in the **Unit** box. Pause 2 s. Click **TWh**. Hover the **Coal** bar in **Capacity factor by source** | "Fossil fuels still supply about 80%. Generation grew 40% since 2015, and all the fossil growth was coal. Capacity factor shows how hard each fleet runs: coal at 81%." |
| 0:36–0:52 | Grid load | Ctrl+click **Grid load** on the rail. Hover the darkest cell in the heatmap (Apr–May, about 21:00) | "Malaysia's grid operator hasn't licensed its hourly data yet, so the grid pages use Thailand's open data as a stand-in, as the banner says. Demand peaks on hot-season evenings." |
| 0:52–1:12 | Forecast | Ctrl+click **Forecast**. Open **Backtest day**, pick any day in **April 2024**. Pause 3 s on the chart | "A day-ahead LightGBM forecast, tested once on all of 2024 under a protocol I locked in advance. It cuts hourly error by 47% against last week's same hour, and April, with Songkran, is its hardest month." |
| 1:12–1:34 | ASEAN → Country Deep Dive | Ctrl+click **ASEAN**. Hover **Vietnam** in the carbon-intensity bars until the country tooltip appears. Right-click **Vietnam** → **Drill through** → **Country Deep Dive**. Pause 2 s. Ctrl+click **Back** | "Among six ASEAN peers, Malaysia is third on renewable share but fifth on carbon intensity, because coal is 45% of its mix. Any country drills through to its own deep dive." |
| 1:34–1:50 | Data quality → About | Ctrl+click **Data quality**. Click **Ember Yearly Electricity Data** in **Rows per source**; the rules table filters. Click it again to clear. Ctrl+click the **ⓘ** at the foot of the rail | "Thirty-four data-quality rules run on every pipeline load; the four warnings are known differences between sources. And every source and licence is credited here. The code and SQL are on GitHub." |

Stop the recording on the About page.

## Checks before uploading

- Length ≤ 2:00 (trim the head and tail in Clipchamp or the Photos app if needed).
- Neither Regions nor State reliability appears in any frame, including during navigation.
- No other window, notification or file path is visible.
- The numbers spoken match the screen: 20.4%, about 80%, 81%, 47%, third and fifth, 34 rules, 4 warnings.
