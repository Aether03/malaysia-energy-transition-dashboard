# Reconciliation evidence (NFR-03, task 1.11)

**Question:** do the warehouse's headline figures reproduce Ember's own numbers?
**Tolerance:** ±0.5% relative difference.
**Scope:** Malaysia, latest complete year (2025). Ember yearly release, `Last-Modified: Tue, 22 Sep 2026 16:24:55 GMT`.

## Check 1: SQL against Ember's raw rows (`sql/showcase/00_reconciliation.sql`), 2026-09-30

| Metric | Warehouse | Ember-derived value | Diff | Result |
|---|---|---|---|---|
| Total generation (TWh) | 210.370 | 210.370 (`Total generation` row) | 0.0000% | PASS |
| Renewable share of generation (%) | 20.411 | 20.412 (Ember's own `Renewables` aggregate) | −0.0049% | PASS |
| Carbon intensity (gCO₂e/kWh) | 605.547 | 605.547 (emissions ÷ generation, recomputed) | −0.0001% | PASS |
| Solar generation (TWh) | 6.639 | 6.639 (`Solar` row) | 0.0000% | PASS |
| Gas share of generation (%) | 33.444 | 33.443 (`Gas` share) | +0.0018% | PASS |

## Check 2: independent recomputation, 2026-09-30

A separate agent with a fresh context recomputed all five from the raw CSV using pandas only. It had no access to the SQL or the database.

| Metric | Independent value | Warehouse | Diff | Result |
|---|---|---|---|---|
| Total generation (TWh) | 210.370 | 210.370 | 0.000% | PASS |
| Renewable share (%) | 20.411 | 20.411 | 0.001% | PASS |
| Carbon intensity (gCO₂e/kWh) | 605.547 | 605.547 | 0.000% | PASS |
| Solar generation (TWh) | 6.639 | 6.639 | 0.000% | PASS |
| Gas share (%) | 33.444 | 33.444 | −0.001% | PASS |

The renewable share in check 2 was summed as (Hydro + Bioenergy + Wind + Solar + Other renewables) ÷ (those + Coal + Gas + Other fossil + Nuclear).

**Verdict:** 5/5 pass both checks. The largest difference is 0.005%, which is rounding in Ember's published 3-decimal shares.

## Re-run
```bash
.venv/Scripts/python -c "from pathlib import Path; from pipeline import db; c=db.connect().cursor(); c.execute(Path('sql/showcase/00_reconciliation.sql').read_text(encoding='utf-8')); [print(r) for r in c.fetchall()]"
```

## Known cross-check warnings (M2, 2026-09-30)
These WARN rules fire by design. Each gap is a real difference between sources or a known source limitation, not a pipeline fault. BLOCKING rules all pass.

| Rule | Rows | What it shows | Handling |
|---|---|---|---|
| `OWID_GEN_WITHIN_5PCT` | MY 2023, 2024 | OWID's Malaysia generation is 7.4% and 6.2% below Ember's (187.8 vs 202.8 TWh; 198.1 vs 211.2). OWID's energy dataset uses a different upstream vintage; the gap narrows to 4.4% for 2025 | Ember stays the single generation basis. OWID supplies population only |
| `DOSM_SUPPLY_WITHIN_10PCT` | MY 2022, 2023 | Ember generation is above DOSM's total supply by a gap that grows over time: 4.3% (2018), 6.0%, 6.8%, 7.0%, 11.4% (2022), 14.1% (2023). DOSM's series ends in Jun 2024. The cause is **not established**; plausible contributors are self-generation, co-generation and rooftop solar outside DOSM's supply statistics | Cross-check only (S1); no report page uses DOSM. The growing gap is stated as a caveat, not a finding |
| `CF_AT_MOST_1` | 117 source-years | Ember's capacity is too small for the generation it reports. Examples: geothermal ("Other renewables") at 0–0.01 GW for the Philippines and Indonesia beside 10–15 TWh; Singapore waste-to-energy; Indonesian captive coal and bioenergy. Malaysia: only Other fossil 2024 (CF 1.10) | `030` treats implausible **renewable** capacity as unreported, so the RE capacity share is NULL for PHL, IDN, SGP and 4 VNM years instead of being understated. Capacity-factor visuals blank values above 1 |
| `STALE_COUNTRY_YEARS` | Brunei, Laos, Myanmar | Ember's data for these three ends in 2024 | The ASEAN ranking uses the latest year all selected countries share (doc 03 P5) |

## DAX vs SQL twins (M2 step 7, 2026-10-02)
`tools/dax_twin_check.py` runs each question in DAX against the model open in Power BI Desktop (via Desktop's own ADOMD client, `tools/dax_query.ps1`) and in SQL against the mart views, mostly through the `sql/showcase` queries. Measured values must agree within max(0.05, 0.1%); years, ranks and counts must match exactly.

**Result: 14/14 PASS.**
- P1 KPIs + YoY (2025, and 2015 to prove the slicer is honoured)
- P2 mix TWh/share; D1 Vietnam 2020 (country in context)
- Demand growth (every year)
- Capacity factor (MY 2024 leap year and 2025; Philippines 2023 geothermal gap)
- P5 values and the rank card: 6 default peers, Singapore deselected, Brunei added (common year 2024, n = 7), range 2015–2020, P1 at 2024
- Target chart 2000–2050

The independent review's fix to the `'Compare Country'` selection measures was verified with query-scoped `DEFINE MEASURE` overrides on the open model, before a reload. The first model run had failed on `IF` returning a table.

## M3: hourly grids (step 6, 2026-10-03)

### Part A: Thailand "sum of regional demand" vs published national peak (doc 05 §2.4 Unverified item)

Our series = sum of the 5 regional `*_demand` columns of Zenodo 17109911 (EGAT website data, hourly MW). Both maxima were confirmed in `dw.fact_grid_hourly` (TH_EGAT) and recomputed from `system_2023.csv` / `system_2024.csv`.

| | 2023 | 2024 |
|---|---|---|
| **Our max (sum of regional demand, hourly)** | 33,443.2 MW, 2023-05-06 21:00 | 35,559.8 MW, 2024-04-29 21:00 |
| ERC infographic "Peak (MW)" and time | 34,827 MW at 21.41 | 36,699 MW at 21.00 |
| EGAT press release (2023 only) | 34,826.5 MW on 6 May 2023 (no time given) | none found |
| EGAT annual table "ความต้องการพลังไฟฟ้าสูงสุด" (system peak, date and time not shown) | 34,130.5 MW | 36,477.8 MW |
| Gap, ours vs ERC/EGAT-release peak | −1,383 MW (−3.97%) | −1,139 MW (−3.10%) |
| Gap, ours vs EGAT annual-table peak | −687 MW (−2.01%) | −918 MW (−2.52%) |
| Timestamps coincide with ours? | Same day. Published 21:41, ours is the 21:00 hourly value | Same day and hour (21:00, 29 Apr 2024) |

**Primary sources used**
- EGAT annual table (Thai page, current to 2568): https://www.egat.co.th/home/statistics-demand-annual/. Rows `2566 34,130.50 +5.82` and `2567 36,477.80 +6.88`. The table has no footnote and does not say what the system covers. **The English page `/home/en/statistics-demand-annual/` is stale: it stops at 2564 (30,135.30).** Use the Thai page. An automated page summary mislabelled the English rows as 2023/2024, so check the year column before quoting.
- EGAT open-data catalogue entry for the same series: https://gdcatalog.egat.co.th/dataset/s_00000002. Description: "ข้อมูลความต้องการไฟฟ้าสูงสุดของระบบ กฟผ. รายปี" (annual maximum demand of the EGAT system), unit MW, source "EGAT generation and transmission statistics".
- EGAT press release, 23 May 2023: https://www.egat.co.th/home/20230523-pre01/. Quote: "ความต้องการใช้ไฟฟ้าสูงสุด (Peak) ของปีนี้ทะลุถึง 34,826.5 เมกะวัตต์ เมื่อวันที่ 6 พฤษภาคม". It does not say which system.
- ERC infographic image (Peak MW and time per year, 2560 to 2567): https://www.erc.or.th/th/infographics/3127 (image `.../tinymce/46-1834e750ad686e957705a1fd0df999bc/1.jpg`). Reads 2566: 34,827 at 21.41; 2567: 36,699 at 21.00. It defines nothing.
- Dataset description (Zenodo): https://zenodo.org/records/17109911. Says only that the data was "collected from the official website" of EGAT. It does not define "demand" or say whether SPP/VSPP, PEA or MEA are included.

**Second-hand, Unverified** (no primary link found; pointers only)
- Thai media attribute the 36,699.9 MW (29 Apr 2024, 21:00) and 34,826.5 MW figures to the combined "3 การไฟฟ้า" system (EGAT, MEA, PEA), e.g. https://www.dailynews.co.th/news/3389381/. A Ministry of Energy spokesperson is the cited source in https://www.nationthailand.com/sustainability/40037782. No primary document states the scope.
- Several outlets report a later 2024 record of 36,792.1 MW on 2 May 2024 at 22:24 (e.g. https://www.thansettakij.com/sustainable/energy/594748 and a search snippet). If correct, 36,699 is not the 2024 annual maximum. Not confirmed at EGAT, EPPO or ERC. EGAT's own annual figure (36,477.8) matches neither.
- The EPPO site returned HTTP 403 to automated fetches, so no EPPO figure was obtained. EGAT's 2024 annual report was not found with a peak figure.

**What the data can and cannot test**
- Timestamp: 2024 coincides (21:00, same day), so "hourly mean vs 21:00 instant" cannot explain the 3.1% gap. For 2023 the published peak is at 21:41, and our hourly values on either side are 33,443 (21:00) and 33,136 (22:00). An intra-hour peak 1.4 GW above both is possible but is not shown by the data.
- Our top-5 hours in 2024 are 29 Apr, 2 May, 27 Apr, 30 Apr and 29 Apr (22:00). Press reports place record peaks on 27 Apr, 29 Apr and 2 May (21:00 to 22:24), so the series tracks the national peak days but sits 2 to 4% lower in level.
- Regional generation + imports − exports does NOT reproduce the demand sum. At the peak hour: 2023 generation 29,037.0 + imports 1,504.1 − exports 585.9 = 29,955.2 vs demand 33,443.2 (gap 3,488 MW); 2024 31,380.0 + 1,540.4 − 638.5 = 32,281.9 vs 35,559.8 (gap 3,278 MW). Across the year the gap averages 2,267 MW (2023) and 2,474 MW (2024), correlation 0.955 to 0.959. So the dataset's "generation" columns cover less than its "demand" columns; the shortfall is plausibly SPP/VSPP/rooftop or other output not in the generation columns, but the files do not say. **Unverified.**
- Observation only: demand sum + exports at the peak hour is 34,029.1 MW (2023) and 36,198.3 MW (2024), within −0.3% and −0.8% of EGAT's annual-table peaks (34,130.5 and 36,477.8). That fits "EGAT peak = demand + exports", but the dates of EGAT's annual peaks are not published, so it may be coincidence. **Unverified.**

**Most likely explanation:** the published peaks are instantaneous (or minute-level) values for a system whose definition (EGAT system vs EGAT+MEA+PEA, treatment of SPP/VSPP, exports) is not stated by any primary source. The regional-demand sum is an hourly series with an undocumented coverage. The gap is 2.0 to 4.0%, in the same direction in both years, and is not fully explained.

**Recommendation for the P4 label: "Sum of regional demand (EGAT)".** The sum is not shown to be the national system demand: the gap is 2 to 4% and falls short of every published peak, no primary source defines the published peak's scope, and the dataset does not define its own "demand". Do not call it the national peak or compare it to EGAT's record figures. Add a footnote: "Hourly mean; published system peaks (instantaneous, EGAT/ERC) are 2 to 4% higher." Resolves doc 05 §2.4 as written ("if they don't reconcile, label it sum of regional demand"). If the gap is later explained, the label can change.

### Part B: FR-22 sample-week hand check, 2024-04-22 to 2024-04-28 (local), pandas from raw files vs SQL

Load factor = mean hourly MW ÷ peak, over the hours present (168 per grid, 0 imputed). Tolerances: peak ±0.1 MW, load factor ±0.01 pp. Scripts were run once, not committed.

**TH_EGAT** (`system_2024.csv`, sum of 5 `*_demand` per hour)

| Metric | pandas (raw CSV) | SQL (`dw.fact_grid_hourly`) | Diff | Result |
|---|---|---|---|---|
| Hours | 168 | 168 | 0 | PASS |
| Peak (MW) | 35,205.7 (2024-04-27 21:00) | 35,205.7 (2024-04-27 21:00) | 0.0 | PASS |
| Mean (MW) | 29,757.504 | 29,757.504 | 0.000 | PASS |
| Load factor (%) | 84.5247 | 84.5247 | 0.0000 pp | PASS |

**SG_EMA** (`20240422.xls`, System Demand (Actual), hour h = mean of half-hours ending h:30 and h+1:00)

| Metric | pandas (raw XLS) | SQL (`dw.fact_grid_hourly`) | Diff | Result |
|---|---|---|---|---|
| Hours | 168 | 168 | 0 | PASS |
| Peak (MW) | 7,984.405 (2024-04-26 15:00) | 7,984.4 (2024-04-26 15:00) | −0.005 | PASS |
| Mean (MW) | 7,063.705 | 7,063.707 | +0.002 | PASS |
| Load factor (%) | 88.4688 | 88.4689 | +0.0001 pp | PASS |

The only differences are the `DECIMAL(10,1)` rounding of stored values on the Singapore half-hour means. **Part B: 8/8 pass.**
