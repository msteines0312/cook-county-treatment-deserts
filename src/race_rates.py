"""
Age-adjusted overdose death rates by race and ethnicity, per year.

Why age-adjust: groups with different age structures can't be compared on
crude rates. If one group skews older and overdose deaths peak in middle age,
its crude rate shifts for reasons that have nothing to do with risk.
Age adjustment computes a rate inside each age band, then combines those rates
with one fixed set of weights (the 2000 U.S. standard population), so every
group is compared as if it had the same age mix. This is the CDC's standard
method for published overdose rates.

Denominators come from ACS 1-year county estimates for each year, since
population shifted a lot over the period (Cook County's Black population
fell by about 111,000 between 2016 and 2024). Comparisons start in 2016
because the ME didn't reliably record Hispanic ethnicity before then.
"""

import os

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

from src.config import (
    ANALYSIS_END_YEAR,
    CENSUS_API_BASE,
    COUNTY_FIPS,
    PROCESSED_DIR,
    PROJECT_ROOT,
    RACE_ANALYSIS_START_YEAR,
    RAW_DIR,
    STATE_FIPS,
)

load_dotenv(PROJECT_ROOT / ".env")

POPULATION_FILENAME = "acs1_population_by_race_age.csv"
RATES_FILENAME = "age_adjusted_rates_by_race.csv"

# ACS race-by-age tables. B01001B is "Black alone" of any ethnicity: the ACS
# has no non-Hispanic Black age table, so Black deaths are matched the same
# way (race = Black, any ethnicity). Hispanic Black residents are about 1-2%
# of Black Cook County residents, so they're counted in both Black and
# Hispanic. See methodology D7.
RACE_TABLES = {
    "Black": "B01001B",
    "White (non-Hispanic)": "B01001H",
    "Hispanic (any race)": "B01001I",
}

# ACS line numbers for each age band. Male lines are 3-16; the matching
# female line is always 15 higher (18-31).
AGE_BAND_LINES = {
    "0-14": [3, 4, 5],
    "15-24": [6, 7, 8],
    "25-34": [9, 10],
    "35-44": [11],
    "45-54": [12],
    "55-64": [13],
    "65-74": [14],
    "75-84": [15],
    "85+": [16],
}

# 2000 U.S. standard population (per million), collapsed to the bands above.
# 0-14 combines the standard's <1, 1-4, and 5-14 groups (13,818 + 55,317 + 145,565).
STANDARD_POPULATION = {
    "0-14": 214_700,
    "15-24": 138_646,
    "25-34": 135_573,
    "35-44": 162_613,
    "45-54": 134_834,
    "55-64": 87_247,
    "65-74": 66_037,
    "75-84": 44_842,
    "85+": 15_508,
}
AGE_BAND_EDGES = [0, 15, 25, 35, 45, 55, 65, 75, 85, 200]

# ACS 1-year estimates weren't released for 2020 (COVID disrupted collection),
# and 2025 isn't out yet. 2020 uses the average of 2019 and 2021; 2025 reuses 2024.
ACS1_YEARS_MISSING = {2020: [2019, 2021], 2025: [2024]}


def fetch_year(year):
    """Pull population by race and age band for Cook County from one ACS 1-year release."""
    counts = {}
    # The Census API caps a request at 50 variables, so pull one race table
    # (28 variables) per request instead of all 84 at once
    for table in RACE_TABLES.values():
        variables = []
        for lines in AGE_BAND_LINES.values():
            for line in lines:
                variables += [f"{table}_{line:03d}E", f"{table}_{line + 15:03d}E"]
        params = {
            "get": ",".join(variables),
            "for": f"county:{COUNTY_FIPS}",
            "in": f"state:{STATE_FIPS}",
            "key": os.getenv("CENSUS_API_KEY"),
        }
        response = requests.get(f"{CENSUS_API_BASE}/{year}/acs/acs1", params=params, timeout=120)
        response.raise_for_status()
        header, values = response.json()
        counts.update(zip(header, values))

    rows = []
    for race, table in RACE_TABLES.items():
        for band, lines in AGE_BAND_LINES.items():
            population = sum(
                int(counts[f"{table}_{line:03d}E"]) + int(counts[f"{table}_{line + 15:03d}E"])
                for line in lines
            )
            rows.append({"year": year, "race_group": race, "age_band": band, "population": population})
    return pd.DataFrame(rows)


def fetch_population():
    """Population by year, race group, and age band for every analysis year."""
    years = range(RACE_ANALYSIS_START_YEAR, ANALYSIS_END_YEAR + 1)
    available = [year for year in years if year not in ACS1_YEARS_MISSING]
    pulled = pd.concat([fetch_year(year) for year in available], ignore_index=True)

    filled = []
    for missing_year, source_years in ACS1_YEARS_MISSING.items():
        if missing_year not in years:
            continue
        stand_in = (
            pulled[pulled["year"].isin(source_years)]
            .groupby(["race_group", "age_band"], as_index=False)["population"].mean()
            .assign(year=missing_year)
        )
        filled.append(stand_in)

    population = pd.concat([pulled, *filled], ignore_index=True).sort_values(["year", "race_group"])
    population.to_csv(RAW_DIR / POPULATION_FILENAME, index=False)
    print(f"  saved population for {population['year'].nunique()} years "
          f"(2020 and 2025 filled from neighboring years)")
    return population


def assign_race_groups(deaths):
    """
    Label each death with the race groups it counts toward.

    Returns one row per (death, group). A Hispanic Black decedent appears
    twice, once in each group, matching how the ACS tables count people.
    """
    is_hispanic = deaths["latino"].astype(str).str.lower().eq("true")
    labeled = [
        deaths[deaths["race"] == "Black"].assign(race_group="Black"),
        deaths[(deaths["race"] == "White") & ~is_hispanic].assign(race_group="White (non-Hispanic)"),
        deaths[is_hispanic].assign(race_group="Hispanic (any race)"),
    ]
    return pd.concat(labeled, ignore_index=True)


def age_adjusted_rates(deaths, population):
    """
    Compute age-adjusted overdose death rates per 100k by year and race group.

    Returns
    -------
    pd.DataFrame
        year, race_group, deaths, crude_rate, age_adjusted_rate, and a 95% CI.

    Notes
    -----
    The CI uses the normal approximation for a weighted sum of Poisson rates:
    variance = sum(weight^2 * deaths / population^2). It's reasonable here
    because every year-group cell has well over 100 deaths.
    """
    deaths = deaths.dropna(subset=["age"]).copy()
    deaths["age_band"] = pd.cut(deaths["age"], bins=AGE_BAND_EDGES, right=False,
                                labels=list(STANDARD_POPULATION))
    death_counts = (
        assign_race_groups(deaths)
        .groupby(["death_year", "race_group", "age_band"], observed=False)
        .size()
        .rename("deaths")
        .reset_index()
        .rename(columns={"death_year": "year"})
    )

    cells = death_counts.merge(population, on=["year", "race_group", "age_band"])
    total_weight = sum(STANDARD_POPULATION.values())
    cells["weight"] = cells["age_band"].map(STANDARD_POPULATION).astype(float) / total_weight
    cells["band_rate"] = cells["deaths"] / cells["population"]
    cells["weighted_rate"] = cells["weight"] * cells["band_rate"]
    cells["weighted_variance"] = cells["weight"] ** 2 * cells["deaths"] / cells["population"] ** 2

    rates = cells.groupby(["year", "race_group"]).agg(
        deaths=("deaths", "sum"),
        population=("population", "sum"),
        adjusted=("weighted_rate", "sum"),
        variance=("weighted_variance", "sum"),
    ).reset_index()
    rates["crude_rate"] = rates["deaths"] / rates["population"] * 100_000
    rates["age_adjusted_rate"] = rates["adjusted"] * 100_000
    margin = 1.96 * np.sqrt(rates["variance"]) * 100_000
    rates["ci_low"] = rates["age_adjusted_rate"] - margin
    rates["ci_high"] = rates["age_adjusted_rate"] + margin
    return rates.drop(columns=["adjusted", "variance"])


def main():
    population = fetch_population()
    deaths = pd.read_csv(PROCESSED_DIR / "overdose_deaths_tracts.csv", dtype={"GEOID": str})
    deaths = deaths[deaths["death_year"].between(RACE_ANALYSIS_START_YEAR, ANALYSIS_END_YEAR)]

    rates = age_adjusted_rates(deaths, population)
    rates.to_csv(PROCESSED_DIR / RATES_FILENAME, index=False)

    wide = rates.pivot(index="year", columns="race_group", values="age_adjusted_rate").round(1)
    wide["Black to White ratio"] = (wide["Black"] / wide["White (non-Hispanic)"]).round(1)
    print(wide.to_string())


if __name__ == "__main__":
    main()
