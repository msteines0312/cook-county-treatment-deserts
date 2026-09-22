"""
Project-wide paths, API endpoints, and analysis decisions.

Anything that counts as a judgment call (what counts as an overdose, what counts
as a desert, when to suppress a number) lives here so it's easy to find, easy
to change, and documented in one place. The reasoning behind each choice is
written up in docs/methodology.md.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Resolve from this file's location so the project runs from any working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"                # untouched API pulls, never edited by hand
PROCESSED_DIR = DATA_DIR / "processed"    # cleaned tables the notebooks read from
REFERENCE_DIR = DATA_DIR / "reference"    # tract boundaries and other lookup files

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
TABLEAU_DIR = OUTPUTS_DIR / "tableau"     # flat CSV extracts for the dashboard

# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------
STATE_FIPS = "17"    # Illinois
COUNTY_FIPS = "031"  # Cook County

# Lat/long (EPSG:4326) is fine for storing points, but distances need a projected
# CRS. EPSG:3435 is Illinois State Plane East, measured in US feet, so distance
# math comes out accurate for Chicagoland.
CRS_LATLON = "EPSG:4326"
CRS_PROJECTED = "EPSG:3435"
FEET_PER_MILE = 5280

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
# Cook County Medical Examiner Case Archive (Socrata)
ME_DATASET_URL = "https://datacatalog.cookcountyil.gov/resource/cjeq-bs86.json"
ME_PAGE_SIZE = 50_000  # Socrata caps a single request, so we page through

# The archive officially starts Aug 2014, but the API returns a handful of
# earlier records and at least one death_date in the future (data entry errors).
# Clip to a clean window so trend charts aren't distorted by stray records.
ME_START_DATE = "2014-08-01"

# FindTreatment.gov (SAMHSA) locator JSON export
FINDTREATMENT_URL = "https://findtreatment.gov/locator/exportsAsJson/v2"

# Census API (ACS 5-year). A free key is required, set CENSUS_API_KEY in .env
CENSUS_API_BASE = "https://api.census.gov/data"
ACS_YEAR = 2023  # most recent 5-year release as of project start

# ---------------------------------------------------------------------------
# Defining an overdose death
# ---------------------------------------------------------------------------
# Start with the ME's own opioids flag plus manner == ACCIDENT, then use keyword
# matching to catch non-opioid overdoses (cocaine, meth) the flag misses.
# Keywords are matched against the combined primarycause text. Since Sept 2023
# that field merges Lines A, B, and C, so the search sees all three lines either way.
OVERDOSE_MANNER = "ACCIDENT"

DRUG_KEYWORDS = [
    "FENTANYL",
    "HEROIN",
    "OPIOID",
    "OPIATE",
    "MORPHINE",
    "OXYCODONE",
    "HYDROCODONE",
    "METHADONE",
    "COCAINE",
    "METHAMPHETAMINE",
    "XYLAZINE",
    "DRUG TOXICITY",
    "DRUG INTOXICATION",
]

# Kept separate so we can report fentanyl-involved deaths on their own. That
# trend line is the headline chart in Phase 2.
FENTANYL_KEYWORDS = ["FENTANYL", "FENTANIL"]

# ---------------------------------------------------------------------------
# Defining a treatment desert
# ---------------------------------------------------------------------------
# Phase 3 v1 uses straight-line distance from each tract's population-weighted
# center to the nearest MOUD facility. This number is a starting point we'll
# test with a sensitivity check (1, 2, and 3 miles), not a final answer.
DESERT_DISTANCE_MILES = 2.0

# Phase 3 v2 (transit): threshold in minutes, set once travel times exist
DESERT_TRANSIT_MINUTES = 30

# ---------------------------------------------------------------------------
# Privacy guardrails
# ---------------------------------------------------------------------------
# Suppress any cell (tract x year, tract x race, etc.) with fewer deaths than
# this before it goes into a chart, the dashboard, or the brief. 10 follows
# common public health practice (the CDC WONDER standard).
SUPPRESSION_THRESHOLD = 10
