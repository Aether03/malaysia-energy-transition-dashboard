# Headline findings: Malaysia's electricity transition

**Status:** audited (M2 step 12, 2026-10-02). The independent `audit-my-work` review confirmed every number against both the warehouse and Ember's raw CSV. Its framing corrections are applied below.

**Data:**
- Ember Yearly Electricity Data (CC BY 4.0): findings 1–2 from the pipeline run of 30 Sep 2026 (unchanged in Ember's 6 Oct 2026 release, which did not revise Malaysia); finding 3 re-verified on that release (run 46, 7 Oct 2026).
- OWID population (CC BY 4.0).

**Latest complete year:** 2025.

Each finding states a number, the caveats that limit it, and the query that reproduces it (`sql/showcase/`).

**Common caveats:**
- All numbers are on Ember's basis: grid generation and capacity as Ember publishes them.
- For recent years, Ember carries some Sabah and Sarawak generation forward from earlier DOSM figures, and its 2025 capacity repeats 2024 values for solar and hydro. The latest levels are partly estimated and may be revised.
- Independent sources also disagree on Malaysia's generation by 6–14% in recent years (OWID and DOSM; see `docs/reconciliation.md`).

---

## 1. Malaysia's renewable share roughly doubled in a decade, mostly in one hydro-driven step

**On 3-year averages, the renewable share of generation rose from 9.6% (2013–15) to 19.7% (2023–25).**
- Most of the gain came in **2015–17**: the share went from 10.0% to 13.5% to 17.4%, as large hydro commissioned around 2014–16 ramped up.
  - Hydro capacity jumped from 4.8 GW (2014) to 6.0 GW (2015).
  - Hydro output then rose from 13.9 TWh (2015) to 34.6 TWh (2025) as those plants reached full output.
- Since 2017 the share has added **3.0 points**. **Hydro and solar now share the growth:**
  - From 2017 to 2025, hydro supplied 52% of the renewable increase and solar 42%.
  - Solar rose from 0.3 to 6.6 TWh.

**Caveats:**
- The base year matters, because 2015 had the decade's lowest hydro capacity factor. Measured from 2015 alone, hydro supplied 74% of the increase; from 2017, 52%.
- Ember does not separate large from small hydro, and hydro output varies with rainfall.

**Source queries:**
- `04_rolling_avg.sql` (3-year averages)
- `06_re_growth_decomposition.sql` (base years 2015 and 2017)
- `01_trends.sql`, `05_capacity_factor.sql`

## 2. Each kWh got cleaner, yet power-sector emissions rose 27%, and all the fossil growth was coal

From 2015 to 2025:
- Carbon intensity fell **9.5%** (669 → 606 gCO₂e/kWh).
- Generation grew **40%** (150.1 → 210.4 TWh) as demand rose 39%.
- So power-sector emissions **rose 27%** (100.5 → 127.4 MtCO₂e).

**All the fossil growth was coal.**
- Gas output was flat (70.0 → 70.4 TWh). Coal output grew **49%** (63.5 → 94.4 TWh), and coal is now 44.9% of generation.
- The fossil fleet itself got slightly dirtier (739 → 752 gCO₂e/kWh). The average kWh got cleaner only because hydro and solar grew.

**Caveats:**
- The emissions are Ember's estimates. They use lifecycle factors that include upstream methane, supply chain and manufacturing, expressed as CO₂e over 100 years ([Ember methodology v1.2, May 2024](https://ember-energy.org/app/uploads/2024/05/Ember-Electricity-Data-Methodology.pdf); the 2026 release may use a later version).
- Ember applies a fixed IPCC hydro factor (24 g/kWh), which does not capture methane from tropical reservoirs.
- Electricity generation only; this is not Malaysia's total emissions.

**Source query:** `07_emissions_vs_demand.sql`.

## 3. Among its ASEAN peers, Malaysia is in the lower half on renewable share and near the bottom on carbon intensity

In 2025, among the six largest ASEAN power systems:
- **Renewable share:** Malaysia's 20.4% ranks **4th of 6**, behind Vietnam (46.0%), the Philippines (23.3%) and Thailand (21.7%). It was also 4th in 2023 and 2024.
- **Carbon intensity:** at 606 gCO₂e/kWh, Malaysia narrowly trails the Philippines (595) for **5th of 6**. Only Indonesia (705) is higher. Malaysia was **4th in 2023 and 2024**, so this rank is close and may move with revisions.
- **Why intensity lags:** Thailand's renewable share is only 1.3 points higher than Malaysia's, yet its electricity is 80 g/kWh cleaner (526 g/kWh), because its generation is mostly gas (61.5%), with little coal (16.7%). Malaysia's mix is 44.9% coal and 33.4% gas.

The coal-to-gas balance therefore matters as much as the renewable share.

**Caveats:**
- **Peer set.** The six are Indonesia, Vietnam, Malaysia, Thailand, the Philippines and Singapore, the largest by 2025 generation; Laos is 7th at 52 TWh in 2024. Adding Cambodia, which also reports 2025, Malaysia ranks 5th of 7 on renewable share and 6th of 7 on intensity.
- **Generation basis.** Thailand imports about 16% of its demand (36.9 TWh in 2025, mostly from Laos), which generation-based shares leave out.
- **Data vintage.** Ember's release of 6 Oct 2026 revised Thailand for every year from 1985: its 2025 bioenergy output doubled (10.2 → 22.1 TWh), lifting its renewable share from 16.6% to 21.7%. That moved Malaysia from 3rd to 4th on renewable share. Vietnam and the Philippines were revised slightly; Malaysia was not. Peer ranks can move with any release.

**Source query:** `03_ranking.sql` (coal and gas shares: the same `mart.generation_annual` pattern as `01_trends.sql`).

---

## A note on measurement (not a finding)

Malaysia's **official** renewable share of installed capacity was **31% at the end of 2025** (government figure), which met the 2025 target. Ember's capacity data gives **24.4%**.

The gap has two plausible causes:
- **Definition.** The official ASEAN definition counts off-grid and rooftop capacity. Ember takes non-fossil capacity from IRENA and includes distributed solar only "where possible".
- **Lag.** Ember's 2025 capacity repeats its 2024 values for solar (3.07 GW) and hydro (6.27 GW).

The report shows both figures side by side (P1, P2), so the Ember figure is never read as a missed target. See `Documents/plans/M2_plan.md`, "Step 1 outcome".
