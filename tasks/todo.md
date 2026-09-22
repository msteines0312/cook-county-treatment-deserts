# To Do

## Setup
- [x] Folder structure, config, module frames, README, methodology log
- [x] Get a free Census API key and add it to `.env`
- [x] First commit and create the GitHub repo

## Phase 1: Pipeline
- [x] `fetch_overdoses.py`: page through the ME API, save the raw CSV (expect ~33k rows)
- [x] `clean_overdoses.py`: flag overdoses, clean dates, report missing coordinates
- [x] Decide what to do with cases missing lat/long (geocode `incident_street`? drop and document?)
- [x] `fetch_treatment.py`: pull facilities, parse MOUD and Medicaid flags
- [x] `fetch_census.py`: tract boundaries and block populations
- [x] Run `fetch_acs()` once the Census API key is in `.env`
- [x] Spatial join: deaths to tracts, facilities to tracts
- [ ] `notebooks/01_data_quality.ipynb`: row counts, nulls, what each overdose rule catches

## Phase 2: Where and when
- [x] Deaths per 100k by tract (pool years, since single-year tract rates are noisy)
- [x] Fentanyl share over time
- [x] Hour of day and day of week patterns
- [ ] Ask Dad whether the daytime peak matches when people are usually found
- [x] Apply suppression before any chart gets saved

## Phase 3: Access
- [x] Population-weighted tract centers (block-level population)
- [x] Straight-line distance to the nearest MOUD facility
- [x] Sensitivity check at 1, 2, and 3 miles (first pass: 667 / 240 / 82 tracts)
- [x] Decide how to handle reverse causality: switched to need-based 2SFCA (methodology D4c)
- [x] 2SFCA access scores (population and need), access groups, catchment sensitivity check
- [x] Map of access groups
- [ ] Use transit travel time as the 2SFCA catchment instead of straight-line miles
- [ ] Transit travel time with r5py plus CTA/Pace GTFS (feeds the catchment above)
- [ ] Ask Mom and my brother which listed facilities actually take new patients

## Phase 4: Demographics and modeling
- [x] First pass: access group comparison table (methodology D4c)
- [x] Decide the regression framing: structural conditions model, descriptive (methodology D6)
- [x] Poisson model, then an overdispersion check, then negative binomial with a population offset
- [x] Residual spatial autocorrelation check (Moran's I) and clustered standard errors
- [x] Interpret the results as rate ratios

## Phase 5: Story
- [ ] Tableau extracts in `outputs/tableau/`
- [ ] Dashboard
- [ ] Policy brief
- [ ] README: key features, figures, what I learned
