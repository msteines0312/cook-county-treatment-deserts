"""
Run the full data pipeline from the project root:

    python -m src.run_pipeline

Each step saves its output to disk, so any single step can also be rerun on
its own (for example `python -m src.assign_tracts`) without hitting the APIs again.
"""

from src import (
    assign_tracts,
    build_tract_table,
    clean_overdoses,
    export_tableau,
    fetch_census,
    fetch_overdoses,
    fetch_places,
    fetch_treatment,
    race_rates,
)
from src.config import PROCESSED_DIR


def main():
    print("1/8 Fetching ME accidental death cases")
    fetch_overdoses.save_raw(fetch_overdoses.fetch_me_cases())

    print("\n2/8 Classifying overdose deaths")
    clean_overdoses.main()

    print("\n3/8 Downloading census tracts and blocks")
    fetch_census.fetch_tract_boundaries()
    fetch_census.fetch_block_population()

    print("\n4/8 Pulling ACS demographics and CDC PLACES health estimates")
    try:
        fetch_census.fetch_acs()
    except RuntimeError as error:
        # Everything else works without a Census key, so don't stop the run over it
        print(f"  skipped: {error}")
    fetch_places.fetch_places()

    print("\n5/8 Assigning deaths to tracts")
    assign_tracts.main()

    print("\n6/8 Pulling treatment sites and building the tract table")
    fetch_treatment.main()
    build_tract_table.main()

    print("\n7/8 Age-adjusted death rates by race and ethnicity")
    race_rates.main()

    print("\n8/8 Writing suppressed extracts for Tableau")
    export_tableau.main()

    print(f"\nDone. Main output: {PROCESSED_DIR / build_tract_table.OUTPUT_FILENAME}")


if __name__ == "__main__":
    main()
