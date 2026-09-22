"""
Pull treatment facilities near Cook County from FindTreatment.gov and flag the
ones offering medications for opioid use disorder (MOUD).

Each facility comes back with a `services` list of {f1, f2, f3} dicts, where
f2 is a short code and f3 is a "; "-separated list of values. The codes we use:
  OM   Opioid Medications used in Treatment (buprenorphine, methadone, naltrexone)
  OT   Type of Opioid Treatment (maintenance, detox, OTP certification, etc.)
  PAY  Payment/Insurance/Funding Accepted
"""

import json

import geopandas as gpd
import pandas as pd
import requests

from src.config import CRS_LATLON, CRS_PROJECTED, FINDTREATMENT_URL, PROCESSED_DIR, RAW_DIR
from src.geocoding import geocode_addresses

# Downtown Chicago. 60 miles covers all of Cook County plus a buffer, and the
# buffer matters: the northwest corner of Cook is about 35 miles out, and
# its nearest clinic may be in McHenry, Lake, or DuPage County. Leaving those
# out would create fake deserts along the county line.
SEARCH_CENTER = "41.8781,-87.6298"
SEARCH_RADIUS_METERS = 96_560  # about 60 miles

# Listings closer than this are treated as the same physical site. 300 feet
# is about one building, which absorbs geocoding differences between
# directories without merging clinics that are a block apart.
SITE_MERGE_FEET = 300

RAW_FILENAME = "findtreatment_facilities.json"
PROCESSED_FILENAME = "treatment_facilities.csv"


def fetch_facilities():
    """
    Download every facility (substance use, mental health, and OTP) in the radius.

    Returns
    -------
    list of dict
        Raw facility records, all pages combined. Also saved to data/raw/.

    Notes
    -----
    We skip the sType filter on purpose. Some mental health facilities also
    prescribe buprenorphine, and OTPs (methadone clinics) are their own type.
    Classifying by services offered is more reliable than by facility category.
    """
    records = []
    page = 1
    while True:
        params = {
            "sAddr": SEARCH_CENTER,
            "limitType": 2,  # 2 = limit by distance in meters
            "limitValue": SEARCH_RADIUS_METERS,
            "pageSize": 500,
            "page": page,
            "sort": 0,
        }
        response = requests.get(FINDTREATMENT_URL, params=params, timeout=300)
        response.raise_for_status()
        result = response.json()

        records.extend(result["rows"])
        print(f"  page {page} of {result['totalPages']}: {len(records):,} facilities so far")
        if page >= result["totalPages"]:
            break
        page += 1

    with open(RAW_DIR / RAW_FILENAME, "w") as raw_file:
        json.dump(records, raw_file)
    return records


def get_service(facility, code):
    """Return the list of values for one service code, or [] if the facility doesn't list it."""
    # Some records have "services": null. .get()'s default only applies when
    # the key is missing entirely, so `or []` also covers the null case.
    for service in facility.get("services") or []:
        if service["f2"] == code:
            return service["f3"].split("; ")
    return []


def parse_facility(facility):
    """
    Flatten one raw facility record into a dict with MOUD and payment flags.

    A facility only counts as offering a medication if its OT (opioid
    treatment) services say it prescribes or maintains patients on it, or if
    it's a federally certified Opioid Treatment Program. We don't use the OM
    list ("Methadone used in Treatment") on its own, because sober living homes
    fill that in when they accept residents who get medication somewhere else.
    That isn't access to treatment.
    """
    opioid_treatment = " ".join(get_service(facility, "OT"))
    payment = get_service(facility, "PAY")

    # Methadone for opioid use disorder can legally only be dispensed by an OTP
    offers_methadone = (
        facility.get("typeFacility") == "OTP"
        or "Federally-certified Opioid Treatment Program" in opioid_treatment
        or "Methadone maintenance" in opioid_treatment
    )
    offers_buprenorphine = (
        "Prescribes buprenorphine" in opioid_treatment
        or "Buprenorphine maintenance" in opioid_treatment
    )
    offers_naltrexone = (
        "Prescribes naltrexone" in opioid_treatment
        or "Relapse prevention with naltrexone" in opioid_treatment
    )

    return {
        "name": facility["name1"],
        "street": facility["street1"],
        "city": facility["city"],
        "state": facility["state"],
        "zip": facility["zip"],
        # pd.to_numeric turns the handful of null coordinates into NaN
        "latitude": pd.to_numeric(facility["latitude"]),
        "longitude": pd.to_numeric(facility["longitude"]),
        "facility_type": facility.get("typeFacility"),
        "offers_methadone": offers_methadone,
        "offers_buprenorphine": offers_buprenorphine,
        "offers_naltrexone": offers_naltrexone,
        # Methadone and buprenorphine are the evidence-based standard for
        # opioid use disorder. Naltrexone is tracked, but doesn't count toward
        # MOUD access here (see methodology D4).
        "offers_moud": offers_methadone or offers_buprenorphine,
        "accepts_medicaid": "Medicaid" in payment,
    }


def fill_missing_coordinates(facilities):
    """
    Geocode facilities that FindTreatment lists without lat/long.

    Only a few dozen listings are missing coordinates, but they include real
    MOUD providers (a West Side clinic among them), so it's worth recovering them.
    Listings with no street address (often sober living homes that keep their
    address private) can't be placed and stay missing.
    """
    facilities = facilities.copy()
    missing = facilities[facilities["latitude"].isna() & facilities["street"].notna()]
    if missing.empty:
        return facilities

    addresses = missing[["street", "city", "state", "zip"]].reset_index(names="id")
    geocoded = geocode_addresses(addresses)
    matched = geocoded[geocoded["match_status"] == "Match"]

    # coordinates come back as one "lon,lat" string
    lon_lat = matched["coordinates"].str.split(",", expand=True).astype(float)
    row_ids = matched["id"].astype(int)
    facilities.loc[row_ids, "longitude"] = lon_lat[0].values
    facilities.loc[row_ids, "latitude"] = lon_lat[1].values
    print(f"  geocoded {len(matched)} of {len(missing)} facilities missing coordinates")
    return facilities


def parse_facilities(records):
    """
    Turn raw records into one row per physical facility.

    Returns
    -------
    pd.DataFrame
        One row per facility location with MOUD and Medicaid flags.
    """
    facilities = pd.DataFrame([parse_facility(record) for record in records])
    facilities = fill_missing_coordinates(facilities)

    # Anything still without coordinates can't be mapped. Drop it explicitly
    # (the groupby below would otherwise drop NaN keys silently).
    unplaced = facilities["latitude"].isna()
    print(f"  dropping {unplaced.sum()} listings with no location "
          f"({facilities.loc[unplaced, 'offers_moud'].sum()} of them offer MOUD)")
    facilities = facilities[~unplaced]

    sites = merge_nearby_listings(facilities)
    return sites


def merge_nearby_listings(facilities):
    """
    Collapse listings within SITE_MERGE_FEET of each other into one site.

    The same clinic often shows up two or three times: once as a substance use
    facility, once as a mental health facility, and once in the separate OTP
    directory, each with a slightly different address and geocode. Matching
    on name or address misses those, so we match on location instead. A site
    keeps a flag as True if any of its listings has it.

    Returns
    -------
    pd.DataFrame
        One row per site, with the name and coordinates of its first listing.
    """
    points = gpd.GeoDataFrame(
        facilities,
        geometry=gpd.points_from_xy(facilities["longitude"], facilities["latitude"]),
        crs=CRS_LATLON,
    ).to_crs(CRS_PROJECTED)

    # Buffer each point by half the merge distance and dissolve overlapping
    # buffers. Points whose buffers touch end up in the same blob (site).
    blobs = points.buffer(SITE_MERGE_FEET / 2).union_all()
    blob_shapes = getattr(blobs, "geoms", [blobs])
    sites_layer = gpd.GeoDataFrame(geometry=list(blob_shapes), crs=CRS_PROJECTED)
    sites_layer["site_id"] = range(len(sites_layer))
    points = gpd.sjoin(points, sites_layer, predicate="within").drop(columns="index_right")

    flag_columns = [col for col in facilities.columns if col.startswith(("offers_", "accepts_"))]
    sites = (
        pd.DataFrame(points.drop(columns="geometry"))
        .groupby("site_id")
        .agg({
            "name": "first", "street": "first", "city": "first", "state": "first",
            "zip": "first", "latitude": "first", "longitude": "first",
            "facility_type": lambda types: ", ".join(sorted(set(types))),
            **{col: "max" for col in flag_columns},
        })
        .reset_index(drop=True)
    )
    print(f"  merged {len(facilities):,} listings into {len(sites):,} sites")
    return sites


def main():
    records = fetch_facilities()
    facilities = parse_facilities(records)

    print(f"\n  {len(facilities):,} treatment sites within about 60 miles of downtown")
    print(f"  {facilities['offers_moud'].sum():,} offer MOUD "
          f"({facilities['offers_methadone'].sum()} methadone, "
          f"{facilities['offers_buprenorphine'].sum()} buprenorphine)")
    print(f"  {(facilities['offers_moud'] & facilities['accepts_medicaid']).sum():,} "
          f"offer MOUD and accept Medicaid")

    facilities.to_csv(PROCESSED_DIR / PROCESSED_FILENAME, index=False)
    print(f"  saved to data/processed/{PROCESSED_FILENAME}")


if __name__ == "__main__":
    main()
