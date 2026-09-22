"""
Pull accidental death records from the Cook County Medical Examiner Case Archive.

We pull every ACCIDENT case (about 33k rows) instead of only opioid cases so
that the overdose filter lives in our own code (clean_overdoses.py), where it's
visible and testable, and not buried inside an API query.
"""

import pandas as pd
import requests

from src.config import ME_DATASET_URL, ME_PAGE_SIZE, OVERDOSE_MANNER, RAW_DIR


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

    Notes
    -----
    Socrata pages with $limit and $offset. Always pass an $order (casenumber
    works) so that pages don't shift between requests and drop or duplicate rows.
    """
    # TODO: loop, requesting ME_PAGE_SIZE rows at a time with params like
    #   {"$where": f"manner='{manner}'", "$order": "casenumber",
    #    "$limit": ME_PAGE_SIZE, "$offset": offset}
    # and stop when a page comes back with fewer rows than ME_PAGE_SIZE.
    # Print the running row count so you can sanity-check it against ~33k.
    raise NotImplementedError


def save_raw(df, filename="me_accidental_cases.csv"):
    """Write the untouched pull to data/raw/ so later steps never re-hit the API."""
    # TODO: save to RAW_DIR / filename, index=False
    raise NotImplementedError


if __name__ == "__main__":
    cases = fetch_me_cases()
    print(cases.shape)
    save_raw(cases)
