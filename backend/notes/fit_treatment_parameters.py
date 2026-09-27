"""Fit versioned treatment parameters from the hand-reviewed Step 4 evidence.

Run from backend/ with ``./.venv/bin/python notes/fit_treatment_parameters.py``.
SciPy and Matplotlib are development dependencies; generated JSON is runtime data.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from typing import get_args


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

from simulation.curves import progress
from simulation.models import CURVES_WITHOUT_DELAY, MAX_EFFECT_UNCERTAINTY, Provenance, TimeCurveType, TreatmentEffect, TreatmentParameters
from simulation.monte_carlo import MAX_RESPONSE_LOG_SD


EVIDENCE_DIR = SCRIPT_DIR / "calibration" / "evidence"
FITS_DIR = SCRIPT_DIR / "calibration" / "fits"
REPORT_PATH = SCRIPT_DIR / "calibration" / "fit_report.md"
PARAMETER_DIR = BACKEND_DIR / "simulation" / "parameters" / "v1"
PARAMETER_VERSION = "v1"
CURVE_ORDER = get_args(TimeCurveType)

# Strictly positive lower bounds satisfy both curve_fit and TreatmentEffect.
LOWER_BOUNDS = (1e-8, 1e-6)
UPPER_BOUNDS = (10.0, 730.0)
RMSE_TIE_TOLERANCE = 1e-8  # GlassSkin points; absorbs tiny optimizer noise only.
MAGNITUDE_BOUND_TOLERANCE = 1e-6
TIME_SCALE_BOUND_TOLERANCE = 1e-4


class CandidateFailure(RuntimeError):
    """One discrete curve/delay candidate could not be trusted."""


@dataclass(frozen=True)
class Candidate:
    curve: TimeCurveType
    delay_days: int
    mean_magnitude: float
    time_scale_days: float
    predictions: tuple[float, ...]
    rmse: float
    max_abs_error: float
    n_points: int
    dof: int
    g_tmax: float
    unconstrained_magnitude_oracle: float
    flags: tuple[str, ...]


@dataclass(frozen=True)
class FittedEffect:
    evidence: dict
    parameter: TreatmentEffect
    candidate: Candidate
    rmse_winner: Candidate
    failures: tuple[str, ...]
    magnitude_ceiling_candidates: tuple[Candidate, ...]
    uncertainty_ineligible_candidates: tuple[Candidate, ...]


def clamp_initial_guess(value: float, lower: float, upper: float) -> float:
    """Keep only the initial guess strictly interior; fitted values are never clipped."""

    margin = min(1e-6, (upper - lower) / 4)
    return min(max(value, lower + margin), upper - margin)


def model_values(times: np.ndarray, curve: TimeCurveType, delay_days: int, magnitude: float, scale: float) -> np.ndarray:
    return np.asarray([magnitude * progress(curve, float(t), delay_days, scale) for t in times], dtype=float)


def bound_flags(magnitude: float, scale: float) -> list[str]:
    flags = []
    if abs(magnitude - LOWER_BOUNDS[0]) <= MAGNITUDE_BOUND_TOLERANCE:
        flags.append("mean_magnitude_bound_hit:lower")
    if abs(magnitude - UPPER_BOUNDS[0]) <= MAGNITUDE_BOUND_TOLERANCE:
        flags.append("mean_magnitude_bound_hit:upper")
    if abs(scale - LOWER_BOUNDS[1]) <= TIME_SCALE_BOUND_TOLERANCE:
        flags.append("time_scale_bound_hit:lower")
    if abs(scale - UPPER_BOUNDS[1]) <= TIME_SCALE_BOUND_TOLERANCE:
        flags.append("time_scale_bound_hit:upper")
    return flags


def fit_candidate(curve: TimeCurveType, delay_days: int, times: np.ndarray, targets: np.ndarray) -> Candidate:
    def candidate_model(t: np.ndarray, magnitude: float, scale: float) -> np.ndarray:
        return model_values(t, curve, delay_days, magnitude, scale)

    initial = (clamp_initial_guess(float(max(targets)), LOWER_BOUNDS[0], UPPER_BOUNDS[0]), clamp_initial_guess(float(max(times)), LOWER_BOUNDS[1], UPPER_BOUNDS[1]))
    magnitude, scale = curve_fit(candidate_model, times, targets, p0=initial, bounds=(LOWER_BOUNDS, UPPER_BOUNDS), method="trf", ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=20_000)[0]
    magnitude, scale = float(magnitude), float(scale)
    fractions = [progress(curve, float(t), delay_days, scale) for t in times]
    denominator = math.fsum(value * value for value in fractions)
    if not denominator > 0:
        raise CandidateFailure("closed-form magnitude denominator is zero")
    unconstrained_oracle = math.fsum(value * float(target) for value, target in zip(fractions, targets)) / denominator
    constrained_oracle = min(max(unconstrained_oracle, LOWER_BOUNDS[0]), UPPER_BOUNDS[0])
    if abs(magnitude - constrained_oracle) > 1e-8 * max(1.0, constrained_oracle):
        raise CandidateFailure(f"closed-form bounded magnitude oracle failed: fitted={magnitude:.9g}, bounded={constrained_oracle:.9g}, unconstrained={unconstrained_oracle:.9g}")

    predictions = tuple(float(value) for value in candidate_model(times, magnitude, scale))
    residuals = [prediction - float(target) for prediction, target in zip(predictions, targets)]
    rmse = math.sqrt(math.fsum(value * value for value in residuals) / len(residuals))
    g_tmax = progress(curve, float(max(times)), delay_days, scale)
    flags = bound_flags(magnitude, scale)
    if unconstrained_oracle > UPPER_BOUNDS[0]:
        flags.append("unconstrained_magnitude_above_model_bound")
    if len(times) - 2 <= 0:
        flags.append("nonpositive_dof:residual_uninformative")
    if g_tmax < 0.8:
        flags.append("extrapolated_asymptote")
    return Candidate(curve, delay_days, magnitude, scale, predictions, rmse, max(abs(value) for value in residuals), len(times), len(times) - 2, g_tmax, unconstrained_oracle, tuple(flags))


def choose_candidate(candidates: list[Candidate]) -> Candidate:
    best_rmse = min(candidate.rmse for candidate in candidates)
    tied = [candidate for candidate in candidates if candidate.rmse <= best_rmse + RMSE_TIE_TOLERANCE]
    # Within the numerical RMSE tie, prefer zero delay, then Literal declaration
    # order, then smaller delay. This does not depend on search iteration order.
    return min(tied, key=lambda candidate: (candidate.delay_days != 0, CURVE_ORDER.index(candidate.curve), candidate.delay_days))


def fit_effect(treatment_id: str, effect_index: int, evidence: dict) -> FittedEffect:
    observations = evidence["observations"]
    times = np.asarray([observation["t_days"] for observation in observations], dtype=float)
    targets = np.asarray([observation["target_points"] for observation in observations], dtype=float)
    if len(times) < 2 or not np.isfinite(times).all() or not np.isfinite(targets).all() or np.any(times <= 0) or np.any(targets <= 0) or np.any(np.diff(times) <= 0):
        raise ValueError(f"{treatment_id} effect {effect_index}: expected at least two increasing nonzero observation times and positive finite targets")
    sigma = float(evidence["response_sigma"])
    if not math.isfinite(sigma) or sigma < 0:
        raise ValueError(f"{treatment_id} effect {effect_index}: invalid Step 4 response_sigma {sigma}")

    candidates = []
    failures = []
    delays = sorted(set(evidence["delay_grid_days"]))
    for curve in CURVE_ORDER:
        for delay_days in delays:
            if curve in CURVES_WITHOUT_DELAY and delay_days != 0:
                continue
            try:
                candidates.append(fit_candidate(curve, delay_days, times, targets))
            except (RuntimeError, ValueError, FloatingPointError, OverflowError) as exc:
                failures.append(f"{curve}/delay={delay_days}: {type(exc).__name__}: {exc}")
    if not candidates:
        raise RuntimeError(f"{treatment_id} effect {effect_index} ({evidence['target_metric']}): every candidate failed: {'; '.join(failures)}")

    rmse_winner = choose_candidate(candidates)
    uncertainty_ineligible = tuple(candidate for candidate in candidates if sigma * candidate.mean_magnitude > MAX_EFFECT_UNCERTAINTY)
    eligible = [candidate for candidate in candidates if sigma * candidate.mean_magnitude <= MAX_EFFECT_UNCERTAINTY]
    if not eligible:
        raise RuntimeError(f"{treatment_id} effect {effect_index}: no candidate satisfies uncertainty <= {MAX_EFFECT_UNCERTAINTY:g}")
    winner = choose_candidate(eligible)
    uncertainty = sigma * winner.mean_magnitude
    if uncertainty / winner.mean_magnitude > MAX_RESPONSE_LOG_SD:
        raise ValueError(f"{treatment_id} effect {effect_index}: response sigma {sigma} exceeds MAX_RESPONSE_LOG_SD {MAX_RESPONSE_LOG_SD}")

    original = Provenance(**evidence["provenance"])
    conversion = original.derivation.removesuffix("Step 5 fit residual pending.").rstrip()
    diagnostics = (f"Step 5 fit: curve={winner.curve}; delay_days={winner.delay_days}; mean_magnitude={winner.mean_magnitude:.9g}; "
                   f"time_scale_days={winner.time_scale_days:.9g}; RMSE={winner.rmse:.9g}; max_abs_error={winner.max_abs_error:.9g}; "
                   f"n_points={winner.n_points}; DoF={winner.dof}; g(t_max)={winner.g_tmax:.9g}; "
                   f"bound_flags={','.join(flag for flag in winner.flags if 'bound_hit' in flag) or 'none'}; "
                   f"extrapolated_asymptote={winner.g_tmax < 0.8}; candidate_failures={len(failures)}.")
    if winner.dof <= 0:
        diagnostics += " Residual quality is uninformative because DoF <= 0."
    if winner.g_tmax < 0.8:
        diagnostics += " Fitted asymptote is extrapolated beyond observed data."
    provenance = Provenance(**{**original.model_dump(), "derivation": f"{conversion} {diagnostics}"})
    parameter = TreatmentEffect(target_metric=evidence["target_metric"], effect_kind=evidence["effect_kind"], direction=evidence["direction"], delay_days=winner.delay_days, mean_magnitude=winner.mean_magnitude, uncertainty=uncertainty, time_scale_days=winner.time_scale_days, time_curve=winner.curve, provenance=provenance)
    return FittedEffect(evidence, parameter, winner, rmse_winner, tuple(failures), tuple(candidate for candidate in candidates if "unconstrained_magnitude_above_model_bound" in candidate.flags), uncertainty_ineligible)


def plot_horizon(fitted: list[FittedEffect]) -> int:
    """Show at least twice the evidence duration and one fitted scale beyond it, capped by the 730-day simulator horizon."""

    horizons = []
    for item in fitted:
        last_day = max(row["t_days"] for row in item.evidence["observations"])
        horizons.append(max(2 * last_day, math.ceil(last_day + item.candidate.time_scale_days)))
    return min(730, max(horizons))


def render_plot(treatment_id: str, fitted: list[FittedEffect]) -> None:
    horizon = plot_horizon(fitted)
    figure, axes = plt.subplots(len(fitted), 1, figsize=(10, max(4.5, 3.8 * len(fitted))), squeeze=False)
    for index, item in enumerate(fitted):
        axis = axes[index, 0]
        observations = item.evidence["observations"]
        last_day = max(row["t_days"] for row in observations)
        before = np.linspace(0, last_day, 201)
        after = np.linspace(last_day, horizon, 201)
        candidate = item.candidate
        axis.plot(before, model_values(before, candidate.curve, candidate.delay_days, candidate.mean_magnitude, candidate.time_scale_days), color="#2563eb", linewidth=2, label="Fitted within evidence")
        axis.plot(after, model_values(after, candidate.curve, candidate.delay_days, candidate.mean_magnitude, candidate.time_scale_days), color="#2563eb", alpha=0.32, linewidth=2, label="Extrapolated")
        axis.scatter([row["t_days"] for row in observations], [row["target_points"] for row in observations], color="#b91c1c", s=42, zorder=3, label="Step 4 targets")
        axis.axvline(last_day, color="#64748b", linestyle="--", linewidth=1)
        axis.set_title(f"{item.parameter.target_metric} · {item.parameter.effect_kind} · RMSE {candidate.rmse:.4f} points")
        axis.set_xlabel("Days since treatment start")
        axis.set_ylabel("Effect magnitude (GlassSkin points)")
        axis.set_xlim(0, horizon)
        axis.set_ylim(bottom=0)
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best", fontsize=8)
    figure.suptitle(f"{treatment_id} — fit to Step 4 evidence", fontsize=13)
    figure.tight_layout()
    figure.savefig(FITS_DIR / f"{treatment_id}.png", dpi=180, bbox_inches="tight")
    plt.close(figure)


def write_report(records: list[tuple[dict, TreatmentParameters, list[FittedEffect]]]) -> None:
    rows = []
    for evidence, parameter, fitted in records:
        for index, item in enumerate(fitted):
            candidate = item.candidate
            flags = list(candidate.flags)
            if item.failures:
                flags.append(f"candidate_failures:{len(item.failures)}")
            failed_bound_hits = sum("mean_magnitude_bound_hit" in failure or "time_scale_bound_hit" in failure for failure in item.failures)
            if failed_bound_hits:
                flags.append(f"failed_candidate_bound_hits:{failed_bound_hits}")
            rows.append((parameter.treatment_id, index, item, ", ".join(flags) or "none"))
    rows.sort(key=lambda row: (-row[2].candidate.rmse, row[0], row[1]))
    lines = ["# Day 12 Step 5 fit report", "", "Fitted against the median-referenced Step 4 targets. RMSE and maximum error are GlassSkin points. Rows are sorted by RMSE descending. A numerical RMSE tie within 1e-8 points prefers zero delay, then `TimeCurveType` declaration order, then smaller delay.", "", "Plot horizon: `min(730, max(2 × last evidence day, last evidence day + fitted time scale))`, rounded up to a whole day. Plotting does not influence fitting.", "", "| treatment | target metric | effect kind | curve | delay days | mean magnitude | time scale days | uncertainty | RMSE | max absolute error | n points | DoF | g(t_max) | flags |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    lines[2] += " Magnitude ceiling candidates pass the bounded oracle and enter the RMSE ranking; candidates whose derived uncertainty exceeds the separate TreatmentEffect limit are ineligible for the final parameter."
    for treatment_id, _, item, flags in rows:
        candidate = item.candidate
        lines.append(f"| `{treatment_id}` | `{item.parameter.target_metric}` | `{item.parameter.effect_kind}` | `{candidate.curve}` | {candidate.delay_days} | {candidate.mean_magnitude:.6f} | {candidate.time_scale_days:.6f} | {item.parameter.uncertainty:.6f} | {candidate.rmse:.6f} | {candidate.max_abs_error:.6f} | {candidate.n_points} | {candidate.dof} | {candidate.g_tmax:.6f} | {flags} |")
    lines.extend(["", "## Candidate failures", ""])
    failures = [(treatment_id, index, failure) for treatment_id, index, item, _ in rows for failure in item.failures]
    if failures:
        lines.extend(f"- `{treatment_id}` effect {index + 1}: {failure}" for treatment_id, index, failure in failures)
    else:
        lines.append("None.")
    lines.extend(["", "## Magnitude ceiling candidates", "", "These candidates passed the bounded oracle and remained eligible for RMSE selection; the unconstrained magnitude optimum exceeded 10.", ""])
    ceiling_candidates = [(treatment_id, index, candidate) for treatment_id, index, item, _ in rows for candidate in item.magnitude_ceiling_candidates]
    if ceiling_candidates:
        lines.extend(f"- `{treatment_id}` effect {index + 1}: {candidate.curve}/delay={candidate.delay_days}; fitted={candidate.mean_magnitude:.9g}; unconstrained_oracle={candidate.unconstrained_magnitude_oracle:.9g}; RMSE={candidate.rmse:.9g}; flags={','.join(candidate.flags)}" for treatment_id, index, candidate in ceiling_candidates)
    else:
        lines.append("None.")
    lines.extend(["", "## Parameter constraint exclusions", "", f"Derived uncertainty must be <= {MAX_EFFECT_UNCERTAINTY:g} points; these fitted candidates passed the magnitude oracle but could not produce a valid TreatmentEffect.", ""])
    exclusions = [(treatment_id, index, candidate, item.evidence["response_sigma"] * candidate.mean_magnitude) for treatment_id, index, item, _ in rows for candidate in item.uncertainty_ineligible_candidates]
    if exclusions:
        lines.extend(f"- `{treatment_id}` effect {index + 1}: {candidate.curve}/delay={candidate.delay_days}; derived_uncertainty={uncertainty:.9g}; RMSE={candidate.rmse:.9g}" for treatment_id, index, candidate, uncertainty in exclusions)
    else:
        lines.append("None.")
    lines.extend(["", "## RMSE winners replaced by the uncertainty limit", ""])
    replacements = [(treatment_id, index, item) for treatment_id, index, item, _ in rows if item.rmse_winner != item.candidate]
    if replacements:
        lines.extend(f"- `{treatment_id}` effect {index + 1}: overall RMSE winner {item.rmse_winner.curve}/delay={item.rmse_winner.delay_days} ({item.rmse_winner.rmse:.9g}) has derived uncertainty {item.evidence['response_sigma'] * item.rmse_winner.mean_magnitude:.9g}; selected {item.candidate.curve}/delay={item.candidate.delay_days} ({item.candidate.rmse:.9g})" for treatment_id, index, item in replacements)
    else:
        lines.append("None.")
    lines.extend(["", "## Evidence notes", ""])
    for evidence, _, _ in records:
        lines.extend([f"### `{evidence['treatment_id']}`", "", evidence["notes"], ""])
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n")


def main() -> None:
    records = []
    paths = sorted(EVIDENCE_DIR.glob("*.json"))
    if not paths:
        raise RuntimeError(f"no evidence files found in {EVIDENCE_DIR}")
    for path in paths:
        evidence = json.loads(path.read_text())
        if path.stem != evidence["treatment_id"]:
            raise ValueError(f"{path.name}: filename does not match treatment_id {evidence['treatment_id']!r}")
        fitted = [fit_effect(evidence["treatment_id"], index + 1, effect) for index, effect in enumerate(evidence["effects"])]
        parameter = TreatmentParameters(treatment_id=evidence["treatment_id"], display_name=evidence["display_name"], parameter_version=PARAMETER_VERSION, effects=[item.parameter for item in fitted])
        records.append((evidence, parameter, fitted))

    PARAMETER_DIR.mkdir(parents=True, exist_ok=True)
    FITS_DIR.mkdir(parents=True, exist_ok=True)
    for _, parameter, fitted in records:
        (PARAMETER_DIR / f"{parameter.treatment_id}.json").write_text(parameter.model_dump_json(indent=2) + "\n")
        render_plot(parameter.treatment_id, fitted)
        print(f"{parameter.treatment_id}: {len(fitted)} validated effect(s); plot and parameter JSON written")
    write_report(records)
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
