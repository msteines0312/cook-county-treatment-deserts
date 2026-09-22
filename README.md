# Cook County Treatment Deserts

Where are overdose deaths happening in Cook County, is treatment supply matched to where people are dying, and who lives in the places where it isn't? This project maps 17,000 overdose deaths against sites offering medications for opioid use disorder (MOUD) and measures access *relative to need*, not just distance.

> Status: in progress. Pipeline done, access analysis underway.

## Tech Stack
- Python (pandas, geopandas, requests)
- statsmodels (count regression models)
- Tableau (dashboard)
- Data: Cook County Medical Examiner Case Archive (Socrata API), SAMHSA FindTreatment.gov, U.S. Census ACS 5-year estimates and TIGER/Line tract boundaries

## How to Run
1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and add a free Census API key (https://api.census.gov/data/key_signup.html).
3. Run the pipeline from the project root:
   ```bash
   python -m src.run_pipeline
   ```
4. Open the notebooks in `notebooks/` in numbered order.

## Project Structure
```
data/
  raw/          untouched API pulls (not committed)
  processed/    cleaned, analysis-ready tables (not committed)
  reference/    census tract boundaries (not committed)
src/            pipeline code: fetch, clean, join
notebooks/      one notebook per analysis phase
outputs/
  figures/      charts for the README and brief
  tableau/      flat extracts that feed the dashboard
docs/           methodology and decision log
tasks/          project to-do list
```

## Analysis Plan
1. **Pipeline:** pull ME cases, filter to accidental drug overdoses, join to census tracts. Pull MOUD facilities and ACS demographics.
2. **Where and when:** overdose death rates per 100k by tract, the shift to fentanyl over time, time of day and day of week patterns.
3. **Access:** a two-step floating catchment area (2SFCA) score for every tract: MOUD sites in reach per 100 annual overdose deaths. Straight-line distance turned out to run backwards (clinics open where need is highest), so access is measured against need. Upgrade to CTA transit travel time next.
4. **Demographics:** compare high-burden, low-access tracts with the rest on race, income, insurance, and vehicle access, then fit a count model (negative binomial with a population offset).
5. **Story:** a Tableau dashboard and a short policy brief.

## Ethics and Limitations
- Any tract-level count below 10 is suppressed so small areas can't point to individuals.
- Findings are framed around access and structural conditions, not individual or group behavior.
- The ME archive covers only deaths under its jurisdiction, so it undercounts overdoses somewhat.
- FindTreatment.gov listings can be outdated or inaccurate, so a listed facility isn't guaranteed to be taking patients.

Full detail is in [docs/methodology.md](docs/methodology.md).

## Key Features
_Coming as the phases are finished._

## What I Learned
_Written at the end of the project._
