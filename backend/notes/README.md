# Simulator evidence and tooling

## Purpose

`backend/notes/` holds development tooling and evidence for simulation calibration, plots, benchmarking, validation, and their documentation. The running application imports nothing from this folder; SciPy and Matplotlib are development-only dependencies in [`requirements-dev.txt`](../requirements-dev.txt). When used, scripts are run from `backend/` with the project virtual-environment Python; their outputs are not clinical proof.

## Scripts

Paths in this table are relative to `backend/notes/`. Fixture plots illustrate model behavior and are marked not medical in their scripts.

| Script | Purpose | Reads | Writes |
| --- | --- | --- | --- |
| [`fit_treatment_parameters.py`](fit_treatment_parameters.py) | Fit versioned effects and render fit diagnostics. | `calibration/evidence/*.json`; simulation curves and models | `calibration/fit_report.md`; `calibration/fits/*.png`; **`../simulation/parameters/v1/*.json`** |
| [`validate_simulation.py`](validate_simulation.py) | Evaluate frozen `v1` against held-out evidence, fingerprint parameters, and analyze sensitivity. | `calibration/evidence/*.json`; `validation/holdout_evidence.json`; `../simulation/parameters/v1/*.json` | `validation/validation_results.md`; `validation/sensitivity.png` |
| [`plot_curves.py`](plot_curves.py) | Plot fixture time-curve progress and print a comparison table. | In-script fixtures; simulation curves | `curves.png` |
| [`plot_trajectory.py`](plot_trajectory.py) | Plot and inspect a deterministic fixture trajectory. | In-script fixtures; simulation engine and models | `trajectory.png` |
| [`plot_fan_chart.py`](plot_fan_chart.py) | Plot fixture percentile bands and a deterministic reference. | In-script fixtures; simulation engine and Monte Carlo | `fan_chart.png` |
| [`benchmark_monte_carlo.py`](benchmark_monte_carlo.py) | Compare fixture naive and vectorised public paths and print timings. | In-script fixtures; simulation Monte Carlo | None; stdout only |

## Files: hand-written vs generated

- **Hand-written sources and records:** [`calibration/sources.md`](calibration/sources.md) is the source ledger; `calibration/evidence/*.json` holds reviewed, converted fitting inputs. [`validation/validation_protocol.md`](validation/validation_protocol.md) fixes the evaluation rules; [`validation/holdout_evidence.json`](validation/holdout_evidence.json) records evidence kept out of fitting; [`validation/validation_report.md`](validation/validation_report.md) interprets the results and limits.
- **Generated outputs:** `../simulation/parameters/v1/*.json`, `calibration/fit_report.md`, `calibration/fits/*.png`, `validation/validation_results.md`, `validation/sensitivity.png`, `curves.png`, `trajectory.png`, and `fan_chart.png` are written by the scripts above. The benchmark writes no file.

Generated reports, plots, and parameters should not be edited by hand because a script rerun may overwrite them. The hand-written evidence, protocol, and report are inputs or dated records and must not be overwritten by tooling. `calibration/research/` holds local-only raw research notes and is gitignored; it may be absent in a fresh clone.

## Pipeline

1. Record source observations in the hand-written ledger and evidence JSON.
2. The calibration fitter consumes those inputs.
3. It produces `v1` parameter JSON, the fit report, and fit plots.
4. Freeze `v1` before evaluating held-out evidence.
5. Record the hand-written validation protocol and separate holdout evidence. Commit `9eae881` recorded them before results.
6. The validation tool reads and fingerprints frozen `v1`, then evaluates the holdout and sensitivity.
7. It produces validation results and the sensitivity plot.
8. Interpret the results in the hand-written validation report. Commit `ac26d42` added the results and report afterward; this order shows the protocol and holdout were recorded before evaluation.

## V1 freeze rule

`backend/simulation/parameters/v1/*.json` is frozen V1 data. **Do not edit it manually or rerun `fit_treatment_parameters.py` against V1.** The fitter's output directory points directly at `v1`, so another run could change the frozen model if dependencies or numerical fitting differ. Future recalibration must write to a new version directory.

After running *any* `backend/notes/` script in the future, inspect this from the repository root before committing:

```bash
git status --short backend/simulation backend/notes
```

See [V5 — Freeze in the validation protocol](validation/validation_protocol.md) and the [simulation design](../SIMULATION_DESIGN.md) for the validation record and model boundaries.

## Tests that depend on this folder

[`test_fit_treatment_parameters.py`](../tests/test_fit_treatment_parameters.py) imports the fitter and calibration evidence. [`test_validation.py`](../tests/test_validation.py) imports the fitter's evidence path and checks the holdout, ledger, and frozen parameters. Keep `backend/notes/` in place so these imports and evidence paths continue to resolve.

## Usage / safety note

Read a script and its output paths before running it. Generated reports and plots may change; frozen V1 parameters must not.
