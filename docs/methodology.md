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

### D5. Small-number suppression
Suppress any published count below 10. This matters most for tract-by-race breakdowns.

### D6. Regression model
Overdose deaths are counts: non-negative integers, mostly small, with a lot of tracts near zero. Linear regression assumes a continuous, normally distributed outcome, which a count isn't. We'll use a negative binomial model with log(population) as an offset (which turns counts into rates), because overdose counts are almost certainly overdispersed (variance much larger than the mean), and overdispersion breaks Poisson's variance = mean assumption. We'll fit Poisson first and test for overdispersion before switching.

## Framing
Findings describe access and structural conditions ("a 45-minute transit trip to the nearest methadone clinic"), not behavior of groups.
