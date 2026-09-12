"""Tests for deterministic time-curve progress functions."""

import math
from typing import get_args

import pytest

from simulation.curves import CURVE_FUNCTIONS, UnknownTimeCurveError, progress
from simulation.models import CURVES_WITHOUT_DELAY, TimeCurveType


ALL_CURVE_NAMES = get_args(TimeCurveType)
DELAY_ACCEPTING_CURVE_NAMES = tuple(curve for curve in ALL_CURVE_NAMES if curve not in CURVES_WITHOUT_DELAY)
ARBITRARY_FIXTURE_TIME_SCALE_DAYS = 30.0
ARBITRARY_FIXTURE_DELAY_DAYS = 11.0


def day_sweep():
    """Return integer days from 0 through 180 inclusive."""

    return range(181)


def curve_values(curve, delay_days=0.0, time_scale_days=ARBITRARY_FIXTURE_TIME_SCALE_DAYS):
    return [progress(curve, day, delay_days, time_scale_days) for day in day_sweep()]


def assert_unit_interval(values):
    assert all(0.0 <= value <= 1.0 for value in values)


def assert_monotone(values, curve):
    for index, (current, following) in enumerate(zip(values, values[1:])):
        assert following >= current, f"{curve} decreased between sweep indices {index} and {index + 1}: {current} -> {following}"


# --- registry / dispatch drift guards ---------------------------------------

def test_curve_registry_matches_declared_names():
    """This makes it impossible to add a Literal curve without implementing it."""

    assert set(CURVE_FUNCTIONS) == set(get_args(TimeCurveType))


@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
def test_every_declared_curve_is_dispatchable(curve):
    value = progress(curve, 15.0, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)

    assert isinstance(value, float)
    assert 0.0 <= value <= 1.0


def test_unknown_curve_raises_value_error_subclass():
    with pytest.raises(ValueError) as excinfo:
        progress("unknown", 15.0, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)

    assert isinstance(excinfo.value, UnknownTimeCurveError)


# --- the delay gate ---------------------------------------------------------

@pytest.mark.parametrize("curve", DELAY_ACCEPTING_CURVE_NAMES)
@pytest.mark.parametrize("t_days", [0.0, 1.0, ARBITRARY_FIXTURE_DELAY_DAYS / 2, ARBITRARY_FIXTURE_DELAY_DAYS])
def test_delay_accepting_curves_are_zero_through_gate(curve, t_days):
    assert progress(curve, t_days, ARBITRARY_FIXTURE_DELAY_DAYS, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) == 0.0


def test_zero_delay_linear_is_zero_at_time_zero():
    assert progress("linear", 0.0, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) == 0.0


@pytest.mark.parametrize("curve", DELAY_ACCEPTING_CURVE_NAMES)
def test_progress_is_nearly_zero_just_after_gate(curve):
    """This fails if logistic is not renormalised: a raw logistic is about 0.018 at the gate."""

    value = progress(curve, ARBITRARY_FIXTURE_DELAY_DAYS + 1e-9, ARBITRARY_FIXTURE_DELAY_DAYS, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)

    assert value < 1e-6


@pytest.mark.parametrize("curve", DELAY_ACCEPTING_CURVE_NAMES)
def test_shifting_time_and_delay_preserves_progress(curve):
    elapsed_days = 17.25
    unshifted = progress(curve, elapsed_days, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)
    shifted = progress(curve, elapsed_days + ARBITRARY_FIXTURE_DELAY_DAYS, ARBITRARY_FIXTURE_DELAY_DAYS, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)

    assert shifted == pytest.approx(unshifted)


def test_linear_rejects_nonzero_delay():
    with pytest.raises(ValueError):
        progress("linear", 20.0, ARBITRARY_FIXTURE_DELAY_DAYS, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)


# --- range and monotonicity, swept ------------------------------------------

@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
def test_sweep_stays_in_unit_interval(curve):
    assert_unit_interval(curve_values(curve))


@pytest.mark.parametrize("curve, delay_days", [(curve, 0.0) for curve in ALL_CURVE_NAMES] + [(curve, ARBITRARY_FIXTURE_DELAY_DAYS) for curve in DELAY_ACCEPTING_CURVE_NAMES])
def test_sweep_is_monotone(curve, delay_days):
    assert_monotone(curve_values(curve, delay_days), curve)


@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
@pytest.mark.parametrize("t_days", [1e6, 1e12])
def test_absurdly_large_times_never_exceed_one(curve, t_days):
    """Use <= because exp underflow lets saturating curves equal 1.0 in doubles."""

    assert progress(curve, t_days, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) <= 1.0


@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
@pytest.mark.parametrize("time_scale_days", [0.5, 1.0, 30.0, 365.0, 730.0])
def test_range_and_monotonicity_hold_across_time_scales(curve, time_scale_days):
    values = curve_values(curve, time_scale_days=time_scale_days)

    assert_unit_interval(values)
    assert_monotone(values, curve)


# --- shape identities -------------------------------------------------------

def test_linear_shapes_agree_without_delay():
    """The two names share one shape by design; this documents that fact rather than leaving it accidental."""

    assert curve_values("linear") == curve_values("delayed_linear")


def test_linear_reaches_and_stays_at_one():
    assert progress("linear", ARBITRARY_FIXTURE_TIME_SCALE_DAYS, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) == 1.0
    assert progress("linear", ARBITRARY_FIXTURE_TIME_SCALE_DAYS + 1.0, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) == 1.0
    assert progress("linear", 1e6, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) == 1.0


def test_exponential_strictly_increases_toward_asymptote():
    """A saturating curve approaches its asymptote without reaching it before floating-point underflow."""

    values = curve_values("exponential")

    assert all(following > current for current, following in zip(values, values[1:]))
    assert all(value < 1.0 for value in values)


def test_logistic_and_exponential_have_distinct_increment_shapes():
    """This mathematical difference between saturation and sigmoid catches a wrong sign or bad renormalisation."""

    step_days = ARBITRARY_FIXTURE_TIME_SCALE_DAYS / 100
    times = [index * step_days for index in range(201)]
    exponential_values = [progress("exponential", t_days, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) for t_days in times]
    logistic_values = [progress("logistic", t_days, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) for t_days in times]
    exponential_increments = [following - current for current, following in zip(exponential_values, exponential_values[1:])]
    logistic_increments = [following - current for current, following in zip(logistic_values, logistic_values[1:])]

    assert exponential_increments.index(max(exponential_increments)) == 0
    logistic_peak_index = logistic_increments.index(max(logistic_increments))
    assert 0 < logistic_peak_index < len(logistic_increments) - 1


# --- representative values -------------------------------------------------

# Computed independently of the implementation; these are pure mathematics, not medical claims.
@pytest.mark.parametrize("curve, ratio, expected", [
    ("linear", 0.5, 0.500000),
    ("linear", 1.0, 1.000000),
    ("linear", 2.0, 1.000000),
    ("exponential", 0.25, 0.221199),
    ("exponential", 0.5, 0.393469),
    ("exponential", 1.0, 0.632121),
    ("exponential", 2.0, 0.864665),
    ("exponential", 3.0, 0.950213),
    ("logistic", 0.25, 0.029979),
    ("logistic", 0.5, 0.103071),
    ("logistic", 1.0, 0.490842),
    ("logistic", 2.0, 0.981684),
    ("logistic", 3.0, 0.999659),
])
def test_representative_values(curve, ratio, expected):
    t_days = ratio * ARBITRARY_FIXTURE_TIME_SCALE_DAYS

    assert progress(curve, t_days, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) == pytest.approx(expected, abs=1e-6)


def test_logistic_renormalised_midpoint_is_below_half():
    """Subtracting the initial constant shifts the halfway crossing slightly later than the raw logistic midpoint."""

    value = progress("logistic", ARBITRARY_FIXTURE_TIME_SCALE_DAYS, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)

    assert value < 0.5
    assert value == pytest.approx(0.490842, abs=1e-6)


@pytest.mark.parametrize("ratio, expected", [(0.25, 0.029979), (1.0, 0.490842), (2.0, 0.981684)])
def test_representative_ratios_are_relative_to_delay_gate(ratio, expected):
    t_days = ARBITRARY_FIXTURE_DELAY_DAYS + ratio * ARBITRARY_FIXTURE_TIME_SCALE_DAYS

    assert progress("logistic", t_days, ARBITRARY_FIXTURE_DELAY_DAYS, ARBITRARY_FIXTURE_TIME_SCALE_DAYS) == pytest.approx(expected, abs=1e-6)


# --- floating point ---------------------------------------------------------

def test_exponential_preserves_tiny_positive_progress():
    """Naive 1 - exp(-x) cancels to zero here; expm1 preserves the 1e-18 result."""

    assert progress("exponential", 1e-18, 0.0, 1.0) > 0.0


@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
def test_sweep_never_returns_nan(curve):
    assert all(not math.isnan(value) for value in curve_values(curve))


@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
def test_identical_calls_are_bit_identical(curve):
    """Purity is what makes seeded reproducibility possible for later Monte Carlo work."""

    first = progress(curve, 47.25, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)
    second = progress(curve, 47.25, 0.0, ARBITRARY_FIXTURE_TIME_SCALE_DAYS)

    assert first == second
    assert repr(first) == repr(second)


# --- input validation -------------------------------------------------------

@pytest.mark.parametrize("curve", ALL_CURVE_NAMES)
@pytest.mark.parametrize("t_days, delay_days, time_scale_days", [
    (-1.0, 0.0, 1.0),
    (0.0, -1.0, 1.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, -1.0),
    (float("nan"), 0.0, 1.0),
    (float("inf"), 0.0, 1.0),
    (0.0, float("nan"), 1.0),
    (0.0, float("inf"), 1.0),
    (0.0, 0.0, float("nan")),
    (0.0, 0.0, float("inf")),
])
def test_invalid_numeric_inputs_raise_value_error(curve, t_days, delay_days, time_scale_days):
    """NaN defeats ordinary bound checks because every comparison is false, so finiteness must be explicit."""

    with pytest.raises(ValueError):
        progress(curve, t_days, delay_days, time_scale_days)
