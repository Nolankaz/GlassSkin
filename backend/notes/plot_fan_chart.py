"""Render Monte Carlo percentile bands and a deterministic fixture reference.

Run from backend/ with ``./.venv/bin/python notes/plot_fan_chart.py``. It writes
``notes/fan_chart.png`` and prints selected band values to stdout.
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
import numpy as np

from simulation.engine import simulate
from simulation.models import PatientResponse, SimulationConfig, SkinState, TreatmentEffect, TreatmentParameters
from simulation.monte_carlo import simulate_many


# FIXTURE VALUES ONLY — NOT MEDICAL
FIXTURE_DURATION_DAYS = 90
FIXTURE_TIME_STEP_DAYS = 1
FIXTURE_N_TRIALS = 10_000
FIXTURE_SEED = 137
FIXTURE_ACNE_DELAY_DAYS = 14
FIXTURE_TABLE_DAYS = (0, 14, 30, 60, 90)
FIXTURE_PLOT_METRICS = ("inflammatory_acne", "dryness")
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

OUTPUT_PATH = SCRIPT_DIR / "fan_chart.png"


def fixture_treatment():
    return TreatmentParameters(
        treatment_id="fixture_monte_carlo",
        display_name="FIXTURE MONTE CARLO (NOT MEDICAL)",
        parameter_version="fixture",
        effects=[
            TreatmentEffect(target_metric="inflammatory_acne", effect_kind="therapeutic", direction="decrease", delay_days=FIXTURE_ACNE_DELAY_DAYS, mean_magnitude=5.0, uncertainty=2.0, time_scale_days=35, time_curve="logistic"),
            TreatmentEffect(target_metric="dryness", effect_kind="side_effect", direction="increase", delay_days=0, mean_magnitude=3.0, uncertainty=1.2, time_scale_days=18, time_curve="exponential"),
            TreatmentEffect(target_metric="dryness", effect_kind="therapeutic", direction="decrease", delay_days=28, mean_magnitude=3.0, uncertainty=0.9, time_scale_days=42, time_curve="delayed_linear"),
        ],
    )


def verify_result(initial_state, result):
    for metric in FIXTURE_PLOT_METRICS:
        band = result.metric_band(metric)
        p10 = np.asarray(band.p10)
        p50 = np.asarray(band.p50)
        p90 = np.asarray(band.p90)
        initial_value = getattr(initial_state, metric)
        np.testing.assert_allclose([p10[0], p50[0], p90[0]], initial_value, rtol=0.0, atol=1e-12)
        assert np.isfinite([p10, p50, p90]).all()
        assert np.all((0.0 <= p10) & (p10 <= p50) & (p50 <= p90) & (p90 <= 10.0))

    acne_band = result.metric_band("inflammatory_acne")
    for time_index, t_days in enumerate(result.times_days):
        if t_days <= FIXTURE_ACNE_DELAY_DAYS:
            expected = initial_state.inflammatory_acne
            np.testing.assert_allclose([acne_band.p10[time_index], acne_band.p50[time_index], acne_band.p90[time_index]], expected, rtol=0.0, atol=1e-12)

    untargeted_band = result.metric_band(FIXTURE_UNTARGETED_METRIC)
    expected = getattr(initial_state, FIXTURE_UNTARGETED_METRIC)
    for percentile in (untargeted_band.p10, untargeted_band.p50, untargeted_band.p90):
        np.testing.assert_allclose(percentile, expected, rtol=0.0, atol=0.0)


def print_table(result, trajectory):
    print("Selected fan-chart values (FIXTURE / NOT MEDICAL)")
    print(f"{'day':>5} {'metric':>22} {'p10':>10} {'p50':>10} {'p90':>10} {'reference':>12}")
    for day in FIXTURE_TABLE_DAYS:
        time_index = result.times_days.index(float(day))
        for metric in FIXTURE_PLOT_METRICS:
            band = result.metric_band(metric)
            reference = trajectory.metric_series(metric)[time_index]
            print(f"{day:>5d} {metric:>22} {band.p10[time_index]:>10.6f} {band.p50[time_index]:>10.6f} {band.p90[time_index]:>10.6f} {reference:>12.6f}")


def render_plot(result, trajectory):
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.8), sharey=True)
    colors = {"inflammatory_acne": "#3b82f6", "dryness": "#f97316"}
    titles = {"inflammatory_acne": "Inflammatory acne", "dryness": "Dryness"}

    for axes_item, metric in zip(axes, FIXTURE_PLOT_METRICS):
        band = result.metric_band(metric)
        color = colors[metric]
        axes_item.fill_between(result.times_days, band.p10, band.p90, color=color, alpha=0.22, label="p10–p90 band")
        axes_item.plot(result.times_days, band.p50, color=color, linewidth=2.2, label="Monte Carlo median (p50)")
        axes_item.plot(trajectory.times_days, trajectory.metric_series(metric), color="#111827", linestyle="--", linewidth=1.8, label="Deterministic reference")
        axes_item.set_xlabel("Days since treatment start")
        axes_item.set_ylim(0.0, 10.0)
        axes_item.set_title(titles[metric])
        axes_item.grid(True, alpha=0.25)
        axes_item.legend(loc="best", fontsize=8)

    axes[0].set_ylabel("Metric score")
    untargeted_band = result.metric_band(FIXTURE_UNTARGETED_METRIC)
    inset = axes[1].inset_axes([0.55, 0.08, 0.41, 0.28])
    inset.fill_between(result.times_days, untargeted_band.p10, untargeted_band.p90, color="#10b981", alpha=0.22)
    inset.plot(result.times_days, untargeted_band.p50, color="#047857", linewidth=1.5)
    inset.set_xlim(0.0, FIXTURE_DURATION_DAYS)
    inset.set_ylim(0.0, 10.0)
    inset.set_title(f"Untargeted {FIXTURE_UNTARGETED_METRIC}\nflat, zero-width", fontsize=8)
    inset.grid(True, alpha=0.2)
    inset.tick_params(labelsize=7)

    figure.suptitle("Monte Carlo fan chart — FIXTURE — NOT MEDICAL", fontsize=13, y=0.98)
    figure.text(0.5, 0.925, f"n_trials = {FIXTURE_N_TRIALS:,} · seed = {FIXTURE_SEED}", ha="center", fontsize=11)
    figure.text(0.5, 0.875, "p10–p90 = middle 80% of simulated patient outcomes at each day (marginal percentiles, not fixed patient trajectories)", ha="center", fontsize=9.5)
    figure.subplots_adjust(left=0.07, right=0.99, bottom=0.12, top=0.79, wspace=0.03)
    figure.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(figure)


def main():
    initial_state = SkinState(**FIXTURE_INITIAL_VALUES)
    treatment = fixture_treatment()
    run_config = SimulationConfig(duration_days=FIXTURE_DURATION_DAYS, time_step_days=FIXTURE_TIME_STEP_DAYS, n_trials=FIXTURE_N_TRIALS, random_seed=FIXTURE_SEED)
    result = simulate_many(initial_state, treatment, run_config)
    reference_response = PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0)
    trajectory = simulate(initial_state, treatment, run_config, reference_response)

    verify_result(initial_state, result)
    print_table(result, trajectory)
    render_plot(result, trajectory)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
