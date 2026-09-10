"""Tests for the simulation domain model."""

import pytest

from pydantic import ValidationError

from schemas import SkinProfileRequest
from simulation.models import (
    SKIN_METRIC_NAMES,
    PatientResponse,
    SimulationConfig,
    SkinState,
    TimeCurveType,
    TreatmentEffect,
    TreatmentParameters,
)


def valid_state_kwargs(**overrides):
    """A valid SkinState keyword dict, with optional field overrides."""

    kwargs = {metric: 5.0 for metric in SKIN_METRIC_NAMES}
    kwargs.update(overrides)
    return kwargs


def valid_effect(**overrides):
    kwargs = dict(
        target_metric="inflammatory_acne",
        effect_kind="therapeutic",
        direction="decrease",
        delay_days=14,
        mean_magnitude=3.0,
        uncertainty=0.8,
        time_curve="logistic",
    )

    kwargs.update(overrides)
    return kwargs


# --- the drift guards -------------------------------------------------------

def test_metric_names_match_skin_state_fields():
    assert set(SKIN_METRIC_NAMES) == set(SkinState.model_fields)


def test_metric_names_match_profile_request_schema():
    """SkinProfileRequest is name/age/gender plus exactly the skin metrics.

    If a metric is added to schemas.py and not here (or vice versa), this
    fails and names the offending field, instead of the simulation quietly
    ignoring a metric the user can score.
    """

    non_metric_fields = {"name", "age", "gender"}
    profile_metrics = (
        set(SkinProfileRequest.model_fields) - non_metric_fields
    )

    assert profile_metrics == set(SKIN_METRIC_NAMES)


# --- SkinState --------------------------------------------------------------

def test_skin_state_coerces_ints_to_floats():
    state = SkinState(**valid_state_kwargs(redness=7))

    assert state.redness == 7.0
    assert isinstance(state.redness, float)


@pytest.mark.parametrize("metric", SKIN_METRIC_NAMES)
@pytest.mark.parametrize("bad_value", [-0.1, -1, 10.1, 11])
def test_skin_state_rejects_out_of_range(metric, bad_value):
    """The [0, 10] invariant holds for every metric, not just the ones we
    happened to think of.
    """

    with pytest.raises(ValidationError):
        SkinState(**valid_state_kwargs(**{metric: bad_value}))


@pytest.mark.parametrize("boundary", [0, 10])
def test_skin_state_accepts_boundaries(boundary):
    SkinState(**valid_state_kwargs(redness=boundary))


def test_skin_state_rejects_unknown_field():
    with pytest.raises(ValidationError):
        SkinState(**valid_state_kwargs(rednes=5.0))


def test_skin_state_json_round_trips():
    """The engine's output has to survive the trip to the browser on Day 15."""

    state = SkinState(**valid_state_kwargs(redness=6.8137))

    assert (SkinState.model_validate_json(state.model_dump_json()) == state)


# --- TreatmentEffect --------------------------------------------------------

def test_effect_rejects_misspelled_metric():
    with pytest.raises(ValidationError):
        TreatmentEffect(**valid_effect(target_metric="reddness"))


def test_effect_rejects_negative_magnitude():
    """direction carries the sign; a negative magnitude is a contradiction."""

    with pytest.raises(ValidationError):
        TreatmentEffect(**valid_effect(mean_magnitude=-3.0))


def test_effect_rejects_unknown_curve():
    with pytest.raises(ValidationError):
        TreatmentEffect(**valid_effect(time_curve="sigmoid"))


@pytest.mark.parametrize("curve", TimeCurveType.__args__)
def test_every_declared_curve_is_constructible(curve):
    """Sweeping the Literal means adding a curve name to the type without
    implementing it on Day 9 will surface here rather than at runtime.
    """

    assert (
        TreatmentEffect(
            **valid_effect(time_curve=curve)
        ).time_curve
        == curve
    )


# --- TreatmentParameters ----------------------------------------------------

@pytest.mark.parametrize("bad_id", ["Adapalene", "adapalene gel", "adapalene-0.1", ""],)
def test_treatment_id_must_be_a_slug(bad_id):
    with pytest.raises(ValidationError):
        TreatmentParameters(
            treatment_id=bad_id,
            display_name="x",
            parameter_version="fixture",
            effects=[TreatmentEffect(**valid_effect())],
        )


def test_treatment_requires_at_least_one_effect():
    with pytest.raises(ValidationError):
        TreatmentParameters(
            treatment_id="placebo",
            display_name="x",
            parameter_version="fixture",
            effects=[],
        )


def test_treatment_supports_therapeutic_and_side_effects_together():
    """The design claim from Step 3: both kinds are the same shape."""

    treatment = TreatmentParameters(
        treatment_id="fixture_retinoid",
        display_name="FIXTURE retinoid (NOT MEDICAL)",
        parameter_version="fixture",
        effects=[
            TreatmentEffect(**valid_effect()),
            TreatmentEffect(
                **valid_effect(
                    target_metric="dryness",
                    effect_kind="side_effect",
                    direction="increase",
                    delay_days=3,
                    mean_magnitude=1.5,
                    time_curve="exponential",
                )
            ),
        ],
    )

    assert {e.effect_kind for e in treatment.effects} == {"therapeutic", "side_effect"}


# --- PatientResponse / SimulationConfig -------------------------------------

@pytest.mark.parametrize("bad", [0, -0.5])
def test_response_multiplier_must_be_positive(bad):
    with pytest.raises(ValidationError):
        PatientResponse(response_multiplier=bad, side_effect_multiplier=1.0,)


def test_config_defaults():
    config = SimulationConfig(duration_days=90)

    assert (
        config.time_step_days,
        config.n_trials,
        config.random_seed,
    ) == (1, 1, None)


def test_config_caps_trial_count():
    """The cost bound that protects POST /simulations on Day 14."""

    with pytest.raises(ValidationError):
        SimulationConfig(duration_days=90, n_trials=10_000_000,)