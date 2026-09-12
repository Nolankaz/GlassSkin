"""Render fixture time curves for development inspection.

This script lives outside simulation/ because it imports Matplotlib, preserving
the rule that simulation/ is importable without any third-party numerical
package. Run it from backend/ with ``./.venv/bin/python notes/plot_curves.py``.
It writes ``notes/curves.png`` and prints a comparison table to stdout.
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

from simulation.curves import progress


# Arbitrary illustration fixtures only; these are NOT MEDICAL parameters.
FIXTURE_HORIZON_DAYS = 180
FIXTURE_STEP_DAYS = 1
FIXTURE_TIME_SCALE_DAYS = 60.0
# Used only for delayed_linear so its plotted line does not hide linear.
FIXTURE_DELAYED_LINEAR_DELAY_DAYS = 21.0

TABLE_DAYS = (0, 15, 30, 60, 90, 180)
OUTPUT_PATH = SCRIPT_DIR / "curves.png"
CURVE_SPECS = (
    ("linear", 0.0),
    ("delayed_linear", FIXTURE_DELAYED_LINEAR_DELAY_DAYS),
    ("exponential", 0.0),
    ("logistic", 0.0),
)


def render_plot():
    days = range(0, FIXTURE_HORIZON_DAYS + 1, FIXTURE_STEP_DAYS)
    figure, axes = plt.subplots(figsize=(10, 6))

    for curve, delay_days in CURVE_SPECS:
        values = [progress(curve, day, delay_days, FIXTURE_TIME_SCALE_DAYS) for day in days]
        label = f"{curve} (delay={delay_days:g} days, scale={FIXTURE_TIME_SCALE_DAYS:g} days)"
        axes.plot(days, values, label=label)

    axes.axhline(1.0, color="gray", linestyle="--", linewidth=1.2, label="asymptote / full effect")
    axes.set_xlabel("days since treatment start")
    axes.set_ylabel("fraction of full effect")
    axes.set_ylim(0.0, 1.08)
    axes.set_title("Time-curve progress — FIXTURE illustration, NOT MEDICAL")
    axes.grid(True, alpha=0.25)
    axes.legend()
    figure.tight_layout()
    figure.savefig(OUTPUT_PATH, dpi=160)
    plt.close(figure)


def print_table():
    print("Progress comparison (delay=0, FIXTURE, NOT MEDICAL)")
    print(f"{'curve':<16}" + "".join(f"{day:>12d}" for day in TABLE_DAYS))
    for curve, _ in CURVE_SPECS:
        values = [progress(curve, day, 0.0, FIXTURE_TIME_SCALE_DAYS) for day in TABLE_DAYS]
        print(f"{curve:<16}" + "".join(f"{value:>12.6f}" for value in values))


def main():
    render_plot()
    print_table()
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
