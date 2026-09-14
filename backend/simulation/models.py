"""Domain model for the GlassSkinAI treatment simulation.

Everything in this module is a pure data definition: no I/O, no environment
variables, no database. Given the same inputs it behaves the same way, which
is what makes the simulation testable without mocking anything.

Nothing here holds medical values. Real treatment parameters arrive on Day 12
with a documented source per number; until then, any parameters used for
testing are named FIXTURE_* and marked NOT MEDICAL.
"""

from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator


# The 17 skin metrics, in the same order and with the same spelling as
# SkinProfileRequest in schemas.py and the skin_profiles table.
# A test in tests/test_simulation_models.py asserts that correspondence, so
# this list cannot drift away from the rest of the system unnoticed.
SkinMetricName = Literal[
    "inflammatory_acne",
    "cystic_nodular_acne",
    "blackheads",
    "whiteheads",
    "pie",
    "pih",
    "redness",
    "rosacea",
    "dryness",
    "sensitivity",
    "irritation",
    "oiliness",
    "texture_irregularity",
    "acne_scarring",
    "enlarged_pores",
    "dark_circles",
    "uneven_skin_tone",
]

# get_args() pulls the strings back out of the Literal at runtime, so the
# type annotation and the iterable list are the same single source of truth.
SKIN_METRIC_NAMES: tuple[str, ...] = get_args(SkinMetricName)

# Every skin metric lives in [0, 10]. This is the engine's core invariant:
# no arithmetic anywhere is allowed to produce a state outside this range.
METRIC_MIN = 0.0
METRIC_MAX = 10.0


class SkinState(BaseModel):
    """Skin at one instant in a simulation. S(t) in the engine's notation."""

    model_config = {"extra": "forbid"}

    inflammatory_acne: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    cystic_nodular_acne: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    blackheads: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    whiteheads: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    pie: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    pih: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    redness: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    rosacea: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    dryness: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    sensitivity: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    irritation: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    oiliness: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    texture_irregularity: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    acne_scarring: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    enlarged_pores: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    dark_circles: float = Field(ge=METRIC_MIN, le=METRIC_MAX)
    uneven_skin_tone: float = Field(ge=METRIC_MIN, le=METRIC_MAX)


# How an effect's magnitude grows with time; this is only the set of allowed names.
TimeCurveType = Literal[
    "linear",           # constant rate until full effect
    "delayed_linear",   # nothing until delay_days, then constant rate
    "exponential",      # fast early, diminishing returns: 1 - exp(-kt)
    "logistic",         # slow, then fast, then plateau (sigmoid)
]

# These curve names mean "no latency", so pairing them with a non-zero
# delay_days is a contradiction rather than a variation. The model validator
# below and progress() in curves.py both read this tuple so the rule has one
# definition. delayed_linear has the same arithmetic shape as linear and is
# the name to use when a treatment does have a latency.
CURVES_WITHOUT_DELAY: tuple[TimeCurveType, ...] = ("linear",)

# Which way this effect pushes its metric. Note that "decrease" is not a
# synonym for "good": decreasing oiliness helps oily skin and harms dry skin.
# The engine models arithmetic direction; whether it is desirable is a
# product-layer judgement made against the user's own profile.
EffectDirection = Literal["increase", "decrease"]

# Whether this effect is the reason to take the treatment, or the price of
# taking it. This is a label for the UI and for scoring on Day 18; the engine
# applies both kinds identically.
EffectKind = Literal["therapeutic", "side_effect"]


class TreatmentEffect(BaseModel):
    """One treatment's influence on exactly one skin metric."""

    model_config = {"extra": "forbid"}

    target_metric: SkinMetricName
    effect_kind: EffectKind
    direction: EffectDirection

    # Days before the effect begins to appear at all.
    delay_days: int = Field(ge=0, le=365)

    # Full magnitude in metric points, on the 0-10 scale, for a patient whose
    # response multiplier is exactly 1.0. Always positive -- `direction`
    # carries the sign, so a negative value here would be a contradiction the
    # model should not be able to express.
    mean_magnitude: float = Field(gt=0, le=10)

    # Spread of individual response around mean_magnitude; it is a slot with a validated range.
    uncertainty: float = Field(ge=0, le=5)

    # The curve's characteristic duration, measured from the end of the delay;
    # its exact meaning depends on the curve. For linear and delayed_linear it
    # is the number of days to reach full effect. For exponential it is the
    # time constant, when about 63% of the full effect has appeared. For
    # logistic it is the sigmoid's midpoint, when about 49% has appeared.
    # le=730 matches SimulationConfig.duration_days: a time scale longer than
    # the longest simulatable run describes an effect that never meaningfully
    # appears. This field is deliberately required with no default because a
    # default would be a treatment parameter invented by omission.
    time_scale_days: float = Field(gt=0, le=730)

    time_curve: TimeCurveType

    @model_validator(mode="after")
    def validate_time_curve_delay(self):
        """Reject a contradictory time-curve and delay combination.

        Field constraints validate one field in isolation and cannot express a
        contradictory combination; an after-validator sees the whole model.
        Raising ValueError here is the documented contract; Pydantic wraps it
        into ValidationError.
        """

        if self.time_curve in CURVES_WITHOUT_DELAY and self.delay_days > 0:
            raise ValueError(f"{self.time_curve} means no latency and requires delay_days == 0; use delayed_linear when a non-zero delay is needed")
        return self


class TreatmentParameters(BaseModel):
    """Everything the engine needs to simulate one treatment."""

    model_config = {"extra": "forbid"}

    # Stable slug: lowercase, digits and underscores only. This is the key
    # that is matched against free-text AI research output, and that
    # is accepted as an API parameter, so it must be URL-safe and stable.
    treatment_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
    )

    display_name: str = Field(min_length=1, max_length=120)

    # Which calibration produced these numbers. Same idea as RESEARCH_VERSION
    # in services/treatment_research.py: bump it when the methodology changes
    # so old cached simulation runs stop being served without being deleted.
    parameter_version: str = Field(min_length=1, max_length=16)

    effects: list[TreatmentEffect] = Field(min_length=1, max_length=20)


class PatientResponse(BaseModel):
    """How strongly one simulated individual responds, relative to the mean.

    Multipliers, not offsets: 1.0 is an average responder, 1.4 is a strong
    responder, 0.6 a weak one. Multiplicative because response scales with
    effect size -- a strong responder gets more out of a strong treatment --
    and because the scale is inherently non-negative.

    These will be sampled per trial. This only fixes the representation; it
    does not choose the distribution.
    """

    model_config = {"extra": "forbid", "allow_inf_nan": False}

    # gt=0: a negative multiplier would mean the treatment does the opposite
    # of what it does, which is a different model, not a variant of this one.
    response_multiplier: float = Field(gt=0)
    side_effect_multiplier: float = Field(gt=0)


class SimulationConfig(BaseModel):
    """Run settings: how long, how finely, how many trials, and reproducibly."""

    model_config = {"extra": "forbid"}

    duration_days: int = Field(gt=0, le=730)
    time_step_days: int = Field(default=1, gt=0, le=30)
    n_trials: int = Field(default=1, ge=1, le=50_000)

    # Fixing the seed makes a randomised run reproducible: same inputs plus
    # same seed gives the same numbers every time. That is what lets a
    # Monte Carlo result be asserted in a test, and what lets it compare
    # treatments under identical noise instead of noise plus treatment.
    random_seed: int | None = None


class SimulationRequest(BaseModel):
    """
    Everything the engine needs for one run.
    Becomes the POST /simulations request body.
    """

    model_config = {"extra": "forbid"}

    initial_state: SkinState
    treatment: TreatmentParameters
    config: SimulationConfig

    # A deterministic single run is given one explicit response;
    # a Monte Carlo run leaves it None and the engine samples one per trial.
    patient_response: PatientResponse | None = None


class Trajectory(BaseModel):
    """One deterministic simulated trajectory produced by simulation.engine.simulate.

    states[i] corresponds to times_days[i], and states[0] is the initial skin
    state. Later Monte Carlo work will aggregate many simulated paths rather
    than storing thousands of these Pydantic objects.
    """

    model_config = {"extra": "forbid", "allow_inf_nan": False}

    treatment_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    parameter_version: str = Field(min_length=1, max_length=16)
    patient_response: PatientResponse
    times_days: list[float] = Field(min_length=2)
    states: list[SkinState] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_structure(self):
        if len(self.times_days) != len(self.states):
            raise ValueError(f"times_days and states must have equal lengths; got {len(self.times_days)} times and {len(self.states)} states")
        if self.times_days[0] != 0.0:
            raise ValueError("times_days[0] must be 0.0 so the trajectory begins at treatment start")
        for index in range(1, len(self.times_days)):
            if self.times_days[index] <= self.times_days[index - 1]:
                raise ValueError(f"times_days must be strictly increasing; violation at index {index}")
        return self

    def metric_series(self, metric: SkinMetricName) -> list[float]:
        if metric not in SKIN_METRIC_NAMES:
            raise ValueError(f"unknown skin metric: {metric}")
        return [getattr(state, metric) for state in self.states]
