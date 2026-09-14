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

Both multipliers must be positive and finite. `PatientResponse` rejects zero, negative, infinite and NaN values before they can enter simulation arithmetic.

---

### SimulationConfig

`SimulationConfig` controls how a simulation runs.

It contains:

- simulation duration
- time step size
- number of trials
- optional random seed

The trial count and random seed are reserved for the later randomized layer. The Day 10 deterministic engine deliberately ignores both.

---

### SimulationRequest

`SimulationRequest` combines everything needed for one simulation run:

- initial skin state
- treatment parameters
- simulation configuration
- optional patient response

This is planned as the eventual simulation API request body. Its patient response remains optional because later routing will distinguish a deterministic run from a Monte Carlo run. The current deterministic `simulate()` function does not consume `SimulationRequest`; it accepts the initial state, treatment, config and an explicit `PatientResponse` directly.

---

### Trajectory

`Trajectory` represents one deterministic simulated path. It records:

- `treatment_id`
- `parameter_version`
- `patient_response`
- `times_days`
- `states`

`states[i]` is the validated `SkinState` at `times_days[i]`. A trajectory has at least two time points and states, the two lists have equal lengths, time starts at `0.0`, and times are finite and strictly increasing. Every state is validated independently, so its metrics remain inside `[0, 10]`.

The model uses `list[SkinState]` instead of a NumPy array today because it is self-validating through Pydantic, directly JSON serializable, readable through named metrics, and keeps NumPy out of `simulation/`. Day 11 will use arrays for large Monte Carlo workloads rather than constructing thousands of Pydantic trajectories.

`metric_series(metric)` extracts one named metric across all states in time order and rejects unknown metric names.

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

## Deterministic Engine

`simulation/engine.py` composes the Day 8 models and Day 9 time curves into one deterministic trajectory. For metric `m` at time `t`, the rule is:

```text
S_m(t) = clamp(S_m(0) + Σ contributions_e(t))
```

Each effect targeting that metric contributes:

```text
direction_sign × mean_magnitude × patient_response_multiplier × progress(...)
```

`direction`, `mean_magnitude` and `effect_kind` come from the Day 8 models. Day 9's `progress()` and time curves determine how much of an effect has appeared at a requested time. Day 10 composes those pieces into deterministic `SkinState` values and a `Trajectory`.

The engine layers are deliberately small:

```text
progress
→ effect_contribution
→ metric_deltas
→ apply_deltas
→ state_at
→ simulate
```

- `progress()` returns the fraction of an effect realized at one time.
- `effect_contribution()` applies direction, magnitude and the correct patient-response multiplier to that fraction.
- `metric_deltas()` groups contributions by target metric and sums them.
- `apply_deltas()` adds one complete delta mapping to the original state and clamps each resulting metric.
- `state_at()` computes one state directly from the original state and requested time.
- `simulate()` builds the time grid, maps `state_at()` over it, and returns a `Trajectory`.

### Absolute Application

Every state is computed directly from the original `SkinState` and the requested `t_days`:

```text
S(t) = clamp(S(0) + Σ contributions(t))
```

The engine is not cumulative and never computes a state from a previous simulated state. Cumulative application combined with clamping makes the result depend on time-step size: an intermediate clamp discards overshoot, so a later opposite effect starts from a different value depending on which intermediate times were evaluated. Absolute application avoids that numerical drift, makes states at shared times step-invariant, and permits Day 11 vectorization because no state depends on its predecessor.

Table C in the deterministic test suite demonstrates the distinction with fixture values, not medical parameters:

- initial dryness is `1.0`
- one therapeutic effect decreases dryness by magnitude `3.0`, linearly over 10 days
- one side effect increases dryness by magnitude `3.0`, using delayed linear progress with a 10-day delay and 10-day scale
- the absolute result at day 10 is `0.0`
- the absolute result at day 20 is `1.0`

At day 20 the two full contributions cancel, so the result returns to the original `1.0`. A cumulative-with-clamping implementation can instead produce different answers depending on the step size because it repeatedly applies already-realized effects and clips intermediate states.

### Superposition

Effects targeting the same metric are superposed additively. Each effect produces a signed delta, all deltas for that metric are summed, and the complete sum is applied once to the original state. Treatment interactions are not modeled yet. Additive superposition is a modeling assumption, not a medical truth.

The unclamped latent sum can exceed `[0, 10]`. In that case a later opposite effect must first overcome the latent overshoot before the visible clamped metric moves back inside the range. This follows directly from the absolute, clamp-after-summing rule.

### Clamping

Metric bounds are enforced in exactly one engine function: `clamp_metric()`. `apply_deltas()` sums all contributions for a metric, adds that sum to the initial value, and then clamps the result. The engine does not clamp each effect separately and does not clamp step-by-step.

Finite results below `METRIC_MIN` or above `METRIC_MAX` are legitimate model outcomes and are clipped into `[METRIC_MIN, METRIC_MAX]` rather than treated as errors. `SkinState` validation remains a backstop if engine clamping is ever bypassed. Non-finite arithmetic is different: `clamp_metric()` checks `math.isfinite()` and raises instead of allowing NaN or infinity into a state.

### Patient Response in Deterministic Mode

`simulate()` requires an explicit `PatientResponse`; there is no hidden default responder. Therapeutic effects use `response_multiplier`, side effects use `side_effect_multiplier`, and `effect_kind` selects the field through `MULTIPLIER_FIELD_BY_KIND`.

The `1.0 / 1.0` response is the reference responder by definition of `mean_magnitude`: that magnitude describes the full effect for a response multiplier of exactly `1.0`. Both multipliers are positive and finite because `PatientResponse` rejects invalid values at construction.

### Stable Summation

`metric_deltas()` uses `math.fsum()` because ordinary running floating-point addition can produce slightly different last-bit results when effects are reordered. Effect order should not change a deterministic trajectory. `math.fsum()` provides a more stable, correctly rounded sum, and the test suite explicitly verifies effect-order independence.

### Time Grid

`build_time_grid()` starts at `0.0`, uses integer multiples of `time_step_days`, and always includes the exact `duration_days` endpoint without duplicating it. The final interval may be shorter than the nominal step:

```text
90 / 1  → 0, 1, ..., 90
90 / 7  → 0, 7, ..., 77, 84, 90
90 / 30 → 0, 30, 60, 90
5 / 30  → 0, 5
```

An uneven final interval is safe because the engine is absolute: the state depends on `t`, not on the length or result of the previous interval.

### Inputs Reserved for Monte Carlo

Deterministic `simulate()` deliberately ignores `SimulationConfig.n_trials`, `SimulationConfig.random_seed` and `TreatmentEffect.uncertainty`. Those inputs belong to the Day 11 Monte Carlo layer. The deterministic test suite explicitly verifies that changing them does not change deterministic output.

### Development Inspection

`notes/plot_trajectory.py` lives outside `simulation/` and uses Matplotlib only for development visualization. It runs one 90-day fixture trajectory, prints selected days, verifies that every untargeted metric remains bit-identical to its initial value, and plots the two targeted metrics plus an untargeted reference metric. The generated figure is written to `notes/trajectory.png`.

---

## Core Invariants

The simulation obeys these model, curve and deterministic-engine rules:

- Every skin metric must remain between `0` and `10`.
- `mean_magnitude` must always be positive.
- `PatientResponse` multipliers must be finite and positive.
- `direction` determines whether an effect increases or decreases a metric.
- `SKIN_METRIC_NAMES`, `SkinState`, and the metric fields in `SkinProfileRequest` must always match.
- Progress must always remain in `[0, 1]`.
- Progress must be exactly `0.0` through the delay gate.
- Every time curve must be monotone non-decreasing.
- The curve-function registry must cover `TimeCurveType` exactly.
- Unknown curve names and non-finite inputs must raise instead of producing a progress value.
- Curve functions must be deterministic and pure.
- Every trajectory state is computed from `initial_state` and `t_days` only.
- `states[0] == initial_state`.
- Untargeted metrics remain bit-identical to their initial values.
- Results at times shared by different time grids are exactly step-invariant.
- Reordering treatment effects does not change the trajectory.
- Deterministic simulations are exactly repeatable for identical inputs.
- Simulation inputs are not mutated.
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

The values in `notes/plot_curves.py` are arbitrary mathematical illustrations marked **FIXTURE** and **NOT MEDICAL**. They are not treatment parameters or medical claims.

All treatments used in `tests/test_engine.py` and `notes/plot_trajectory.py` are arbitrary fixtures marked NOT MEDICAL. `simulation/` contains no treatment parameters of any kind.

---

## Deliberately Not Decided Yet

Day 10 fixed the deterministic application rule, additive superposition, clamp placement, time-grid construction and trajectory representation. The following parts remain intentionally unresolved for later work:

- calibrated real treatment parameters and their provenance
- Monte Carlo response distributions
- exact curve choice for each treatment
- treatment interactions
- adherence
- treatment discontinuation and rebound
- mapping clinical study outcomes onto the `0–10` scale
- clinical validation

Day 8 defines the simulation vocabulary and validation rules. Day 9 fixes the mathematical curve shapes and their invariants. Day 10 composes them into an absolute deterministic trajectory. Assigning a curve and calibrated delay, time scale, magnitude and provenance to each real treatment remains future work.
