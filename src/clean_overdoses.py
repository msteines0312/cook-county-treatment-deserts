"""
Turn the raw ME pull into a clean table of overdose deaths.

This step makes the first big judgment call in the project: which deaths count
as overdoses. See docs/methodology.md for why the rules are what they are.
"""

import pandas as pd

from src.config import (
    DRUG_KEYWORDS,
    FENTANYL_KEYWORDS,
    ME_START_DATE,
    PROCESSED_DIR,
    RAW_DIR,
)


def flag_overdoses(df):
    """
    Add boolean columns marking overdose deaths and fentanyl involvement.

    Parameters
    ----------
    df : pd.DataFrame
        Raw ME cases with `primarycause` and `opioids` columns.

    Returns
    -------
    pd.DataFrame
        Same rows plus `is_overdose` and `fentanyl_involved` columns.

    Notes
    -----
    A case counts as an overdose if the ME's opioids flag is True OR the cause
    text matches any DRUG_KEYWORDS entry. Keep both source flags as columns
    so you can report how many cases each rule catches on its own.
    """
    # TODO: uppercase primarycause (it has NaNs, so fillna("") first),
    # build a regex from the keyword list with "|".join(...), then use .str.contains
    # Watch for: alcohol-only deaths ("ETHANOL TOXICITY") and carbon monoxide
    # ("CARBON MONOXIDE TOXICITY") both contain TOXICITY, which is why we use
    # drug-specific keywords and don't match on "TOXICITY" alone.
    raise NotImplementedError


def clean_dates(df):
    """Parse date columns, add year/month/hour/weekday, and clip to ME_START_DATE onward."""
    # TODO: also drop anything with a death_date after today (the API contains
    # at least one future-dated record)
    raise NotImplementedError


def report_missing_coordinates(df):
    """
    Print how many overdose cases lack lat/long, broken down by year.

    About 7% of opioid cases have no coordinates. If they cluster in certain
    years or places, dropping them biases the map, so we look before deciding.
    """
    # TODO
    raise NotImplementedError


if __name__ == "__main__":
    raw = pd.read_csv(RAW_DIR / "me_accidental_cases.csv")
    # TODO: chain the steps above, filter to is_overdose, save to PROCESSED_DIR
