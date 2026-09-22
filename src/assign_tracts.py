"""
Assign every overdose death to a Cook County census tract.

Two routes:
  1. Cases with ME coordinates get a point-in-polygon spatial join.
  2. Cases without coordinates get their street address sent through the
     Census Bureau batch geocoder, which returns the tract directly.

Deaths that land outside Cook County are dropped. The ME's jurisdiction
includes some incidents outside the county (for example, someone found in
Will County who died at a Cook County hospital), but this project is about
where deaths happen in Cook.
"""

import re
from io import StringIO

import geopandas as gpd
import pandas as pd
import requests

from src.config import COUNTY_FIPS, CRS_LATLON, PROCESSED_DIR, REFERENCE_DIR, STATE_FIPS
from src.fetch_census import TRACTS_FILENAME

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
GEOCODER_BATCH_SIZE = 1_000  # the service allows 10k, but smaller batches time out less
OUTPUT_FILENAME = "overdose_deaths_tracts.csv"

GEOCODER_COLUMNS = [
    "casenumber", "input_address", "match_status", "match_type",
    "matched_address", "coordinates", "tiger_line_id", "side",
    "state_fips", "county_fips", "tract_code", "block_code",
]

# Anything after one of these is apartment/room detail that confuses the geocoder
UNIT_PATTERN = re.compile(
    r"\s*(\bAPT\b|\bAPARTMENT\b|\bUNIT\b|\bROOM\b|\bRM\b|\bSUITE\b|\bSTE\b|"
    r"\bBASEMENT\b|\bFLOOR\b|\b\d+(ST|ND|RD|TH)?\s?FL\b|#).*$",
    flags=re.IGNORECASE,
)


def join_points_to_tracts(deaths, tracts):
    """
    Spatial join for cases that have ME coordinates.

    Returns
    -------
    pd.DataFrame
        casenumber and GEOID for every case whose point falls inside a Cook tract.
    """
    with_coords = deaths.dropna(subset=["latitude", "longitude"])
    points = gpd.GeoDataFrame(
        with_coords[["casenumber"]],
        geometry=gpd.points_from_xy(with_coords["longitude"], with_coords["latitude"]),
        crs=CRS_LATLON,
    )
    # Both layers need the same CRS before a spatial join. Tracts come in as
    # NAD83 (EPSG:4269), which is within a meter or two of WGS84 here.
    points = points.to_crs(tracts.crs)
    joined = gpd.sjoin(points, tracts[["GEOID", "geometry"]], how="inner", predicate="within")

    outside = len(points) - len(joined)
    print(f"  {len(joined):,} cases matched to a tract by coordinates "
          f"({outside:,} fell outside Cook County tracts)")
    return pd.DataFrame(joined[["casenumber", "GEOID"]]).assign(geo_source="me_coordinates")


def clean_address(street):
    """Strip unit and room details from a street address; return '' for unusable values."""
    if pd.isna(street) or street.strip().upper().startswith("UNKNOWN"):
        return ""
    return UNIT_PATTERN.sub("", street).strip(" ,.")


def geocode_batch(batch):
    """
    Send one batch of addresses to the Census geocoder.

    Parameters
    ----------
    batch : pd.DataFrame
        Columns casenumber, street, city, state, zip (the order the API expects).

    Returns
    -------
    pd.DataFrame
        One row per input with the geocoder's match status and tract codes.
    """
    csv_body = batch.to_csv(index=False, header=False)
    response = requests.post(
        GEOCODER_URL,
        files={"addressFile": ("addresses.csv", csv_body)},
        # Census2020_Current vintage returns 2020 tract codes, matching our tracts
        data={"benchmark": "Public_AR_Current", "vintage": "Census2020_Current"},
        timeout=600,
    )
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), header=None, names=GEOCODER_COLUMNS, dtype=str)


def geocode_missing(deaths):
    """
    Geocode cases that have no ME coordinates.

    Returns
    -------
    pd.DataFrame
        casenumber, GEOID, and match_type for every case the geocoder placed
        inside Cook County.
    """
    missing = deaths[deaths["latitude"].isna()].copy()
    addresses = pd.DataFrame({
        "casenumber": missing["casenumber"],
        "street": missing["incident_street"].apply(clean_address),
        "city": missing["incident_city"].fillna("").replace("UNKNOWN", ""),
        "state": "IL",
        # ZIPs were read as floats (60641.0), so convert back to 5-digit text
        "zip": missing["incident_zip"].astype("Int64").astype(str).replace("<NA>", ""),
    })
    addresses = addresses[addresses["street"] != ""]
    print(f"  {len(missing):,} cases lack coordinates, {len(addresses):,} have a usable address")

    results = []
    for start in range(0, len(addresses), GEOCODER_BATCH_SIZE):
        batch = addresses.iloc[start:start + GEOCODER_BATCH_SIZE]
        results.append(geocode_batch(batch))
        print(f"  geocoded {min(start + GEOCODER_BATCH_SIZE, len(addresses)):,} addresses")
    geocoded = pd.concat(results, ignore_index=True)

    matched = geocoded[geocoded["match_status"] == "Match"]
    in_cook = matched[(matched["state_fips"] == STATE_FIPS) & (matched["county_fips"] == COUNTY_FIPS)]
    print(f"  geocoder matched {len(matched):,}; {len(in_cook):,} of those are in Cook County")
    print(f"  match types: {in_cook['match_type'].value_counts().to_dict()}")

    in_cook = in_cook.assign(
        GEOID=in_cook["state_fips"] + in_cook["county_fips"] + in_cook["tract_code"],
        geo_source="census_geocoder",
    )
    return in_cook[["casenumber", "GEOID", "geo_source", "match_type"]]


def main():
    deaths = pd.read_csv(PROCESSED_DIR / "overdose_deaths.csv", low_memory=False)
    tracts = gpd.read_file(REFERENCE_DIR / TRACTS_FILENAME)

    by_coordinates = join_points_to_tracts(deaths, tracts)
    by_geocoder = geocode_missing(deaths)
    assignments = pd.concat([by_coordinates, by_geocoder], ignore_index=True)

    # A tract from the geocoder should still be one of our land tracts
    assignments = assignments[assignments["GEOID"].isin(tracts["GEOID"])]

    deaths_with_tracts = deaths.merge(assignments, on="casenumber", how="inner")
    share = len(deaths_with_tracts) / len(deaths)
    print(f"\n  {len(deaths_with_tracts):,} of {len(deaths):,} deaths ({share:.1%}) assigned to a Cook tract")

    deaths_with_tracts.to_csv(PROCESSED_DIR / OUTPUT_FILENAME, index=False)
    print(f"  saved to data/processed/{OUTPUT_FILENAME}")


if __name__ == "__main__":
    main()
