"""
Turn the raw ME pull into a clean table of overdose deaths.

This step makes the first big judgment call in the project: which deaths count
as overdoses. The rules live in config.py and the reasoning is written up in
docs/methodology.md (decision D1).
"""

import re
from datetime import datetime

import pandas as pd

from src.config import (
    CAUSE_COLUMNS,
    DRUG_KEYWORDS,
    FENTANYL_KEYWORDS,
    ME_START_DATE,
    OPIOID_KEYWORDS,
    POISONING_KEYWORDS,
    PROCESSED_DIR,
    RAW_DIR,
    STIMULANT_KEYWORDS,
)

PROCESSED_FILENAME = "overdose_deaths.csv"

# Columns worth carrying forward. Everything else (gun, heat, transport flags)
# is irrelevant for overdoses and just adds noise to the processed file.
KEEP_COLUMNS = [
    "casenumber", "death_date", "incident_date",
    "death_year", "death_month", "death_weekday", "incident_hour",
    "age", "gender", "race", "latino",
    "cause_text", "fentanyl_involved", "opioid_involved", "stimulant_involved",
    "opioids",  # the ME's own flag, kept for comparison
    "incident_street", "incident_city", "incident_zip",
    "latitude", "longitude", "residence_zip", "chi_commarea",
]


def contains_any(text, keywords):
    """
    Return a boolean Series marking rows whose text contains any keyword.

    re.escape matters here: keywords like "U-47700" contain characters that
    would otherwise be read as regex syntax.
    """
    pattern = "|".join(re.escape(word) for word in keywords)
    return text.str.contains(pattern, regex=True)


def build_cause_text(df):
    """
    Combine all cause-of-death lines into one uppercase string per case.

    Parameters
    ----------
    df : pd.DataFrame
        Raw ME cases containing the CAUSE_COLUMNS.

    Returns
    -------
    pd.Series
        Uppercase cause text, with Lines A, B, and C included for every year.
    """
    present_columns = [col for col in CAUSE_COLUMNS if col in df.columns]
    return df[present_columns].fillna("").agg(" ".join, axis=1).str.upper()


def flag_overdoses(df):
    """
    Add columns marking overdose deaths and which drug classes were involved.

    Parameters
    ----------
    df : pd.DataFrame
        Raw ME cases.

    Returns
    -------
    pd.DataFrame
        Same rows plus `cause_text`, `is_overdose`, `fentanyl_involved`,
        `opioid_involved`, and `stimulant_involved`.
    """
    df = df.copy()
    df["cause_text"] = build_cause_text(df)

    names_a_drug = contains_any(df["cause_text"], DRUG_KEYWORDS)
    names_poisoning = contains_any(df["cause_text"], POISONING_KEYWORDS)

    # Requiring both keeps out cases like "PNEUMONIA ... CHRONIC DRUG ABUSE",
    # where drug use is mentioned but poisoning wasn't the cause
    df["is_overdose"] = names_a_drug & names_poisoning

    df["fentanyl_involved"] = contains_any(df["cause_text"], FENTANYL_KEYWORDS)
    df["opioid_involved"] = contains_any(df["cause_text"], OPIOID_KEYWORDS)
    df["stimulant_involved"] = contains_any(df["cause_text"], STIMULANT_KEYWORDS)
    return df


def clean_dates(df):
    """
    Parse dates, add calendar and time-of-day columns, and drop out-of-range records.

    Notes
    -----
    `death_date` is the date of record (it's what CDC counts use). For
    time-of-day patterns we use `incident_date` instead, because a death time
    is often when someone was pronounced dead at a hospital, not when the
    overdose happened.
    """
    df = df.copy()
    df["death_date"] = pd.to_datetime(df["death_date"])
    df["incident_date"] = pd.to_datetime(df["incident_date"])

    in_range = (df["death_date"] >= ME_START_DATE) & (df["death_date"] <= datetime.now())
    dropped = (~in_range).sum()
    print(f"  dropped {dropped} cases dated before {ME_START_DATE} or in the future")
    df = df[in_range].copy()

    df["death_year"] = df["death_date"].dt.year
    df["death_month"] = df["death_date"].dt.to_period("M").astype(str)
    df["death_weekday"] = df["death_date"].dt.day_name()
    df["incident_hour"] = df["incident_date"].dt.hour
    return df


def report_rule_overlap(df):
    """Print how our text rule compares to the ME's own opioid flag."""
    me_flag = df["opioids"].fillna(False).astype(bool)
    print("\n  Our overdose rule vs the ME opioids flag:")
    print(pd.crosstab(df["is_overdose"], me_flag,
                      rownames=["is_overdose"], colnames=["ME opioids flag"]))


def report_missing_coordinates(df):
    """
    Print the share of overdose cases without lat/long, by year.

    If missing coordinates cluster in certain years, dropping them would
    distort the trend, so we look before deciding what to do.
    """
    missing_by_year = (
        df.assign(missing_coords=df["latitude"].isna())
        .groupby("death_year")["missing_coords"]
        .agg(["sum", "mean"])
        .rename(columns={"sum": "missing", "mean": "share_missing"})
    )
    print("\n  Overdose cases missing coordinates, by year:")
    print(missing_by_year.round(3))


def main():
    raw = pd.read_csv(RAW_DIR / "me_accidental_cases.csv", low_memory=False)
    print(f"  loaded {len(raw):,} accidental cases")

    flagged = flag_overdoses(raw)
    report_rule_overlap(flagged)

    overdoses = clean_dates(flagged[flagged["is_overdose"]])
    print(f"\n  {len(overdoses):,} overdose deaths after date cleaning")
    report_missing_coordinates(overdoses)

    output_path = PROCESSED_DIR / PROCESSED_FILENAME
    overdoses[KEEP_COLUMNS].to_csv(output_path, index=False)
    print(f"\n  saved to data/processed/{PROCESSED_FILENAME}")


if __name__ == "__main__":
    main()
