"""
Write the flat files the Tableau dashboard reads, with small numbers suppressed.

Everything in outputs/tableau/ is meant to be published, so this is the step
where the privacy guardrail is enforced: tract-level death counts under
SUPPRESSION_THRESHOLD are blanked (along with the rate built from them), and
per-year tract counts are left out entirely since most would be tiny.

Outputs:
  tracts.geojson      tract shapes with access, burden, and demographic fields
  annual_trend.csv    countywide deaths by year and drug involvement
  moud_sites.csv      treatment sites (public directory data)
"""

import geopandas as gpd
import pandas as pd

from src.config import (
    ANALYSIS_END_YEAR,
    ANALYSIS_START_YEAR,
    CRS_LATLON,
    PROCESSED_DIR,
    REFERENCE_DIR,
    SUPPRESSION_THRESHOLD,
    TABLEAU_DIR,
)
from src.fetch_census import TRACTS_FILENAME

TRACT_FIELDS = [
    "GEOID", "tract_name", "population_2020",
    "overdose_deaths", "fentanyl_deaths", "overdose_rate_per_100k",
    "miles_to_moud", "miles_to_moud_medicaid", "miles_to_methadone",
    "access_moud_per_100k_pop", "access_moud_per_100_deaths",
    "access_moud_medicaid_per_100_deaths", "access_group",
    "median_household_income", "pct_poverty", "pct_uninsured", "pct_no_vehicle",
    "pct_nh_black", "pct_hispanic", "pct_nh_white", "pct_nh_asian",
]


def suppress_small_counts(tracts):
    """
    Blank out death counts under the threshold, and the rates built from them.

    Returns
    -------
    pd.DataFrame
        Same rows, with a `deaths_suppressed` flag so the dashboard can label
        those tracts "fewer than 10" instead of showing them as missing data.
    """
    tracts = tracts.copy()
    small = tracts["overdose_deaths"] < SUPPRESSION_THRESHOLD
    tracts["deaths_suppressed"] = small
    tracts.loc[small, ["overdose_deaths", "overdose_rate_per_100k"]] = None

    # Fentanyl deaths are a subset, so they need their own check. A tract can
    # have 25 deaths total but only 4 involving fentanyl.
    tracts.loc[tracts["fentanyl_deaths"] < SUPPRESSION_THRESHOLD, "fentanyl_deaths"] = None
    return tracts


def export_tracts():
    """Tract shapes plus analysis fields, as GeoJSON (Tableau reads it as a spatial file)."""
    tract_table = pd.read_csv(PROCESSED_DIR / "tract_table.csv", dtype={"GEOID": str})
    shapes = gpd.read_file(REFERENCE_DIR / TRACTS_FILENAME)[["GEOID", "geometry"]]

    tracts = suppress_small_counts(tract_table[TRACT_FIELDS])
    tracts = shapes.merge(tracts, on="GEOID").to_crs(CRS_LATLON)

    # Simplify the outlines (about 10 meters of tolerance) so the dashboard
    # loads fast. That's invisible at the zoom levels a county map uses.
    tracts["geometry"] = tracts.geometry.simplify(0.0001, preserve_topology=True)
    tracts.round(3).to_file(TABLEAU_DIR / "tracts.geojson", driver="GeoJSON")
    print(f"  tracts.geojson: {len(tracts):,} tracts, "
          f"{tracts['deaths_suppressed'].sum()} with suppressed counts")


def export_annual_trend():
    """Countywide deaths per year, split by drug involvement. No suppression needed at this level."""
    deaths = pd.read_csv(PROCESSED_DIR / "overdose_deaths_tracts.csv", dtype={"GEOID": str})
    deaths = deaths[deaths["death_year"].between(ANALYSIS_START_YEAR, ANALYSIS_END_YEAR)]
    trend = deaths.groupby("death_year").agg(
        total_deaths=("casenumber", "size"),
        fentanyl_involved=("fentanyl_involved", "sum"),
        opioid_involved=("opioid_involved", "sum"),
        stimulant_involved=("stimulant_involved", "sum"),
    ).reset_index()
    trend.to_csv(TABLEAU_DIR / "annual_trend.csv", index=False)
    print(f"  annual_trend.csv: {len(trend)} years")


def export_sites():
    """MOUD sites from the public FindTreatment directory."""
    facilities = pd.read_csv(PROCESSED_DIR / "treatment_facilities.csv")
    sites = facilities[facilities["offers_moud"]].drop(columns=["offers_moud"])
    sites.to_csv(TABLEAU_DIR / "moud_sites.csv", index=False)
    print(f"  moud_sites.csv: {len(sites)} sites")


def main():
    export_tracts()
    export_annual_trend()
    export_sites()


if __name__ == "__main__":
    main()
