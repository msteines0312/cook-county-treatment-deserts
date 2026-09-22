"""
Shared wrapper around the Census Bureau batch geocoder.

Free, no API key, and it returns the census tract along with the coordinates.
Used for overdose cases and treatment facilities that come without lat/long.
"""

from io import StringIO

import pandas as pd
import requests

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
GEOCODER_BATCH_SIZE = 1_000  # the service allows 10k, but smaller batches time out less

GEOCODER_COLUMNS = [
    "id", "input_address", "match_status", "match_type",
    "matched_address", "coordinates", "tiger_line_id", "side",
    "state_fips", "county_fips", "tract_code", "block_code",
]


def geocode_batch(addresses):
    """
    Send one batch of addresses to the Census geocoder.

    Parameters
    ----------
    addresses : pd.DataFrame
        Exactly five columns in this order: id, street, city, state, zip.

    Returns
    -------
    pd.DataFrame
        One row per input with match status, "lon,lat" coordinates, and tract codes.
    """
    csv_body = addresses.to_csv(index=False, header=False)
    response = requests.post(
        GEOCODER_URL,
        files={"addressFile": ("addresses.csv", csv_body)},
        # Census2020_Current vintage returns 2020 tract codes, matching our tracts
        data={"benchmark": "Public_AR_Current", "vintage": "Census2020_Current"},
        timeout=600,
    )
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), header=None, names=GEOCODER_COLUMNS, dtype=str)


def geocode_addresses(addresses):
    """Geocode any number of addresses by splitting them into batches."""
    results = []
    for start in range(0, len(addresses), GEOCODER_BATCH_SIZE):
        batch = addresses.iloc[start:start + GEOCODER_BATCH_SIZE]
        results.append(geocode_batch(batch))
        print(f"  geocoded {min(start + GEOCODER_BATCH_SIZE, len(addresses)):,} addresses")
    return pd.concat(results, ignore_index=True)
