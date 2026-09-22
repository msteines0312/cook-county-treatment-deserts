# Cook County Treatment Deserts

Public health spatial analysis: overdose deaths vs access to MOUD treatment in Cook County, by census tract. Portfolio project, analysis plan in README.md.

## Commands
- Run pipeline: `python -m src.run_pipeline` (from project root, so `src.` imports resolve)
- Run one step: `python -m src.fetch_overdoses`
- Run a notebook headless: `.venv/Scripts/python -m nbconvert --to notebook --execute --inplace notebooks/<name>.ipynb`. Use `python -m nbconvert`, not the `jupyter` launcher: without an activated venv, `jupyter` dispatches to the global install and its kernel can't see geopandas.
- Clear notebook outputs before committing: `python -m nbconvert --clear-output --inplace notebooks/*.ipynb`

## Conventions
- All paths, thresholds, and definitions live in `src/config.py`. Don't hardcode them in modules or notebooks.
- Any judgment call (definitions, thresholds, exclusions) gets an entry in `docs/methodology.md`.
- `data/raw/` is write-once. Cleaning reads from raw and writes to `processed/`.
- Distances are computed in EPSG:3435 (feet), never in lat/long.
- Tract GEOIDs are 11-character strings. Read them with `dtype=str` or the leading zeros get lost.
- Suppress counts below `SUPPRESSION_THRESHOLD` before anything is saved to `outputs/`.
- Frame findings around access and structure, not group behavior.
- Claude writes the module logic and works through tasks/todo.md. Explain the non-obvious choices as you go (Matt is learning from the code).

## Data gotchas
- ME API dataset `cjeq-bs86`: some cases lack lat/long, some dates fall outside 2014 to present, and the cause text has typos.
- Since Sept 2023 `primarycause` merges Lines A, B, and C.
- Census API returns negative sentinel values (e.g. -666666666) for missing estimates.
- FindTreatment `services` is a list of {f1, f2, f3}. f2 == "OT" is opioid treatment and "PAY" is payment accepted. OTP listings have `services: null`. Some listings have null coordinates. The API returns rows in a different order per call, so anything that picks a "first" row must sort first.
- ME and FindTreatment are live sources, so reruns shift headline numbers slightly. Docs cite the Sept 22, 2026 pull.
- The ME `opioids` flag means involvement, not cause. Don't use it to define overdoses.
