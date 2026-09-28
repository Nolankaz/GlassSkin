"""Day 13 evidence-integrity and model-sanity checks."""

import json
import math
from pathlib import Path
import re

import numpy as np
import pytest

from notes.fit_treatment_parameters import EVIDENCE_DIR
from simulation.models import MAX_EFFECT_UNCERTAINTY, METRIC_MAX, METRIC_MIN, SKIN_METRIC_NAMES, SkinState, TreatmentParameters
from simulation.monte_carlo import response_column, sample_log_responses, simulate_trials_vectorised
from simulation.parameters import available_treatment_ids, load_treatment


BACKEND_DIR = Path(__file__).resolve().parents[1]
VALIDATION_DIR = BACKEND_DIR / "notes" / "validation"
HOLDOUT_PATH = VALIDATION_DIR / "holdout_evidence.json"
SOURCES_PATH = BACKEND_DIR / "notes" / "calibration" / "sources.md"
NCT_PATTERN = re.compile(r"\bNCT\d{8}\b")
COMPARISON_KEYS = {"comparison_id", "treatment_id", "tier", "trial", "source_url", "target_metric", "statistic", "baseline_reported", "baseline_points", "observations", "caveats"}
OBSERVATION_KEYS = {"t_days", "reported", "value_percent", "spread_reported", "spread_percent", "n"}
EXPECTED_COMPARISONS = {"tretinoin_302_il_mean", "tazarotene_302_il_mean", "clindamycin_label_il_mean", "benzoyl_peroxide_eos_il_quartiles"}


def load_holdout() -> dict:
    return json.loads(HOLDOUT_PATH.read_text(encoding="utf-8"))


def is_finite_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


# --- holdout integrity ------------------------------------------------------

def test_holdout_file_shape_and_allowed_values():
    data = load_holdout()
    assert isinstance(data, dict)
    assert isinstance(data.get("sign_convention"), str) and data["sign_convention"].strip()
    assert isinstance(data.get("comparisons"), list) and data["comparisons"]
    assert isinstance(data.get("excluded"), list) and data["excluded"]
    valid_treatments = set(available_treatment_ids("v1"))
    ids = []

    for comparison in data["comparisons"]:
        assert isinstance(comparison, dict) and COMPARISON_KEYS <= comparison.keys()
        ids.append(comparison["comparison_id"])
        assert isinstance(comparison["comparison_id"], str) and comparison["comparison_id"].strip()
        assert comparison["tier"] in {"holdout_replicate", "partial"}
        assert comparison["treatment_id"] in valid_treatments
        assert comparison["target_metric"] in SKIN_METRIC_NAMES
        assert comparison["statistic"] in {"mean", "median", "quartiles"}
        assert isinstance(comparison["trial"], str) and comparison["trial"].strip()
        assert isinstance(comparison["source_url"], str) and comparison["source_url"].startswith("https://")
        assert comparison["baseline_reported"] is None or isinstance(comparison["baseline_reported"], str)
        assert comparison["baseline_points"] is None or (is_finite_number(comparison["baseline_points"]) and comparison["baseline_points"] > 0)
        assert isinstance(comparison["caveats"], str) and comparison["caveats"].strip()
        assert isinstance(comparison["observations"], list) and comparison["observations"]

        for observation in comparison["observations"]:
            assert isinstance(observation, dict) and OBSERVATION_KEYS <= observation.keys()
            assert observation["t_days"] is None or (type(observation["t_days"]) is int and observation["t_days"] > 0)
            assert isinstance(observation["reported"], str) and observation["reported"].strip()
            assert is_finite_number(observation["value_percent"]) and observation["value_percent"] >= 0
            assert observation["spread_reported"] is None or isinstance(observation["spread_reported"], str)
            assert observation["spread_percent"] is None or (is_finite_number(observation["spread_percent"]) and observation["spread_percent"] >= 0)
            assert observation["spread_percent"] is None or observation["spread_reported"].startswith("SD ")
            assert observation["n"] is None or (type(observation["n"]) is int and observation["n"] > 0)
            if comparison["statistic"] == "quartiles":
                quartiles = observation["quartiles_percent"]
                assert set(quartiles) == {"p25", "median", "p75"}
                assert all(is_finite_number(value) and value >= 0 for value in quartiles.values())
                assert quartiles["p25"] <= quartiles["median"] <= quartiles["p75"]
                assert observation["value_percent"] == quartiles["median"]

    assert set(ids) == EXPECTED_COMPARISONS and len(ids) == len(EXPECTED_COMPARISONS)


@pytest.mark.parametrize("field", ["reported", "spread_reported", "baseline_reported"])
def test_verbatim_source_traceability(field):
    sources = SOURCES_PATH.read_text(encoding="utf-8")
    for comparison in load_holdout()["comparisons"]:
        values = [comparison.get(field)] if field == "baseline_reported" else [observation.get(field) for observation in comparison["observations"]]
        for value in values:
            if value is not None:
                assert value in sources, f"{comparison['comparison_id']} {field}: {value!r} is absent from sources.md"


def test_numeric_percentages_and_urls_match_reported_sources():
    sources = SOURCES_PATH.read_text(encoding="utf-8")
    for comparison in load_holdout()["comparisons"]:
        assert comparison["source_url"] in sources
        for observation in comparison["observations"]:
            reported_value = re.search(r"[−-]?(\d+(?:\.\d+)?)%", observation["reported"])
            assert reported_value and observation["value_percent"] == float(reported_value.group(1))
            if observation["spread_percent"] is not None:
                match = re.fullmatch(r"SD (\d+(?:\.\d+)?) percentage points", observation["spread_reported"])
                assert match and observation["spread_percent"] == float(match.group(1))
            if comparison["statistic"] == "quartiles":
                quartiles = re.fullmatch(r"(\d+(?:\.\d+)?)% \((\d+(?:\.\d+)?)[–-](\d+(?:\.\d+)?)%\)", observation["reported"])
                assert quartiles
                assert observation["quartiles_percent"] == {"p25": float(quartiles.group(2)), "median": float(quartiles.group(1)), "p75": float(quartiles.group(3))}


def test_tier1_trials_are_disjoint_from_calibration_provenance():
    provenances = [effect["provenance"] for path in sorted(EVIDENCE_DIR.glob("*.json")) for effect in json.loads(path.read_text(encoding="utf-8"))["effects"]]
    for comparison in load_holdout()["comparisons"]:
        if comparison["tier"] != "holdout_replicate":
            continue
        trial_ids = NCT_PATTERN.findall(comparison["trial"])
        assert len(trial_ids) == 1, f"{comparison['comparison_id']} must name exactly one NCT trial"
        trial_id = trial_ids[0]
        for provenance in provenances:
            assert trial_id not in provenance["source_url"]
            assert trial_id not in provenance["citation"]


def test_validation_directory_is_outside_fitter_evidence_directory():
    validation_dir = HOLDOUT_PATH.parent.resolve()
    evidence_dir = EVIDENCE_DIR.resolve()
    assert validation_dir != evidence_dir
    assert not validation_dir.is_relative_to(evidence_dir)


def test_tier1_comparisons_have_baselines_and_multiple_positive_times():
    for comparison in load_holdout()["comparisons"]:
        if comparison["tier"] == "holdout_replicate":
            assert len(comparison["observations"]) >= 2
            assert comparison["baseline_points"] is not None
            assert all(type(observation["t_days"]) is int and observation["t_days"] > 0 for observation in comparison["observations"])


def test_exclusion_list_has_candidates_and_reasons():
    excluded = load_holdout()["excluded"]
    assert excluded
    for entry in excluded:
        assert isinstance(entry, dict)
        assert isinstance(entry.get("candidate"), str) and entry["candidate"].strip()
        assert isinstance(entry.get("reason"), str) and entry["reason"].strip()


# --- model sanity properties -----------------------------------------------

SANITY_SEED = 42
SANITY_TRIALS = 1_001
EXACT_MEDIAN_TRIALS = 10_001
WEEK_12_DAYS = 84


def calibrated_case(treatment_id: str):
    treatment = load_treatment(treatment_id, "v1")
    evidence = json.loads((EVIDENCE_DIR / f"{treatment_id}.json").read_text(encoding="utf-8"))
    assert evidence["treatment_id"] == treatment_id
    assert len(treatment.effects) == len(evidence["effects"]) == 1
    effect = treatment.effects[0]
    record = evidence["effects"][0]
    assert (effect.target_metric, effect.effect_kind, effect.direction) == (record["target_metric"], record["effect_kind"], record["direction"])
    assert effect.effect_kind == "therapeutic" and effect.direction == "decrease"
    return treatment, effect, record["reference_baseline_points"]


def perturbed(treatment: TreatmentParameters, **effect_changes) -> TreatmentParameters:
    """Revalidate the whole treatment, including its changed effect."""
    data = treatment.model_dump()
    assert len(data["effects"]) == 1
    data["effects"][0].update(effect_changes)
    return TreatmentParameters.model_validate(data)


def legal_factor(effect, nominal_factor: float) -> float:
    assert nominal_factor > 1 and effect.uncertainty > 0
    return min(nominal_factor, MAX_EFFECT_UNCERTAINTY / effect.uncertainty)


def sampled_patients(n_trials: int) -> np.ndarray:
    return sample_log_responses(n_trials, np.random.default_rng(SANITY_SEED))


def metric_values(treatment: TreatmentParameters, baseline: float, times_days, log_responses: np.ndarray) -> np.ndarray:
    metric = treatment.effects[0].target_metric
    state = SkinState(**{name: baseline if name == metric else (METRIC_MIN + METRIC_MAX) / 2 for name in SKIN_METRIC_NAMES})
    trials = simulate_trials_vectorised(state, treatment, times_days, log_responses)
    return trials[:, :, SKIN_METRIC_NAMES.index(metric)]


@pytest.mark.parametrize("treatment_id", available_treatment_ids("v1"))
def test_stronger_magnitude_increases_week12_response(treatment_id):
    treatment, effect, baseline = calibrated_case(treatment_id)
    factor = legal_factor(effect, 1.2)
    assert factor > 1.0
    stronger = perturbed(treatment, mean_magnitude=effect.mean_magnitude * factor, uncertainty=effect.uncertainty * factor)
    assert math.isclose(stronger.effects[0].uncertainty / stronger.effects[0].mean_magnitude, effect.uncertainty / effect.mean_magnitude, rel_tol=1e-15)
    patients = sampled_patients(SANITY_TRIALS)
    base_changes = baseline - metric_values(treatment, baseline, [WEEK_12_DAYS], patients)[:, 0]
    stronger_changes = baseline - metric_values(stronger, baseline, [WEEK_12_DAYS], patients)[:, 0]
    base_median, base_p90 = np.percentile(base_changes, (50, 90), method="linear")
    stronger_median, stronger_p90 = np.percentile(stronger_changes, (50, 90), method="linear")
    assert stronger_median > base_median
    assert stronger_p90 >= base_p90  # Clamping can leave the upper percentile unchanged.


@pytest.mark.parametrize("treatment_id", available_treatment_ids("v1"))
def test_longer_delay_reaches_response_threshold_later(treatment_id):
    treatment, effect, baseline = calibrated_case(treatment_id)
    delayed = perturbed(treatment, delay_days=effect.delay_days + 7)
    patients = sampled_patients(SANITY_TRIALS)
    days = list(range(WEEK_12_DAYS + 1))
    base_medians = np.percentile(baseline - metric_values(treatment, baseline, days, patients), 50, axis=0, method="linear")
    delayed_medians = np.percentile(baseline - metric_values(delayed, baseline, days, patients), 50, axis=0, method="linear")
    assert np.all(delayed_medians <= base_medians + 1e-12)
    threshold = 0.5 * base_medians[WEEK_12_DAYS]
    assert threshold > 0
    base_day = int(np.flatnonzero(base_medians >= threshold)[0])
    delayed_hits = np.flatnonzero(delayed_medians >= threshold)
    if len(delayed_hits) == 0:
        # Five time scales reaches near-asymptote for saturating curves and exceeds full delayed-linear progress; 730 is the live simulation horizon.
        safe_day = min(730, max(WEEK_12_DAYS + 1, math.ceil(delayed.effects[0].delay_days + 5 * delayed.effects[0].time_scale_days)))
        extra_days = list(range(WEEK_12_DAYS + 1, safe_day + 1))
        extra_medians = np.percentile(baseline - metric_values(delayed, baseline, extra_days, patients), 50, axis=0, method="linear")
        delayed_hits = np.flatnonzero(extra_medians >= threshold) + WEEK_12_DAYS + 1
    assert len(delayed_hits) > 0, f"delayed {treatment_id} never reached the base response threshold by the safe bound"
    assert int(delayed_hits[0]) > base_day


@pytest.mark.parametrize("treatment_id", available_treatment_ids("v1"))
def test_wider_sigma_widens_band_with_exact_sampled_median(treatment_id):
    treatment, effect, baseline = calibrated_case(treatment_id)
    factor = legal_factor(effect, 2.0)
    assert factor > 1.0
    wider = perturbed(treatment, uncertainty=effect.uncertainty * factor)
    assert wider.effects[0].mean_magnitude == effect.mean_magnitude
    patients = sampled_patients(EXACT_MEDIAN_TRIALS)
    assert len(patients) % 2 == 1
    base_values = metric_values(treatment, baseline, [WEEK_12_DAYS], patients)[:, 0]
    wider_values = metric_values(wider, baseline, [WEEK_12_DAYS], patients)[:, 0]
    base_p10, base_median, base_p90 = np.percentile(baseline - base_values, (10, 50, 90), method="linear")
    wider_p10, wider_median, wider_p90 = np.percentile(baseline - wider_values, (10, 50, 90), method="linear")
    assert wider_p90 - wider_p10 > base_p90 - base_p10
    assert np.percentile(base_values, 50, method="linear") > METRIC_MIN
    assert np.percentile(wider_values, 50, method="linear") > METRIC_MIN
    sigma = effect.uncertainty / effect.mean_magnitude
    assert math.isclose(wider.effects[0].uncertainty / wider.effects[0].mean_magnitude, factor * sigma, rel_tol=1e-15)
    median_latent = np.percentile(patients[:, response_column(effect.effect_kind)], 50, method="linear")
    expected_wider_median = base_median * math.exp((factor - 1) * sigma * median_latent)
    assert math.isclose(wider_median, expected_wider_median, rel_tol=1e-12, abs_tol=1e-12)
    # No mean-direction assertion: stronger responses may be cut off by clamping at the baseline.
