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

# Rates and trends only use complete calendar years. 2014 starts in August, and
# the current year has hundreds of cases still marked manner = PENDING while
# toxicology comes back (624 in 2026 as of Sept 2026, vs 17 left in 2025).
ANALYSIS_START_YEAR = 2015
ANALYSIS_END_YEAR = 2025

# FindTreatment.gov (SAMHSA) locator JSON export
FINDTREATMENT_URL = "https://findtreatment.gov/locator/exportsAsJson/v2"

# Census API (ACS 5-year). A free key is required, set CENSUS_API_KEY in .env
CENSUS_API_BASE = "https://api.census.gov/data"
ACS_YEAR = 2023  # most recent 5-year release as of project start

# ---------------------------------------------------------------------------
# Defining an overdose death
# ---------------------------------------------------------------------------
# An overdose is manner == ACCIDENT and a cause of death that names a drug
# alongside a poisoning word (toxicity, intoxication, overdose). This tracks the
# CDC definition of unintentional drug poisoning (ICD-10 X40-X44): any drug or
# medication counts, while alcohol alone, carbon monoxide, and solvents don't.
#
# We do NOT use the ME's `opioids` flag to decide. It's set on cases like
# asthma and drowning where opioids were present but weren't the cause, so it
# measures involvement, not cause. It's kept as a cross-check.
#
# Cause text is built from Lines A, B, and C for every year. The ME started
# merging those lines into `primarycause` in Sept 2023, and earlier years only
# have Line A there. Combining them ourselves keeps the definition the same
# across the whole time series.
OVERDOSE_MANNER = "ACCIDENT"

CAUSE_COLUMNS = [
    "primarycause",
    "primarycause_linea",
    "primarycause_lineb",
    "primarycause_linec",
]

POISONING_KEYWORDS = ["TOXIC", "INTOX", "OVERDOSE", "POISON"]

# Fentanyl gets its own list because the shift to fentanyl is the headline
# trend in Phase 2. These are substring matches, so "FENTAN" also catches
# FENTANYL, FENTANLY, CARFENTANIL, and ACETYLFENTANYL. The misspellings are
# real ones found in the data.
FENTANYL_KEYWORDS = [
    "FENTAN", "FENATANYL", "FENTNAYL", "FENTAYL", "FENANYL",
    "FENTNANYL", "FENATNYL",
]

OPIOID_KEYWORDS = FENTANYL_KEYWORDS + [
    "HEROIN", "HERION", "HERON",
    "OPIOID", "OPIOD", "OPIATE",
    "MORPHINE", "HYDROMORPHONE", "OXYMORPHONE", "CODEINE",
    "OXYCODONE", "HYDROCODONE", "METHADONE", "BUPRENORPHINE",
    "TRAMADOL", "TAPENTADOL", "MEPERIDINE", "LOPERAMIDE",
    "MITRAGYNINE", "KRATOM", "NITAZENE", "U-47700",
]

STIMULANT_KEYWORDS = [
    "COCAINE", "COCAETHYLENE",
    "AMPHETAMINE", "METHAPHETAMINE", "MDMA",
    "PENTYLONE", "CATHINONE", "PYRROLIDINOVALEROPHENONE",
]

OTHER_DRUG_KEYWORDS = [
    "PHENCYCLIDINE", "PCP", "XYLAZINE",
    "BENZODIAZEPINE", "ALPRAZOLAM", "CLONAZEPAM", "DIAZEPAM", "LORAZEPAM",
    "ETIZOLAM", "BUTALBITAL",
    "GABAPENTIN", "NEURONTIN", "CYCLOBENZAPRINE",
    "ACETAMINOPHEN", "SALICYLATE", "DIPHENHYDRAMINE", "DEXTROMETHORPHAN",
    "ANTIDEPRESSANT", "AMITRIPTYLINE", "IMIPRAMINE", "BUPROPION", "VENLAFAXINE",
    "QUETIAPINE", "OLANZAPINE", "RISPERIDONE", "LITHIUM", "METOPROLOL",
    "CANNABINOID",
    # generic wording the ME uses when it doesn't list specific drugs
    "DRUG", "MEDICATION", "POLYSUBSTANCE", "NARCOTIC",
]

DRUG_KEYWORDS = OPIOID_KEYWORDS + STIMULANT_KEYWORDS + OTHER_DRUG_KEYWORDS

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
# Access relative to need (two-step floating catchment area, 2SFCA)
# ---------------------------------------------------------------------------
# Straight-line distance showed clinics sit where overdoses are highest, so
# "distance to nearest clinic" mostly measures where clinics chose to open.
# 2SFCA instead asks how much treatment supply each tract can reach relative
# to the demand competing for it. See methodology D4c.
CATCHMENT_MILES = 2.0
CATCHMENT_SENSITIVITY_MILES = [1.0, 2.0, 3.0]

# Need is measured with recent deaths, because the facility list is current.
# Comparing today's clinics to 2016 overdose patterns would mismatch the two.
NEED_START_YEAR = 2021
NEED_END_YEAR = 2025

# ---------------------------------------------------------------------------
# Privacy guardrails
# ---------------------------------------------------------------------------
# Suppress any cell (tract x year, tract x race, etc.) with fewer deaths than
# this before it goes into a chart, the dashboard, or the brief. 10 follows
# common public health practice (the CDC WONDER standard).
SUPPRESSION_THRESHOLD = 10

# Rates for tiny tracts are meaningless: O'Hare Airport (tract 9801) has 18
# residents, so 3 deaths there works out to 1,500 per 100k. Tracts under
# this population get no rate. Their deaths still count in the totals.
MIN_POPULATION_FOR_RATE = 500
