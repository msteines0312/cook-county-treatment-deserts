"""
Run the full Phase 1 pipeline from the project root:

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
    fetch_treatment,
)
from src.config import PROCESSED_DIR


def main():
    print("1/7 Fetching ME accidental death cases")
    fetch_overdoses.save_raw(fetch_overdoses.fetch_me_cases())

    print("\n2/6 Classifying overdose deaths")
    clean_overdoses.main()

    print("\n3/6 Downloading census tracts and blocks")
    fetch_census.fetch_tract_boundaries()
    fetch_census.fetch_block_population()

    print("\n4/6 Pulling ACS demographics")
    try:
        fetch_census.fetch_acs()
    except RuntimeError as error:
        # Everything else works without a Census key, so don't stop the run over it
        print(f"  skipped: {error}")

    print("\n5/6 Assigning deaths to tracts")
    assign_tracts.main()

    print("\n6/6 Pulling treatment sites and building the tract table")
    fetch_treatment.main()
    build_tract_table.main()

    print("
7/7 Writing suppressed extracts for Tableau")
    export_tableau.main()

    print(f"\nDone. Main output: {PROCESSED_DIR / build_tract_table.OUTPUT_FILENAME}")


if __name__ == "__main__":
    main()
