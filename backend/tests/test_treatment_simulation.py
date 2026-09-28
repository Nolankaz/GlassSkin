"""Service-level tests for calibrated simulations and test-only multi-effect behavior."""

import pytest

from services.treatment_simulation import (
    DEFAULT_DURATION_DAYS,
    SIMULATION_N_TRIALS,
    SIMULATION_SEED,
    SIMULATION_TIME_STEP_DAYS,
    UnknownTreatmentError,
    affected_metrics,
    find_treatment,
    list_simulatable_treatments,
    run_profile_simulation,
    simulate_profile_treatment,
)
from simulation.models import FIXTURE_PROVENANCE, SKIN_METRIC_NAMES, SimulationConfig, TreatmentEffect, TreatmentParameters
from simulation.monte_carlo import simulate_many
from simulation.parameters import available_treatment_ids, load_treatment
from simulation.profile_adapter import ProfileConversionError, skin_state_from_profile


def valid_profile(**overrides):
    profile = {"id": 123, "name": "Test profile", "age": 30, "gender": "Not specified", **{metric: 5.0 for metric in SKIN_METRIC_NAMES}}
    profile.update(overrides)
    return profile


def fixture_effect(target_metric, effect_kind, direction, mean_magnitude):
    return TreatmentEffect(
        target_metric=target_metric,
        effect_kind=effect_kind,
        direction=direction,
        delay_days=0,
        mean_magnitude=mean_magnitude,
        uncertainty=0.1,
        time_scale_days=28.0,
        time_curve="linear",
        provenance=FIXTURE_PROVENANCE,
    )


def multi_effect_fixture():
    """Synthetic effects in reverse metric order; these are NOT MEDICAL DATA."""

    return TreatmentParameters(
        treatment_id="fixture_multi_effect",
        display_name="FIXTURE (NOT MEDICAL)",
        parameter_version="fixture",
        effects=[
            fixture_effect("dryness", "side_effect", "increase", 2.0),
            fixture_effect("dryness", "therapeutic", "decrease", 0.25),
            fixture_effect("blackheads", "therapeutic", "decrease", 1.0),
            fixture_effect("inflammatory_acne", "therapeutic", "decrease", 1.0),
        ],
    )


# --- catalogue -------------------------------------------------------------

def test_catalogue_matches_packaged_v1_treatments():
    treatments = list_simulatable_treatments()

    assert tuple(treatment.treatment_id for treatment in treatments) == available_treatment_ids("v1")
    for treatment in treatments:
        assert treatment.parameter_version == "v1"
        assert treatment.effects
        assert all(effect.source_url.startswith("https://") for effect in treatment.effects)


# --- real v1 simulations ---------------------------------------------------

@pytest.mark.parametrize("treatment_id", available_treatment_ids("v1"))
def test_real_v1_returns_exactly_affected_metrics_in_canonical_order(treatment_id):
    treatment = load_treatment(treatment_id, "v1")
    result = run_profile_simulation(valid_profile(), treatment_id, DEFAULT_DURATION_DAYS)

    assert tuple(metric.metric for metric in result.metrics) == affected_metrics(treatment)


@pytest.mark.parametrize("treatment_id", available_treatment_ids("v1"))
def test_real_v1_response_metadata_baselines_and_percentile_bands(treatment_id):
    profile = valid_profile(inflammatory_acne=8, blackheads=6, dryness=3)
    duration_days = DEFAULT_DURATION_DAYS
    result = run_profile_simulation(profile, treatment_id, duration_days)

    assert result.times_days[0] == 0
    assert result.times_days[-1] == duration_days
    assert result.n_trials == SIMULATION_N_TRIALS
    assert result.random_seed == SIMULATION_SEED
    for metric in result.metrics:
        assert metric.baseline == profile[metric.metric]
        assert len(metric.p10) == len(result.times_days)
        assert len(metric.p50) == len(result.times_days)
        assert len(metric.p90) == len(result.times_days)
        assert all(p10 <= p50 <= p90 for p10, p50, p90 in zip(metric.p10, metric.p50, metric.p90))


def test_service_p50_exactly_matches_production_simulate_many():
    profile = valid_profile(inflammatory_acne=8)
    state = skin_state_from_profile(profile)
    treatment = load_treatment("tretinoin", "v1")
    config = SimulationConfig(duration_days=DEFAULT_DURATION_DAYS, time_step_days=SIMULATION_TIME_STEP_DAYS, n_trials=SIMULATION_N_TRIALS, random_seed=SIMULATION_SEED)

    production_result = simulate_many(state, treatment, config)
    service_result = simulate_profile_treatment(profile["id"], state, treatment, DEFAULT_DURATION_DAYS)
    metric_name = affected_metrics(treatment)[0]

    assert next(metric for metric in service_result.metrics if metric.metric == metric_name).p50 == production_result.metric_band(metric_name).p50


def test_tretinoin_day13_numerical_anchor():
    profile = valid_profile(inflammatory_acne=8)
    treatment = load_treatment("tretinoin", "v1")
    result = run_profile_simulation(profile, treatment.treatment_id, DEFAULT_DURATION_DAYS)
    assert DEFAULT_DURATION_DAYS == 84
    assert "inflammatory_acne" in affected_metrics(treatment)
    metric = next(metric for metric in result.metrics if metric.metric == "inflammatory_acne")

    assert abs(metric.p50[-1] - (8 - 2.9066)) < 0.05


def test_identical_service_inputs_return_identical_full_responses():
    profile = valid_profile(inflammatory_acne=8)
    first = run_profile_simulation(profile, "tretinoin", DEFAULT_DURATION_DAYS)
    second = run_profile_simulation(profile, "tretinoin", DEFAULT_DURATION_DAYS)

    assert first.model_dump() == second.model_dump()


# --- errors and generality -------------------------------------------------

def test_unknown_treatment_reports_current_catalogue_ids():
    with pytest.raises(UnknownTreatmentError) as caught:
        find_treatment("not_a_treatment")

    assert caught.value.valid_ids == available_treatment_ids("v1")


def test_missing_profile_metric_is_not_silently_filled():
    profile = valid_profile(cystic_nodular_acne=None)

    with pytest.raises(ProfileConversionError, match="cystic_nodular_acne"):
        run_profile_simulation(profile, available_treatment_ids("v1")[0], DEFAULT_DURATION_DAYS)


def test_multi_effect_fixture_uses_unique_canonical_metric_order():
    treatment = multi_effect_fixture()
    state = skin_state_from_profile(valid_profile(dryness=3))
    targets = {effect.target_metric for effect in treatment.effects}
    expected = tuple(metric for metric in SKIN_METRIC_NAMES if metric in targets)
    effect_order = tuple(dict.fromkeys(effect.target_metric for effect in treatment.effects))

    assert expected == ("inflammatory_acne", "blackheads", "dryness")
    assert expected != effect_order
    assert affected_metrics(treatment) == expected
    assert len(affected_metrics(treatment)) == len(targets)

    result = simulate_profile_treatment(123, state, treatment, DEFAULT_DURATION_DAYS)
    assert tuple(metric.metric for metric in result.metrics) == expected
    assert len(result.metrics) == len(targets)

    dryness = next(metric for metric in result.metrics if metric.metric == "dryness")
    assert set(dryness.effect_kinds) == {"therapeutic", "side_effect"}
    assert len(dryness.effect_kinds) == 2
    assert dryness.p50[-1] > dryness.baseline
