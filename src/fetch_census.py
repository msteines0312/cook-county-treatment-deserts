"""
Pull Cook County census tract boundaries and ACS 5-year demographics.

Tracts are the unit of analysis for the whole project. Everything else (deaths,
facility distance, demographics) gets joined onto this table by GEOID.
"""

import os

import pandas as pd
import requests
from dotenv import load_dotenv

from src.config import ACS_YEAR, CENSUS_API_BASE, COUNTY_FIPS, RAW_DIR, REFERENCE_DIR, STATE_FIPS

load_dotenv()

# ACS variable codes -> readable names. Look codes up at
# https://api.census.gov/data/2023/acs/acs5/variables.html
# Poverty, uninsured, and no-vehicle rates need a numerator AND a denominator,
# so each rate is two variables. Compute the rate after pulling.
ACS_VARIABLES = {
    "B01003_001E": "total_population",
    "B19013_001E": "median_household_income",
    # TODO: add race/ethnicity (B03002), poverty (B17001),
    # uninsured (B27010 or S2701), and households without a vehicle (B08201)
}


def fetch_tract_boundaries():
    """
    Download TIGER/Line tract shapes for Cook County into data/reference/.

    Notes
    -----
    Use the same vintage as ACS_YEAR so the tract GEOIDs line up. Tract
    boundaries get redrawn every decade (2010 vs 2020), and mixing vintages
    silently drops tracts during the join.
    """
    # TODO: download the Illinois tract zip from
    # https://www2.census.gov/geo/tiger/TIGER{ACS_YEAR}/TRACT/ and filter
    # to COUNTYFP == COUNTY_FIPS with geopandas
    raise NotImplementedError


def fetch_acs():
    """
    Pull ACS_VARIABLES for every Cook County tract.

    Returns
    -------
    pd.DataFrame
        One row per tract with a GEOID column (state + county + tract) and
        the renamed variables.
    """
    # TODO: GET {CENSUS_API_BASE}/{ACS_YEAR}/acs/acs5 with
    #   get = "NAME," + ",".join(ACS_VARIABLES)
    #   for = "tract:*", in = f"state:{STATE_FIPS} county:{COUNTY_FIPS}"
    #   key = os.getenv("CENSUS_API_KEY")
    # Watch out: the Census uses negative sentinel values like -666666666 to mean
    # "no estimate". Replace them with NaN or they'll wreck every average.
    raise NotImplementedError


if __name__ == "__main__":
    fetch_tract_boundaries()
    acs = fetch_acs()
    print(acs.shape)
