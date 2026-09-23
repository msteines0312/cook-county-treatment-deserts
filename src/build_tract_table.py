"""
Build the main analysis table: one row per Cook County census tract.

Joins together:
  - overdose death counts (2015 through 2025)
  - 2020 census population, from the block file
  - a population-weighted center for each tract
  - straight-line distance from that center to the nearest MOUD site
  - 2SFCA access scores (treatment supply relative to population and to need)
  - ACS demographics, if they've been pulled (needs a Census API key)
"""

import geopandas as gpd
import numpy as np
import pandas as pd

from src.access import distance_matrix_feet, two_step_fca
from src.config import (
    ANALYSIS_END_YEAR,
    ANALYSIS_START_YEAR,
    CATCHMENT_MILES,
    CRS_LATLON,
    CRS_PROJECTED,
    DESERT_DISTANCE_MILES,
    FEET_PER_MILE,
    MIN_POPULATION_FOR_RATE,
    NEED_END_YEAR,
    NEED_START_YEAR,
    PROCESSED_DIR,
    REFERENCE_DIR,
)
from src.fetch_census import ACS_FILENAME, BLOCKS_FILENAME, TRACTS_FILENAME
from src.fetch_places import PROCESSED_FILENAME as PLACES_FILENAME

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


def add_access_scores(tract_table, centers, sites, catchment_miles=CATCHMENT_MILES):
    """
    Add 2SFCA access columns to the tract table.

    Two kinds of demand:
      - population: MOUD sites per 100k residents in reach (the textbook version)
      - need: MOUD sites per 100 annual overdose deaths in reach, using
        NEED_START_YEAR through NEED_END_YEAR. This is the version that answers
        "is treatment supply matched to where people are dying?"

    Each site counts as 1 unit of supply. FindTreatment doesn't publish
    capacity (slots, hours, waitlists), so a small buprenorphine practice and
    a large methadone clinic count the same. See methodology D4c.
    """
    tract_table = tract_table.copy()
    need_years = range(NEED_START_YEAR, NEED_END_YEAR + 1)
    need_columns = [f"deaths_{year}" for year in need_years]
    tract_table["need_deaths_per_year"] = tract_table[need_columns].sum(axis=1) / len(need_years)

    # centers and tract_table are both in GEOID order from the same source,
    # but align explicitly so a future change can't silently scramble rows
    centers = centers.set_index("GEOID").loc[tract_table["GEOID"]]
    population = tract_table["population_2020"]
    need = tract_table["need_deaths_per_year"]

    supply_sets = {
        "moud": sites[sites["offers_moud"]],
        "moud_medicaid": sites[sites["offers_moud"] & sites["accepts_medicaid"]],
    }
    for label, supply in supply_sets.items():
        distances = distance_matrix_feet(centers, supply)
        tract_table[f"access_{label}_per_100k_pop"] = (
            two_step_fca(distances, population, catchment_miles) * 100_000
        )
        # Floor of 1 death a year per site: a site with no deaths nearby would
        # otherwise divide by zero and hand its tracts an infinite score
        tract_table[f"access_{label}_per_100_deaths"] = (
            two_step_fca(distances, need, catchment_miles, min_site_demand=1) * 100
        )
    return tract_table


def label_quadrants(tract_table):
    """
    Sort tracts into four groups by overdose burden and access relative to need.

    "High burden" means an overdose rate in the county's top quartile.
    "Low access" means fewer MOUD sites per 100 deaths than the county as a
    whole, where the county figure is the need-weighted average access score.

    Why not the median access score: at small catchments over half of all
    tracts (mostly suburbs) have no site in reach, so the median is exactly 0
    and "below the median" matches nothing. The need-weighted average is
    close to total sites / total deaths, which is easier to explain anyway.
    """
    tract_table = tract_table.copy()
    rate_cutoff = tract_table["overdose_rate_per_100k"].quantile(0.75)
    access_benchmark = np.average(
        tract_table["access_moud_per_100_deaths"],
        weights=tract_table["need_deaths_per_year"],
    )
    print(f"  county benchmark: {access_benchmark:.2f} MOUD sites per 100 annual deaths")

    high_burden = tract_table["overdose_rate_per_100k"] >= rate_cutoff
    low_access = tract_table["access_moud_per_100_deaths"] < access_benchmark
    tract_table["access_group"] = np.select(
        [high_burden & low_access, high_burden & ~low_access,
         ~high_burden & low_access, ~high_burden & ~low_access],
        ["high burden, low access", "high burden, high access",
         "low burden, low access", "low burden, high access"],
        # np.select's default is the integer 0, which can't share an array
        # with strings, so give it a string default
        default="no rate",
    )
    # Tracts too small for a rate don't get a group
    tract_table.loc[tract_table["overdose_rate_per_100k"].isna(), "access_group"] = "no rate"
    return tract_table


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

    tract_table = add_access_scores(tract_table, centers, sites)
    tract_table = label_quadrants(tract_table)

    acs_path = PROCESSED_DIR / ACS_FILENAME
    if acs_path.exists():
        acs = pd.read_csv(acs_path, dtype={"GEOID": str})
        tract_table = tract_table.merge(acs, on="GEOID", how="left")
        print("  joined ACS demographics")
    else:
        print("  ACS file not found, skipping demographics (run fetch_census with a Census API key)")

    places_path = PROCESSED_DIR / PLACES_FILENAME
    if places_path.exists():
        places = pd.read_csv(places_path, dtype={"GEOID": str})
        tract_table = tract_table.merge(places, on="GEOID", how="left")
        print("  joined CDC PLACES health estimates")

    tract_table.to_csv(PROCESSED_DIR / OUTPUT_FILENAME, index=False)
    print(f"  saved {len(tract_table):,} tracts to data/processed/{OUTPUT_FILENAME}")
    print(f"  deaths in table: {tract_table['overdose_deaths'].sum():,} "
          f"({ANALYSIS_START_YEAR} through {ANALYSIS_END_YEAR})")
    print(f"  tracts more than {DESERT_DISTANCE_MILES} miles from MOUD: {tract_table['is_desert'].sum():,}")
    print(f"  access groups: {tract_table['access_group'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
