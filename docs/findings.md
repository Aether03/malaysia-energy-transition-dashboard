# Headline findings: Malaysia's electricity transition

**Status:** draft for audit (M2 step 12, 2026-10-02) · **Data:** Ember Yearly Electricity Data (CC BY 4.0), OWID population (CC BY 4.0), pipeline run of 30 Sep 2026 · **Latest complete year:** 2025

Each finding states a number, the caveat that limits it, and the query that reproduces it (`sql/showcase/`). The numbers are on Ember's basis: grid generation and grid capacity as Ember publishes them.

---

## 1. Malaysia's renewable share doubled in a decade, but hydropower did most of the work, not solar

The renewable share of Malaysia's electricity generation rose from **10.0% in 2015 to 20.4% in 2025**. Renewable generation grew by **28.0 TWh**:
- Hydropower supplied **20.7 TWh (74%)** of that increase.
- Solar supplied **6.4 TWh (23%)**, from almost nothing (0.3 TWh in 2015).
- Bioenergy supplied the rest (1.0 TWh).

Solar is the fastest-growing source in relative terms. In absolute terms, the decade's renewable gain came mainly from more hydro output.

**Caveats:**
- Ember does not separate large from small hydro, so the data cannot say which plants or which region delivered the increase.
- Hydro output also varies with rainfall from year to year. The 3-year rolling average (`04_rolling_avg.sql`) shows the rise is a trend, not a single wet year: 17.7% for 2019–2021 and 19.7% for 2023–2025.

**Source queries:** `06_re_growth_decomposition.sql`, `01_trends.sql`, `04_rolling_avg.sql`.

## 2. Each kWh got cleaner, yet power-sector emissions still rose by a quarter

From 2015 to 2025:
- Carbon intensity fell **9.5%**, from 669 to 606 gCO₂e/kWh.
- Generation grew **40%**, from 150.1 to 210.4 TWh, as demand rose 39%.

So power-sector emissions still **rose 27%**, from 100.5 to 127.4 MtCO₂e. Coal generation grew **49%** (63.5 → 94.4 TWh) over the same period. Coal is still the largest single source, at 44.9% of generation in 2025.

**Caveats:**
- The emissions are Ember's estimates. They are lifecycle-based and include upstream methane, which is why the unit is CO₂e.
- They cover electricity generation only, not Malaysia's total emissions.
- 2025 is Ember's latest release year and may be revised.

**Source query:** `07_emissions_vs_demand.sql` (intensity: `02_yoy_lag.sql`).

## 3. Among its ASEAN peers, Malaysia ranks 3rd of 6 on renewable share but 5th of 6 on carbon intensity

**Renewable share.** In 2025, Malaysia's 20.4% renewable share puts it **3rd of the six largest ASEAN power systems** (Indonesia, Malaysia, Philippines, Singapore, Thailand, Vietnam). It is behind Vietnam (45.3%) and the Philippines (23.3%).

**Carbon intensity.** On carbon intensity Malaysia is **5th of 6** at 606 gCO₂e/kWh; only Indonesia (705) is higher. Thailand has a lower renewable share (16.6%) but cleaner electricity (546 g/kWh), because it relies on gas (65.5% of generation) rather than coal (17.8%). Malaysia's mix is 44.9% coal and 33.4% gas.

The renewable share alone therefore understates how far Malaysia's grid sits from its cleaner peers. The coal-to-gas balance matters as much.

**Caveats:**
- The comparison uses the latest year all six report (2025), and the peer set is this project's choice (doc 01).
- Brunei, Cambodia, Laos and Myanmar are excluded by default but can be added on the ASEAN page.

**Source query:** `03_ranking.sql` (coal and gas shares: `01_trends.sql` pattern on `mart.generation_annual`).

---

## A note on measurement (not a finding)

Malaysia's **official** renewable share of installed capacity was **31% at the end of 2025** (government figure), which met the 2025 target. Ember's grid-capacity basis gives **24.4%**.

The gap is a matter of definition, not an error in either source:
- The official ASEAN definition also counts off-grid and rooftop capacity.
- Ember's capacity data covers the grid.

The report shows both side by side (P1, P2), so the Ember figure is never read as a missed target. See `Documents/plans/M2_plan.md`, "Step 1 outcome".
