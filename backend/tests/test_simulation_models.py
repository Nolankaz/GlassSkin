"""Tests for the simulation domain model."""

from typing import get_args

import pytest

from pydantic import ValidationError

from schemas import SkinProfileRequest
from simulation.models import (
    CURVES_WITHOUT_DELAY,
    FIXTURE_PROVENANCE,
    SKIN_METRIC_NAMES,
    MonteCarloResult,
    PatientResponse,
    PercentileBand,
    Provenance,
    SimulationConfig,
    SkinState,
    TimeCurveType,
    Trajectory,
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
        time_scale_days=90.0,
        time_curve="logistic",
        provenance=FIXTURE_PROVENANCE,
    )

    kwargs.update(overrides)
    return kwargs


def valid_provenance(**overrides):
    kwargs = dict(kind="published", source_url="https://example.org/study", citation="Example citation", reported_figure="Example reported value", derivation="Example conversion for test")
    kwargs.update(overrides)
    return kwargs


def valid_trajectory_kwargs(**overrides):
    kwargs = dict(
        treatment_id="fixture_treatment",
        parameter_version="fixture",
        patient_response=PatientResponse(response_multiplier=1.0, side_effect_multiplier=1.0),
        times_days=[0.0, 1.0, 2.0],
        states=[SkinState(**valid_state_kwargs()) for _ in range(3)],
    )

    kwargs.update(overrides)
    return kwargs


def valid_band_kwargs(length, **overrides):
    kwargs = {"p10": [4.0] * length, "p50": [5.0] * length, "p90": [6.0] * length}
    kwargs.update(overrides)
    return kwargs


def valid_monte_carlo_result_kwargs(**overrides):
    kwargs = dict(
        treatment_id="fixture_treatment",
        parameter_version="fixture",
        n_trials=10_000,
        random_seed=42,
        times_days=[0.0, 1.0, 2.0],
        bands={metric: PercentileBand(**valid_band_kwargs(3)) for metric in SKIN_METRIC_NAMES},
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


def test_curves_without_delay_are_declared_curve_names():
    assert set(CURVES_WITHOUT_DELAY) <= set(get_args(TimeCurveType))


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


# --- Provenance -------------------------------------------------------------

def test_published_provenance_constructs():
    provenance = Provenance(**valid_provenance())

    assert provenance.kind == "published"
    assert provenance.source_url == "https://example.org/study"


def test_fixture_provenance_constructs():
    provenance = Provenance(kind="fixture", source_url="", citation="Test fixture — NOT MEDICAL", reported_figure="none", derivation="arbitrary test value")

    assert provenance.kind == "fixture"


def test_shared_fixture_provenance_is_marked_non_medical():
    assert FIXTURE_PROVENANCE.kind == "fixture"
    assert "NOT MEDICAL" in FIXTURE_PROVENANCE.citation


@pytest.mark.parametrize("source_url", ["http://example.org/study", "", "ftp://example.org/study"])
def test_published_provenance_requires_https_source_url(source_url):
    with pytest.raises(ValidationError, match="source_url"):
        Provenance(**valid_provenance(source_url=source_url))


@pytest.mark.parametrize("field", ["citation", "reported_figure", "derivation"])
def test_published_provenance_rejects_whitespace_only_text(field):
    with pytest.raises(ValidationError, match=field):
        Provenance(**valid_provenance(**{field: "   "}))


def test_fixture_provenance_rejects_nonempty_source_url():
    with pytest.raises(ValidationError, match="source_url"):
        Provenance(**valid_provenance(kind="fixture", source_url="https://example.org/study", citation="FIXTURE — NOT MEDICAL"))


def test_fixture_provenance_requires_not_medical_citation():
    with pytest.raises(ValidationError, match="citation"):
        Provenance(**valid_provenance(kind="fixture", source_url="", citation="Test fixture"))


def test_provenance_rejects_unknown_kind():
    with pytest.raises(ValidationError, match="kind"):
        Provenance(**valid_provenance(kind="unknown"))


def test_provenance_rejects_extra_field():
    with pytest.raises(ValidationError, match="unexpected"):
        Provenance(**valid_provenance(unexpected="value"))


def test_shared_fixture_provenance_is_frozen():
    with pytest.raises(ValidationError, match="frozen"):
        FIXTURE_PROVENANCE.citation = "changed"


# --- TreatmentEffect --------------------------------------------------------

def test_effect_requires_provenance():
    kwargs = valid_effect()
    del kwargs["provenance"]

    with pytest.raises(ValidationError, match="provenance"):
        TreatmentEffect(**kwargs)


def test_effect_json_round_trip_preserves_provenance():
    provenance = Provenance(**valid_provenance())
    effect = TreatmentEffect(**valid_effect(provenance=provenance))

    restored = TreatmentEffect.model_validate_json(effect.model_dump_json())
    assert restored == effect
    assert restored.provenance == provenance


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


def test_effect_requires_time_scale_days():
    kwargs = valid_effect()
    del kwargs["time_scale_days"]

    with pytest.raises(ValidationError):
        TreatmentEffect(**kwargs)


@pytest.mark.parametrize("time_scale_days", [0, -0.1, -1])
def test_effect_rejects_non_positive_time_scale_days(time_scale_days):
    with pytest.raises(ValidationError):
        TreatmentEffect(**valid_effect(time_scale_days=time_scale_days))


def test_effect_rejects_time_scale_days_above_730():
    with pytest.raises(ValidationError):
        TreatmentEffect(**valid_effect(time_scale_days=730.1))


def test_effect_coerces_integer_time_scale_days_to_float():
    effect = TreatmentEffect(**valid_effect(time_scale_days=90))

    assert effect.time_scale_days == 90.0
    assert isinstance(effect.time_scale_days, float)


def test_linear_effect_accepts_zero_delay():
    assert TreatmentEffect(**valid_effect(time_curve="linear", delay_days=0)).delay_days == 0


def test_linear_effect_rejects_nonzero_delay():
    with pytest.raises(ValidationError, match="linear.*delayed_linear"):
        TreatmentEffect(**valid_effect(time_curve="linear", delay_days=1))


@pytest.mark.parametrize("curve", tuple(curve for curve in get_args(TimeCurveType) if curve not in CURVES_WITHOUT_DELAY))
def test_delay_accepting_effect_curves_accept_nonzero_delay(curve):
    assert TreatmentEffect(**valid_effect(time_curve=curve, delay_days=14)).delay_days == 14


@pytest.mark.parametrize("curve", get_args(TimeCurveType))
def test_every_declared_curve_is_constructible(curve):
    """Sweeping the Literal means adding a curve name to the type without
    implementing it on Day 9 will surface here rather than at runtime.
    """

    assert (
        TreatmentEffect(
            **valid_effect(time_curve=curve, delay_days=0 if curve in CURVES_WITHOUT_DELAY else 14, provenance=FIXTURE_PROVENANCE)
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
                    provenance=FIXTURE_PROVENANCE,
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


@pytest.mark.parametrize("field", ["response_multiplier", "side_effect_multiplier"])
@pytest.mark.parametrize("bad_value", [float("inf"), float("-inf"), float("nan")])
def test_patient_response_rejects_non_finite_multipliers(field, bad_value):
    kwargs = {"response_multiplier": 1.0, "side_effect_multiplier": 1.0, field: bad_value}

    with pytest.raises(ValidationError):
        PatientResponse(**kwargs)


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


# --- Trajectory -------------------------------------------------------------

def test_valid_trajectory_constructs():
    trajectory = Trajectory(**valid_trajectory_kwargs())

    assert trajectory.times_days == [0.0, 1.0, 2.0]


@pytest.mark.parametrize(
    ("times_days", "state_count"),
    [([0.0, 1.0, 2.0], 2), ([0.0, 1.0], 3)],
)
def test_trajectory_rejects_mismatched_lengths(times_days, state_count):
    states = [SkinState(**valid_state_kwargs()) for _ in range(state_count)]

    with pytest.raises(ValidationError):
        Trajectory(**valid_trajectory_kwargs(times_days=times_days, states=states))


def test_trajectory_rejects_one_point():
    states = [SkinState(**valid_state_kwargs())]

    with pytest.raises(ValidationError):
        Trajectory(**valid_trajectory_kwargs(times_days=[0.0], states=states))


def test_trajectory_must_start_at_zero():
    with pytest.raises(ValidationError):
        Trajectory(**valid_trajectory_kwargs(times_days=[1.0, 2.0, 3.0]))


def test_trajectory_rejects_repeated_time():
    with pytest.raises(ValidationError):
        Trajectory(**valid_trajectory_kwargs(times_days=[0.0, 1.0, 1.0]))


def test_trajectory_rejects_decreasing_time():
    with pytest.raises(ValidationError):
        Trajectory(**valid_trajectory_kwargs(times_days=[0.0, 2.0, 1.0]))


def test_trajectory_rejects_nan_time():
    with pytest.raises(ValidationError):
        Trajectory(**valid_trajectory_kwargs(times_days=[0.0, float("nan"), 2.0]))


def test_trajectory_rejects_unknown_field():
    with pytest.raises(ValidationError):
        Trajectory(**valid_trajectory_kwargs(unknown="value"))


def test_trajectory_json_round_trips():
    """This matches the trajectory shape that Day 14 stores and Day 15 renders."""

    trajectory = Trajectory(**valid_trajectory_kwargs())

    assert Trajectory.model_validate_json(trajectory.model_dump_json()) == trajectory


def test_trajectory_metric_series_returns_values_in_order():
    states = [SkinState(**valid_state_kwargs(redness=redness)) for redness in (2.0, 4.5, 7.0)]
    trajectory = Trajectory(**valid_trajectory_kwargs(states=states))

    assert trajectory.metric_series("redness") == [2.0, 4.5, 7.0]


def test_trajectory_metric_series_rejects_unknown_metric():
    trajectory = Trajectory(**valid_trajectory_kwargs())

    with pytest.raises(ValueError):
        trajectory.metric_series("reddness")


# --- PercentileBand ---------------------------------------------------------

def test_valid_percentile_band_constructs():
    band = PercentileBand(**valid_band_kwargs(3))

    assert band.p50 == [5.0, 5.0, 5.0]


def test_percentile_band_rejects_unequal_lengths():
    with pytest.raises(ValidationError, match=r"p10=3, p50=2, p90=1"):
        PercentileBand(**valid_band_kwargs(3, p50=[5.0, 5.0], p90=[6.0]))


def test_percentile_band_rejects_p10_above_p50():
    with pytest.raises(ValidationError, match="index 1"):
        PercentileBand(**valid_band_kwargs(3, p10=[4.0, 5.5, 4.0]))


def test_percentile_band_rejects_p50_above_p90():
    with pytest.raises(ValidationError, match="index 1"):
        PercentileBand(**valid_band_kwargs(3, p50=[5.0, 6.5, 5.0]))


def test_percentile_band_allows_equal_values():
    band = PercentileBand(p10=[5.0, 5.0], p50=[5.0, 5.0], p90=[5.0, 5.0])

    assert band.p10 == band.p50 == band.p90


@pytest.mark.parametrize("bad_value", [10.5, -0.5, float("nan"), float("inf")])
def test_percentile_band_rejects_invalid_values(bad_value):
    with pytest.raises(ValidationError):
        PercentileBand(**valid_band_kwargs(3, p50=[5.0, bad_value, 5.0]))


def test_percentile_band_rejects_unknown_field():
    with pytest.raises(ValidationError):
        PercentileBand(**valid_band_kwargs(3), unknown="value")


# --- MonteCarloResult -------------------------------------------------------

def test_valid_monte_carlo_result_constructs():
    result = MonteCarloResult(**valid_monte_carlo_result_kwargs())

    assert result.n_trials == 10_000


def test_monte_carlo_result_rejects_missing_metric():
    bands = valid_monte_carlo_result_kwargs()["bands"]
    del bands["redness"]

    with pytest.raises(ValidationError, match="redness"):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(bands=bands))


def test_monte_carlo_result_rejects_unknown_metric():
    bands = valid_monte_carlo_result_kwargs()["bands"]
    bands["reddness"] = PercentileBand(**valid_band_kwargs(3))

    with pytest.raises(ValidationError):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(bands=bands))


def test_monte_carlo_result_rejects_short_band():
    bands = valid_monte_carlo_result_kwargs()["bands"]
    bands["redness"] = PercentileBand(**valid_band_kwargs(2))

    with pytest.raises(ValidationError, match=r"redness.*got 2"):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(bands=bands))


def test_monte_carlo_result_must_start_at_zero():
    with pytest.raises(ValidationError):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(times_days=[1.0, 2.0, 3.0]))


def test_monte_carlo_result_rejects_repeated_time():
    with pytest.raises(ValidationError):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(times_days=[0.0, 1.0, 1.0]))


def test_monte_carlo_result_rejects_zero_trials():
    with pytest.raises(ValidationError):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(n_trials=0))


def test_monte_carlo_result_rejects_none_seed():
    with pytest.raises(ValidationError):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(random_seed=None))


def test_monte_carlo_result_rejects_negative_seed():
    with pytest.raises(ValidationError):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(random_seed=-1))


def test_monte_carlo_result_rejects_unknown_field():
    with pytest.raises(ValidationError):
        MonteCarloResult(**valid_monte_carlo_result_kwargs(unknown="value"))


def test_monte_carlo_result_json_round_trips():
    """This is the shape later API/persistence and plotting code will use."""

    result = MonteCarloResult(**valid_monte_carlo_result_kwargs())

    assert MonteCarloResult.model_validate_json(result.model_dump_json()) == result


def test_monte_carlo_result_metric_band_returns_band():
    result = MonteCarloResult(**valid_monte_carlo_result_kwargs())

    assert result.metric_band("redness") == result.bands["redness"]


def test_monte_carlo_result_metric_band_rejects_unknown_metric():
    result = MonteCarloResult(**valid_monte_carlo_result_kwargs())

    with pytest.raises(ValueError):
        result.metric_band("reddness")
