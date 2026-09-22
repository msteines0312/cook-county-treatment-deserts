"""
Run the full Phase 1 ETL from the project root:

    python -m src.run_pipeline

Each step saves its output to disk, so a later step can be rerun on its own
without pulling from the APIs again.
"""

from src import clean_overdoses, fetch_census, fetch_overdoses, fetch_treatment


def main():
    # TODO: wire the steps together once each module works on its own:
    #   1. fetch_overdoses  -> data/raw/me_accidental_cases.csv
    #   2. clean_overdoses  -> data/processed/overdose_deaths.csv
    #   3. fetch_treatment  -> data/processed/moud_facilities.csv
    #   4. fetch_census     -> data/reference/ tracts + data/processed/acs_tracts.csv
    #   5. spatial join deaths -> tracts (build this once 1 through 4 exist)
    raise NotImplementedError


if __name__ == "__main__":
    main()
