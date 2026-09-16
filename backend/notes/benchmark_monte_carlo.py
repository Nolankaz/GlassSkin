"""Benchmark the full public Monte Carlo paths with fixture-only inputs.

Run from backend/ with ``./.venv/bin/python notes/benchmark_monte_carlo.py``.
The timing assertion belongs here rather than in pytest because it is a
development-machine performance check.
"""

from pathlib import Path
import sys
import time

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent

# pytest.ini sets pythonpath = . for backend imports; add the same backend root
# when running this script directly from notes/.
sys.path.insert(0, str(BACKEND_DIR))

from simulation.models import SKIN_METRIC_NAMES, SimulationConfig, SkinState, TreatmentEffect, TreatmentParameters
from simulation.monte_carlo import simulate_many, simulate_many_naive


# FIXTURE VALUES ONLY — NOT MEDICAL
FIXTURE_DURATION_DAYS = 90
FIXTURE_TIME_STEP_DAYS = 1
FIXTURE_SEED = 137
FIXTURE_VECTORISED_TRIAL_COUNTS = (1_000, 10_000, 50_000)
FIXTURE_NAIVE_TRIAL_COUNTS = (1_000, 10_000)
FIXTURE_VECTORISED_REPEATS = 5
FIXTURE_INITIAL_VALUES = {
    "inflammatory_acne": 7.5,
    "cystic_nodular_acne": 5.25,
    "blackheads": 4.5,
    "whiteheads": 4.0,
    "pie": 6.0,
    "pih": 5.5,
    "redness": 4.25,
    "rosacea": 2.0,
    "dryness": 3.0,
    "sensitivity": 4.75,
    "irritation": 3.5,
    "oiliness": 6.25,
    "texture_irregularity": 5.0,
    "acne_scarring": 4.0,
    "enlarged_pores": 5.75,
    "dark_circles": 6.5,
    "uneven_skin_tone": 5.25,
}


def fixture_treatment():
    return TreatmentParameters(
        treatment_id="fixture_monte_carlo",
        display_name="FIXTURE MONTE CARLO (NOT MEDICAL)",
        parameter_version="fixture",
        effects=[
            TreatmentEffect(target_metric="inflammatory_acne", effect_kind="therapeutic", direction="decrease", delay_days=14, mean_magnitude=5.0, uncertainty=2.0, time_scale_days=35, time_curve="logistic"),
            TreatmentEffect(target_metric="dryness", effect_kind="side_effect", direction="increase", delay_days=0, mean_magnitude=3.0, uncertainty=1.2, time_scale_days=18, time_curve="exponential"),
            TreatmentEffect(target_metric="dryness", effect_kind="therapeutic", direction="decrease", delay_days=28, mean_magnitude=3.0, uncertainty=0.9, time_scale_days=42, time_curve="delayed_linear"),
        ],
    )


def result_band_array(result):
    return np.stack([np.column_stack([getattr(result.metric_band(metric), percentile) for metric in SKIN_METRIC_NAMES]) for percentile in ("p10", "p50", "p90")])


def run_config(n_trials):
    return SimulationConfig(duration_days=FIXTURE_DURATION_DAYS, time_step_days=FIXTURE_TIME_STEP_DAYS, n_trials=n_trials, random_seed=FIXTURE_SEED)


def time_vectorised(initial_state, treatment, config):
    elapsed_times = []
    result = None
    for _ in range(FIXTURE_VECTORISED_REPEATS):
        started = time.perf_counter()
        result = simulate_many(initial_state, treatment, config)
        elapsed_times.append(time.perf_counter() - started)
    return min(elapsed_times), result


def time_naive(initial_state, treatment, config):
    started = time.perf_counter()
    result = simulate_many_naive(initial_state, treatment, config)
    return time.perf_counter() - started, result


def assert_results_agree(naive, vectorised):
    assert naive.treatment_id == vectorised.treatment_id
    assert naive.parameter_version == vectorised.parameter_version
    assert naive.n_trials == vectorised.n_trials
    assert naive.random_seed == vectorised.random_seed
    assert naive.times_days == vectorised.times_days
    np.testing.assert_allclose(result_band_array(vectorised), result_band_array(naive), atol=1e-10, rtol=0.0)


def raw_trial_state_mib(n_trials, n_steps):
    return 8 * n_trials * n_steps * len(SKIN_METRIC_NAMES) / 1024 ** 2


def main():
    initial_state = SkinState(**FIXTURE_INITIAL_VALUES)
    treatment = fixture_treatment()
    n_steps = FIXTURE_DURATION_DAYS // FIXTURE_TIME_STEP_DAYS + 1
    vectorised_timings = {}
    vectorised_results = {}
    naive_timings = {}

    for n_trials in FIXTURE_VECTORISED_TRIAL_COUNTS:
        vectorised_timings[n_trials], vectorised_results[n_trials] = time_vectorised(initial_state, treatment, run_config(n_trials))

    for n_trials in FIXTURE_NAIVE_TRIAL_COUNTS:
        naive_timings[n_trials], naive_result = time_naive(initial_state, treatment, run_config(n_trials))
        assert_results_agree(naive_result, vectorised_results[n_trials])

    print("Monte Carlo public-path benchmark (FIXTURE / NOT MEDICAL)")
    print(f"seed={FIXTURE_SEED}  duration={FIXTURE_DURATION_DAYS} days  step={FIXTURE_TIME_STEP_DAYS} day  time_points={n_steps}  effects={len(treatment.effects)}  metrics={len(SKIN_METRIC_NAMES)}")
    print(f"Vectorised values are the minimum of {FIXTURE_VECTORISED_REPEATS} runs; naive values are one run.")
    print(f"{'Trials':>8} {'Naive s':>12} {'Vectorised s':>14} {'Speedup':>10} {'Raw states MiB':>16}")
    for n_trials in FIXTURE_VECTORISED_TRIAL_COUNTS:
        vectorised_seconds = vectorised_timings[n_trials]
        naive_seconds = naive_timings.get(n_trials)
        naive_display = f"{naive_seconds:.6f}" if naive_seconds is not None else "-"
        speedup_display = f"{naive_seconds / vectorised_seconds:.1f}x" if naive_seconds is not None else "-"
        print(f"{n_trials:>8,d} {naive_display:>12} {vectorised_seconds:>14.6f} {speedup_display:>10} {raw_trial_state_mib(n_trials, n_steps):>16.2f}")

    maximum_bytes = 8 * 50_000 * 731 * 17
    print("\nRaw trial-state memory is approximate and excludes temporary/intermediate arrays.")
    print(f"Maximum-config theoretical raw states (50,000 × 731 × 17): {maximum_bytes / 1024 ** 3:.2f} GiB; not simulated")

    ten_thousand_seconds = vectorised_timings[10_000]
    if ten_thousand_seconds >= 1.0:
        raise RuntimeError("10,000-trial vectorised benchmark exceeded the 1-second Step 6 target")
    print(f"10,000-trial Step 6 criterion: PASS ({ten_thousand_seconds:.6f}s < 1.0s)")
    print("Naive/vectorised public result comparisons: PASS")


if __name__ == "__main__":
    main()
