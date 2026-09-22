"""
Build the main analysis table: one row per Cook County census tract.

Joins together:
  - overdose death counts (2015 through 2025)
  - 2020 census population, from the block file
  - a population-weighted center for each tract
  - straight-line distance from that center to the nearest MOUD site
  - ACS demographics, if they've been pulled (needs a Census API key)
"""

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import (
    ANALYSIS_END_YEAR,
    ANALYSIS_START_YEAR,
    CRS_LATLON,
    CRS_PROJECTED,
    DESERT_DISTANCE_MILES,
    FEET_PER_MILE,
    MIN_POPULATION_FOR_RATE,
    PROCESSED_DIR,
    REFERENCE_DIR,
)
from src.fetch_census import ACS_FILENAME, BLOCKS_FILENAME, TRACTS_FILENAME

OUTPUT_FILENAME = "tract_table.csv"
CENTERS_FILENAME = "tract_population_centers.gpkg"


def population_weighted_centers(blocks):
    """
    Compute each tract's population-weighted center from its census blocks.

    Parameters
    ----------
    blocks : gpd.GeoDataFrame
        Census blocks with `tract_geoid` and `population`, in a projected CRS.

    Returns
    -------
    gpd.GeoDataFrame
        One point per tract, with the tract's total 2020 population.

    Notes
    -----
    This is a weighted average of block centroids, using population as the
    weight. The center lands where people actually live, not at the geometric
    middle of the tract, which could be a rail yard or a forest preserve.
    Tracts with zero residents fall back to their plain block average.
    """
    blocks = blocks.copy()
    blocks["x"] = blocks.geometry.centroid.x
    blocks["y"] = blocks.geometry.centroid.y

    def weighted_center(group):
        weights = group["population"]
        if weights.sum() == 0:
            weights = np.ones(len(group))
        return pd.Series({
            "x": np.average(group["x"], weights=weights),
            "y": np.average(group["y"], weights=weights),
            "population_2020": group["population"].sum(),
        })

    centers = blocks.groupby("tract_geoid")[["x", "y", "population"]].apply(weighted_center)
    return gpd.GeoDataFrame(
        centers.drop(columns=["x", "y"]).reset_index().rename(columns={"tract_geoid": "GEOID"}),
        geometry=gpd.points_from_xy(centers["x"], centers["y"]),
        crs=blocks.crs,
    )


def nearest_site_miles(centers, sites, label):
    """
    Add a column with straight-line miles from each tract center to the nearest site.

    Both layers are in EPSG:3435 (feet), so distances come out in feet and get
    converted to miles.
    """
    joined = gpd.sjoin_nearest(centers, sites[["geometry"]], how="left", distance_col="feet")
    # sjoin_nearest returns multiple rows when two sites tie for nearest
    joined = joined[~joined.index.duplicated()]
    centers[f"miles_to_{label}"] = joined["feet"] / FEET_PER_MILE
    return centers


def count_deaths(deaths):
    """
    Count overdose deaths per tract for the analysis years.

    Returns
    -------
    pd.DataFrame
        GEOID plus total, fentanyl-involved, and per-year death counts.
    """
    in_window = deaths["death_year"].between(ANALYSIS_START_YEAR, ANALYSIS_END_YEAR)
    deaths = deaths[in_window]

    totals = deaths.groupby("GEOID").agg(
        overdose_deaths=("casenumber", "size"),
        fentanyl_deaths=("fentanyl_involved", "sum"),
    )
    by_year = (
        deaths.pivot_table(index="GEOID", columns="death_year", values="casenumber",
                           aggfunc="size", fill_value=0)
        .add_prefix("deaths_")
    )
    return totals.join(by_year).reset_index()


def main():
    tracts = gpd.read_file(REFERENCE_DIR / TRACTS_FILENAME)
    blocks = gpd.read_file(REFERENCE_DIR / BLOCKS_FILENAME).to_crs(CRS_PROJECTED)
    deaths = pd.read_csv(PROCESSED_DIR / "overdose_deaths_tracts.csv", dtype={"GEOID": str})
    facilities = pd.read_csv(PROCESSED_DIR / "treatment_facilities.csv")

    centers = population_weighted_centers(blocks)
    centers = centers[centers["GEOID"].isin(tracts["GEOID"])].reset_index(drop=True)
    print(f"  built population-weighted centers for {len(centers):,} tracts")

    sites = gpd.GeoDataFrame(
        facilities,
        geometry=gpd.points_from_xy(facilities["longitude"], facilities["latitude"]),
        crs=CRS_LATLON,
    ).to_crs(CRS_PROJECTED)

    # Three versions of "nearest treatment", from most to least generous
    centers = nearest_site_miles(centers, sites[sites["offers_moud"]], "moud")
    centers = nearest_site_miles(
        centers, sites[sites["offers_moud"] & sites["accepts_medicaid"]], "moud_medicaid")
    centers = nearest_site_miles(centers, sites[sites["offers_methadone"]], "methadone")
    centers.to_file(REFERENCE_DIR / CENTERS_FILENAME)

    tract_table = (
        pd.DataFrame(centers.drop(columns="geometry"))
        .merge(tracts[["GEOID", "tract_name", "land_area_sqm"]], on="GEOID", how="left")
        .merge(count_deaths(deaths), on="GEOID", how="left")
    )
    # Tracts with no deaths aren't in the counts table at all. They're real
    # zeros, not missing data, and the count model in Phase 4 needs them.
    death_columns = [col for col in tract_table.columns if col.endswith("deaths") or col.startswith("deaths_")]
    tract_table[death_columns] = tract_table[death_columns].fillna(0).astype(int)

    years = ANALYSIS_END_YEAR - ANALYSIS_START_YEAR + 1
    # Rate per 100k per year, pooled over all analysis years. Pooling steadies
    # the rate for small tracts, where one or two deaths swing a single year a lot.
    with np.errstate(divide="ignore", invalid="ignore"):
        tract_table["overdose_rate_per_100k"] = (
            tract_table["overdose_deaths"] / (tract_table["population_2020"] * years) * 100_000
        )
    tract_table["overdose_rate_per_100k"] = tract_table["overdose_rate_per_100k"].replace(np.inf, np.nan)
    too_small = tract_table["population_2020"] < MIN_POPULATION_FOR_RATE
    tract_table.loc[too_small, "overdose_rate_per_100k"] = np.nan
    print(f"  {too_small.sum()} tracts under {MIN_POPULATION_FOR_RATE} residents get no rate")
    tract_table["is_desert"] = tract_table["miles_to_moud"] > DESERT_DISTANCE_MILES

    acs_path = PROCESSED_DIR / ACS_FILENAME
    if acs_path.exists():
        acs = pd.read_csv(acs_path, dtype={"GEOID": str})
        tract_table = tract_table.merge(acs, on="GEOID", how="left")
        print("  joined ACS demographics")
    else:
        print("  ACS file not found, skipping demographics (run fetch_census with a Census API key)")

    tract_table.to_csv(PROCESSED_DIR / OUTPUT_FILENAME, index=False)
    print(f"  saved {len(tract_table):,} tracts to data/processed/{OUTPUT_FILENAME}")
    print(f"  deaths in table: {tract_table['overdose_deaths'].sum():,} "
          f"({ANALYSIS_START_YEAR} through {ANALYSIS_END_YEAR})")
    print(f"  tracts more than {DESERT_DISTANCE_MILES} miles from MOUD: {tract_table['is_desert'].sum():,}")


if __name__ == "__main__":
    main()
