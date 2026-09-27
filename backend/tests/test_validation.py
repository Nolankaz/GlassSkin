"""Integrity checks for Day 13 held-out and partial comparison evidence."""

import json
import math
from pathlib import Path
import re

import pytest

from notes.fit_treatment_parameters import EVIDENCE_DIR
from simulation.models import SKIN_METRIC_NAMES
from simulation.parameters import available_treatment_ids


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
