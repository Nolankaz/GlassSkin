"""Tests for the deterministic simulation engine's numerical and structural invariants.

All treatment values in this file are arbitrary fixtures and are NOT MEDICAL.
"""

import itertools
import math
from typing import get_args

import pytest

from pydantic import ValidationError

from simulation.curves import progress
from simulation.engine import (
    DIRECTION_SIGN,
    MULTIPLIER_FIELD_BY_KIND,
    apply_deltas,
    build_time_grid,
    clamp_metric,
    effect_contribution,
    effect_multiplier,
    metric_deltas,
    simulate,
    state_at,
)
from simulation.models import (
    CURVES_WITHOUT_DELAY,
    SKIN_METRIC_NAMES,
    EffectDirection,
    EffectKind,
    PatientResponse,
    SimulationConfig,
    SkinState,
    TimeCurveType,
    TreatmentEffect,
    TreatmentParameters,
)


ALL_CURVE_NAMES = get_args(TimeCurveType)
DELAY_ACCEPTING_CURVE_NAMES = tuple(curve for curve in ALL_CURVE_NAMES if curve not in CURVES_WITHOUT_DELAY)


def uniform_state(value):
    return SkinState(**{metric: value for metric in SKIN_METRIC_NAMES})


def distinct_state():
    return SkinState(**{metric: 1.0137 + 0.5 * index for index, metric in enumerate(SKIN_METRIC_NAMES)})


def fixture_effect(**overrides):
    kwargs = dict(
        target_metric="dryness",
        effect_kind="therapeutic",
        direction="decrease",
        delay_days=0,
        mean_magnitude=2.0,
        uncertainty=0.0,
        time_scale_days=30,
        time_curve="linear",
    )

    kwargs.update(overrides)
    return TreatmentEffect(**kwargs)


def fixture_treatment(*effects):
    return TreatmentParameters(
        treatment_id="fixture_treatment",
        display_name="FIXTURE (NOT MEDICAL)",
        parameter_version="fixture",
        effects=list(effects),
    )


def reference_response():
    """The definitional reference responder for fixtures, not a medical claim."""

    return PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0)


def config(duration_days, time_step_days):
    return SimulationConfig(duration_days=duration_days, time_step_days=time_step_days)


def legal_delay(curve):
    return 0 if curve in CURVES_WITHOUT_DELAY else 14


def absolute_rule_treatment():
    return fixture_treatment(
        fixture_effect(direction="decrease", mean_magnitude=3.0, time_scale_days=10),
        fixture_effect(effect_kind="side_effect", direction="increase", delay_days=10, mean_magnitude=3.0, time_scale_days=10, time_curve="delayed_linear"),
    )


# --- time grid --------------------------------------------------------------

@pytest.mark.parametrize(("duration", "step", "expected_length"), [
    (90, 1, 91),
    (90, 7, 14),
    (90, 30, 4),
    (5, 30, 2),
    (1, 1, 2),
    (730, 30, 26),
])
def test_known_time_grid_boundaries_and_lengths(duration, step, expected_length):
    times = build_time_grid(duration, step)

    assert times[0] == 0.0
    assert times[-1] == float(duration)
    assert len(times) == expected_length


def test_uneven_time_grid_ends_at_exact_duration():
    assert build_time_grid(90, 7)[-2:] == [84.0, 90.0]


def test_even_time_grid_has_exact_values():
    assert build_time_grid(90, 30) == [0.0, 30.0, 60.0, 90.0]


def test_time_grid_swept_invariants():
    for duration in range(1, 121):
        for step in range(1, 31):
            times = build_time_grid(duration, step)
            gaps = [following - current for current, following in zip(times, times[1:])]

            assert times[0] == 0.0
            assert times[-1] == float(duration)
            assert all(isinstance(value, float) for value in times)
            assert all(following > current for current, following in zip(times, times[1:]))
            assert all(gap <= step for gap in gaps)
            assert all(gap == step for gap in gaps[:-1])
            assert len(times) == math.ceil(duration / step) + 1


@pytest.mark.parametrize(("duration", "step"), [(0, 1), (-1, 1), (1, 0), (1, -1)])
def test_time_grid_rejects_non_positive_inputs(duration, step):
    with pytest.raises(ValueError):
        build_time_grid(duration, step)


# --- clamp ------------------------------------------------------------------

@pytest.mark.parametrize(("value", "expected"), [
    (4.5, 4.5),
    (0.0, 0.0),
    (10.0, 10.0),
    (-0.5, 0.0),
    (10.5, 10.0),
    (1e300, 10.0),
])
def test_clamp_metric(value, expected):
    assert clamp_metric(value) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_clamp_metric_rejects_non_finite_values(value):
    """Bounds comparisons do not safely reject NaN, so finiteness is explicit."""

    with pytest.raises(ValueError):
        clamp_metric(value)


# --- dispatch drift guards --------------------------------------------------

def test_direction_sign_covers_declared_directions():
    assert set(DIRECTION_SIGN) == set(get_args(EffectDirection))
    assert DIRECTION_SIGN == {"increase": 1.0, "decrease": -1.0}


def test_multiplier_fields_cover_declared_effect_kinds():
    assert set(MULTIPLIER_FIELD_BY_KIND) == set(get_args(EffectKind))
    assert all(field in PatientResponse.model_fields for field in MULTIPLIER_FIELD_BY_KIND.values())


# --- effect multiplier and contribution ------------------------------------

def test_effect_multiplier_selects_by_effect_kind():
    response = PatientResponse(response_multiplier=0.5, side_effect_multiplier=2.0)

    assert effect_multiplier("therapeutic", response) == 0.5
    assert effect_multiplier("side_effect", response) == 2.0


@pytest.mark.parametrize(("direction", "comparison"), [("increase", 1), ("decrease", -1)])
def test_effect_contribution_uses_direction_sign(direction, comparison):
    contribution = effect_contribution(fixture_effect(direction=direction), 15.0, reference_response())

    assert contribution * comparison > 0.0


@pytest.mark.parametrize("t_days", [0.0, 7.0, 14.0])
def test_effect_contribution_is_zero_through_delay(t_days):
    effect = fixture_effect(delay_days=14, time_curve="delayed_linear")

    assert effect_contribution(effect, t_days, reference_response()) == 0.0


# --- table A: known one-effect values --------------------------------------

@pytest.mark.parametrize(("t_days", "expected"), [(0.0, 5.0), (15.0, 3.5), (30.0, 2.0), (90.0, 2.0)])
def test_table_a_known_linear_values(t_days, expected):
    initial = uniform_state(5.0)
    treatment = fixture_treatment(fixture_effect(mean_magnitude=3.0, time_scale_days=30))

    assert state_at(initial, treatment, t_days, reference_response()).dryness == expected


def test_table_a_strong_response_value():
    initial = uniform_state(5.0)
    treatment = fixture_treatment(fixture_effect(mean_magnitude=3.0, time_scale_days=30))
    response = PatientResponse(response_multiplier=1.5, side_effect_multiplier=1.0)

    assert state_at(initial, treatment, 15.0, response).dryness == 2.75


# --- exponential and logistic known values ---------------------------------

@pytest.mark.parametrize(("curve", "t_days", "expected"), [
    ("exponential", 15.0, 3.819592),
    ("exponential", 30.0, 3.103638),
    ("logistic", 15.0, 4.690788),
    ("logistic", 30.0, 3.527473),
])
def test_saturating_curve_known_values(curve, t_days, expected):
    """Expected values come from Day 9 curve behavior, not this engine."""

    initial = uniform_state(5.0)
    treatment = fixture_treatment(fixture_effect(mean_magnitude=3.0, time_scale_days=30, time_curve=curve))

    assert state_at(initial, treatment, t_days, reference_response()).dryness == pytest.approx(expected, abs=1e-6)


# --- consistency with progress ---------------------------------------------

@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
def test_simulation_matches_progress_at_actual_grid_times(curve):
    """A 7-day step exposes index-vs-time bugs that a 1-day step can hide."""

    delay = legal_delay(curve)
    scale = 90
    initial = uniform_state(6.0)
    effect = fixture_effect(delay_days=delay, mean_magnitude=2.0, time_scale_days=scale, time_curve=curve)
    response = PatientResponse(response_multiplier=1.25, side_effect_multiplier=1.0)
    trajectory = simulate(initial, fixture_treatment(effect), config(180, 7), response)

    for index, t_days in enumerate(trajectory.times_days):
        expected = 6.0 - 2.5 * progress(curve, t_days, delay, scale)
        assert trajectory.states[index].dryness == pytest.approx(expected, abs=1e-12)


# --- monotonicity -----------------------------------------------------------

@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
@pytest.mark.parametrize("direction", get_args(EffectDirection))
def test_target_metric_is_monotone_through_saturation(curve, direction):
    delay = legal_delay(curve)
    effect = fixture_effect(direction=direction, delay_days=delay, mean_magnitude=10.0, time_scale_days=30, time_curve=curve)
    response = PatientResponse(response_multiplier=2.0, side_effect_multiplier=1.0)
    values = simulate(uniform_state(5.0), fixture_treatment(effect), config(180, 7), response).metric_series("dryness")

    if direction == "decrease":
        assert all(following <= current for current, following in zip(values, values[1:]))
    else:
        assert all(following >= current for current, following in zip(values, values[1:]))


# --- delay window -----------------------------------------------------------

@pytest.mark.parametrize("curve", DELAY_ACCEPTING_CURVE_NAMES)
def test_delay_window_preserves_entire_initial_state(curve):
    initial = distinct_state()
    effect = fixture_effect(delay_days=14, time_curve=curve)
    trajectory = simulate(initial, fixture_treatment(effect), config(21, 7), reference_response())

    for t_days, state in zip(trajectory.times_days, trajectory.states):
        if t_days <= 14:
            assert state == initial


# --- initial state invariant ------------------------------------------------

@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
def test_every_curve_starts_at_initial_state(curve):
    initial = distinct_state()
    effect = fixture_effect(delay_days=legal_delay(curve), time_curve=curve)
    trajectory = simulate(initial, fixture_treatment(effect), config(60, 7), reference_response())

    assert trajectory.states[0] == initial


# --- untargeted metrics -----------------------------------------------------

@pytest.mark.parametrize("target_metric", SKIN_METRIC_NAMES)
def test_untargeted_metrics_remain_bit_identical(target_metric):
    """Bit identity catches deltas written to the wrong metric as well as drift."""

    initial = distinct_state()
    effect = fixture_effect(target_metric=target_metric)
    trajectory = simulate(initial, fixture_treatment(effect), config(60, 7), reference_response())

    for state in trajectory.states:
        for metric in SKIN_METRIC_NAMES:
            if metric != target_metric:
                assert getattr(state, metric) == getattr(initial, metric)
                assert repr(getattr(state, metric)) == repr(getattr(initial, metric))


# --- metric deltas ----------------------------------------------------------

def test_metric_deltas_has_exact_metric_keys_and_zero_untargeted_values():
    deltas = metric_deltas([fixture_effect(target_metric="dryness")], 15.0, reference_response())

    assert tuple(deltas) == SKIN_METRIC_NAMES
    assert set(deltas) == set(SKIN_METRIC_NAMES)
    assert all(value == 0.0 for metric, value in deltas.items() if metric != "dryness")


@pytest.mark.parametrize("t_days", [0.0, 15.0, 90.0])
def test_empty_effects_produce_zero_deltas(t_days):
    initial = distinct_state()
    deltas = metric_deltas([], t_days, reference_response())

    assert tuple(deltas) == SKIN_METRIC_NAMES
    assert all(value == 0.0 for value in deltas.values())
    assert apply_deltas(initial, deltas) == initial


def test_treatment_parameters_still_requires_an_effect():
    with pytest.raises(ValidationError):
        fixture_treatment()


# --- exact cancellation -----------------------------------------------------

def test_opposite_effects_cancel_exactly():
    initial = distinct_state()
    decrease = fixture_effect(direction="decrease")
    increase = fixture_effect(direction="increase")
    trajectory = simulate(initial, fixture_treatment(decrease, increase), config(90, 7), reference_response())

    assert all(state == initial for state in trajectory.states)


# --- apply deltas key validation -------------------------------------------

def test_apply_deltas_rejects_missing_metric():
    deltas = {metric: 0.0 for metric in SKIN_METRIC_NAMES}
    del deltas[SKIN_METRIC_NAMES[0]]

    with pytest.raises(ValueError, match="missing keys"):
        apply_deltas(distinct_state(), deltas)


def test_apply_deltas_rejects_unknown_metric():
    deltas = {metric: 0.0 for metric in SKIN_METRIC_NAMES}
    deltas["unknown_metric"] = 0.0

    with pytest.raises(ValueError, match="unknown keys"):
        apply_deltas(distinct_state(), deltas)


# --- table B: multiple effects and distinct multipliers --------------------

def test_table_b_distinct_multiplier_fingerprint():
    """Wrong multiplier rules yield fingerprints such as 4.5, 6.0, 1.5, or 5.0 at day 20."""

    initial = uniform_state(5.0).model_copy(update={"dryness": 4.0})
    response = PatientResponse(response_multiplier=0.5, side_effect_multiplier=2.0)
    therapeutic = fixture_effect(direction="decrease", mean_magnitude=2.0, time_scale_days=20)
    side_effect = fixture_effect(effect_kind="side_effect", direction="increase", delay_days=10, mean_magnitude=3.0, time_scale_days=10, time_curve="delayed_linear")
    trajectory = simulate(initial, fixture_treatment(therapeutic, side_effect), config(40, 5), response)
    values_by_time = dict(zip(trajectory.times_days, trajectory.metric_series("dryness")))

    assert values_by_time[0.0] == 4.0
    assert values_by_time[5.0] == 3.75
    assert values_by_time[10.0] == 3.5
    assert values_by_time[15.0] == 6.25
    assert values_by_time[20.0] == 9.0
    assert values_by_time[40.0] == 9.0


# --- superposition across metrics ------------------------------------------

def test_effects_on_distinct_metrics_superpose_exactly():
    initial = distinct_state()
    dryness_effect = fixture_effect(target_metric="dryness", mean_magnitude=1.5)
    redness_effect = fixture_effect(target_metric="redness", direction="increase", mean_magnitude=2.5)
    run_config = config(90, 7)
    response = reference_response()
    combined = simulate(initial, fixture_treatment(dryness_effect, redness_effect), run_config, response)
    dryness_only = simulate(initial, fixture_treatment(dryness_effect), run_config, response)
    redness_only = simulate(initial, fixture_treatment(redness_effect), run_config, response)

    assert combined.metric_series("dryness") == dryness_only.metric_series("dryness")
    assert combined.metric_series("redness") == redness_only.metric_series("redness")


# --- effect-order independence ---------------------------------------------

def test_effect_order_does_not_change_trajectory():
    """Permutation identity protects math.fsum from replacement by an ordinary running total."""

    initial = uniform_state(5.0).model_copy(update={"dryness": 4.8137})
    effects = [fixture_effect(mean_magnitude=magnitude, time_scale_days=1) for magnitude in (0.1, 0.2, 0.3)]
    trajectories = [simulate(initial, fixture_treatment(*order), config(1, 1), reference_response()) for order in itertools.permutations(effects)]

    assert all(trajectory == trajectories[0] for trajectory in trajectories[1:])
    assert trajectories[0].states[-1].dryness == pytest.approx(4.2137)


# --- saturation and bounds -------------------------------------------------

def test_strong_effects_saturate_and_all_metrics_stay_bounded():
    initial = uniform_state(5.0)
    response = PatientResponse(response_multiplier=5.0, side_effect_multiplier=1.0)
    increase = simulate(initial, fixture_treatment(fixture_effect(direction="increase", mean_magnitude=10.0)), config(30, 30), response)
    decrease = simulate(initial, fixture_treatment(fixture_effect(direction="decrease", mean_magnitude=10.0)), config(30, 30), response)

    assert increase.states[-1].dryness == 10.0
    assert decrease.states[-1].dryness == 0.0
    for trajectory in (increase, decrease):
        assert all(0.0 <= getattr(state, metric) <= 10.0 for state in trajectory.states for metric in SKIN_METRIC_NAMES)


# --- table C: absolute vs cumulative ---------------------------------------

def test_table_c_absolute_application_recovers_after_clamping():
    """Cumulative clamping can yield 3.0 or 2.1, while per-effect clamping also gives a wrong answer."""

    initial = uniform_state(5.0).model_copy(update={"dryness": 1.0})
    trajectory = simulate(initial, absolute_rule_treatment(), config(20, 10), reference_response())
    values_by_time = dict(zip(trajectory.times_days, trajectory.metric_series("dryness")))

    assert values_by_time[10.0] == 0.0
    assert values_by_time[20.0] == 1.0


# --- step invariance --------------------------------------------------------

def test_absolute_engine_is_step_invariant_at_shared_times():
    """Step invariance is a defining property of computing every state from the initial state."""

    table_c = absolute_rule_treatment()
    clamping = fixture_treatment(
        fixture_effect(direction="increase", mean_magnitude=10.0, time_scale_days=10),
        fixture_effect(direction="decrease", mean_magnitude=2.0, time_scale_days=10),
    )
    initial = uniform_state(5.0).model_copy(update={"dryness": 1.0})

    for treatment in (table_c, clamping):
        trajectories = {step: simulate(initial, treatment, config(40, step), reference_response()) for step in (1, 5, 7)}
        states_by_step = {step: dict(zip(trajectory.times_days, trajectory.states)) for step, trajectory in trajectories.items()}
        for first_step, second_step in itertools.combinations(states_by_step, 2):
            shared_times = set(states_by_step[first_step]) & set(states_by_step[second_step])
            assert all(states_by_step[first_step][t_days] == states_by_step[second_step][t_days] for t_days in shared_times)


# --- state_at and simulate --------------------------------------------------

def test_simulate_maps_state_at_over_every_grid_time():
    initial = distinct_state()
    treatment = fixture_treatment(
        fixture_effect(target_metric="dryness"),
        fixture_effect(target_metric="redness", effect_kind="side_effect", direction="increase"),
    )
    response = PatientResponse(response_multiplier=0.75, side_effect_multiplier=1.25)
    trajectory = simulate(initial, treatment, config(40, 7), response)

    for index, t_days in enumerate(trajectory.times_days):
        assert state_at(initial, treatment, t_days, response) == trajectory.states[index]


# --- trajectory contents ---------------------------------------------------

def test_simulate_populates_trajectory_metadata_and_shape():
    initial = distinct_state()
    treatment = fixture_treatment(fixture_effect())
    run_config = config(40, 7)
    response = reference_response()
    trajectory = simulate(initial, treatment, run_config, response)

    assert trajectory.times_days == build_time_grid(40, 7)
    assert trajectory.treatment_id == treatment.treatment_id
    assert trajectory.parameter_version == treatment.parameter_version
    assert trajectory.patient_response == response
    assert len(trajectory.states) == len(trajectory.times_days)


# --- determinism ------------------------------------------------------------

def test_identical_simulations_are_exactly_deterministic():
    initial = distinct_state()
    treatment = fixture_treatment(fixture_effect(time_curve="logistic"))
    run_config = config(90, 7)
    response = reference_response()
    first = simulate(initial, treatment, run_config, response)
    second = simulate(initial, treatment, run_config, response)

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


# --- ignored deterministic-layer inputs ------------------------------------

def test_monte_carlo_inputs_are_ignored_by_deterministic_engine():
    """Day 11 owns trials, seeds, and uncertainty; this prevents hidden deterministic use."""

    initial = distinct_state()
    response = reference_response()
    base_treatment = fixture_treatment(fixture_effect(uncertainty=0.0))
    base_config = SimulationConfig(duration_days=90, time_step_days=7, n_trials=1, random_seed=None)
    baseline = simulate(initial, base_treatment, base_config, response)
    trial_variant = simulate(initial, base_treatment, SimulationConfig(duration_days=90, time_step_days=7, n_trials=10_000), response)
    seed_variant = simulate(initial, base_treatment, SimulationConfig(duration_days=90, time_step_days=7, random_seed=42), response)
    uncertainty_variant = simulate(initial, fixture_treatment(fixture_effect(uncertainty=5.0)), base_config, response)

    assert trial_variant == baseline
    assert seed_variant == baseline
    assert uncertainty_variant == baseline


# --- input immutability -----------------------------------------------------

def test_simulate_does_not_mutate_inputs():
    initial = distinct_state()
    treatment = fixture_treatment(fixture_effect())
    run_config = config(90, 7)
    response = reference_response()
    before = tuple(value.model_dump() for value in (initial, treatment, run_config, response))

    simulate(initial, treatment, run_config, response)

    after = tuple(value.model_dump() for value in (initial, treatment, run_config, response))
    assert after == before


# --- non-finite response ----------------------------------------------------

def test_non_finite_patient_response_remains_blocked():
    """This documents the deterministic engine's dependency on Step 2 hardening."""

    with pytest.raises(ValidationError):
        PatientResponse(response_multiplier=float("inf"), side_effect_multiplier=1.0)
