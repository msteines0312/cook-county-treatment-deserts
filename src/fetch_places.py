"""
Pull CDC PLACES health estimates for every Cook County tract.

PLACES gives tract-level estimates of things the Census doesn't measure, like
depression, frequent mental distress, and binge drinking. They're modeled, not
counted: the CDC fits survey responses (BRFSS) to each tract's age, sex, race,
poverty, and county, then predicts a prevalence. That makes them useful for
spotting patterns but means they partly repeat the demographics already in
the model. See methodology D8.
"""

import pandas as pd
import requests

from src.config import COUNTY_FIPS, PLACES_URL, PROCESSED_DIR, STATE_FIPS

PROCESSED_FILENAME = "places_tracts.csv"

# PLACES field -> our column name. All are "crude prevalence", percent of adults.
PLACES_MEASURES = {
    "mhlth_crudeprev": "pct_frequent_mental_distress",  # 14+ bad mental health days a month
    "depression_crudeprev": "pct_depression",           # ever told they have depression
    "binge_crudeprev": "pct_binge_drinking",
    "csmoking_crudeprev": "pct_smoking",
    "loneliness_crudeprev": "pct_loneliness",
    "housinsecu_crudeprev": "pct_housing_insecurity",
    "lacktrpt_crudeprev": "pct_lack_transportation",   # transportation got in the way of daily life
    "disability_crudeprev": "pct_disability",
}


def fetch_places():
    """
    Download PLACES measures for Cook County tracts and save them to data/processed/.

    Returns
    -------
    pd.DataFrame
        One row per tract: GEOID plus the measures in PLACES_MEASURES.
    """
    params = {
        "$select": ",".join(["tractfips", *PLACES_MEASURES]),
        "$where": f"countyfips='{STATE_FIPS}{COUNTY_FIPS}'",
        "$limit": 5000,  # Cook has about 1,330 tracts, so one page covers it
    }
    response = requests.get(PLACES_URL, params=params, timeout=120)
    response.raise_for_status()

    places = pd.DataFrame(response.json()).rename(columns={"tractfips": "GEOID", **PLACES_MEASURES})
    measure_columns = list(PLACES_MEASURES.values())
    places[measure_columns] = places[measure_columns].apply(pd.to_numeric)

    places.to_csv(PROCESSED_DIR / PROCESSED_FILENAME, index=False)
    print(f"  saved PLACES estimates for {len(places):,} tracts")
    return places


if __name__ == "__main__":
    fetch_places()
