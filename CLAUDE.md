# Cook County Treatment Deserts

Public health spatial analysis: overdose deaths vs access to MOUD treatment in Cook County, by census tract. Portfolio project, analysis plan in README.md.

## Commands
- Run pipeline: `python -m src.run_pipeline` (from project root, so `src.` imports resolve)
- Run one step: `python -m src.fetch_overdoses`

## Conventions
- All paths, thresholds, and definitions live in `src/config.py`. Don't hardcode them in modules or notebooks.
- Any judgment call (definitions, thresholds, exclusions) gets an entry in `docs/methodology.md`.
- `data/raw/` is write-once. Cleaning reads from raw and writes to `processed/`.
- Distances are computed in EPSG:3435 (feet), never in lat/long.
- Tract GEOIDs are 11-character strings. Read them with `dtype=str` or the leading zeros get lost.
- Suppress counts below `SUPPRESSION_THRESHOLD` before anything is saved to `outputs/`.
- Frame findings around access and structure, not group behavior.
- Matt fills in the module logic. Provide frames and guidance, not finished code, unless asked.

## Data gotchas
- ME API dataset `cjeq-bs86`: some cases lack lat/long, some dates fall outside 2014 to present, and the cause text has typos.
- Since Sept 2023 `primarycause` merges Lines A, B, and C.
- Census API returns negative sentinel values (e.g. -666666666) for missing estimates.
- FindTreatment `services` is a list of {f1, f2, f3}. f2 == "OT" is opioid treatment and "PAY" is payment accepted.
