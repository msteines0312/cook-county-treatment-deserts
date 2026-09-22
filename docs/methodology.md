# Methodology and Decision Log

Every judgment call in the project gets written down here with the reasoning
behind it. When a decision changes, update the entry and note what changed.
The matching constants live in `src/config.py`.

## Data Sources

| Source | What it gives us | Access | Known issues |
|---|---|---|---|
| Cook County ME Case Archive | Death records with cause, date/time, demographics, lat/long | Socrata API, dataset `cjeq-bs86` | Covers ME-jurisdiction deaths only. Around 7% of opioid cases lack coordinates. A few records are dated before 2014 or in the future. Cause text contains typos. |
| FindTreatment.gov (SAMHSA) | Treatment facilities, services offered, payment accepted | JSON export at `/locator/exportsAsJson/v2` | Criticized for outdated listings. Doesn't cover individual buprenorphine prescribers well. |
| Census ACS 5-year | Tract-level race, income, poverty, insurance, vehicle access | Census API (free key) | Margins of error are large for small tracts. |
| Census TIGER/Line | Tract boundaries | Direct download | Vintage must match the ACS year. |
| CDC SVI (optional) | Composite vulnerability score | Direct download | Built from ACS, so it overlaps with our own variables. |

## First look at the data (2026-09-22)

- 32,992 ACCIDENT cases in total. 15,309 have the ME `opioids` flag set.
- 1,117 opioid-flagged accidental cases (7.3%) have no latitude, so they can't be mapped without geocoding the `incident_street` text.
- The date range runs 2008 through 2027 even though the archive officially starts in Aug 2014, so the clean step clips it.
- The cause text has typos (for example "COCIANE"), so a pure keyword search will miss some cases. The ME `opioids` flag works as a safety net.

## Decisions

### D1. What counts as an overdose death
**Rule:** `manner == ACCIDENT` AND the cause text (Lines A, B, and C combined) names a drug AND a poisoning word (toxicity, intoxication, overdose, poisoning).

**Why:** Accidental manner excludes suicides and undetermined cases, which matches the CDC definition of unintentional drug poisoning (ICD-10 X40-X44). Any drug or medication counts. Alcohol alone, carbon monoxide, and solvents don't. Requiring a poisoning word keeps out cases where drug use is mentioned but wasn't the cause. Alcohol plus a drug counts.

**Changed from the first draft (2026-09-22):** the first version also counted any case with the ME `opioids` flag set. Looking at the data showed that flag marks opioid *involvement*, not cause: 308 flagged cases have causes like asthma, drowning, and heart disease. The flag is now only a cross-check.

**Result:** 17,041 overdose deaths. 15,001 of them also carry the ME opioid flag. The other 2,040 are mostly cocaine, meth, PCP, and prescription drug deaths that the flag was never meant to catch.

**Typos:** the cause text misspells fentanyl at least a dozen ways ("FENATANYL", "FENTNAYL", "FENANYL"...), plus "HERION", "OPIOD", and "METHAPHETAMINE". Those are listed explicitly in `config.py` rather than fuzzy-matched, so every match can be explained.

**Consistency over time:** since Sept 2023, `primarycause` merges Lines A, B, and C. Before that it held Line A only. We combine the lines ourselves for every year so the definition doesn't shift in 2023.

### D1b. Analysis window: 2015 through 2025
2014 starts in August (partial year). In the current year, hundreds of cases are still `manner = PENDING` while toxicology comes back (624 for 2026 at the time of writing), so the current year would show a fake drop. 2025 has 17 pending cases, a small enough undercount to accept. The 2024 and 2025 declines are real (they aren't driven by pending cases) and match the national trend.

### D1c. Cases without coordinates
1,333 overdose cases (7.8%) have no lat/long. The missing share is fairly steady by year (5% to 13%, highest in 2014 and 2015), so dropping them wouldn't badly bend the trend, but 95% have a street address. We run those addresses through the Census Bureau batch geocoder, which returns the tract directly. Anything that still doesn't match is dropped, and the final match rate is reported.

**Result:** all 15,708 cases with ME coordinates fall inside a Cook tract. Of the 1,333 without coordinates, 319 had no usable address ("Unknown", blank), and the geocoder matched 487 of the remaining 1,014. 91 of those matches were outside Cook County, which suggests the ME only stores coordinates for addresses inside Cook. That leaves 396 recovered cases (78 exact matches, 318 non-exact). Final coverage is **16,104 of 17,041 deaths (94.5%)** assigned to a tract. The 5.5% we lose is a known undercount, documented here and in the README.

Non-exact matches can land a few doors or a block away (one case matched "E. Delaware" to "W Delaware Pl"). That error is small next to a census tract, so they're kept, and every case has a `geo_source` and `match_type` column for filtering.

### D2. Unit of analysis: census tract
Tracts (about 1,300 in Cook County, roughly 4,000 people each) are small enough to show neighborhood variation, and they're the level where ACS data exists. Community areas would give more stable rates but only cover Chicago, not suburban Cook.

### D3. Place of death, not place of residence
The ME records where the incident happened and, separately, the residence ZIP. We map the incident location because that's where people are when they die, and it's the only field with coordinates. Tradeoff: tracts with a lot of daytime or transient population (the Loop, transit hubs) may look worse than their residents' actual risk.

### D4. What counts as a treatment desert
**v1:** tract population-weighted center is more than `DESERT_DISTANCE_MILES` (2.0) straight-line miles from the nearest MOUD facility. We'll run a sensitivity check at 1, 2, and 3 miles.

**v2:** transit travel time to the nearest MOUD facility exceeds `DESERT_TRANSIT_MINUTES`. Transit is the better measure because many people in recovery don't have a car. Likely tooling: `r5py` with the CTA and Pace GTFS feeds plus an OpenStreetMap extract.

**Open question:** should the definition also require the facility to accept Medicaid?

### D4b. Which facilities count as MOUD providers
**Rule:** a site offers MOUD if any of its listings is a federally certified Opioid Treatment Program (methadone) or says in its opioid treatment services that it prescribes buprenorphine or maintains patients on buprenorphine or methadone. Naltrexone is tracked but doesn't count: methadone and buprenorphine are the medications with the strongest evidence for reducing overdose deaths.

**Why not the "medications used" list:** FindTreatment has a separate field, "Methadone used in Treatment", and sober living homes fill it in when they accept residents who get medication elsewhere. Counting those would call a sober house a methadone provider. Only OTPs can legally dispense methadone for opioid use disorder, so the first draft's 148 "methadone facilities" (vs 77 OTP listings) was the tip-off.

**Deduplication:** the same clinic often appears two or three times (as a substance use facility, a mental health facility, and in the separate OTP directory), with slightly different addresses. Listings within 300 feet of each other are merged into one site. 813 listings became 534 sites.

**Result (Sept 2026 pull, 60-mile radius):** 534 sites, 204 offering MOUD (96 methadone, 160 buprenorphine), 163 offering MOUD and accepting Medicaid. 20 methadone sites don't line up with an OTP directory record but describe themselves as OTPs or methadone maintenance programs, so they're kept.

**Radius:** 60 miles from downtown, not just Cook County. Tracts near the county line may be closest to a clinic in DuPage, Lake, McHenry, or Will County, and ignoring those would create fake deserts at the border.

**Known gaps:**
- FindTreatment doesn't list individual buprenorphine prescribers. Since the federal X-waiver ended in 2023, any DEA-registered clinician can prescribe it, so primary care access is invisible here. This analysis measures access to *specialty* MOUD sites.
- 14 listings had no usable location (mostly sober living homes that keep their address private). 2 of them list MOUD.
- Telehealth buprenorphine isn't captured by a physical-distance measure at all.

### D4c. Access relative to need (2SFCA), the main access measure
**Why the switch:** straight-line distance ran backwards (see "First look at access" below). The hardest-hit tracts are closest to clinics, because clinics open where the need is. Distance to the nearest clinic mostly measures where clinics chose to open, so it can't tell us whether supply matches need.

**Method:** two-step floating catchment area (Luo and Wang, 2003), a standard health-access measure.
1. Draw a 2-mile catchment around every MOUD site and add up the demand from tract centers inside it. Each site's ratio = 1 / that demand.
2. Each tract's access score = the sum of ratios of every site whose catchment reaches it.

Two versions of demand:
- **Population** (sites per 100k residents), the textbook version.
- **Need** (sites per 100 annual overdose deaths, 2021 to 2025). This is the main measure. Recent years are used because the facility list is current.

**Groups:** a tract is *high burden* if its overdose rate is in the county's top quartile, and *low access* if its need-based score is below the county benchmark (the need-weighted average score, 7.6 sites per 100 annual deaths at 2 miles). That benchmark works out close to total sites divided by total deaths, so "low access" means "less treatment per death than the county as a whole."

**Changed during build:** the first cutoff for "low access" was the county *median* score. At a 1-mile catchment over half of all tracts (mostly suburbs) have no site in reach, so the median was exactly 0 and no tract could be below it. The sensitivity check returned zero underserved tracts, which is how the bug showed up. The need-weighted benchmark doesn't have that problem.

**Result (2-mile catchment):**

| Group | Tracts | Share of population | Share of 2015-2025 deaths | Sites per 100 deaths | Miles to nearest MOUD | Median income | % no vehicle | % Black |
|---|---|---|---|---|---|---|---|---|
| High burden, low access | 229 | 12.5% | **39.5%** | 4.3 | 0.6 | $43,569 | 29.7 | 79.8 |
| High burden, high access | 103 | 6.4% | 17.5% | 10.0 | 0.6 | $58,494 | 21.2 | 67.3 |
| Low burden, high access | 435 | 34.6% | 17.2% | 13.8 | 0.9 | $93,632 | 11.4 | 4.4 |
| Low burden, low access | 561 | 46.5% | 25.8% | 2.6 | 1.6 | $82,768 | 9.1 | 3.8 |

(Medians across tracts in each group, except the shares.)

The high-burden, low-access tracts are **not** deserts by distance: their median tract is 0.6 miles from a clinic. Per resident they look fine. Per overdose death, they have less than half the treatment supply of other high-burden tracts.

**Sensitivity:** at 1, 2, and 3 mile catchments the high-burden, low-access group has 239, 229, and 244 tracts. 84% of the 2-mile group appears in the 1-mile group, and 84% appears in the 3-mile group. The group's median demographics barely move (about 80% Black, about 30% of households without a vehicle).

**Limitations:**
- Every site counts as 1 unit of supply. FindTreatment doesn't publish capacity (slots, hours, waitlists), so a large methadone clinic and a small buprenorphine practice count the same. This is the biggest weakness of the measure, and it's a good question for people who work in treatment.
- Demand only comes from Cook tracts. Sites just outside the county also serve DuPage and Lake residents, so access near the county line is somewhat overstated. This barely touches the city tracts the analysis focuses on.
- Using deaths as demand and then comparing groups by overdose rate is partly built in: a high-death tract pushes up the demand at its nearby sites. The comparison between the two *high burden* groups (similar rates, very different access) is the cleaner contrast.
- Catchments are straight-line circles for now. Transit travel time is the planned upgrade.

### D5. Small-number suppression
Suppress any published count below 10. This matters most for tract-by-race breakdowns.

### D6. Regression model
**Question:** across tracts, which structural conditions go along with higher overdose death rates when considered together? The results are descriptive associations, not causal effects.

**Why not "deaths explained by access":** need-based 2SFCA has deaths in its denominator, so using it to predict deaths is circular. Distance and population-based access have the reverse-causality problem (clinics open where deaths are already high). Population-based access is kept in the model as a control and read with that caveat.

**Model:** negative binomial regression of 2015-2025 tract deaths with log(population x 11 years) as an offset, so coefficients describe rates. Percent predictors are scaled per 10 points. 1,328 tracts (population 500+ with complete ACS data).

**Checks that shaped the model:**
- *Overdispersion:* the variance of tract deaths is 177.5 against a mean of 11.5, and the Poisson dispersion ratio is 6.8. Poisson would understate uncertainty, so the model is negative binomial (AIC 8,373 vs 12,149).
- *Collinearity:* all variance inflation factors are under 3. Poverty and median income overlap conceptually, so only one goes in at a time. Swapping them barely moves the other estimates.
- *Spatial autocorrelation:* Moran's I of the residuals is 0.30 (p = 0.001, queen contiguity, 999 permutations). Standard errors are clustered by the first two digits of the tract code (81 area clusters; in Chicago these line up with community areas). A spatial lag or spatial error model would be the next step up.

**Results (rate ratios, 95% CI):**

| Per 10 percentage points | Rate ratio | 95% CI |
|---|---|---|
| Households without a vehicle | 1.20 | 1.12 to 1.29 |
| Black residents | 1.15 | 1.10 to 1.21 |
| Residents uninsured | 1.15 | 1.04 to 1.27 |
| Residents below poverty | 1.13 | 1.07 to 1.19 |
| Hispanic residents | 1.08 | 1.03 to 1.13 |
| MOUD sites per 100k residents (per site) | 1.04 | 0.99 to 1.09 |

**Interpretation guardrails:** racial composition stands in for conditions tied to segregation that the ACS doesn't measure (disinvestment, drug market concentration, policing, historical access to care). It says nothing about individuals. The analysis is ecological and cross-sectional, and deaths are placed where they happened rather than where people lived.

## Framing
Findings describe access and structural conditions ("a 45-minute transit trip to the nearest methadone clinic"), not behavior of groups.

## First look at access (2026-09-22)

Straight-line distance from population-weighted tract centers to the nearest MOUD site, 2015 through 2025 deaths:

| | Deaths | Population | Rate per 100k per year |
|---|---|---|---|
| Within 2 miles of MOUD | 13,765 | 4.12M | 30.4 |
| More than 2 miles (240 tracts) | 1,578 | 1.16M | 12.4 |

The simple hypothesis ("deserts have more overdose deaths") runs backwards on straight-line distance. The highest-rate tracts in the county (East and West Garfield Park and Humboldt Park, 330 to 455 per 100k) sit 0.2 to 0.6 miles from an MOUD site. Clinics are located where the need is, so distance and overdose burden are tangled together (reverse causality), and most 2-mile deserts are lower-burden suburbs. Median distance countywide is 1.0 mile.

This matters for Phase 4. A regression with distance as the predictor would pick up where clinics chose to open, not the effect of access. **Resolved:** access is now measured relative to need with 2SFCA (D4c).
