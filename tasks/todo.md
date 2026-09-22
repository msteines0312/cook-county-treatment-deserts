# To Do

## Setup
- [x] Folder structure, config, module frames, README, methodology log
- [ ] Get a free Census API key and add it to `.env`
- [ ] First commit and create the GitHub repo

## Phase 1: Pipeline
- [ ] `fetch_overdoses.py`: page through the ME API, save the raw CSV (expect ~33k rows)
- [ ] `clean_overdoses.py`: flag overdoses, clean dates, report missing coordinates
- [ ] Decide what to do with cases missing lat/long (geocode `incident_street`? drop and document?)
- [ ] `fetch_treatment.py`: pull facilities, parse MOUD and Medicaid flags
- [ ] `fetch_census.py`: tract boundaries plus ACS variables
- [ ] Spatial join: deaths to tracts, facilities to tracts
- [ ] `notebooks/01_data_quality.ipynb`: row counts, nulls, what each overdose rule catches

## Phase 2: Where and when
- [ ] Deaths per 100k by tract (pool years, since single-year tract rates are noisy)
- [ ] Fentanyl share over time
- [ ] Hour of day and day of week patterns (ask Dad what he'd expect to see)
- [ ] Apply suppression before any chart gets saved

## Phase 3: Access
- [ ] Population-weighted tract centers (block-level population)
- [ ] Straight-line distance to the nearest MOUD facility
- [ ] Sensitivity check at 1, 2, and 3 miles
- [ ] Transit travel time with r5py plus CTA/Pace GTFS
- [ ] Ask Mom and my brother which listed facilities actually take new patients

## Phase 4: Demographics and modeling
- [ ] Desert vs non-desert comparison table
- [ ] Poisson model, then an overdispersion check, then negative binomial with a population offset
- [ ] Interpret the results as rate ratios

## Phase 5: Story
- [ ] Tableau extracts in `outputs/tableau/`
- [ ] Dashboard
- [ ] Policy brief
- [ ] README: key features, figures, what I learned
