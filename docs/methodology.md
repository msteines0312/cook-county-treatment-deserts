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
**Current rule:** `manner == ACCIDENT` AND (`opioids` flag is True OR the cause text matches a drug keyword).

**Why:** Accidental manner excludes suicides and undetermined cases, which is the standard definition for "unintentional drug overdose" in CDC reporting. The ME's own opioid flag is more reliable than our text search, but it misses stimulant-only deaths (cocaine, meth), so keywords fill that gap. We avoid matching on "TOXICITY" alone because it also catches alcohol-only and carbon monoxide deaths.

**Open questions:** Should alcohol-plus-drug deaths count? (Yes if a drug keyword is present.) How many cases does each rule catch on its own?

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
