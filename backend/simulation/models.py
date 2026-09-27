"""Domain model for the GlassSkinAI treatment simulation.

Everything in this module is a pure data definition: no I/O, no environment
variables, no database. Given the same inputs it behaves the same way, which
is what makes the simulation testable without mocking anything.

Nothing here holds medical values. Real treatment parameters arrive on Day 12
with a documented source per number; until then, any parameters used for
testing are named FIXTURE_* and marked NOT MEDICAL.
"""

from typing import Annotated, Literal, get_args

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
BandValue = Annotated[float, Field(ge=METRIC_MIN, le=METRIC_MAX)]


def _validate_time_axis(times_days: list[float]) -> None:
    if times_days[0] != 0.0:
        raise ValueError("times_days[0] must be 0.0 so the trajectory begins at treatment start")
    for index in range(1, len(times_days)):
        if times_days[index] <= times_days[index - 1]:
            raise ValueError(f"times_days must be strictly increasing; violation at index {index}")


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
# taking it. The kind selects which PatientResponse multiplier the deterministic
# engine uses and which latent response the Monte Carlo layer shares.
EffectKind = Literal["therapeutic", "side_effect"]


ProvenanceKind = Literal["published", "fixture"]


class Provenance(BaseModel):
    """Record where one TreatmentEffect's values came from.

    reported_figure keeps the source's wording and numbers; derivation explains
    how those figures became the effect's model parameters.
    """

    model_config = {"extra": "forbid", "frozen": True}

    kind: ProvenanceKind
    source_url: str = Field(max_length=500)
    citation: str = Field(min_length=1, max_length=300)
    reported_figure: str = Field(min_length=1, max_length=300)
    # Step 5 appends fit diagnostics to the preserved clinical conversion text.
    derivation: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_kind_fields(self):
        if self.kind == "published":
            if not self.source_url.startswith("https://"):
                raise ValueError(f"published source_url must start with https://; got {self.source_url!r}")
            for field in ("citation", "reported_figure", "derivation"):
                value = getattr(self, field)
                if not value.strip():
                    raise ValueError(f"published {field} must not be whitespace-only; got {value!r}")
        elif self.kind == "fixture":
            if self.source_url != "":
                raise ValueError(f"fixture source_url must be empty because fixtures have no published source; got {self.source_url!r}")
            if "NOT MEDICAL" not in self.citation:
                raise ValueError(f"fixture citation must contain 'NOT MEDICAL'; got {self.citation!r}")
        return self


# Legitimate provenance for non-medical test and development fixture values.
FIXTURE_PROVENANCE = Provenance(kind="fixture", source_url="", citation="FIXTURE — NOT MEDICAL", reported_figure="none", derivation="arbitrary fixture value for tests and development plots")

# The fitter reads the same limit when converting response sigma into points.
MAX_EFFECT_UNCERTAINTY = 5.0


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

    # Spread in metric points, like mean_magnitude. Monte Carlo interprets
    # uncertainty / mean_magnitude as the log-scale standard deviation of the
    # response multiplier; 0 means every patient responds at the reference magnitude.
    uncertainty: float = Field(ge=0, le=MAX_EFFECT_UNCERTAINTY)

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
    provenance: Provenance

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

    Multipliers, not offsets: 1.0 is a reference responder, 1.4 is a strong
    responder, 0.6 a weak one. Multiplicative because response scales with
    effect size -- a strong responder gets more out of a strong treatment --
    and because the scale is inherently non-negative.

    Monte Carlo samples a median-1 log-normal response per effect kind per trial,
    so 1.0 / 1.0 is the median/reference responder. The distribution belongs in
    the future simulation/monte_carlo.py implementation.
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
        _validate_time_axis(self.times_days)
        return self

    def metric_series(self, metric: SkinMetricName) -> list[float]:
        if metric not in SKIN_METRIC_NAMES:
            raise ValueError(f"unknown skin metric: {metric}")
        return [getattr(state, metric) for state in self.states]


class PercentileBand(BaseModel):
    """One skin metric's marginal p10/p50/p90 values across time.

    Each list contains one value per time point. These are marginal percentiles,
    so the p50 list is not necessarily one patient's trajectory.
    """

    model_config = {"extra": "forbid", "allow_inf_nan": False}

    p10: list[BandValue]
    p50: list[BandValue]
    p90: list[BandValue]

    @model_validator(mode="after")
    def validate_structure(self):
        lengths = (len(self.p10), len(self.p50), len(self.p90))
        if len(set(lengths)) != 1:
            raise ValueError(f"p10, p50, and p90 must have equal lengths; got p10={lengths[0]}, p50={lengths[1]}, p90={lengths[2]}")
        for index, values in enumerate(zip(self.p10, self.p50, self.p90)):
            if not values[0] <= values[1] <= values[2]:
                raise ValueError(f"percentile values must satisfy p10 <= p50 <= p90; violation at index {index}")
        return self


class MonteCarloResult(BaseModel):
    """Aggregated output of the future simulation.monte_carlo.simulate_many.

    bands[metric].p50[i] is that metric's median across trials at times_days[i].
    Raw trial trajectories are deliberately not stored in this model.
    """

    model_config = {"extra": "forbid", "allow_inf_nan": False}

    treatment_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    parameter_version: str = Field(min_length=1, max_length=16)
    n_trials: int = Field(ge=1)
    random_seed: int = Field(ge=0)
    times_days: list[float] = Field(min_length=2)
    bands: dict[SkinMetricName, PercentileBand]

    @model_validator(mode="after")
    def validate_structure(self):
        _validate_time_axis(self.times_days)
        missing_metrics = [metric for metric in SKIN_METRIC_NAMES if metric not in self.bands]
        if missing_metrics:
            raise ValueError(f"bands must contain every skin metric; missing: {', '.join(missing_metrics)}")
        expected_length = len(self.times_days)
        for metric, band in self.bands.items():
            if len(band.p50) != expected_length:
                raise ValueError(f"band for {metric} must have {expected_length} values to match times_days; got {len(band.p50)}")
        return self

    def metric_band(self, metric: SkinMetricName) -> PercentileBand:
        if metric not in SKIN_METRIC_NAMES:
            raise ValueError(f"unknown skin metric: {metric}")
        return self.bands[metric]
