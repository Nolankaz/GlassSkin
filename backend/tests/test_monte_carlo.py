"""Tests for Monte Carlo sampling, aggregation, and deterministic equivalence.

All treatment values in this file are arbitrary fixtures and are NOT MEDICAL.
"""

import ast
import inspect
import itertools
import math
import random
import statistics
from typing import get_args

import numpy as np
import pytest

import simulation.curves as curves_module
import simulation.engine as engine_module
import simulation.models as models_module
from simulation.engine import MULTIPLIER_FIELD_BY_KIND, build_time_grid, simulate
from simulation.models import (
    FIXTURE_PROVENANCE,
    METRIC_MAX,
    METRIC_MIN,
    SKIN_METRIC_NAMES,
    EffectKind,
    PatientResponse,
    PercentileBand,
    SimulationConfig,
    SkinState,
    TimeCurveType,
    TreatmentEffect,
    TreatmentParameters,
)
from simulation.monte_carlo import (
    BAND_PERCENTILES,
    MAX_RESPONSE_LOG_SD,
    RESPONSE_FIELDS,
    check_log_responses,
    effective_response,
    percentile_bands,
    require_seed,
    response_column,
    response_log_sd,
    sample_log_responses,
    simulate_many,
    simulate_many_naive,
    simulate_trials_naive,
    simulate_trials_vectorised,
)


def uniform_state(value=5.0, **overrides):
    values = {metric: value for metric in SKIN_METRIC_NAMES}
    values.update(overrides)
    return SkinState(**values)


def distinct_state():
    return SkinState(**{metric: 1.0137 + 0.5 * index for index, metric in enumerate(SKIN_METRIC_NAMES)})


def fixture_effect(**overrides):
    kwargs = dict(
        target_metric="dryness",
        effect_kind="therapeutic",
        direction="decrease",
        delay_days=0,
        mean_magnitude=2.0,
        uncertainty=1.0,
        time_scale_days=30.0,
        time_curve="linear",
        provenance=FIXTURE_PROVENANCE,
    )
    kwargs.update(overrides)
    return TreatmentEffect(**kwargs)


def fixture_treatment(*effects, treatment_id="fixture_treatment"):
    return TreatmentParameters(
        treatment_id=treatment_id,
        display_name="FIXTURE (NOT MEDICAL)",
        parameter_version="fixture",
        effects=list(effects),
    )


def mc_config(n_trials=7, seed=42, duration_days=30, time_step_days=5):
    return SimulationConfig(duration_days=duration_days, time_step_days=time_step_days, n_trials=n_trials, random_seed=seed)


def explicit_log_responses(rows):
    return np.array(rows, dtype=np.float64)


def trajectory_array(trajectory):
    return np.array([[getattr(state, metric) for metric in SKIN_METRIC_NAMES] for state in trajectory.states], dtype=np.float64)


def result_band_array(result):
    return np.stack([np.column_stack([getattr(result.bands[metric], percentile) for metric in SKIN_METRIC_NAMES]) for percentile in ("p10", "p50", "p90")])


def representative_treatment():
    return fixture_treatment(
        fixture_effect(target_metric="dryness", mean_magnitude=2.0, uncertainty=0.8, time_scale_days=30.0),
        fixture_effect(target_metric="irritation", effect_kind="side_effect", direction="increase", delay_days=5, mean_magnitude=1.5, uncertainty=0.6, time_scale_days=20.0, time_curve="exponential"),
        fixture_effect(target_metric="redness", delay_days=7, mean_magnitude=2.5, uncertainty=1.25, time_scale_days=45.0, time_curve="logistic"),
    )


def oracle_treatment(log_sd):
    return fixture_treatment(
        fixture_effect(target_metric="dryness", mean_magnitude=2.0, uncertainty=2.0 * log_sd, time_scale_days=30.0),
        fixture_effect(target_metric="dryness", effect_kind="side_effect", direction="increase", delay_days=7, mean_magnitude=1.5, uncertainty=1.5 * log_sd, time_scale_days=20.0, time_curve="delayed_linear"),
        fixture_effect(target_metric="redness", direction="increase", mean_magnitude=2.5, uncertainty=2.5 * log_sd, time_scale_days=45.0, time_curve="exponential"),
    )


def table_d_fixture():
    state = uniform_state(5.0)
    treatment = fixture_treatment(fixture_effect(mean_magnitude=2.0, uncertainty=1.0, time_scale_days=10.0))
    times = [0.0, 5.0, 10.0]
    log_responses = explicit_log_responses([[-2.0, 0.0], [-1.0, 0.0], [0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    return state, treatment, times, log_responses


def table_e_fixture():
    state = uniform_state(5.0, dryness=6.0)
    treatment = fixture_treatment(
        fixture_effect(mean_magnitude=2.0, uncertainty=2.0, time_scale_days=10.0),
        fixture_effect(effect_kind="side_effect", direction="increase", mean_magnitude=1.0, uncertainty=1.0, time_scale_days=10.0),
    )
    return state, treatment, [0.0, 10.0], explicit_log_responses([[1.0, -1.0]])


def assert_numpy_random_states_equal(first, second):
    assert first[0] == second[0]
    np.testing.assert_array_equal(first[1], second[1])
    assert first[2:] == second[2:]


# --- seeds and generator isolation -----------------------------------------

@pytest.mark.parametrize("runner", [simulate_many_naive, simulate_many])
@pytest.mark.parametrize("seed", [None, -1])
def test_public_monte_carlo_rejects_invalid_seed(runner, seed):
    with pytest.raises(ValueError, match="random_seed|reproducible"):
        runner(uniform_state(), representative_treatment(), mc_config(seed=seed))


@pytest.mark.parametrize("runner", [simulate_many_naive, simulate_many])
def test_public_monte_carlo_accepts_zero_seed(runner):
    assert runner(uniform_state(), representative_treatment(), mc_config(seed=0)).random_seed == 0


@pytest.mark.parametrize("bad_rng", [np.random, np.random.RandomState(0), 0, None])
def test_sample_log_responses_requires_generator(bad_rng):
    with pytest.raises(TypeError):
        sample_log_responses(5, bad_rng)


@pytest.mark.parametrize("n_trials", [0, -1])
def test_sample_log_responses_rejects_non_positive_trials(n_trials):
    with pytest.raises(ValueError):
        sample_log_responses(n_trials, np.random.default_rng(42))


def test_monte_carlo_is_isolated_from_global_random_state():
    """Local RNG isolation works in both directions."""

    original_numpy_state = np.random.get_state()
    original_python_state = random.getstate()
    try:
        np.random.seed(17)
        random.seed(17)
        before_numpy = np.random.get_state()
        before_python = random.getstate()
        simulate_many(uniform_state(), representative_treatment(), mc_config())
        assert_numpy_random_states_equal(before_numpy, np.random.get_state())
        assert before_python == random.getstate()

        np.random.seed(1)
        random.seed(1)
        first = simulate_many(uniform_state(), representative_treatment(), mc_config())
        np.random.seed(2)
        random.seed(2)
        second = simulate_many(uniform_state(), representative_treatment(), mc_config())
        assert first == second
    finally:
        np.random.set_state(original_numpy_state)
        random.setstate(original_python_state)


# --- sampling ---------------------------------------------------------------

@pytest.mark.parametrize("n_trials", [1, 5, 257])
def test_sample_log_responses_shape_dtype_and_finiteness(n_trials):
    samples = sample_log_responses(n_trials, np.random.default_rng(42))

    assert samples.shape == (n_trials, len(RESPONSE_FIELDS))
    assert samples.dtype == np.float64
    assert np.isfinite(samples).all()


def test_sample_log_responses_same_seed_is_exactly_reproducible():
    first = sample_log_responses(20, np.random.default_rng(42))
    second = sample_log_responses(20, np.random.default_rng(42))

    assert np.array_equal(first, second)


def test_sample_log_responses_different_seeds_differ():
    first = sample_log_responses(20, np.random.default_rng(42))
    second = sample_log_responses(20, np.random.default_rng(43))

    assert not np.array_equal(first, second)


def test_sample_log_responses_is_prefix_stable():
    """Raising n_trials adds patients without replacing the existing prefix."""

    small = sample_log_responses(10, np.random.default_rng(137))
    large = sample_log_responses(100, np.random.default_rng(137))

    assert np.array_equal(small, large[:10])


def test_sample_log_responses_fixed_seed_distribution_sanity():
    """Margins are at least about seven standard errors for this fixed sample."""

    samples = sample_log_responses(20_000, np.random.default_rng(137))
    assert np.all(np.abs(samples.mean(axis=0)) < 0.05)
    assert np.all(np.abs(samples.std(axis=0) - 1.0) < 0.05)
    assert abs(np.corrcoef(samples, rowvar=False)[0, 1]) < 0.05


def test_monte_carlo_field_and_percentile_mappings_do_not_drift():
    assert RESPONSE_FIELDS == tuple(PatientResponse.model_fields)
    assert set(MULTIPLIER_FIELD_BY_KIND.values()) == set(RESPONSE_FIELDS)
    assert len({response_column(kind) for kind in get_args(EffectKind)}) == len(get_args(EffectKind))
    assert tuple(f"p{int(percentile)}" for percentile in BAND_PERCENTILES) == tuple(PercentileBand.model_fields)


@pytest.mark.parametrize("effect_kind", get_args(EffectKind))
def test_response_column_matches_day_10_mapping(effect_kind):
    expected = RESPONSE_FIELDS.index(MULTIPLIER_FIELD_BY_KIND[effect_kind])

    assert response_column(effect_kind) == expected


# --- latent-response validation --------------------------------------------

def test_check_log_responses_accepts_valid_array():
    assert check_log_responses(np.zeros((3, len(RESPONSE_FIELDS)), dtype=np.float64)) is None


@pytest.mark.parametrize("bad_array", [
    np.zeros(2, dtype=np.float64),
    np.zeros((3, 3), dtype=np.float64),
    np.zeros((2, 5), dtype=np.float64),
    np.empty((0, len(RESPONSE_FIELDS)), dtype=np.float64),
], ids=["one-dimensional", "three-columns", "transposed-shape", "zero-rows"])
def test_check_log_responses_rejects_bad_shape(bad_array):
    with pytest.raises(ValueError):
        check_log_responses(bad_array)


def test_check_log_responses_rejects_float32():
    with pytest.raises(ValueError, match="float64"):
        check_log_responses(np.zeros((3, len(RESPONSE_FIELDS)), dtype=np.float32))


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_check_log_responses_rejects_non_finite_values(bad_value):
    values = np.zeros((3, len(RESPONSE_FIELDS)), dtype=np.float64)
    values[1, 0] = bad_value

    with pytest.raises(ValueError, match="finite"):
        check_log_responses(values)


def test_check_log_responses_rejects_non_numpy_input():
    with pytest.raises(ValueError, match="numpy array"):
        check_log_responses([[0.0, 0.0]])


# --- response spread and effective response --------------------------------

@pytest.mark.parametrize(("uncertainty", "expected"), [(0.0, 0.0), (1.0, 0.5), (2.0, 1.0), (4.0, 2.0)])
def test_response_log_sd_uses_uncertainty_over_magnitude(uncertainty, expected):
    assert response_log_sd(fixture_effect(mean_magnitude=2.0, uncertainty=uncertainty)) == expected


def test_response_log_sd_allows_exact_cap():
    assert response_log_sd(fixture_effect(mean_magnitude=2.0, uncertainty=4.0)) == MAX_RESPONSE_LOG_SD


def test_response_log_sd_rejects_above_cap_and_names_effect():
    effect = fixture_effect(target_metric="dryness", effect_kind="therapeutic", mean_magnitude=1.0, uncertainty=2.5)

    with pytest.raises(ValueError, match=r"dryness.*therapeutic.*2\.5"):
        response_log_sd(effect)


def test_effective_response_with_zero_log_sd_is_reference_response():
    response = effective_response(np.array([-3.0, 2.0], dtype=np.float64), 0.0)

    assert response == PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0)


def test_effective_response_with_unit_log_sd_exponentiates_each_field():
    values = np.array([0.5, -0.25], dtype=np.float64)
    response = effective_response(values, 1.0)

    assert response.response_multiplier == math.exp(values[0])
    assert response.side_effect_multiplier == math.exp(values[1])


# --- naive reference pinned to Day 10 --------------------------------------

def test_zero_uncertainty_naive_trials_equal_day_10_reference_exactly():
    treatment = oracle_treatment(0.0)
    config = SimulationConfig(duration_days=90, time_step_days=7)
    times = build_time_grid(config.duration_days, config.time_step_days)
    log_responses = sample_log_responses(25, np.random.default_rng(42))
    trials = simulate_trials_naive(distinct_state(), treatment, times, log_responses)
    expected = trajectory_array(simulate(distinct_state(), treatment, config, PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0)))

    np.testing.assert_array_equal(trials, np.broadcast_to(expected, trials.shape))


def test_unit_sigma_naive_trials_equal_day_10_sampled_people_exactly():
    """This pins kind columns and composition to the trusted Day 10 engine."""

    treatment = oracle_treatment(1.0)
    config = SimulationConfig(duration_days=90, time_step_days=7)
    times = build_time_grid(config.duration_days, config.time_step_days)
    log_responses = sample_log_responses(25, np.random.default_rng(42))
    trials = simulate_trials_naive(distinct_state(), treatment, times, log_responses)

    for trial_index, row in enumerate(log_responses):
        response = PatientResponse(response_multiplier=math.exp(row[0]), side_effect_multiplier=math.exp(row[1]))
        expected = trajectory_array(simulate(distinct_state(), treatment, config, response))
        np.testing.assert_array_equal(trials[trial_index], expected)


@pytest.mark.parametrize("trials_function", [simulate_trials_naive, simulate_trials_vectorised])
def test_table_d_hand_calculated_states_and_bands(trials_function):
    state, treatment, times, log_responses = table_d_fixture()
    trials = trials_function(state, treatment, times, log_responses)
    dryness_index = SKIN_METRIC_NAMES.index("dryness")
    expected_states = np.array([
        [5.0, 4.632121, 4.264241],
        [5.0, 4.393469, 3.786939],
        [5.0, 4.0, 3.0],
        [5.0, 3.351279, 1.702557],
        [5.0, 2.281718, 0.0],
    ])
    expected_bands = np.array([
        [5.0, 2.709542, 0.681023],
        [5.0, 4.0, 3.0],
        [5.0, 4.536660, 4.073320],
    ])

    np.testing.assert_allclose(trials[:, :, dryness_index], expected_states, rtol=0.0, atol=1e-6)
    bands = percentile_bands(trials)
    np.testing.assert_allclose(bands[:, :, dryness_index], expected_bands, rtol=0.0, atol=1e-6)
    assert bands[1, 2, dryness_index] == 3.0


@pytest.mark.parametrize("trials_function", [simulate_trials_naive, simulate_trials_vectorised])
def test_table_e_kind_column_fingerprint(trials_function):
    """Wrong rules give 7.982523, 3.281718, 5.0, 0.0, or 2.925688."""

    state, treatment, times, log_responses = table_e_fixture()
    trials = trials_function(state, treatment, times, log_responses)
    dryness_index = SKIN_METRIC_NAMES.index("dryness")

    assert trials[0, 1, dryness_index] == pytest.approx(0.931316, abs=1e-6)


# --- vectorised equivalence -------------------------------------------------

def curve_treatment():
    effects = []
    for index, curve in enumerate(get_args(TimeCurveType)):
        effects.append(fixture_effect(target_metric=SKIN_METRIC_NAMES[index], delay_days=0 if curve == "linear" else 7, mean_magnitude=1.0 + index * 0.25, uncertainty=0.5, time_curve=curve))
    return fixture_treatment(*effects, treatment_id="fixture_curves")


@pytest.mark.parametrize("treatment", [
    fixture_treatment(fixture_effect(), treatment_id="fixture_single"),
    fixture_treatment(
        fixture_effect(target_metric="dryness", direction="decrease"),
        fixture_effect(target_metric="dryness", effect_kind="side_effect", direction="increase", delay_days=7, time_curve="delayed_linear"),
        treatment_id="fixture_opposing",
    ),
    fixture_treatment(
        fixture_effect(target_metric="dryness", mean_magnitude=1.0, uncertainty=0.2),
        fixture_effect(target_metric="dryness", effect_kind="side_effect", direction="increase", mean_magnitude=1.5, uncertainty=0.6),
        fixture_effect(target_metric="dryness", mean_magnitude=2.0, uncertainty=1.0, time_curve="logistic"),
        fixture_effect(target_metric="redness", direction="increase", mean_magnitude=1.0, uncertainty=0.4),
        treatment_id="fixture_duplicate_targets",
    ),
    curve_treatment(),
    fixture_treatment(
        fixture_effect(target_metric="dryness", direction="decrease", mean_magnitude=10.0, uncertainty=5.0),
        fixture_effect(target_metric="redness", direction="increase", mean_magnitude=10.0, uncertainty=5.0),
        treatment_id="fixture_clamping",
    ),
], ids=["single", "opposing-kinds", "duplicate-targets", "all-curves", "clamping"])
def test_naive_and_vectorised_trial_arrays_agree(treatment):
    """The production optimisation must match the plausible-looking reference."""

    times = build_time_grid(90, 7)
    log_responses = sample_log_responses(257, np.random.default_rng(137))
    naive = simulate_trials_naive(distinct_state(), treatment, times, log_responses)
    vectorised = simulate_trials_vectorised(distinct_state(), treatment, times, log_responses)

    assert naive.shape == vectorised.shape
    np.testing.assert_allclose(vectorised, naive, rtol=0.0, atol=1e-10)


def test_public_naive_and_vectorised_results_agree():
    config = mc_config(n_trials=257, seed=7, duration_days=90, time_step_days=7)
    naive = simulate_many_naive(distinct_state(), representative_treatment(), config)
    vectorised = simulate_many(distinct_state(), representative_treatment(), config)

    assert (naive.treatment_id, naive.parameter_version, naive.n_trials, naive.random_seed) == (vectorised.treatment_id, vectorised.parameter_version, vectorised.n_trials, vectorised.random_seed)
    assert naive.times_days == vectorised.times_days
    np.testing.assert_allclose(result_band_array(vectorised), result_band_array(naive), rtol=0.0, atol=1e-10)


def test_vectorised_zero_uncertainty_matches_day_10():
    """Single-effect targets retain Day 10's multiplication order."""

    treatment = oracle_treatment(0.0)
    config = SimulationConfig(duration_days=90, time_step_days=7)
    times = build_time_grid(config.duration_days, config.time_step_days)
    log_responses = sample_log_responses(7, np.random.default_rng(42))
    trials = simulate_trials_vectorised(distinct_state(), treatment, times, log_responses)
    expected = trajectory_array(simulate(distinct_state(), treatment, config, PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0)))

    np.testing.assert_allclose(trials, np.broadcast_to(expected, trials.shape), rtol=0.0, atol=1e-10)
    redness_index = SKIN_METRIC_NAMES.index("redness")
    np.testing.assert_array_equal(trials[:, :, redness_index], np.broadcast_to(expected[:, redness_index], trials[:, :, redness_index].shape))


def test_duplicate_target_effects_accumulate_in_vectorised_path():
    treatment = fixture_treatment(
        fixture_effect(target_metric="dryness", direction="decrease", mean_magnitude=2.0, uncertainty=1.0, time_scale_days=10.0),
        fixture_effect(target_metric="dryness", effect_kind="side_effect", direction="increase", mean_magnitude=1.0, uncertainty=0.5, time_scale_days=10.0),
    )
    times = [0.0, 10.0]
    log_responses = explicit_log_responses([[0.0, 0.0], [1.0, -1.0]])
    naive = simulate_trials_naive(uniform_state(), treatment, times, log_responses)
    vectorised = simulate_trials_vectorised(uniform_state(), treatment, times, log_responses)
    dryness_index = SKIN_METRIC_NAMES.index("dryness")

    np.testing.assert_allclose(vectorised, naive, rtol=0.0, atol=1e-10)
    assert vectorised[0, 1, dryness_index] == 4.0


# --- shapes, axes, and percentile aggregation ------------------------------

@pytest.mark.parametrize("trials_function", [simulate_trials_naive, simulate_trials_vectorised])
def test_raw_trial_state_shape_and_dtype(trials_function):
    times = [0.0, 10.0, 20.0, 30.0]
    trials = trials_function(uniform_state(), representative_treatment(), times, sample_log_responses(7, np.random.default_rng(42)))

    assert trials.shape == (7, 4, len(SKIN_METRIC_NAMES))
    assert trials.dtype == np.float64


def test_distinct_axis_sizes_and_band_shape():
    times = build_time_grid(90, 7)
    trials = simulate_trials_vectorised(distinct_state(), representative_treatment(), times, sample_log_responses(257, np.random.default_rng(42)))

    assert trials.shape == (257, 14, 17)
    assert percentile_bands(trials).shape == (3, 14, 17)


def test_percentile_bands_linear_method_and_axis_order():
    trial_states = np.array([
        [[0.0, 100.0], [10.0, 110.0]],
        [[10.0, 110.0], [20.0, 120.0]],
        [[20.0, 120.0], [30.0, 130.0]],
        [[30.0, 130.0], [40.0, 140.0]],
        [[40.0, 140.0], [50.0, 150.0]],
    ])
    expected = np.array([
        [[4.0, 104.0], [14.0, 114.0]],
        [[20.0, 120.0], [30.0, 130.0]],
        [[36.0, 136.0], [46.0, 146.0]],
    ])

    np.testing.assert_array_equal(percentile_bands(trial_states), expected)


def test_percentile_bands_known_values_across_trials():
    trial_states = np.broadcast_to(np.arange(11, dtype=np.float64)[:, None, None], (11, 2, len(SKIN_METRIC_NAMES))).copy()
    bands = percentile_bands(trial_states)

    np.testing.assert_array_equal(bands[0], np.ones((2, len(SKIN_METRIC_NAMES))))
    np.testing.assert_array_equal(bands[1], np.full((2, len(SKIN_METRIC_NAMES)), 5.0))
    np.testing.assert_array_equal(bands[2], np.full((2, len(SKIN_METRIC_NAMES)), 9.0))


def test_percentile_bands_preserves_time_and_metric_axes():
    trial_states = np.array([[[trial + 100 * time + metric for metric in range(17)] for time in range(14)] for trial in range(5)], dtype=np.float64)
    bands = percentile_bands(trial_states)

    for time_index in range(14):
        for metric_index in range(17):
            expected = np.percentile(trial_states[:, time_index, metric_index], BAND_PERCENTILES, method="linear")
            np.testing.assert_array_equal(bands[:, time_index, metric_index], expected)


@pytest.mark.parametrize("n_trials", [2, 3, 10, 257])
def test_percentile_bands_matches_statistics_quantiles_oracle(n_trials):
    trial_states = np.random.default_rng(137).normal(size=(n_trials, 3, 4))
    bands = percentile_bands(trial_states)

    for time_index in range(3):
        for metric_index in range(4):
            deciles = statistics.quantiles(trial_states[:, time_index, metric_index], n=10, method="inclusive")
            np.testing.assert_allclose(bands[:, time_index, metric_index], [deciles[0], deciles[4], deciles[8]], rtol=0.0, atol=1e-12)


def test_percentile_bands_single_trial_has_zero_width():
    trial_states = np.random.default_rng(42).normal(size=(1, 3, 4))
    bands = percentile_bands(trial_states)

    for percentile_index in range(3):
        np.testing.assert_array_equal(bands[percentile_index], trial_states[0])


@pytest.mark.parametrize("bad_states", [np.zeros((3, 4)), np.empty((0, 3, 4))], ids=["two-dimensional", "zero-trials"])
def test_percentile_bands_rejects_malformed_input(bad_states):
    with pytest.raises(ValueError):
        percentile_bands(bad_states)


# --- seed validation --------------------------------------------------------

@pytest.mark.parametrize("seed", [0, 42])
def test_require_seed_returns_nonnegative_seed(seed):
    assert require_seed(mc_config(seed=seed)) == seed


def test_require_seed_rejects_none():
    with pytest.raises(ValueError, match="reproducible.*random_seed"):
        require_seed(mc_config(seed=None))


def test_require_seed_rejects_negative_value():
    with pytest.raises(ValueError, match="non-negative"):
        require_seed(mc_config(seed=-1))


# --- result invariants ------------------------------------------------------

def test_result_bands_are_ordered_finite_and_bounded():
    treatment = fixture_treatment(
        fixture_effect(target_metric="dryness", direction="decrease", mean_magnitude=10.0, uncertainty=5.0),
        fixture_effect(target_metric="redness", effect_kind="side_effect", direction="increase", mean_magnitude=10.0, uncertainty=5.0),
    )
    for seed in range(5):
        bands = result_band_array(simulate_many(uniform_state(), treatment, mc_config(n_trials=20, seed=seed)))
        assert np.all(bands[0] <= bands[1])
        assert np.all(bands[1] <= bands[2])
        assert np.isfinite(bands).all()
        assert np.all((METRIC_MIN <= bands) & (bands <= METRIC_MAX))


@pytest.mark.parametrize("runner", [simulate_many_naive, simulate_many])
def test_untargeted_metrics_remain_bit_identical_in_bands(runner):
    state = distinct_state()
    result = runner(state, fixture_treatment(fixture_effect(target_metric="dryness")), mc_config())

    for metric in SKIN_METRIC_NAMES:
        if metric == "dryness":
            continue
        expected = [getattr(state, metric)] * len(result.times_days)
        for percentile in ("p10", "p50", "p90"):
            values = getattr(result.bands[metric], percentile)
            assert values == expected
            assert [repr(value) for value in values] == [repr(value) for value in expected]


def test_result_starts_at_initial_state_and_respects_delay_window():
    state = distinct_state()
    treatment = fixture_treatment(fixture_effect(delay_days=14, time_curve="exponential"))
    result = simulate_many(state, treatment, mc_config(n_trials=20, duration_days=21, time_step_days=7))

    for time_index, t_days in enumerate(result.times_days):
        if t_days <= 14:
            for metric in SKIN_METRIC_NAMES:
                expected = getattr(state, metric)
                assert all(getattr(result.bands[metric], percentile)[time_index] == expected for percentile in ("p10", "p50", "p90"))


@pytest.mark.parametrize("runner", [simulate_many_naive, simulate_many])
def test_zero_uncertainty_produces_zero_width_bands(runner):
    result = runner(distinct_state(), oracle_treatment(0.0), mc_config(n_trials=7))

    for band in result.bands.values():
        assert band.p10 == band.p50 == band.p90


def test_reference_responder_is_the_sample_median():
    """The 0.05 margin is about five standard errors for this fixed sample."""

    state = uniform_state(8.0)
    treatment = fixture_treatment(fixture_effect(mean_magnitude=2.0, uncertainty=1.0, time_scale_days=30.0))
    config = mc_config(n_trials=20_001, seed=137, duration_days=90, time_step_days=7)
    result = simulate_many(state, treatment, config)
    reference = simulate(state, treatment, config, PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0))

    np.testing.assert_allclose(result.bands["dryness"].p50, reference.metric_series("dryness"), rtol=0.0, atol=0.05)


@pytest.mark.parametrize(("runner", "n_trials"), [(simulate_many_naive, 5), (simulate_many, 20)])
def test_monte_carlo_bands_are_step_invariant_at_shared_times(runner, n_trials):
    treatment = representative_treatment()
    results = {step: runner(distinct_state(), treatment, mc_config(n_trials=n_trials, seed=42, duration_days=35, time_step_days=step)) for step in (1, 5, 7)}

    for first_step, second_step in itertools.combinations(results, 2):
        first = results[first_step]
        second = results[second_step]
        shared_times = set(first.times_days) & set(second.times_days)
        for t_days in shared_times:
            first_index = first.times_days.index(t_days)
            second_index = second.times_days.index(t_days)
            for metric in SKIN_METRIC_NAMES:
                for percentile in ("p10", "p50", "p90"):
                    assert getattr(first.bands[metric], percentile)[first_index] == getattr(second.bands[metric], percentile)[second_index]


def test_effect_order_does_not_change_results():
    effects = [
        fixture_effect(target_metric="dryness", mean_magnitude=0.1, uncertainty=0.05),
        fixture_effect(target_metric="dryness", mean_magnitude=0.2, uncertainty=0.1),
        fixture_effect(target_metric="dryness", mean_magnitude=0.3, uncertainty=0.15),
    ]
    treatments = [fixture_treatment(*order) for order in itertools.permutations(effects)]
    config = mc_config(n_trials=7)
    naive_results = [simulate_many_naive(uniform_state(), treatment, config) for treatment in treatments]
    vectorised_results = [simulate_many(uniform_state(), treatment, config) for treatment in treatments]

    assert all(result == naive_results[0] for result in naive_results[1:])
    for result in vectorised_results[1:]:
        np.testing.assert_allclose(result_band_array(result), result_band_array(vectorised_results[0]), rtol=0.0, atol=1e-10)


def test_common_random_numbers_preserve_existing_metric_bands():
    """Day 17 can compare treatments using the same simulated patients."""

    dryness_effect = fixture_effect(target_metric="dryness")
    base = fixture_treatment(dryness_effect)
    extended = fixture_treatment(dryness_effect, fixture_effect(target_metric="redness", direction="increase"))
    config = mc_config(n_trials=20, seed=137)

    assert simulate_many(uniform_state(), base, config).bands["dryness"] == simulate_many(uniform_state(), extended, config).bands["dryness"]


def test_result_metadata_matches_inputs():
    treatment = representative_treatment()
    config = mc_config(n_trials=20, seed=137, duration_days=35, time_step_days=7)
    result = simulate_many(uniform_state(), treatment, config)

    assert result.treatment_id == treatment.treatment_id
    assert result.parameter_version == treatment.parameter_version
    assert result.n_trials == config.n_trials
    assert result.random_seed == config.random_seed
    assert result.times_days == build_time_grid(config.duration_days, config.time_step_days)


# --- reproducibility --------------------------------------------------------

@pytest.mark.parametrize("runner", [simulate_many_naive, simulate_many])
def test_same_seed_reproduces_identical_public_result(runner):
    state = distinct_state()
    treatment = representative_treatment()
    config = mc_config(n_trials=20, seed=137)
    first = runner(state, treatment, config)
    second = runner(state, treatment, config)

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


@pytest.mark.parametrize("runner", [simulate_many_naive, simulate_many])
def test_different_seeds_change_only_stochastic_targeted_bands(runner):
    state = distinct_state()
    treatment = fixture_treatment(fixture_effect(target_metric="dryness", uncertainty=1.0))
    first = runner(state, treatment, mc_config(n_trials=20, seed=42))
    second = runner(state, treatment, mc_config(n_trials=20, seed=43))

    assert first.bands["dryness"] != second.bands["dryness"]
    assert all(first.bands[metric] == second.bands[metric] for metric in SKIN_METRIC_NAMES if metric != "dryness")


# --- loud failure, purity, and immutability --------------------------------

@pytest.mark.parametrize("trials_function", [simulate_trials_naive, simulate_trials_vectorised])
@pytest.mark.parametrize("bad_log_responses", [
    np.zeros(2, dtype=np.float64),
    np.zeros((2, 5), dtype=np.float64),
    np.zeros((3, 3), dtype=np.float64),
    np.empty((0, len(RESPONSE_FIELDS)), dtype=np.float64),
    np.zeros((3, len(RESPONSE_FIELDS)), dtype=np.float32),
    np.array([[float("nan"), 0.0]], dtype=np.float64),
], ids=["one-dimensional", "transposed-shape", "three-columns", "zero-rows", "float32", "nan"])
def test_trial_functions_reject_malformed_log_responses(trials_function, bad_log_responses):
    with pytest.raises(ValueError):
        trials_function(uniform_state(), representative_treatment(), [0.0, 1.0], bad_log_responses)


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.parametrize(("latent_response", "naive_error"), [(800.0, OverflowError), (709.0, ValueError)])
def test_overflow_fails_loudly_before_invalid_values_escape(latent_response, naive_error):
    treatment = fixture_treatment(fixture_effect(mean_magnitude=5.0, uncertainty=5.0, time_scale_days=10.0))
    log_responses = explicit_log_responses([[latent_response, 0.0], [0.0, 0.0]])

    with pytest.raises(naive_error):
        simulate_trials_naive(uniform_state(), treatment, [0.0, 10.0], log_responses)
    with pytest.raises(ValueError, match="non-finite"):
        simulate_trials_vectorised(uniform_state(), treatment, [0.0, 10.0], log_responses)


@pytest.mark.parametrize("runner", [simulate_many_naive, simulate_many])
def test_public_paths_enforce_response_log_sd_cap(runner):
    treatment = fixture_treatment(fixture_effect(mean_magnitude=1.0, uncertainty=5.0))

    with pytest.raises(ValueError, match="dryness"):
        runner(uniform_state(), treatment, mc_config())


def test_monte_carlo_does_not_mutate_inputs():
    state = distinct_state()
    treatment = representative_treatment()
    config = mc_config()
    log_responses = sample_log_responses(7, np.random.default_rng(42))
    before_models = tuple(value.model_dump() for value in (state, treatment, config))
    before_responses = log_responses.copy()

    simulate_trials_naive(state, treatment, build_time_grid(30, 5), log_responses)
    simulate_trials_vectorised(state, treatment, build_time_grid(30, 5), log_responses)
    simulate_many_naive(state, treatment, config)
    simulate_many(state, treatment, config)

    assert tuple(value.model_dump() for value in (state, treatment, config)) == before_models
    np.testing.assert_array_equal(log_responses, before_responses)


def test_randomness_dependency_points_only_toward_monte_carlo():
    """Day 10 stays NumPy-free and RNG-free; Monte Carlo depends upward only."""

    forbidden_roots = {"numpy", "random"}
    for module in (models_module, curves_module, engine_module):
        source = inspect.getsource(module)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] not in forbidden_roots for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module is None or node.module.split(".")[0] not in forbidden_roots
                assert node.module != "simulation.monte_carlo"
