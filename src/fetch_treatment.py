"""
Pull substance use treatment facilities near Cook County from FindTreatment.gov
and keep the ones offering medications for opioid use disorder (MOUD).

Each facility comes back with a `services` list of {f1, f2, f3} dicts. The one
we care about has f2 == "OT" (Type of Opioid Treatment), and its f3 text says
whether the facility offers buprenorphine, methadone, or naltrexone, or
"Does not treat opioid use disorders".
"""

import pandas as pd
import requests

from src.config import FINDTREATMENT_URL, RAW_DIR

# Downtown Chicago. A 40-mile radius covers all of Cook County plus a buffer,
# and the buffer matters: people on the county edge may use a facility in DuPage
# or Lake County, and ignoring those would invent fake deserts at the border.
SEARCH_CENTER = "41.8781,-87.6298"
SEARCH_RADIUS_METERS = 64_374  # about 40 miles


def fetch_facilities():
    """
    Download every substance use (sType=SA) facility within the search radius.

    Returns
    -------
    list of dict
        Raw facility records, all pages combined.
    """
    # TODO: params look like
    #   {"sAddr": SEARCH_CENTER, "limitType": 2, "limitValue": SEARCH_RADIUS_METERS,
    #    "sType": "SA", "pageSize": 100, "page": page, "sort": 0}
    # Response JSON has "totalPages" and "rows". Loop until page > totalPages.
    # Save the raw JSON to RAW_DIR before parsing anything.
    raise NotImplementedError


def parse_facilities(records):
    """
    Flatten raw records into one row per facility with MOUD flags.

    Returns
    -------
    pd.DataFrame
        name, address, lat/long, plus boolean columns offers_buprenorphine,
        offers_methadone, offers_naltrexone, and accepts_medicaid.
    """
    # TODO: pull the f3 text for f2 == "OT" (opioid treatment) and f2 == "PAY"
    # (payment accepted). Medicaid acceptance matters a lot here: a clinic that
    # only takes private insurance or cash isn't real access for most people
    # in the highest-burden tracts.
    raise NotImplementedError


if __name__ == "__main__":
    raw_records = fetch_facilities()
    facilities = parse_facilities(raw_records)
    print(facilities.shape)
