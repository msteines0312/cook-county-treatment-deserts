"""
Pull Cook County census tract boundaries, block populations, and ACS 5-year
demographics.

Tracts are the unit of analysis for the whole project. Everything else (deaths,
facility distance, demographics) gets joined onto the tract table by GEOID.
"""

import os
import zipfile
from io import BytesIO

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

from src.config import (
    ACS_YEAR,
    CENSUS_API_BASE,
    COUNTY_FIPS,
    PROCESSED_DIR,
    REFERENCE_DIR,
    STATE_FIPS,
)

load_dotenv()

TIGER_BASE = "https://www2.census.gov/geo/tiger"
TRACTS_FILENAME = "cook_tracts.gpkg"
BLOCKS_FILENAME = "cook_blocks.gpkg"
ACS_FILENAME = "acs_tracts.csv"

# ACS variable codes -> readable names. Labels were checked against
# https://api.census.gov/data/2023/acs/acs5/variables.json
# Rates need a numerator and a denominator, so we pull counts and divide later.
ACS_VARIABLES = {
    "B01003_001E": "total_population",
    "B19013_001E": "median_household_income",
    # Race/ethnicity (B03002 splits Hispanic out first, so groups don't overlap)
    "B03002_001E": "race_universe",
    "B03002_003E": "nh_white",
    "B03002_004E": "nh_black",
    "B03002_006E": "nh_asian",
    "B03002_012E": "hispanic",
    # Poverty
    "B17001_001E": "poverty_universe",
    "B17001_002E": "below_poverty",
    # Health insurance: B27010 has no single "uninsured" total, so we add up
    # the "no coverage" line for each of its four age groups
    "B27010_001E": "insurance_universe",
    "B27010_017E": "uninsured_under_19",
    "B27010_033E": "uninsured_19_34",
    "B27010_050E": "uninsured_35_64",
    "B27010_066E": "uninsured_65_plus",
    # Vehicle access
    "B08201_001E": "households",
    "B08201_002E": "households_no_vehicle",
    # Unemployment (share of the civilian labor force, not of all adults)
    "B23025_003E": "civilian_labor_force",
    "B23025_005E": "unemployed",
    # Education, adults 25 and over
    "B06009_001E": "education_universe",
    "B06009_002E": "no_high_school_diploma",
}


def download_tiger_layer(url):
    """Download a zipped TIGER/Line shapefile and read it with geopandas."""
    print(f"  downloading {url.rsplit('/', 1)[-1]}")
    response = requests.get(url, timeout=600)
    response.raise_for_status()
    # geopandas can read a shapefile straight out of an in-memory zip
    with zipfile.ZipFile(BytesIO(response.content)) as zipped:
        shapefile_name = next(name for name in zipped.namelist() if name.endswith(".shp"))
    return gpd.read_file(BytesIO(response.content), layer=shapefile_name.removesuffix(".shp"))


def fetch_tract_boundaries():
    """
    Download TIGER/Line tract shapes for Cook County and save them to data/reference/.

    Notes
    -----
    ACS 2023 uses 2020-vintage tract boundaries, and so does the TIGER 2023 tract
    file. Mixing vintages (2010 vs 2020 tracts) would silently drop tracts
    during joins, since the GEOIDs changed when the Census redrew boundaries.
    """
    url = f"{TIGER_BASE}/TIGER{ACS_YEAR}/TRACT/tl_{ACS_YEAR}_{STATE_FIPS}_tract.zip"
    tracts = download_tiger_layer(url)
    tracts = tracts[tracts["COUNTYFP"] == COUNTY_FIPS]

    # ALAND = 0 means the "tract" is entirely water (the Lake Michigan tracts).
    # Nobody lives there, so they'd only add empty rows to every table.
    tracts = tracts[tracts["ALAND"] > 0]
    tracts = tracts[["GEOID", "NAMELSAD", "ALAND", "geometry"]].rename(
        columns={"NAMELSAD": "tract_name", "ALAND": "land_area_sqm"}
    )

    tracts.to_file(REFERENCE_DIR / TRACTS_FILENAME)
    print(f"  saved {len(tracts):,} tracts")
    return tracts


def fetch_block_population():
    """
    Download 2020 census blocks for Cook County with their population counts.

    Used in Phase 3 to compute population-weighted tract centers. A plain
    geometric centroid can land in a park, rail yard, or cemetery, which makes
    distance-to-treatment wrong for the people who actually live in the tract.
    """
    url = f"{TIGER_BASE}/TIGER2020/TABBLOCK20/tl_2020_{STATE_FIPS}_tabblock20.zip"
    blocks = download_tiger_layer(url)
    blocks = blocks[blocks["COUNTYFP20"] == COUNTY_FIPS]

    # The first 11 characters of a block GEOID are its tract GEOID
    blocks["tract_geoid"] = blocks["GEOID20"].str[:11]
    blocks = blocks[["GEOID20", "tract_geoid", "POP20", "geometry"]].rename(
        columns={"GEOID20": "block_geoid", "POP20": "population"}
    )

    blocks.to_file(REFERENCE_DIR / BLOCKS_FILENAME)
    print(f"  saved {len(blocks):,} blocks ({blocks['population'].sum():,} people)")
    return blocks


def fetch_acs():
    """
    Pull ACS_VARIABLES for every Cook County tract and compute rates.

    Returns
    -------
    pd.DataFrame
        One row per tract with an 11-character GEOID, the raw counts, and
        derived percentage columns.
    """
    api_key = os.getenv("CENSUS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "CENSUS_API_KEY is missing. Get a free key at "
            "https://api.census.gov/data/key_signup.html and add it to .env"
        )

    params = {
        "get": "NAME," + ",".join(ACS_VARIABLES),
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",
        "key": api_key,
    }
    response = requests.get(f"{CENSUS_API_BASE}/{ACS_YEAR}/acs/acs5", params=params, timeout=120)
    response.raise_for_status()

    # The API returns a list of lists, with the header as the first row
    rows = response.json()
    acs = pd.DataFrame(rows[1:], columns=rows[0])

    acs["GEOID"] = acs["state"] + acs["county"] + acs["tract"]
    acs = acs.rename(columns=ACS_VARIABLES)
    count_columns = list(ACS_VARIABLES.values())
    acs[count_columns] = acs[count_columns].apply(pd.to_numeric)

    # The Census uses large negative numbers (like -666666666) to mean "no
    # estimate available". Left alone, they would wreck every average.
    acs[count_columns] = acs[count_columns].where(acs[count_columns] >= 0, np.nan)

    acs = add_rates(acs)
    acs = acs.drop(columns=["NAME", "state", "county", "tract"])
    acs.to_csv(PROCESSED_DIR / ACS_FILENAME, index=False)
    print(f"  saved ACS data for {len(acs):,} tracts")
    return acs


def add_rates(acs):
    """Turn raw ACS counts into percentages, one column per measure."""
    acs = acs.copy()
    uninsured_columns = ["uninsured_under_19", "uninsured_19_34", "uninsured_35_64", "uninsured_65_plus"]
    uninsured_total = acs[uninsured_columns].sum(axis=1, min_count=1)

    # Dividing by a zero universe gives inf, so turn those into NaN
    with np.errstate(divide="ignore", invalid="ignore"):
        acs["pct_nh_white"] = acs["nh_white"] / acs["race_universe"] * 100
        acs["pct_nh_black"] = acs["nh_black"] / acs["race_universe"] * 100
        acs["pct_nh_asian"] = acs["nh_asian"] / acs["race_universe"] * 100
        acs["pct_hispanic"] = acs["hispanic"] / acs["race_universe"] * 100
        acs["pct_poverty"] = acs["below_poverty"] / acs["poverty_universe"] * 100
        acs["pct_uninsured"] = uninsured_total / acs["insurance_universe"] * 100
        acs["pct_no_vehicle"] = acs["households_no_vehicle"] / acs["households"] * 100
        acs["pct_unemployed"] = acs["unemployed"] / acs["civilian_labor_force"] * 100
        acs["pct_no_high_school"] = acs["no_high_school_diploma"] / acs["education_universe"] * 100

    pct_columns = [col for col in acs.columns if col.startswith("pct_")]
    acs[pct_columns] = acs[pct_columns].replace([np.inf, -np.inf], np.nan)
    return acs


if __name__ == "__main__":
    fetch_tract_boundaries()
    fetch_block_population()
    fetch_acs()
