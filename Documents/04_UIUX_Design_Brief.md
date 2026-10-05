# 04 — UI/UX Design Brief: Malaysia Energy Transition Dashboard

**Status:** Approved 2026-09-30 · **Updated:** 2026-09-30 · **Builds on:** [01 PRD](01_Product_Requirements.md), [03 App Flow](03_App_Flow.md) (Approved) · **Next:** 05 Data Schema

> **Scope:** the visual system for the **Power BI report (v1, light theme)**, delivered as one theme JSON file plus layout rules. The same tokens carry over to the **post-v1 Streamlit app**, which also gets the validated dark values. Every colour below was **measured**: categorical palettes with the `dataviz` skill's validator (`validate_palette.js`, OKLab ΔE ×100 under simulated protan/deutan vision), and text/UI colours as WCAG contrast ratios.
> Labels: **Decided** · **Recommended** · **Unverified**.

## 1. Design principles
1. **Engineering report, not infographic.** Calm neutrals and one navy accent, with colour reserved for data. It should look like a utility's internal analytics pack (doc 01 tone).
2. **Every title is a takeaway.** "Solar tripled since 2019, but coal still supplies 40%" beats "Generation by source". The numbers carry the story.
3. **Colour follows the entity, everywhere.** Solar is the same yellow on every page and in every visual, and Malaysia is always navy. Filters never repaint survivors.
4. **Honest by default.** Units on every axis and KPI, gaps shown as gaps, "not reported" shown as such, and caveats in footnotes, not hidden.
5. **Readable without colour.** Legends plus direct labels, a table view for every chart, and status shown as icon + word.

## 2. Typography
Power BI can only use fonts installed on the viewer's machine, not web fonts. **Segoe UI** is Windows' system font and Power BI's default, so it renders identically for every Windows viewer and in PDF/PNG exports (**Decided**).

| Token | Role | Font | Size (pt) | Weight | Colour token |
|---|---|---|---|---|---|
| `type.page-title` | Page takeaway title | Segoe UI Semibold | 20 | 600 | `text.primary` |
| `type.page-subtitle` | Scope line ("Malaysia · 2000–2025 · Ember, OWID") | Segoe UI | 11 | 400 | `text.secondary` |
| `type.kpi-value` | KPI number | Segoe UI Semibold | 28 | 600 | `text.primary` |
| `type.kpi-label` | KPI label + unit | Segoe UI | 10 | 400 | `text.secondary` |
| `type.kpi-delta` | YoY change | Segoe UI Semibold | 10 | 600 | `status.*-text` + ▲/▼ glyph |
| `type.visual-title` | Chart title (takeaway) | Segoe UI Semibold | 12 | 600 | `text.primary` |
| `type.body` | Findings text, table cells | Segoe UI | 10 | 400 | `text.primary` |
| `type.axis` | Axis labels, legends, data labels | Segoe UI | 9 | 400 | `text.secondary` |
| `type.footnote` | Sources, caveats, consent notice | Segoe UI | 9 | 400 | `text.muted` |
| `type.nav` | Nav rail labels | Segoe UI Semibold | 10 | 600 | `nav.text` |

- **Numbers:** thousands separators; 1 decimal for TWh, % and gCO₂/kWh; whole numbers for MW. Units always in the label or axis title, never implied. Right-align numeric table columns. **Unverified:** whether Segoe UI's default digits are tabular (equal width); check column alignment at build and switch table numerals to DIN (a built-in Power BI font) if they drift.
- **Streamlit (post-v1):** the same scale, in the `"Segoe UI", system-ui, sans-serif` stack.

## 3. Colour palette

### 3.1 UI tokens (light, v1)
Contrast is measured against `surface.card` `#fcfcfb` / `surface.page` `#f4f3ef`.

| Token | Hex | Use | Contrast (card / page) | WCAG |
|---|---|---|---|---|
| `surface.page` | `#f4f3ef` | Report canvas background | — | — |
| `surface.card` | `#fcfcfb` | Visual backgrounds, KPI cards | — | — |
| `border.subtle` | `#e4e3df` | Card borders, gridlines (decorative only) | 1.25 / 1.16 | Decorative; not relied on |
| `text.primary` | `#0b0b0b` | Titles, values, body | **19.17** / 17.73 | AA ✓ |
| `text.secondary` | `#52514e` | Labels, axes, subtitles | **7.73** / 7.15 | AA ✓ |
| `text.muted` | `#6b6a66` | Footnotes, source credits | **5.27** / 4.88 | AA ✓ |
| `accent.navy` | `#104281` | Nav rail, **Malaysia highlight**, key lines | **9.66** / 8.93 | AA ✓ |
| `accent.blue` | `#256abf` | Links, selected-state outlines | **5.26** / 4.86 | AA ✓ |
| `nav.text` | `#ffffff` on navy | Nav labels | **9.91** | AA ✓ |
| `nav.text-inactive` | `#cde2fb` on navy | Inactive nav labels | **7.49** | AA ✓ |
| `peer.muted` | `#8a8984` | Non-Malaysia lines/bars on P5 | **3.41** / 3.16 | ≥3:1 graphics ✓ |

### 3.2 Energy-source categorical palette (Decided after validation)
Fixed order = stacking order, bottom to top (fossil first, then renewables). The same entity keeps the same colour on every page (principle 3).

| Slot | Source (Ember category) | Light | Dark (post-v1) |
|---|---|---|---|
| 1 | Coal | `#a0522d` | `#a0522d` |
| 2 | Other fossil (oil, diesel) | `#4a3aa7` | `#9085e9` |
| 3 | Gas | `#eb6834` | `#d95926` |
| 4 | Hydro | `#2a78d6` | `#3987e5` |
| 5 | Bioenergy | `#008300` | `#008300` |
| 6 | Wind & other renewables | `#1baf7a` | `#1ca3a6` |
| 7 | Solar | `#eda100` | `#c98500` |

Nuclear is not generated in Malaysia or the peer set. If a D1 country ever shows it, it folds into "Other fossil & other", with no 8th generated hue.

**Validator results (adjacent pairs, the right pairlist for stacked areas and bars):**
| Mode | Lightness band | Chroma | Worst CVD ΔE (≥8 target) | Worst normal-vision ΔE (≥15 floor) | Contrast |
|---|---|---|---|---|---|
| Light (surface `#fcfcfb`) | PASS | PASS | **9.1** (solar↔wind, protan) | **15.6** (wind↔bio) | WARN: wind 2.74:1, solar 2.11:1 |
| Dark (surface `#1a1a19`) | PASS | PASS | **16.0** (solar↔wind, protan) | **19.2** (wind↔bio) | PASS, all ≥3:1 |

**Relief for the light-mode contrast WARN (mandatory, not optional):** stacked areas carry **direct labels** at the right edge, the legend is always on, and every chart has Power BI's **Show as table** available. Coal was re-stepped from the brown `#6b4f3a` to sienna `#a0522d`, because the validator flagged the first as reading grey (chroma floor). Other fossil sits between coal and gas because next to hydro it failed dark-mode CVD (ΔE 1.9).

**Pair cap for all-pairs charts:** scatter/bubble charts don't colour by source (P5's scatter colours by country: Malaysia navy, peers muted), so the all-pairs limit doesn't bite.

### 3.3 Country highlight (P5, D1)
**Malaysia = `accent.navy` `#104281`, 2.5 px line. Peers = `peer.muted` `#8a8984`, 1.5 px, direct-labelled at the line end.** This is highlight-versus-context, not a categorical palette. Identity comes from direct labels, so it never relies on telling five greys apart. Hover (T2) names the country.

### 3.4 Sequential scale: SAIFI/SAIDI map and heatmap (P3, P4)
One hue, **blue**, light→dark = better→worse (more interruptions or higher load). The validator checks it as ordinal steps `#86b6ef → #5598e7 → #256abf → #184f95 → #0d366b`: **ALL PASS** (monotone lightness, step gaps ≥ 0.06, light end 2.06:1). Power BI theme: `minimum #cde2fb`, `center #3987e5`, `maximum #0d366b` (continuous). "Not reported" (Sabah, Sarawak) = `border.subtle` `#e4e3df` plus the label "Not reported", never a data colour. **As built (M4):** the P3b Shape Map gradient runs `#86b6ef` → `#0d366b` (the theme minimum `#cde2fb` was too close to the "not reported" grey); unreported shapes take Shape Map's default grey, with an on-page note. The P3b ranked bar uses solid `accent.blue` with data labels (a gradient fill isn't accepted on the bar). Region series colours on P3 (Peninsular `#730d62`, Sabah `#bc629e`, Sarawak `#52514e`) are kept clear of the energy-source palette, checked with CIEDE2000 under colour-blind simulation.

### 3.5 Status (P6 data quality, pipeline state), fixed
| Status | Mark colour | Text-safe variant | Icon + word |
|---|---|---|---|
| Pass | `#0ca30c` | `#087a08` (5.39:1) | ✓ Pass |
| Warn | `#fab219` | `#8a5a00` (5.77:1) | ! Warn |
| Fail | `#d03b3b` | `#d03b3b` (4.68:1) | ✕ Fail |

YoY deltas on KPI cards use the text-safe variants with ▲/▼ plus sign. **Direction ≠ good/bad automatically:** for RE share, up = good; for carbon intensity, down = good. Each KPI measure declares its polarity (doc 05/06).

### 3.6 Power BI theme JSON mapping (**Recommended** file: `report/theme/energy-transition.json`)
`dataColors` = the 7 light slots in order · `background` `#fcfcfb` · `foreground` `#0b0b0b` · `tableAccent` `#104281` · `good` `#0ca30c`, `neutral` `#fab219`, `bad` `#d03b3b` · `minimum` `#cde2fb`, `center` `#3987e5`, `maximum` `#0d366b` · text classes mapped to §2. Colours are also bound per source in the model (a source dimension column `color_hex`, doc 05), so colour follows the entity even when a filter removes series.

## 4. Spacing, layout and grid
- **Canvas:** 1280 × 720 px (16:9, Power BI default), which is also the PNG export size (**Decided**). A page that can't fit legibly is split rather than made taller: P4 became Grid load + Forecast (M3, 2026-10-04).
- **Spacing scale:** 4 · 8 · 12 · 16 · 24 · 32 px. Visual padding 12. Gap between visuals 16.
- **Regions:**
  - **Nav rail:** x 0–176, navy.
  - **Content:** x 200–1256, with 24 px margins.
  - **Header band:** y 16–88, holding the title, subtitle, "Data as of", Reset and ⓘ.
  - **Body:** y 104–680.
  - **Footnote strip:** y 688–712.
- **Grid:** the content area is a 12-column grid with 16 px gutters (column ≈ 73 px). KPI rows use 5 equal cards (P1) or 3 (region cards on P3: one card per region, 5 callouts in a 3-column table layout; **as built, M4**).
- **Wireframe, P1 (other pages follow the same frame):**

```
┌─────────┬──────────────────────────────────────────────────────────────┐
│  NAV    │ Solar is rising, but fossil fuels still supply ~80%   [↺][ⓘ]│
│ ● Over. │ Malaysia · 2024 · Data as of 15 Sep 2026                      │
│ ○ Gen.  ├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│ ○ Reg.  │ 190 TWh  │ 19.8 %   │ 80.2 %   │ 585 g/kWh│ 5.6 MWh/cap      │
│ ○ Load  │ ▲2.1%    │ ▲1.2 pp  │ ▼1.2 pp  │ ▼1.0%    │ ▲1.8%            │
│ ○ ASEAN ├──────────────────────────────┬───────────────────────────────┤
│ ○ About │ Generation mix 2000–2024     │ RE capacity vs NETR target     │
│         │ (stacked area, labelled)     │ 31% · 40% · 70% markers        │
│         ├──────────────────────────────┴───────────────────────────────┤
│         │ Malaysia ranks 4 of 6 on RE share → │ 3 findings (text)        │
│         ├──────────────────────────────────────────────────────────────┤
│         │ Sources: Ember (CC BY 4.0), OWID (CC BY 4.0) … footnotes     │
└─────────┴──────────────────────────────────────────────────────────────┘
```
*(Numbers are placeholders, not data.)*
- **Breakpoints:** not applicable to the Power BI report (fixed canvas). The Power BI **mobile layout** is out of scope for v1 (**Recommended**). Streamlit (post-v1) uses its own responsive columns and collapses to one column under 768 px.

## 5. Components
| Component | Variants | States | Used on (doc 03) |
|---|---|---|---|
| **Nav rail** (buttons or page navigator) | Icon + label | Default (`nav.text-inactive`) · Hover (white, 8% white overlay) · **Selected** (white text, 4 px `#86b6ef` left bar) · Focus (2 px white outline) | All pages |
| **KPI card** (Card visual) | Value + label + YoY delta; P3 region variant has no delta | Default · Hover (border → `accent.blue`, T1 tooltip) · Blank → "No data for <year>" measure · Clickable (P1) shows a "→" affordance | P1, P3 |
| **Rank card** | "Ranks N of M" + arrow | Default · Hover · Click → P5 | P1 |
| **Slicers** | Year single (P1), year range between (P2, P3, P5, D1), dropdown (source, country, grid), date (P4) | Default · Hover · Selected (`accent.blue` chip) · Disabled (e.g. Peninsular grid before GSO consent: hidden, not greyed, per doc 03) | P1–P5, D1 |
| **Toggle** (field parameter / bookmark buttons) | TWh │ %, SAIFI │ SAIDI, Weekday │ Weekend | Default · Hover · Selected (navy fill, white text) · Focus | P2, P3, P4 |
| **Buttons** | Reset (↺), About (ⓘ), Back (D1) | Default · Hover · Pressed · Focus · Disabled | All; Back on D1 only |
| **Stacked area** | TWh or % | Hover crosshair + tooltip; legend click = highlight | P1, P2, D1 |
| **Line** | Highlight vs muted (P5); actual vs model vs baseline (P4) | Hover tooltip; baseline is dashed `text.secondary`, model is `accent.navy`, actual is `text.primary` | P2, P4, P5 |
| **Bar (ranked)** | Horizontal, sorted, Malaysia navy / others muted, or sequential blue (SAIFI) | Hover; click cross-filters | P2, P3, P5 |
| **Shape Map** | Sequential blue; "Not reported" grey | Hover; click cross-filters | P3 |
| **Heatmap** (matrix + conditional formatting) | Hour × month, sequential blue | Hover value | P4 |
| **Scatter** | RE share × carbon intensity; bubble = demand | Hover T2; drill-through | P5 |
| **Status chip** | Pass / Warn / Fail | Static (icon + word) | P6, P4 banner |
| **Banner** | Info (data source on P4), Warn (forecast worse than baseline) | Static | P4 |
| **Table** | Sources, DQ results, KPI definitions | Row hover · Click filters (DQ) | P6 |
| **Tooltip pages** | T1 KPI definition, T2 country | Hover-triggered, 320 × 240 px | All / P5 |

**Icons and imagery:** Power BI's built-in button shapes and Segoe Fluent Icons glyphs only (they ship with Windows). No photos, logos or flags (doc 03 T2: avoids asset licensing).

**Chart marks (dataviz mark spec):** 2 px lines (Malaysia 2.5 px), 2 px surface gap between stacked segments and bars, gridlines `border.subtle` horizontal only, **no dual-axis charts** (see §8, F1), and no pie or donut charts.

## 6. Motion and feedback
Power BI motion is native and minimal: visual transitions, the loading spinner and tooltips. There are **no custom animations** (**Decided**, fits principle 1). Feedback comes from Power BI's cross-highlight on click and the selected-state styling in §5. No sound or haptics. Streamlit (post-v1) keeps default transitions and respects `prefers-reduced-motion`.

## 7. Accessibility
- **Contrast:** all text tokens are ≥ 4.5:1 (measured, §3.1). Graphics are ≥ 3:1, except the two light-mode source colours whose relief is mandatory (§3.2).
- **Not colour-alone:** legends plus direct labels, status icons plus words, ▲/▼ on deltas, and "Not reported" labels.
- **Alt text** on every visual, in the Power BI *Alt text* field: what it shows plus the takeaway sentence. The export checklist (doc 06) verifies it.
- **Tab order:** set in the Selection pane per page: nav → header controls → slicers → visuals in reading order (left→right, top→bottom).
- **Keyboard:** Power BI's native visual navigation (Ctrl+F6 into the canvas, Tab between visuals, Alt+Shift+F11 for Show as table). It's documented in the README's "How to explore" section.
- **Target size:** buttons and slicer chips ≥ 44 × 44 px at 100% canvas zoom.
- **High-contrast mode:** Power BI adapts to Windows high-contrast themes automatically. Check P1 once in Windows high-contrast (doc 06).
- **Reduced motion:** no custom motion to reduce (§6).
- **Review tools during the build:** `design:accessibility-review` on exported PNGs, and `design:design-critique` on the first page before the rest are built.

## 8. Fixes & improvements
| # | Item | Found in | Fix |
|---|---|---|---|
| F1 | **Dual-axis combo charts** in doc 03: P2 "demand growth (column TWh + YoY % line)" and P4 "monthly peak demand and load factor (combo)". Dual axes are a hard anti-pattern in the `dataviz` method, because two y-scales invite false correlations. | doc 03 P2, P4 | Replace each with **two aligned single-axis charts** sharing the x-axis (P2: annual demand TWh │ YoY growth %; P4: monthly peak MW │ load factor %). Once this doc is approved, Claude makes this one-line change to doc 03 and logs it in the index. |

## 9. Open questions
Resolved in review 2026-09-30: nav labels "Overview · Generation · Regions · Grid load · ASEAN · About" (**Decided**; **as built** after the M3/M4 page splits: Overview · Generation · Regions · State reliability · Grid load · Forecast · ASEAN · About, 8 buttons); accent stays navy `#104281` (**Decided**). Nothing open remains.
