"""Packaged parameter rules and real-engine calibration checks."""

import json
import math
from importlib import resources
from pathlib import Path
import re

import pytest

import simulation.parameters as parameter_loader
from simulation.engine import simulate
from simulation.models import FIXTURE_PROVENANCE, METRIC_MAX, METRIC_MIN, SKIN_METRIC_NAMES, PatientResponse, SimulationConfig, SkinState, TreatmentParameters
from simulation.monte_carlo import MAX_RESPONSE_LOG_SD, response_log_sd, simulate_many
from simulation.parameters import ParameterLoadError, available_treatment_ids, available_versions, load_treatment, load_treatment_parameters


EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "notes" / "calibration" / "evidence"
EVIDENCE_FILES = tuple(sorted(EVIDENCE_DIR.glob("*.json")))
RMSE_PATTERN = re.compile(r"\bRMSE=([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)")
NUMERICAL_ALLOWANCE = 1e-8


def sample_parameter_data() -> dict:
    return load_treatment("benzoyl_peroxide", "v1").model_dump()


def use_temporary_package(monkeypatch, tmp_path, files: dict[str, str]) -> None:
    version_dir = tmp_path / "v1"
    version_dir.mkdir()
    for filename, contents in files.items():
        (version_dir / filename).write_text(contents)
    monkeypatch.setattr(parameter_loader.resources, "files", lambda package: tmp_path)


def recorded_rmse(effect) -> float:
    matches = RMSE_PATTERN.findall(effect.provenance.derivation)
    assert len(matches) == 1, f"expected one recorded RMSE for {effect.target_metric}"
    value = float(matches[0])
    assert math.isfinite(value) and value >= 0
    return value


# --- packaged loader rules --------------------------------------------------

def test_available_versions_contains_v1_and_is_sorted():
    versions = available_versions()
    assert "v1" in versions
    assert versions == tuple(sorted(versions))


def test_available_versions_ignores_unrelated_entries(monkeypatch, tmp_path):
    use_temporary_package(monkeypatch, tmp_path, {})
    for name in ("v2", "v10", "v2x", "notes"):
        (tmp_path / name).mkdir()
    (tmp_path / "v3").write_text("not a directory")
    assert available_versions() == ("v1", "v10", "v2")


def test_loaded_v1_is_complete_sorted_unique_and_repeatable():
    first = load_treatment_parameters("v1")
    second = load_treatment_parameters("v1")
    ids = tuple(treatment.treatment_id for treatment in first)
    shipped_stems = {entry.name[:-5] for entry in resources.files("simulation.parameters").joinpath("v1").iterdir() if entry.is_file() and entry.name.endswith(".json")}

    assert len(first) >= len(EVIDENCE_FILES) >= 6
    assert all(isinstance(treatment, TreatmentParameters) for treatment in first)
    assert ids == tuple(sorted(ids)) == available_treatment_ids("v1")
    assert len(ids) == len(set(ids))
    assert set(ids) == shipped_stems
    assert all(treatment.parameter_version == "v1" for treatment in first)
    assert first == second and first is not second and all(a is not b for a, b in zip(first, second))
    assert all(load_treatment(treatment_id, "v1").treatment_id == treatment_id for treatment_id in ids)


@pytest.mark.parametrize("version", ["../notes", "v1/..", "v1/../../", "", "V1", "v1 ", "."])
def test_malformed_version_rejected_before_resource_access(monkeypatch, version):
    def fail_if_accessed(package):
        pytest.fail("resources.files was called before version validation")

    monkeypatch.setattr(parameter_loader.resources, "files", fail_if_accessed)
    with pytest.raises(ParameterLoadError) as excinfo:
        load_treatment_parameters(version)
    assert repr(version) in str(excinfo.value)
    assert parameter_loader.PARAMETER_VERSION_PATTERN in str(excinfo.value)


def test_unknown_version_names_available_versions():
    with pytest.raises(ParameterLoadError) as excinfo:
        load_treatment_parameters("v99")
    assert "v99" in str(excinfo.value)
    assert "v1" in str(excinfo.value)


def test_unknown_treatment_names_valid_ids():
    with pytest.raises(ParameterLoadError) as excinfo:
        load_treatment("does_not_exist", "v1")
    assert "does_not_exist" in str(excinfo.value)
    assert "v1" in str(excinfo.value)
    assert all(treatment_id in str(excinfo.value) for treatment_id in available_treatment_ids("v1"))


def test_loaded_provenance_is_published_and_complete():
    for treatment in load_treatment_parameters("v1"):
        for effect in treatment.effects:
            provenance = effect.provenance
            assert provenance.kind == "published"
            assert provenance.source_url.startswith("https://")
            assert all(getattr(provenance, field).strip() for field in ("citation", "reported_figure", "derivation"))
            assert FIXTURE_PROVENANCE.citation not in provenance.model_dump_json()


def test_empty_version_directory_is_rejected(monkeypatch, tmp_path):
    use_temporary_package(monkeypatch, tmp_path, {})
    with pytest.raises(ParameterLoadError, match="v1.*no JSON"):
        load_treatment_parameters("v1")


def test_invalid_json_names_file_and_chains_cause(monkeypatch, tmp_path):
    use_temporary_package(monkeypatch, tmp_path, {"broken.json": "{"})
    with pytest.raises(ParameterLoadError, match="broken.json") as excinfo:
        load_treatment_parameters("v1")
    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)


def test_invalid_model_names_file_and_chains_cause(monkeypatch, tmp_path):
    data = sample_parameter_data()
    data["effects"][0]["mean_magnitude"] = -1
    use_temporary_package(monkeypatch, tmp_path, {"benzoyl_peroxide.json": json.dumps(data)})
    with pytest.raises(ParameterLoadError, match="benzoyl_peroxide.json") as excinfo:
        load_treatment_parameters("v1")
    assert excinfo.value.__cause__ is not None


def test_filename_id_mismatch_names_both(monkeypatch, tmp_path):
    use_temporary_package(monkeypatch, tmp_path, {"wrong_name.json": json.dumps(sample_parameter_data())})
    with pytest.raises(ParameterLoadError) as excinfo:
        load_treatment_parameters("v1")
    assert "wrong_name.json" in str(excinfo.value)
    assert "benzoyl_peroxide" in str(excinfo.value)


def test_version_mismatch_names_file_and_both_versions(monkeypatch, tmp_path):
    data = sample_parameter_data()
    data["parameter_version"] = "v2"
    use_temporary_package(monkeypatch, tmp_path, {"benzoyl_peroxide.json": json.dumps(data)})
    with pytest.raises(ParameterLoadError) as excinfo:
        load_treatment_parameters("v1")
    assert "benzoyl_peroxide.json" in str(excinfo.value)
    assert "v1" in str(excinfo.value) and "v2" in str(excinfo.value)


def test_duplicate_id_names_both_files(monkeypatch, tmp_path):
    data = sample_parameter_data()
    use_temporary_package(monkeypatch, tmp_path, {"benzoyl_peroxide.json": json.dumps(data), "duplicate.json": json.dumps(data)})
    with pytest.raises(ParameterLoadError) as excinfo:
        load_treatment_parameters("v1")
    assert "benzoyl_peroxide.json" in str(excinfo.value)
    assert "duplicate.json" in str(excinfo.value)


@pytest.mark.parametrize("complete_fixture", [False, True])
def test_fixture_effect_is_rejected_with_file_metric_and_kind(monkeypatch, tmp_path, complete_fixture):
    data = sample_parameter_data()
    if complete_fixture:
        data["effects"][0]["provenance"] = FIXTURE_PROVENANCE.model_dump()
    else:
        data["effects"][0]["provenance"]["kind"] = "fixture"
    use_temporary_package(monkeypatch, tmp_path, {"benzoyl_peroxide.json": json.dumps(data)})
    with pytest.raises(ParameterLoadError) as excinfo:
        load_treatment_parameters("v1")
    assert "benzoyl_peroxide.json" in str(excinfo.value)
    assert "inflammatory_acne" in str(excinfo.value)
    assert "fixture" in str(excinfo.value)


# --- Day 11 compatibility ---------------------------------------------------

def test_real_effects_have_supported_response_spread():
    for treatment in load_treatment_parameters("v1"):
        for effect in treatment.effects:
            assert response_log_sd(effect) <= MAX_RESPONSE_LOG_SD


def test_real_treatment_runs_through_monte_carlo():
    treatment = load_treatment("benzoyl_peroxide", "v1")
    initial = SkinState(**{metric: 7.5 if metric == "inflammatory_acne" else 5.0 for metric in SKIN_METRIC_NAMES})
    result = simulate_many(initial, treatment, SimulationConfig(duration_days=84, time_step_days=7, n_trials=64, random_seed=137))

    assert result.treatment_id == treatment.treatment_id
    assert set(result.bands) == set(SKIN_METRIC_NAMES)
    for band in result.bands.values():
        for values in zip(band.p10, band.p50, band.p90):
            assert all(math.isfinite(value) and METRIC_MIN <= value <= METRIC_MAX for value in values)
            assert values[0] <= values[1] <= values[2]


# --- real-engine reproduction of Step 4 evidence ---------------------------

@pytest.mark.parametrize("evidence_path", EVIDENCE_FILES, ids=lambda path: path.stem)
def test_real_engine_reproduces_step_4_targets(evidence_path):
    evidence = json.loads(evidence_path.read_text())
    treatment = load_treatment(evidence["treatment_id"], "v1")
    assert len(treatment.effects) == len(evidence["effects"])

    for source_effect in evidence["effects"]:
        identity = (source_effect["target_metric"], source_effect["effect_kind"], source_effect["direction"])
        matches = [effect for effect in treatment.effects if (effect.target_metric, effect.effect_kind, effect.direction) == identity]
        assert len(matches) == 1, f"{evidence_path.name}: expected one runtime effect for {identity}"
        effect = matches[0]
        baseline = source_effect["reference_baseline_points"]
        initial = SkinState(**{metric: baseline if metric == effect.target_metric else 5.0 for metric in SKIN_METRIC_NAMES})
        observations = source_effect["observations"]
        config = SimulationConfig(duration_days=max(row["t_days"] for row in observations), time_step_days=1)
        trajectory = simulate(initial, treatment, config, PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0))
        states_by_day = dict(zip(trajectory.times_days, trajectory.states))
        residuals = []

        for observation in observations:
            t_days = observation["t_days"]
            assert t_days in states_by_day, f"{evidence_path.name}: observation day {t_days} is absent from simulation grid"
            value = getattr(states_by_day[t_days], effect.target_metric)
            assert METRIC_MIN < value < METRIC_MAX, f"{evidence_path.name}: target clamped at day {t_days}: {value}"
            simulated_change = baseline - value if effect.direction == "decrease" else value - baseline
            residuals.append(simulated_change - observation["target_points"])

        rmse = recorded_rmse(effect)
        assert all(abs(residual) <= math.sqrt(len(residuals)) * (rmse + NUMERICAL_ALLOWANCE) for residual in residuals), f"{evidence_path.name}: point residual exceeds RMSE-derived bound"
        actual_rmse = math.sqrt(math.fsum(residual * residual for residual in residuals) / len(residuals))
        assert abs(actual_rmse - rmse) <= NUMERICAL_ALLOWANCE, f"{evidence_path.name}: engine RMSE {actual_rmse} differs from recorded {rmse}"
