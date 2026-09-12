# Simulation Design Notes

## Models

### SkinState

`SkinState` represents the condition of the skin at one specific moment in a simulation.

It contains the same 17 skin metrics as the stored skin profile, but the values are floats instead of integers because simulated values can change gradually over time.

Example:

```text
Profile redness: 7

Simulation values over time:
7.0
6.8
6.4
5.9
```

A `SkinProfile` describes the user.

A `SkinState` describes the skin at one point in the simulated timeline.

---

### TreatmentEffect

`TreatmentEffect` represents one effect that a treatment has on one skin metric.

Each effect stores:

- the metric being affected
- whether it is therapeutic or a side effect
- whether the metric increases or decreases
- how long the effect is delayed
- the average magnitude of the effect
- the uncertainty in patient response
- the curve's characteristic duration
- the type of time curve used

Therapeutic effects and side effects use the same model because both are changes to a skin metric.

The characteristic duration is required as `time_scale_days: float = Field(gt=0, le=730)`. It is measured from the end of the delay, and its exact meaning depends on the selected curve. The upper bound matches the longest allowed `SimulationConfig.duration_days`; a longer time scale would describe an effect that never meaningfully appears during a simulatable run.

`time_scale_days` intentionally has no default. A default would silently invent a treatment parameter when the caller omitted one.

---

### TreatmentParameters

`TreatmentParameters` represents the full behavior of one treatment.

It contains:

- a stable treatment ID
- a display name
- a parameter version
- a list of `TreatmentEffect` objects

A treatment can therefore affect several metrics without needing a separate field for every possible skin metric.

---

### PatientResponse

`PatientResponse` represents how strongly one simulated person responds to a treatment.

It contains:

- `response_multiplier`
- `side_effect_multiplier`

A value of `1.0` represents an average response.

Values above `1.0` represent a stronger response, while values below `1.0` represent a weaker response.

This is separate from `TreatmentParameters` because treatment behavior and individual patient response are different concepts.

---

### SimulationConfig

`SimulationConfig` controls how a simulation runs.

It contains:

- simulation duration
- time step size
- number of trials
- optional random seed

The random seed allows a randomized simulation to be reproduced using the same inputs.

---

### SimulationRequest

`SimulationRequest` combines everything needed for one simulation run:

- initial skin state
- treatment parameters
- simulation configuration
- optional patient response

This will later become the input to the simulation engine and eventually the simulation API endpoint.

---

## Time Curves

`progress()` returns the dimensionless fraction of a treatment effect that has appeared at a given time. The result is always in `[0, 1]`.

Progress answers **when** an effect appears, not **how much** the effect is. Magnitude remains a separate `TreatmentEffect` parameter.

The delay gate is applied once inside `progress()`:

```text
u = max(t_days - delay_days, 0)
```

Every curve receives this elapsed time `u`, which makes progress exactly `0.0` for `t_days <= delay_days`. Let `s` mean `time_scale_days`.

| Curve | Formula after the delay gate | Meaning of `time_scale_days` | Value at `u = s` |
| --- | --- | --- | --- |
| `linear` | `min(u / s, 1)` | Days to reach full effect | `1.0` |
| `delayed_linear` | `min(u / s, 1)` | Days after the delay to reach full effect | `1.0` |
| `exponential` | `1 - exp(-u / s)` | Time constant | About `0.632121` |
| `logistic` | `(L(u) - L(0)) / (1 - L(0))` | Sigmoid midpoint and scale | About `0.490842` |

`linear` and `delayed_linear` intentionally share one arithmetic shape. Their names express different latency contracts: `linear` means no latency and rejects a non-zero `delay_days`, while `delayed_linear` is the name for the same shape after a delay.

`CURVES_WITHOUT_DELAY` lives in `models.py` as the single source of truth for that contract. Both the `TreatmentEffect` model validator and the guard in `progress()` read the same tuple.

For the logistic curve, `L(u) = 1 / (1 + exp(-k(u - s)))`, `LOGISTIC_STEEPNESS = 4.0`, and `k = LOGISTIC_STEEPNESS / time_scale_days`. Scaling `k` inversely with the time scale makes the curve scale-free: changing `time_scale_days` stretches or compresses time without changing the normalized shape.

The raw logistic begins at `L(0) ≈ 0.018`. Using it directly would create a visible jump from zero when the delay ends. Subtracting `L(0)` and rescaling by `1 - L(0)` makes progress exactly zero at the gate while preserving monotonicity and the asymptote at `1`.

The exponential implementation uses `-math.expm1(-x)` rather than `1 - math.exp(-x)`. For very small `x`, subtracting two nearly equal floating-point values can cancel to `0.0`; `expm1` preserves the small positive progress value accurately.

At very large elapsed times, floating-point underflow can make a saturating curve return exactly `1.0`. The invariant is therefore `progress <= 1.0`, not `progress < 1.0`.

---

## Core Invariants

The simulation should always obey these rules:

- Every skin metric must remain between `0` and `10`.
- `mean_magnitude` must always be positive.
- `direction` determines whether an effect increases or decreases a metric.
- `SKIN_METRIC_NAMES`, `SkinState`, and the metric fields in `SkinProfileRequest` must always match.
- Progress must always remain in `[0, 1]`.
- Progress must be exactly `0.0` through the delay gate.
- Every time curve must be monotone non-decreasing.
- The curve-function registry must cover `TimeCurveType` exactly.
- Unknown curve names and non-finite inputs must raise instead of producing a progress value.
- Curve functions must be deterministic and pure.
- The simulation package must remain a pure boundary with no FastAPI, Supabase, OpenAI, network, environment, clock, or randomness dependencies.

These rules are enforced through Pydantic validation and automated tests.

---

## Profile to Simulation Boundary

Stored Supabase profiles contain information such as:

```text
id
name
age
gender
created_at
skin metrics
```

The simulation engine should not depend on database-specific fields.

`skin_state_from_profile()` extracts only the 17 skin metrics and converts them into a validated `SkinState`.

This keeps the simulation engine independent from the database structure.

---

## Scale Mapping — Not Yet Decided

The skin metrics use a `0–10` scale, while medical studies may report outcomes using measurements such as percentage lesion reduction.

The method for converting clinical evidence into the simulation's `0–10` scale has not yet been decided.

This will be defined during treatment parameter calibration.

It is one of the most important modeling assumptions in the project and should be applied consistently across all treatments.

---

## No Invented Medical Values

Simulation parameters must not be invented.

AI treatment research may help identify treatments and summarize medical evidence, but it must not automatically generate numerical simulation coefficients.

For example:

```text
"Adapalene may reduce inflammatory acne"
```

does not justify assuming:

```text
mean_magnitude = 3.0
```

Every real numerical treatment parameter should eventually have a documented source.

Until real parameters are added, any values used for development or testing should be clearly labeled as fixture or non-medical values.

The values in tests and `notes/plot_curves.py` are arbitrary illustrations marked **FIXTURE** and **NOT MEDICAL**. They are not treatment parameters or medical claims.

---

## Deliberately Not Decided Yet

The following parts of the simulation are intentionally left for later days:

- calibrated delay, time-scale, magnitude, and provenance for each treatment effect
- response probability distributions
- exact curve choice for each treatment
- treatment interactions
- adherence
- treatment discontinuation
- mapping clinical study outcomes onto the `0–10` scale

Day 8 defines the simulation vocabulary and validation rules. Day 9 fixes the mathematical curve shapes and their invariants, so those shapes are no longer an open decision. Assigning a curve and calibrated delay, time scale, magnitude, and provenance to each real treatment remains future work.
