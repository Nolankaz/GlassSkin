"""Evaluate frozen v1 simulation against preregistered Day 13 evidence.

Run from backend/ with ``./.venv/bin/python notes/validate_simulation.py``.
This script reads evidence and parameters; it never fits or updates either.
"""

import hashlib
import json
import math
from pathlib import Path
import re
import sys

import matplotlib
import numpy as np
from pydantic import ValidationError

matplotlib.use("Agg")
import matplotlib.pyplot as plt


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from simulation.curves import progress
from simulation.models import MAX_EFFECT_UNCERTAINTY, METRIC_MAX, METRIC_MIN, SKIN_METRIC_NAMES, SimulationConfig, SkinState, TreatmentParameters
from simulation.monte_carlo import response_column, sample_log_responses, simulate_many, simulate_trials_vectorised
from simulation.parameters import load_treatment_parameters


PARAMETER_VERSION = "v1"
N_TRIALS = 10_000
SEED = 42
NOISE_SEEDS = (42, 43, 44, 45, 46)
WEEK_12_DAYS = 84
PARAMETER_DIR = BACKEND_DIR / "simulation" / "parameters" / PARAMETER_VERSION
EVIDENCE_DIR = SCRIPT_DIR / "calibration" / "evidence"
VALIDATION_DIR = SCRIPT_DIR / "validation"
HOLDOUT_PATH = VALIDATION_DIR / "holdout_evidence.json"
OUTPUT_PATH = VALIDATION_DIR / "validation_results.md"
SENSITIVITY_PLOT_PATH = VALIDATION_DIR / "sensitivity.png"
OTHER_METRIC_VALUE = (METRIC_MIN + METRIC_MAX) / 2
BASELINE_SWEEP = (2.5, 5.0, 7.5, 10.0)
SENSITIVITY_PARAMETERS = ("mean_magnitude", "sigma", "time_scale_days", "delay_days")
PERCENT_RE = re.compile(r"[−-]?(\d+(?:\.\d+)?)%")
RMSE_RE = re.compile(r"\bRMSE=(\d+(?:\.\d+)?)\b")
TYPED_SD_RE = re.compile(r"week\s+(\d+)\s+(?:LS mean\s+)?[−-]\d+(?:\.\d+)?%\s+\(SD\s+(\d+(?:\.\d+)?)(?: percentage points)?\)", re.IGNORECASE)


def parameter_fingerprints() -> dict[str, str]:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(PARAMETER_DIR.glob("*.json"))}


def reference_state(metric: str, baseline_points: float) -> SkinState:
    if metric not in SKIN_METRIC_NAMES:
        raise ValueError(f"unknown metric: {metric}")
    return SkinState(**{name: baseline_points if name == metric else OTHER_METRIC_VALUE for name in SKIN_METRIC_NAMES})


def simulate_changes(treatment, metric: str, baseline_points: float, times_days, seed: int) -> np.ndarray:
    """Return positive point improvements using production's sampling and raw engine."""
    state = reference_state(metric, baseline_points)
    rng = np.random.default_rng(seed)
    log_responses = sample_log_responses(N_TRIALS, rng)
    trial_states = simulate_trials_vectorised(state, treatment, times_days, log_responses)
    return baseline_points - trial_states[:, :, SKIN_METRIC_NAMES.index(metric)]


def summarise(changes_at_t: np.ndarray, baseline_points: float) -> dict[str, float]:
    values = np.asarray(changes_at_t, dtype=np.float64)
    if values.shape != (N_TRIALS,) or baseline_points <= 0:
        raise ValueError("expected one positive-baseline, N_TRIALS-sized simulation column")
    percentiles = np.percentile(values, (10, 25, 50, 75, 90), method="linear")
    metric_values = baseline_points - values
    summary = {"mean": float(np.mean(values)), "median": float(percentiles[2]), "p10": float(percentiles[0]), "p25": float(percentiles[1]), "p75": float(percentiles[3]), "p90": float(percentiles[4]), "sd": float(np.std(values, ddof=1)), "clamped_fraction": float(np.mean(metric_values == METRIC_MIN))}
    summary.update({f"{name}_percent": 100 * summary[name] / baseline_points for name in ("mean", "median", "p10", "p25", "p75", "p90", "sd")})
    return summary


def load_evidence() -> dict[str, dict]:
    evidence = {}
    for path in sorted(EVIDENCE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.stem != data["treatment_id"] or data["treatment_id"] in evidence:
            raise ValueError(f"evidence identity mismatch: {path.name}")
        evidence[data["treatment_id"]] = data
    return evidence


def calibrated_effects(treatments: dict, evidence: dict):
    if set(treatments) != set(evidence):
        raise ValueError("frozen parameter and evidence treatment IDs differ")
    for treatment_id in sorted(treatments):
        effects = treatments[treatment_id].effects
        records = evidence[treatment_id]["effects"]
        if len(effects) != len(records) or len(effects) != 1:
            raise ValueError(f"expected one calibrated effect for {treatment_id}")
        for effect, record in zip(effects, records):
            if (effect.target_metric, effect.effect_kind, effect.direction) != (record["target_metric"], record["effect_kind"], record["direction"]):
                raise ValueError(f"parameter/evidence effect mismatch for {treatment_id}")
            if effect.effect_kind != "therapeutic" or effect.direction != "decrease":
                raise ValueError(f"positive-improvement comparison does not apply to {treatment_id}")
            yield treatment_id, treatments[treatment_id], effect, record


def production_path_pin(treatment, metric: str, baseline_points: float, times_days: list[int]) -> float:
    config = SimulationConfig(duration_days=max(times_days), time_step_days=1, n_trials=N_TRIALS, random_seed=SEED)
    production = simulate_many(reference_state(metric, baseline_points), treatment, config)
    changes = simulate_changes(treatment, metric, baseline_points, times_days, SEED)
    gaps = []
    for index, day in enumerate(times_days):
        production_p50 = production.metric_band(metric).p50[production.times_days.index(float(day))]
        raw_p50 = baseline_points - np.percentile(changes[:, index], 50, method="linear")
        gaps.append(abs(production_p50 - raw_p50))
    maximum_gap = max(gaps)
    if maximum_gap > 1e-10:
        raise AssertionError(f"production-path p50 pin failed: maximum gap {maximum_gap}")
    return maximum_gap


def reported_percent(text: str) -> float:
    match = PERCENT_RE.search(text)
    if match is None:
        raise ValueError(f"no reported percentage in {text!r}")
    return float(match.group(1))


def recorded_rmse(effect) -> float:
    match = RMSE_RE.search(effect.provenance.derivation)
    if match is None:
        raise ValueError("parameter provenance has no recorded RMSE")
    return float(match.group(1))


def simulation_summaries(treatment, metric: str, baseline: float, times: list[int], seed: int = SEED) -> dict[int, dict]:
    changes = simulate_changes(treatment, metric, baseline, times, seed)
    return {day: summarise(changes[:, index], baseline) for index, day in enumerate(times)}


def tier0_rows(treatments: dict, evidence: dict) -> tuple[list[dict], dict]:
    rows = []
    by_treatment_day = {}
    for treatment_id, treatment, effect, record in calibrated_effects(treatments, evidence):
        baseline = record["reference_baseline_points"]
        basis = record["reported_basis"]
        sigma = record["response_sigma"]
        rmse = recorded_rmse(effect)
        times = sorted(observation["t_days"] for observation in record["observations"])
        summaries = simulation_summaries(treatment, effect.target_metric, baseline, times)
        for observation in sorted(record["observations"], key=lambda item: item["t_days"]):
            day = observation["t_days"]
            stats = summaries[day]
            target = observation["target_points"]
            reported = target if basis == "median" else target * math.exp(sigma ** 2 / 2)
            matching = stats[basis]
            median_residual = stats["median"] - target
            row = {"tier": "Tier 0", "treatment": treatment_id, "metric": effect.target_metric, "t_days": day, "basis": basis, "baseline": baseline, "reported_points": reported, "reported_percent": 100 * reported / baseline, "matching_statistic": basis, "simulated_points": matching, "simulated_percent": stats[f"{basis}_percent"], "error_points": matching - reported, "error_pp": stats[f"{basis}_percent"] - 100 * reported / baseline, "median_points": stats["median"], "median_target": target, "median_residual": median_residual, "rmse": rmse, "clamped_fraction": stats["clamped_fraction"], "status": "within RMSE" if abs(median_residual) <= rmse else "outside RMSE"}
            rows.append(row)
            by_treatment_day[treatment_id, day] = row
    return sorted(rows, key=lambda row: (row["treatment"], row["t_days"])), by_treatment_day


def check_preregistered_references(tier0: dict, tier1: list[dict]) -> None:
    tret = tier0["tretinoin", WEEK_12_DAYS]
    if not math.isclose(tret["reported_points"], 3.8175, abs_tol=0.0001) or not math.isclose(tret["reported_percent"], 50.90, abs_tol=0.01):
        raise AssertionError("tretinoin week-12 mean disagrees with preregistered reference")
    expected = {"tretinoin": (2.236, 2.5), "tazarotene": (1.675, 3.98)}
    for row in tier1:
        if row["t_days"] == WEEK_12_DAYS and row["treatment"] in expected:
            se, gap = expected[row["treatment"]]
            if row["se_pct"] is None or not math.isclose(row["se_pct"], se, abs_tol=0.001) or not math.isclose(row["replicate_gap"], gap, abs_tol=0.001):
                raise AssertionError(f"{row['treatment']} week-12 arithmetic disagrees with preregistered reference")


def tier1_rows(treatments: dict, evidence: dict, comparisons: list[dict], tier0: dict) -> list[dict]:
    rows = []
    for comparison in comparisons:
        if comparison["tier"] != "holdout_replicate":
            continue
        treatment_id = comparison["treatment_id"]
        metric = comparison["target_metric"]
        baseline = comparison["baseline_points"]
        statistic = comparison["statistic"]
        times = sorted(observation["t_days"] for observation in comparison["observations"])
        summaries = simulation_summaries(treatments[treatment_id], metric, baseline, times)
        calibration = next(record for record in evidence[treatment_id]["effects"] if record["target_metric"] == metric)
        calibration_by_day = {observation["t_days"]: observation for observation in calibration["observations"]}
        for observation in sorted(comparison["observations"], key=lambda item: item["t_days"]):
            day = observation["t_days"]
            reported_pct = observation["value_percent"]
            calibration_pct = reported_percent(calibration_by_day[day]["reported"])
            replicate_gap = abs(calibration_pct - reported_pct)
            stats = summaries[day]
            simulated_pct = stats[f"{statistic}_percent"]
            error_pp = simulated_pct - reported_pct
            se_pct = None if observation["spread_percent"] is None else observation["spread_percent"] / math.sqrt(observation["n"])
            if se_pct is None:
                verdict = "within replication spread" if abs(error_pp) <= replicate_gap else "disagrees"
            elif abs(error_pp) <= 2 * se_pct:
                verdict = "consistent"
            elif abs(error_pp) <= replicate_gap + 2 * se_pct:
                verdict = "within replication spread"
            else:
                verdict = "disagrees"
            rows.append({"tier": "Tier 1", "treatment": treatment_id, "t_days": day, "baseline": baseline, "statistic": statistic, "reported_percent": reported_pct, "reported_points": baseline * reported_pct / 100, "simulated_percent": simulated_pct, "simulated_points": stats[statistic], "error_pp": error_pp, "error_points": stats[statistic] - baseline * reported_pct / 100, "se_pct": se_pct, "replicate_gap": replicate_gap, "clamped_fraction": stats["clamped_fraction"], "verdict": verdict, "tier0_error_pp": tier0[treatment_id, day]["error_pp"]})
    return sorted(rows, key=lambda row: (row["treatment"], row["t_days"]))


def tier2_rows(treatments: dict, comparisons: list[dict]) -> list[dict]:
    rows = []
    for comparison in comparisons:
        if comparison["tier"] != "partial":
            continue
        treatment_id = comparison["treatment_id"]
        metric = comparison["target_metric"]
        observation = comparison["observations"][0]
        if comparison["statistic"] == "mean" and comparison["baseline_points"] is None:
            for baseline in (5.0, 7.5):
                stats = simulation_summaries(treatments[treatment_id], metric, baseline, [observation["t_days"]])[observation["t_days"]]
                rows.append({"tier": "Tier 2", "treatment": treatment_id, "time": str(observation["t_days"]), "baseline": baseline, "baseline_note": "analyst-selected; source baseline unavailable", "statistic": "mean", "reported_percent": observation["value_percent"], "simulated_percent": stats["mean_percent"], "error_pp": stats["mean_percent"] - observation["value_percent"], "clamped_fraction": stats["clamped_fraction"], "caveat": comparison["caveats"]})
        elif comparison["statistic"] == "quartiles" and observation["t_days"] is None:
            baseline = comparison["baseline_points"]
            stats = simulation_summaries(treatments[treatment_id], metric, baseline, [WEEK_12_DAYS])[WEEK_12_DAYS]
            for statistic in ("p25", "median", "p75"):
                reported_pct = observation["quartiles_percent"][statistic]
                rows.append({"tier": "Tier 2", "treatment": treatment_id, "time": "EOS (~84)", "baseline": baseline, "baseline_note": "source mapped", "statistic": statistic, "reported_percent": reported_pct, "simulated_percent": stats[f"{statistic}_percent"], "error_pp": stats[f"{statistic}_percent"] - reported_pct, "clamped_fraction": stats["clamped_fraction"], "caveat": comparison["caveats"]})
        else:
            raise ValueError(f"unsupported Tier 2 comparison: {comparison['comparison_id']}")
    order = {"mean": 0, "p25": 1, "median": 2, "p75": 3}
    return sorted(rows, key=lambda row: (row["treatment"], row["time"], row["baseline"], order[row["statistic"]]))


def spread_rows(treatments: dict, evidence: dict, comparisons: list[dict]) -> list[dict]:
    rows = []
    for treatment_id in ("tretinoin", "tazarotene"):
        record = evidence[treatment_id]["effects"][0]
        typed = {int(day) * 7: float(sd) for day, sd in TYPED_SD_RE.findall(record["provenance"]["reported_figure"])}
        expected = {84} if treatment_id == "tretinoin" else {28, 56, 84}
        if set(typed) != expected:
            raise ValueError(f"unexpected typed 301 spread observations for {treatment_id}: {typed}")
        baseline = record["reference_baseline_points"]
        summaries = simulation_summaries(treatments[treatment_id], record["target_metric"], baseline, sorted(typed))
        for day, reported_sd in sorted(typed.items()):
            stats = summaries[day]
            rows.append({"tier": "Tier 0" if day == WEEK_12_DAYS else "Tier 2", "treatment": treatment_id, "source": "301", "t_days": day, "reported_sd": reported_sd, "simulated_sd": stats["sd_percent"], "difference": stats["sd_percent"] - reported_sd, "clamped_fraction": stats["clamped_fraction"]})
    for comparison in comparisons:
        if comparison["tier"] != "holdout_replicate":
            continue
        baseline = comparison["baseline_points"]
        typed = [observation for observation in comparison["observations"] if observation["spread_percent"] is not None]
        summaries = simulation_summaries(treatments[comparison["treatment_id"]], comparison["target_metric"], baseline, sorted(observation["t_days"] for observation in typed))
        for observation in typed:
            stats = summaries[observation["t_days"]]
            rows.append({"tier": "Tier 1", "treatment": comparison["treatment_id"], "source": "302", "t_days": observation["t_days"], "reported_sd": observation["spread_percent"], "simulated_sd": stats["sd_percent"], "difference": stats["sd_percent"] - observation["spread_percent"], "clamped_fraction": stats["clamped_fraction"]})
    return sorted(rows, key=lambda row: (int(row["tier"].split()[1]), row["treatment"], row["t_days"]))


def monte_carlo_noise(treatments: dict, evidence: dict) -> tuple[list[dict], dict, dict]:
    rows = []
    by_statistic = {}
    for treatment_id, treatment, effect, record in calibrated_effects(treatments, evidence):
        baseline = record["reference_baseline_points"]
        seeds = {seed: simulation_summaries(treatment, effect.target_metric, baseline, [WEEK_12_DAYS], seed)[WEEK_12_DAYS] for seed in NOISE_SEEDS}
        for statistic in ("mean", "median"):
            values = [seeds[seed][statistic] for seed in NOISE_SEEDS]
            sd = float(np.std(values, ddof=1))
            row = {"treatment": treatment_id, "statistic": statistic, "baseline": baseline, "seed_values": values, "seed_sd": sd}
            rows.append(row)
            by_statistic[treatment_id, statistic] = sd
    maximum = max(rows, key=lambda row: row["seed_sd"])
    return rows, maximum, by_statistic


def simulate_changes_with_samples(treatment, metric: str, baseline: float, times_days, log_responses: np.ndarray) -> np.ndarray:
    state = reference_state(metric, baseline)
    trial_states = simulate_trials_vectorised(state, treatment, times_days, log_responses)
    return baseline - trial_states[:, :, SKIN_METRIC_NAMES.index(metric)]


def sensitivity_summary(treatment, metric: str, baseline: float, log_responses: np.ndarray) -> dict[str, float]:
    changes = simulate_changes_with_samples(treatment, metric, baseline, [WEEK_12_DAYS], log_responses)
    stats = summarise(changes[:, 0], baseline)
    stats["band_width"] = stats["p90"] - stats["p10"]
    return stats


def revalidated_perturbation(treatment: TreatmentParameters, changes: dict) -> TreatmentParameters:
    data = treatment.model_dump()
    if len(data["effects"]) != 1:
        raise ValueError("the frozen v1 sensitivity analysis expects one calibrated effect")
    data["effects"][0].update(changes)
    return TreatmentParameters.model_validate(data)


def perturbation_spec(effect, parameter: str, side: str) -> tuple[dict, str, float | None]:
    factor = 0.8 if side == "low" else 1.2
    if parameter == "mean_magnitude":
        return {"mean_magnitude": effect.mean_magnitude * factor, "uncertainty": effect.uncertainty * factor}, f"×{factor:.1f}", factor - 1
    if parameter == "sigma":
        return {"uncertainty": effect.uncertainty * factor}, f"×{factor:.1f}", factor - 1
    if parameter == "time_scale_days":
        return {"time_scale_days": effect.time_scale_days * factor}, f"×{factor:.1f}", factor - 1
    if parameter == "delay_days":
        delta = -7 if side == "low" else 7
        return {"delay_days": effect.delay_days + delta}, f"{delta:+d} days", None
    raise ValueError(f"unknown sensitivity parameter: {parameter}")


def perturbation_failure(error: ValidationError, changes: dict) -> str:
    issue = error.errors(include_url=False)[0]
    location = issue["loc"]
    if "uncertainty" in location and changes.get("uncertainty", 0) > MAX_EFFECT_UNCERTAINTY:
        return f"uncertainty {changes['uncertainty']:.4f} exceeds MAX_EFFECT_UNCERTAINTY ({MAX_EFFECT_UNCERTAINTY:.4f})"
    field = location[-1] if location else "treatment"
    return f"{field} {changes.get(field, '')} violates model validation: {issue['msg']}"


def sigma_origin(record: dict) -> str:
    derivation = record["provenance"]["derivation"].lower()
    borrowed = "pooled sigma" in derivation and "borrowed" in derivation
    if record["response_cv"] is None and not borrowed:
        raise ValueError("missing response CV without documented borrowed sigma")
    if record["response_cv"] is not None and borrowed:
        raise ValueError("response CV and borrowed-sigma provenance conflict")
    return "borrowed pooled" if borrowed else "treatment-specific"


def relative_percent(delta: float, base: float) -> float | None:
    return None if abs(base) < 1e-12 else 100 * delta / base


def elasticity(delta: float, base: float, fractional_input_change: float | None) -> float | None:
    if fractional_input_change is None or abs(base) < 1e-12:
        return None
    return delta / base / fractional_input_change


def oat_sensitivity(treatments: dict, evidence: dict) -> tuple[dict, list[dict], dict, np.ndarray]:
    patients = sample_log_responses(N_TRIALS, np.random.default_rng(SEED))
    bases = {}
    cells = []
    records = {}
    for treatment_id, treatment, effect, record in calibrated_effects(treatments, evidence):
        baseline = record["reference_baseline_points"]
        base = sensitivity_summary(treatment, effect.target_metric, baseline, patients)
        bases[treatment_id] = {"baseline": baseline, "metric": effect.target_metric, "sigma_origin": sigma_origin(record), **base}
        records[treatment_id] = record
        for parameter in SENSITIVITY_PARAMETERS:
            for side in ("low", "high"):
                changes, requested, fractional_change = perturbation_spec(effect, parameter, side)
                cell = {"treatment": treatment_id, "parameter": parameter, "side": side, "requested": requested, "fractional_change": fractional_change, "status": "constructible", "reason": ""}
                try:
                    variant = revalidated_perturbation(treatment, changes)
                except ValidationError as error:
                    cell.update(status="not constructible", reason=perturbation_failure(error, changes))
                    cells.append(cell)
                    continue
                stats = sensitivity_summary(variant, effect.target_metric, baseline, patients)
                cell.update(stats=stats, delta_median=stats["median"] - base["median"], delta_mean=stats["mean"] - base["mean"], delta_width=stats["band_width"] - base["band_width"], delta_clamped=stats["clamped_fraction"] - base["clamped_fraction"])
                cell["delta_median_percent"] = relative_percent(cell["delta_median"], base["median"])
                cell["delta_mean_percent"] = relative_percent(cell["delta_mean"], base["mean"])
                cell["delta_width_percent"] = relative_percent(cell["delta_width"], base["band_width"])
                cell["median_elasticity"] = elasticity(cell["delta_median"], base["median"], fractional_change)
                cell["width_elasticity"] = elasticity(cell["delta_width"], base["band_width"], fractional_change)
                if parameter == "mean_magnitude" and base["median"] < baseline - METRIC_MIN and stats["median"] < baseline - METRIC_MIN:
                    if cell["median_elasticity"] is None or not math.isclose(cell["median_elasticity"], 1.0, abs_tol=1e-9):
                        raise AssertionError(f"{treatment_id} {side} magnitude/median elasticity is not linear")
                if parameter == "sigma":
                    median_shift = cell["delta_median_percent"]
                    width_shift = cell["delta_width_percent"]
                    if median_shift is None or width_shift is None or abs(median_shift) >= 1.0 or abs(width_shift) <= 5 * abs(median_shift):
                        raise AssertionError(f"{treatment_id} {side} sigma median change is not negligible relative to band-width change")
                cells.append(cell)
    if len(cells) != len(bases) * len(SENSITIVITY_PARAMETERS) * 2:
        raise AssertionError("standardized OAT grid is incomplete")
    tret = {cell["side"]: cell for cell in cells if cell["treatment"] == "tretinoin" and cell["parameter"] == "time_scale_days"}
    for side, approximate in (("low", 7.3), ("high", -7.0)):
        actual = tret[side]["delta_median_percent"]
        if actual is None or abs(actual - approximate) > 1.0:
            raise AssertionError(f"tretinoin time-scale {side} disagrees with Day 13 hand reference: {actual}")
        effect = treatments["tretinoin"].effects[0]
        factor = 0.8 if side == "low" else 1.2
        expected = 100 * (progress(effect.time_curve, WEEK_12_DAYS, effect.delay_days, effect.time_scale_days * factor) / progress(effect.time_curve, WEEK_12_DAYS, effect.delay_days, effect.time_scale_days) - 1)
        if not math.isclose(actual, expected, abs_tol=1e-9):
            raise AssertionError(f"tretinoin time-scale {side} does not match the curve oracle")
    return bases, cells, records, patients


def evidence_linkage(parameter: str, effect, record: dict) -> str:
    if parameter == "mean_magnitude":
        return f"fitted {record['reported_basis']}-basis improvement series"
    if parameter == "sigma":
        if sigma_origin(record) == "borrowed pooled":
            return "borrowed pooled spread from three direct effects"
        return "source change SE → CV" if "change SE" in record["provenance"]["derivation"] else "source percentage-change SD → CV"
    if parameter == "time_scale_days":
        days = ", ".join(str(observation["t_days"]) for observation in record["observations"])
        return f"longitudinal fitted visits at days {days}"
    return f"selected from Day 12 delay grid {record['delay_grid_days']} ({effect.time_curve})"


def influence_rankings(treatments: dict, cells: list[dict], records: dict, output: str) -> list[dict]:
    rankings = []
    for treatment_id in sorted(treatments):
        choices = []
        for parameter in SENSITIVITY_PARAMETERS:
            pair = [cell for cell in cells if cell["treatment"] == treatment_id and cell["parameter"] == parameter]
            available = [cell for cell in pair if cell["status"] == "constructible"]
            if not available:
                raise AssertionError(f"no constructible {parameter} sensitivity for {treatment_id}")
            influence = max(abs(cell[f"delta_{output}"]) for cell in available)
            choices.append({"treatment": treatment_id, "parameter": parameter, "influence": influence, "coverage": "both sides" if len(available) == 2 else f"one-sided ({available[0]['side']} only)", "evidence": evidence_linkage(parameter, treatments[treatment_id].effects[0], records[treatment_id]), "borrowed_sigma": parameter == "sigma" and sigma_origin(records[treatment_id]) == "borrowed pooled"})
        for rank, row in enumerate(sorted(choices, key=lambda row: (-row["influence"], SENSITIVITY_PARAMETERS.index(row["parameter"]))), start=1):
            rankings.append({"rank": rank, **row})
    return rankings


def source_reference_percent(record: dict) -> tuple[float | None, str]:
    observation = next((item for item in record["observations"] if item["t_days"] == WEEK_12_DAYS), None)
    if observation is None:
        return None, "unavailable (no day-84 source observation)"
    if PERCENT_RE.search(observation["reported"]):
        return reported_percent(observation["reported"]), f"source {record['reported_basis']}"
    if record["reported_basis"] == "mean":
        reported_points = observation["target_points"] * math.exp(record["response_sigma"] ** 2 / 2)
        return 100 * reported_points / record["reference_baseline_points"], "derived source mean from counts"
    return None, "unavailable for source basis"


def baseline_sweep(treatments: dict, evidence: dict, patients: np.ndarray) -> list[dict]:
    rows = []
    for treatment_id, treatment, effect, record in calibrated_effects(treatments, evidence):
        reference = record["reference_baseline_points"]
        source_percent, source_basis = source_reference_percent(record)
        for baseline in BASELINE_SWEEP:
            stats = sensitivity_summary(treatment, effect.target_metric, baseline, patients)
            median_percent = stats["median_percent"]
            if median_percent < -1e-10 or median_percent > 100 + 1e-10:
                raise AssertionError(f"{treatment_id} baseline {baseline}: impossible median improvement percentage {median_percent}")
            rows.append({"treatment": treatment_id, "baseline": baseline, "reference_baseline": reference, "median_points": stats["median"], "median_percent": median_percent, "clamped_fraction": stats["clamped_fraction"], "source_percent": source_percent, "source_basis": source_basis})
    return rows


def point(value: float) -> str:
    return f"{value:.4f}"


def signed_point(value: float) -> str:
    return f"{value:+.4f}"


def percent(value: float) -> str:
    return f"{value:.2f}"


def signed_percent(value: float) -> str:
    return f"{value:+.2f}"


def fraction(value: float) -> str:
    return f"{value:.4f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |", *("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)]


def noise_context(treatment: str, statistic: str, day: int, error_points: float, noise_sds: dict) -> str:
    if day != WEEK_12_DAYS:
        return "week-12 noise only"
    return "below 3× seed SD" if abs(error_points) < 3 * noise_sds[treatment, statistic] else "above 3× seed SD"


def render_results(fingerprints: dict, pin_gap: float, tier0: list[dict], tier1: list[dict], tier2: list[dict], spread: list[dict], noise: list[dict], maximum_noise: dict, noise_sds: dict) -> str:
    lines = ["# Day 13 Step 3 validation results", "", "Generated by `notes/validate_simulation.py`. Do not edit by hand.", "", f"- Parameter version: `{PARAMETER_VERSION}`", f"- N_TRIALS: {N_TRIALS:,}", f"- Reporting seed: {SEED}", f"- Noise seeds: {', '.join(map(str, NOISE_SEEDS))}", f"- Monte Carlo noise floor: {point(maximum_noise['seed_sd'])} points (week 12, {maximum_noise['treatment']} {maximum_noise['statistic']}; sample SD across seeds)", f"- Production-path p50 pin: passed; maximum absolute gap {pin_gap:.12f} points", "", "## Frozen parameter SHA-256 fingerprints", ""]
    lines += markdown_table(["File", "SHA-256 (raw bytes)"], [[name, digest] for name, digest in fingerprints.items()])
    lines += ["", "## Tier 0 — in-sample reproduction (not validation)", "", "Reported mean points reverse Day 12's mean-to-median conversion; median target is the original fitted target. Errors are simulated minus reported. Status compares the median residual with the recorded fit RMSE.", ""]
    lines += markdown_table(["Tier", "Treatment", "Day", "Basis", "Baseline pts", "Reported pts", "Reported %", "Matching stat", "Simulated pts", "Simulated %", "Error pts", "Error pp", "Sim median pts", "Median target pts", "Median residual pts", "Fit RMSE pts", "Clamped frac", "Status", "MC context"], [[row["tier"], row["treatment"], row["t_days"], row["basis"], point(row["baseline"]), point(row["reported_points"]), percent(row["reported_percent"]), row["matching_statistic"], point(row["simulated_points"]), percent(row["simulated_percent"]), signed_point(row["error_points"]), signed_percent(row["error_pp"]), point(row["median_points"]), point(row["median_target"]), signed_point(row["median_residual"]), point(row["rmse"]), fraction(row["clamped_fraction"]), row["status"], noise_context(row["treatment"], row["matching_statistic"], row["t_days"], row["error_points"], noise_sds)] for row in tier0])
    lines += ["", "## Tier 1 — held-out replicate validation", "", "Verdicts follow protocol V4. `SE unavailable` means no typed SD of percentage change; those rows use the replicate gap alone. Tier 0 error is the matching-statistic error at the same treatment and day.", ""]
    lines += markdown_table(["Tier", "Treatment", "Day", "Baseline pts", "Statistic", "Reported pts", "Reported %", "Simulated pts", "Simulated %", "Error pts", "Error pp", "SE pp", "Replicate gap pp", "Clamped frac", "Verdict", "Tier 0 error pp", "MC context"], [[row["tier"], row["treatment"], row["t_days"], point(row["baseline"]), row["statistic"], point(row["reported_points"]), percent(row["reported_percent"]), point(row["simulated_points"]), percent(row["simulated_percent"]), signed_point(row["error_points"]), signed_percent(row["error_pp"]), "SE unavailable" if row["se_pct"] is None else f"{row['se_pct']:.3f}", percent(row["replicate_gap"]), fraction(row["clamped_fraction"]), row["verdict"], signed_percent(row["tier0_error_pp"]), noise_context(row["treatment"], row["statistic"], row["t_days"], row["error_points"], noise_sds)] for row in tier1])
    lines += ["", "## Tier 2 — partial / cross-source comparisons", "", "No verdicts apply. Clindamycin's 5.0 and 7.5 baselines are analyst-selected because the label source baseline is unavailable. Benzoyl peroxide's end-of-study quartiles are same-trial partial evidence, compared with simulated day 84 as an approximation; end of study also includes early discontinuation.", ""]
    lines += markdown_table(["Tier", "Treatment", "Source time", "Baseline pts", "Baseline status", "Statistic", "Reported %", "Simulated %", "Error pp", "Clamped frac"], [[row["tier"], row["treatment"], row["time"], point(row["baseline"]), row["baseline_note"], row["statistic"], percent(row["reported_percent"]), percent(row["simulated_percent"]), signed_percent(row["error_pp"]), fraction(row["clamped_fraction"])] for row in tier2])
    lines += ["", "### Tier 2 source caveats", ""]
    for treatment_id in sorted({row["treatment"] for row in tier2}):
        caveat = next(row["caveat"] for row in tier2 if row["treatment"] == treatment_id)
        lines.append(f"- **Tier 2 {treatment_id}:** {caveat}")
    lines += ["", "## Spread comparisons", "", "Only typed SDs of percentage change are included. Tier 0 301 week-12 SDs helped derive sigma and are in-sample; Tier 2 301 intermediate SDs are same-trial partial evidence. Differences are simulated minus reported. Simulated SD uses the sample definition (`ddof=1`).", ""]
    lines += markdown_table(["Tier", "Treatment", "Trial", "Day", "Reported SD pp", "Simulated SD pp", "Difference pp", "Clamped frac"], [[row["tier"], row["treatment"], row["source"], row["t_days"], percent(row["reported_sd"]), percent(row["simulated_sd"]), signed_percent(row["difference"]), fraction(row["clamped_fraction"])] for row in spread])
    lines += ["", "## Monte Carlo noise summary", "", "Each seed uses 10,000 raw production-path trials at the treatment's own calibration reference baseline on day 84. The seed SD is the sample SD across the five displayed point estimates. For week-12 location errors smaller than three times the matching seed SD, the error sign is indistinguishable from Monte Carlo noise; noise was measured only at week 12.", ""]
    lines += markdown_table(["Treatment", "Statistic", "Baseline pts", *[f"Seed {seed} pts" for seed in NOISE_SEEDS], "Seed SD pts"], [[row["treatment"], row["statistic"], point(row["baseline"]), *[point(value) for value in row["seed_values"]], point(row["seed_sd"])] for row in noise])
    lines += ["", f"Largest seed-to-seed SD: **{point(maximum_noise['seed_sd'])} points**, {maximum_noise['treatment']} {maximum_noise['statistic']} at day {WEEK_12_DAYS}.", ""]
    return "\n".join(lines)


def optional_number(value: float | None, formatter=point) -> str:
    return "unavailable" if value is None else formatter(value)


def sensitivity_cell_row(cell: dict) -> list[str]:
    identity = [cell["treatment"], cell["parameter"], cell["side"], cell["requested"]]
    if cell["status"] != "constructible":
        return [*identity, f"not constructible — {cell['reason']}", *(["—"] * 15)]
    stats = cell["stats"]
    return [*identity, "constructible", point(stats["median"]), signed_point(cell["delta_median"]), optional_number(cell["delta_median_percent"], signed_percent), point(stats["mean"]), signed_point(cell["delta_mean"]), optional_number(cell["delta_mean_percent"], signed_percent), point(stats["p10"]), point(stats["p90"]), point(stats["band_width"]), signed_point(cell["delta_width"]), optional_number(cell["delta_width_percent"], signed_percent), fraction(stats["clamped_fraction"]), f"{cell['delta_clamped']:+.4f}", optional_number(cell["median_elasticity"], signed_point), optional_number(cell["width_elasticity"], signed_point)]


def ranking_table(rankings: list[dict], noise_floor: float | None = None) -> list[str]:
    rows = []
    for row in rankings:
        parameter = f"{row['parameter']} (borrowed pooled)" if row["borrowed_sigma"] else row["parameter"]
        noise_note = "below overall week-12 seed SD" if noise_floor is not None and row["influence"] < noise_floor else "—"
        rows.append([row["treatment"], row["rank"], parameter, point(row["influence"]), row["coverage"], row["evidence"], noise_note])
    return markdown_table(["Treatment", "Rank", "Parameter", "Max absolute delta pts", "Coverage", "Day 12 evidence link", "Noise context"], rows)


def render_sensitivity(bases: dict, cells: list[dict], median_rankings: list[dict], width_rankings: list[dict], sweep: list[dict], records: dict, noise_floor: float) -> str:
    constructible = sum(cell["status"] == "constructible" for cell in cells)
    lines = ["## Sensitivity analysis", "", f"Local one-at-a-time (OAT) sensitivity at day {WEEK_12_DAYS}: {len(cells)} standardized cells attempted, {constructible} constructible, {len(cells) - constructible} not constructible. Each treatment uses its calibration baseline, {N_TRIALS:,} trials, seed {SEED}, and the same sampled latent patients for its base and every perturbation. This analysis does not measure higher-order parameter interactions or produce global sensitivity indices. Rankings describe these local model outputs, not clinical importance.", "", "### Base week-12 outcomes", ""]
    lines += markdown_table(["Treatment", "Reference baseline pts", "Mean pts", "Median pts", "p10 pts", "p90 pts", "Band width pts", "Clamped frac", "Sigma origin"], [[treatment_id, point(base["baseline"]), point(base["mean"]), point(base["median"]), point(base["p10"]), point(base["p90"]), point(base["band_width"]), fraction(base["clamped_fraction"]), base["sigma_origin"]] for treatment_id, base in sorted(bases.items())])
    lines += ["", "### OAT perturbations", "", "Deltas are signed relative to each treatment's base row. Percentage deltas use the base output as denominator; clamped-fraction deltas are fractions. Median and width elasticities divide the relative output change by the relative parameter change for multiplicative inputs. Delay is ±7 days, so its elasticities are unavailable. Every attempted side is listed, including failed Pydantic validation.", ""]
    headers = ["Treatment", "Parameter", "Side", "Requested", "Status / reason", "Median pts", "Δ median pts", "Δ median %", "Mean pts", "Δ mean pts", "Δ mean %", "p10 pts", "p90 pts", "Width pts", "Δ width pts", "Δ width %", "Clamped frac", "Δ clamped frac", "Median elasticity", "Width elasticity"]
    lines += markdown_table(headers, [sensitivity_cell_row(cell) for cell in cells])
    lines += ["", "### Median influence rankings", "", "Influence is the largest absolute signed median delta across constructible low/high sides. One-sided entries have only one legal standardized perturbation. Entries below the overall week-12 seed SD are flagged; paired common-random-number differences may be more precise, but these small ranks should not be over-interpreted.", ""]
    lines += ranking_table(median_rankings, noise_floor)
    lines += ["", "### Band-width influence rankings", "", "Influence is the largest absolute p10–p90 width delta across constructible sides. This ranking is separate from the median ranking. The Step 3 noise summary did not measure seed-to-seed width variability.", ""]
    lines += ranking_table(width_rankings)
    borrowed = [treatment_id for treatment_id, base in sorted(bases.items()) if base["sigma_origin"] == "borrowed pooled"]
    lines += ["", "### Evidence linkage and sigma origin", "", "Magnitude uses the fitted source improvement series; time scale uses its longitudinal visits; delay was selected from the recorded Day 12 grid. Sigma comes from a source-derived CV where available or a pooled value borrowed from three direct effects.", ""]
    lines += markdown_table(["Treatment", "Day 12 evidence", "Source basis", "Fitted observation days", "Sigma origin"], [[treatment_id, f"[calibration evidence](../calibration/evidence/{treatment_id}.json)", record["reported_basis"], ", ".join(str(observation["t_days"]) for observation in record["observations"]), bases[treatment_id]["sigma_origin"]] for treatment_id, record in sorted(records.items())])
    lines += ["", f"Borrowed pooled sigma treatments: **{', '.join(borrowed)}**. Their band-width sensitivity uses a spread assumption that is not treatment-specific.", "", "### Sigma calibration caveat", "", "The sigma OAT cells hold fitted `mean_magnitude` fixed and measure only direct simulator sensitivity. For mean-basis Day 12 evidence, sigma also changed the mean-to-median target conversion, `median_target = reported_mean / exp(sigma² / 2)`, and therefore influenced the fitted magnitude. That indirect calibration path is absent here; no fitting was rerun.", ""]
    example = records["tretinoin"]
    if example["reported_basis"] != "mean":
        raise AssertionError("analytic sigma example requires mean-basis evidence")
    sigma = example["response_sigma"]
    original_factor = math.exp(sigma ** 2 / 2)
    increased_factor = math.exp((1.2 * sigma) ** 2 / 2)
    lines += markdown_table(["Example treatment", "Base sigma", "Original exp(sigma²/2)", "At sigma ×1.2", "Relative change %"], [["tretinoin", f"{sigma:.9f}", point(original_factor), point(increased_factor), signed_percent(100 * (increased_factor / original_factor - 1))]])
    lines += ["", "## Baseline sweep", "", f"The same frozen absolute-point treatment model is simulated at baselines {', '.join(point(value) for value in BASELINE_SWEEP)} with the same {N_TRIALS:,} sampled patients and seed {SEED}. Different starting severity changes realized percentage improvement and clamping. These rows are model sensitivity, not external clinical evidence or validated efficacy at the tested baselines. Source/reference percentages retain their own reported mean or median basis and are not like-for-like comparisons with simulated medians when the basis differs.", ""]
    lines += markdown_table(["Treatment", "Tested baseline pts", "Calibration baseline pts", "Median improvement pts", "Median improvement %", "Clamped frac", "Day-84 source/ref %", "Source basis / availability"], [[row["treatment"], point(row["baseline"]), point(row["reference_baseline"]), point(row["median_points"]), percent(row["median_percent"]), fraction(row["clamped_fraction"]), optional_number(row["source_percent"], percent), row["source_basis"]] for row in sweep])
    lines += ["", "The baseline percentages use realized post-clamp improvement divided by the tested baseline; no source outcome is imputed for a missing day-84 observation.", ""]
    return "\n".join(lines)


def plot_sensitivity(bases: dict, cells: list[dict], median_rankings: list[dict]) -> None:
    figure, axes = plt.subplots(3, 2, figsize=(15, 13), constrained_layout=True)
    colors = {"low": "#3B6FA8", "high": "#D97932"}
    for axis, treatment_id in zip(axes.flat, sorted(bases)):
        ordered = [row["parameter"] for row in median_rankings if row["treatment"] == treatment_id]
        treatment_cells = {(cell["parameter"], cell["side"]): cell for cell in cells if cell["treatment"] == treatment_id}
        finite_deltas = [abs(cell["delta_median"]) for cell in treatment_cells.values() if cell["status"] == "constructible"]
        limit = max(finite_deltas) * 1.35 if finite_deltas else 1.0
        for index, parameter in enumerate(ordered):
            for side, offset in (("low", -0.18), ("high", 0.18)):
                cell = treatment_cells[parameter, side]
                y = index + offset
                if cell["status"] == "constructible":
                    label = "Low: ×0.8 / −7 days" if side == "low" else "High: ×1.2 / +7 days"
                    axis.barh(y, cell["delta_median"], height=0.31, color=colors[side], label=label if index == 0 else None)
                else:
                    axis.scatter(0, y, marker="x", color="#555555", s=48, linewidths=1.5)
                    axis.annotate("NC", (0, y), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8, color="#555555")
        axis.axvline(0, color="#444444", linewidth=0.8)
        axis.set_xlim(-limit, limit)
        axis.set_yticks(range(len(ordered)), ordered)
        axis.invert_yaxis()
        axis.set_title(f"{treatment_id} · base median {point(bases[treatment_id]['median'])} pts")
        axis.set_xlabel("Change in week-12 median improvement (points)")
        axis.grid(axis="x", alpha=0.2)
    axes.flat[0].legend(loc="lower right", fontsize=9, frameon=True)
    figure.suptitle("Local OAT sensitivity · frozen v1 · NC = not constructible", fontsize=15)
    figure.savefig(SENSITIVITY_PLOT_PATH, dpi=160, metadata={"Software": "GlassSkinAI validation harness"})
    plt.close(figure)


def main() -> None:
    treatments = {treatment.treatment_id: treatment for treatment in load_treatment_parameters(PARAMETER_VERSION)}
    evidence = load_evidence()
    comparisons = json.loads(HOLDOUT_PATH.read_text(encoding="utf-8"))["comparisons"]
    effects = list(calibrated_effects(treatments, evidence))
    fingerprints = parameter_fingerprints()
    if set(fingerprints) != {f"{treatment_id}.json" for treatment_id in treatments}:
        raise ValueError("parameter fingerprint file set differs from loaded treatments")
    _, pin_treatment, pin_effect, pin_record = next(item for item in effects if item[0] == "tretinoin")
    pin_times = sorted(observation["t_days"] for observation in pin_record["observations"])
    pin_gap = production_path_pin(pin_treatment, pin_effect.target_metric, pin_record["reference_baseline_points"], pin_times)
    tier0, tier0_lookup = tier0_rows(treatments, evidence)
    tier1 = tier1_rows(treatments, evidence, comparisons, tier0_lookup)
    check_preregistered_references(tier0_lookup, tier1)
    tier2 = tier2_rows(treatments, comparisons)
    spread = spread_rows(treatments, evidence, comparisons)
    noise, maximum_noise, noise_sds = monte_carlo_noise(treatments, evidence)
    bases, cells, records, patients = oat_sensitivity(treatments, evidence)
    median_rankings = influence_rankings(treatments, cells, records, "median")
    width_rankings = influence_rankings(treatments, cells, records, "width")
    sweep = baseline_sweep(treatments, evidence, patients)
    output = render_results(fingerprints, pin_gap, tier0, tier1, tier2, spread, noise, maximum_noise, noise_sds)
    output += "\n" + render_sensitivity(bases, cells, median_rankings, width_rankings, sweep, records, maximum_noise["seed_sd"])
    plot_sensitivity(bases, cells, median_rankings)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"Production-path pin passed (maximum p50 gap {pin_gap:.12f} points).")
    print(f"Wrote {OUTPUT_PATH.relative_to(BACKEND_DIR)}: Tier 0 {len(tier0)}, Tier 1 {len(tier1)}, Tier 2 {len(tier2)}, spread {len(spread)} rows.")
    print(f"OAT: {len(cells)} attempted, {sum(cell['status'] == 'constructible' for cell in cells)} constructible, {sum(cell['status'] != 'constructible' for cell in cells)} not constructible; baseline sweep {len(sweep)} rows.")
    print(f"Monte Carlo noise floor: {maximum_noise['seed_sd']:.6f} points ({maximum_noise['treatment']} {maximum_noise['statistic']}).")


if __name__ == "__main__":
    main()
