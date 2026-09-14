"""Run and plot one deterministic fixture trajectory for development inspection.

This script lives outside simulation/ because Matplotlib is a visualization
dependency, not part of the pure simulation engine. Run it from backend/ with
``./.venv/bin/python notes/plot_trajectory.py``. It writes
``notes/trajectory.png`` and prints selected trajectory values to stdout.
"""

from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent

# pytest.ini sets pythonpath = . for backend imports; add the same backend root
# when running this script directly from notes/.
sys.path.insert(0, str(BACKEND_DIR))

import matplotlib

# Agg renders directly to a file and never tries to open a GUI window.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simulation.engine import simulate
from simulation.models import SKIN_METRIC_NAMES, PatientResponse, SimulationConfig, SkinState, TreatmentEffect, TreatmentParameters


# FIXTURE VALUES ONLY — NOT MEDICAL
FIXTURE_DURATION_DAYS = 90
FIXTURE_TIME_STEP_DAYS = 1
FIXTURE_TABLE_DAYS = (0, 7, 14, 30, 60, 90)
FIXTURE_UNTARGETED_METRIC = "redness"
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

OUTPUT_PATH = SCRIPT_DIR / "trajectory.png"


def fixture_treatment():
    return TreatmentParameters(
        treatment_id="fixture_trajectory",
        display_name="FIXTURE TRAJECTORY (NOT MEDICAL)",
        parameter_version="fixture",
        effects=[
            TreatmentEffect(
                target_metric="inflammatory_acne",
                effect_kind="therapeutic",
                direction="decrease",
                delay_days=14,
                mean_magnitude=4.0,
                uncertainty=0.0,
                time_scale_days=35,
                time_curve="logistic",
            ),
            TreatmentEffect(
                target_metric="dryness",
                effect_kind="side_effect",
                direction="increase",
                delay_days=0,
                mean_magnitude=3.0,
                uncertainty=0.0,
                time_scale_days=18,
                time_curve="exponential",
            ),
            TreatmentEffect(
                target_metric="dryness",
                effect_kind="therapeutic",
                direction="decrease",
                delay_days=28,
                mean_magnitude=3.0,
                uncertainty=0.0,
                time_scale_days=42,
                time_curve="delayed_linear",
            ),
        ],
    )


def print_table(trajectory):
    states_by_day = dict(zip(trajectory.times_days, trajectory.states))
    print("Selected trajectory values (FIXTURE, NOT MEDICAL)")
    print(f"{'day':>5} {'inflammatory_acne':>22} {'dryness':>12} {FIXTURE_UNTARGETED_METRIC:>12}")
    for day in FIXTURE_TABLE_DAYS:
        state = states_by_day[float(day)]
        print(f"{day:>5d} {state.inflammatory_acne:>22.6f} {state.dryness:>12.6f} {getattr(state, FIXTURE_UNTARGETED_METRIC):>12.6f}")


def verify_untargeted_metrics(initial_state, treatment, trajectory):
    targeted_metrics = {effect.target_metric for effect in treatment.effects}
    untargeted_metrics = [metric for metric in SKIN_METRIC_NAMES if metric not in targeted_metrics]
    bit_identical = all(getattr(state, metric) == getattr(initial_state, metric) for state in trajectory.states for metric in untargeted_metrics)
    print(f"\nUntargeted metrics bit-identical: {bit_identical}")
    if not bit_identical:
        raise RuntimeError("An untargeted metric changed during the fixture trajectory")


def render_plot(trajectory):
    figure, axes = plt.subplots(figsize=(10, 6))
    axes.plot(trajectory.times_days, trajectory.metric_series("inflammatory_acne"), label="inflammatory_acne")
    axes.plot(trajectory.times_days, trajectory.metric_series("dryness"), label="dryness")
    axes.plot(trajectory.times_days, trajectory.metric_series(FIXTURE_UNTARGETED_METRIC), label=f"{FIXTURE_UNTARGETED_METRIC} (untargeted)")
    axes.set_xlabel("Days since treatment start")
    axes.set_ylabel("Metric value")
    axes.set_ylim(0.0, 10.0)
    axes.set_title("Deterministic trajectory — FIXTURE, NOT MEDICAL")
    axes.grid(True, alpha=0.25)
    axes.legend()
    figure.tight_layout()
    figure.savefig(OUTPUT_PATH, dpi=160)
    plt.close(figure)


def main():
    initial_state = SkinState(**FIXTURE_INITIAL_VALUES)
    treatment = fixture_treatment()
    patient_response = PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0)
    run_config = SimulationConfig(duration_days=FIXTURE_DURATION_DAYS, time_step_days=FIXTURE_TIME_STEP_DAYS)
    trajectory = simulate(initial_state, treatment, run_config, patient_response)

    print_table(trajectory)
    verify_untargeted_metrics(initial_state, treatment, trajectory)
    render_plot(trajectory)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
