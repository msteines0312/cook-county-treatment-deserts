"""
Pull accidental death records from the Cook County Medical Examiner Case Archive.

We pull every ACCIDENT case (about 33k rows) instead of only opioid cases so
that the overdose filter lives in our own code (clean_overdoses.py), where it's
visible and testable, and not buried inside an API query.
"""

import pandas as pd
import requests

from src.config import ME_DATASET_URL, ME_PAGE_SIZE, OVERDOSE_MANNER, RAW_DIR

RAW_FILENAME = "me_accidental_cases.csv"


def fetch_me_cases(manner=OVERDOSE_MANNER):
    """
    Download all ME cases with the given manner of death, paging through the API.

    Parameters
    ----------
    manner : str
        Value of the `manner` field to filter on (default "ACCIDENT").

    Returns
    -------
    pd.DataFrame
        One row per case, columns as returned by the Socrata API.
    """
    pages = []
    offset = 0

    while True:
        params = {
            "$where": f"manner='{manner}'",
            # A fixed sort order keeps pages stable. Without it Socrata can
            # return rows in a different order per request and we'd get
            # duplicates on one page and gaps on another.
            "$order": "casenumber",
            "$limit": ME_PAGE_SIZE,
            "$offset": offset,
        }
        response = requests.get(ME_DATASET_URL, params=params, timeout=120)
        response.raise_for_status()

        page = response.json()
        pages.extend(page)
        print(f"  fetched {len(pages):,} rows so far")

        # A short page means we've hit the end
        if len(page) < ME_PAGE_SIZE:
            break
        offset += ME_PAGE_SIZE

    cases = pd.DataFrame(pages)

    # `location` is a nested dict that just repeats latitude/longitude, and
    # nested dicts don't survive a round trip through CSV cleanly
    cases = cases.drop(columns=["location"], errors="ignore")
    return cases


def save_raw(df, filename=RAW_FILENAME):
    """Write the untouched pull to data/raw/ so later steps never re-hit the API."""
    path = RAW_DIR / filename
    df.to_csv(path, index=False)
    print(f"  saved {len(df):,} rows to {path.relative_to(RAW_DIR.parent.parent)}")


if __name__ == "__main__":
    print("Fetching ME accidental death cases...")
    cases = fetch_me_cases()
    print(cases.shape)
    save_raw(cases)
