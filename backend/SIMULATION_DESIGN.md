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
- the effect's provenance

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

A value of `1.0` represents the median/reference response.

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

The Monte Carlo layer uses the trial count and requires a nonnegative random seed. The deterministic engine deliberately ignores both.

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

The model uses `list[SkinState]` instead of a NumPy array because it is self-validating through Pydantic, directly JSON serializable, and readable through named metrics. Monte Carlo uses arrays internally for large workloads rather than constructing thousands of Pydantic trajectories.

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

### Inputs Used by Monte Carlo

Deterministic `simulate()` deliberately ignores `SimulationConfig.n_trials`, `SimulationConfig.random_seed` and `TreatmentEffect.uncertainty`. The Monte Carlo layer consumes those inputs without altering deterministic behavior. The deterministic test suite explicitly verifies that changing them does not change deterministic output.

### Development Inspection

`notes/plot_trajectory.py` lives outside `simulation/` and uses Matplotlib only for development visualization. It runs one 90-day fixture trajectory, prints selected days, verifies that every untargeted metric remains bit-identical to its initial value, and plots the two targeted metrics plus an untargeted reference metric. The generated figure is written to `notes/trajectory.png`.

## Monte Carlo

Day 10 produces one deterministic trajectory for one explicit `PatientResponse`. Day 11 samples many patient responses and summarizes the resulting trajectories with percentile bands. Monte Carlo changes the simulated patient response, not the deterministic treatment mechanics.

The underlying composition rules remain:

```text
signed magnitude
× patient-response multiplier
× curve progress
→ per-effect contribution

sum contributions targeting the same metric
→ metric delta

initial state + total delta
→ latent state

clamp once to [0, 10]
→ final state
```

### Sampled Patient Response

Each simulated patient receives exactly two independent standard-normal latent values:

```text
z_ther ~ N(0, 1)
z_side  ~ N(0, 1)
```

`z_ther` represents therapeutic response tendency and is shared by all therapeutic effects for that patient. `z_side` represents side-effect response tendency and is shared by all side-effect effects. Each effect still has its own response spread.

### Fixed Treatment Assumptions

Monte Carlo does not sample or vary:

- initial skin state
- effect direction
- mean/reference magnitude
- the uncertainty parameter itself
- delay
- time scale
- curve type
- time grid
- treatment structure

The resulting bands represent **between-patient variability under fixed treatment assumptions**. They are not parameter uncertainty, model uncertainty, or confidence intervals on a population mean or median.

### Response Distribution

For effect `e`, the log-scale spread and patient-specific multiplier are:

```text
sigma_e = uncertainty_e / mean_magnitude_e
multiplier_i,e = exp(sigma_e * z_i,kind)
```

This is a positive multiplicative response model. `MAX_RESPONSE_LOG_SD = 2.0` limits the permitted log-scale spread as a numerical and model-validity guard; it is not a medical threshold.

The implementation uses `exp(sigma * z)`, not a mean-centered form such as `exp(sigma * z - sigma^2 / 2)`, because the required invariant is:

```text
z = 0
→ multiplier = 1
```

for every `sigma`. The multiplier-1 deterministic responder is therefore the median/reference responder. Under this stochastic interpretation, the existing `mean_magnitude` field behaves as the magnitude for that median/reference responder. Day 12 converts reported means to median-referenced targets before fitting, as described under Calibration.

### Shared Responses by Effect Kind

Within one patient, effects of the same kind use the same latent response but may have different multipliers because their spreads differ:

```text
therapeutic effects:
exp(sigma_1 * z_ther)
exp(sigma_2 * z_ther)
exp(sigma_3 * z_ther)

side-effect effects:
exp(sigma_4 * z_side)
exp(sigma_5 * z_side)
```

Same-kind effects therefore move together according to the patient's shared latent response, while differing in strength according to their individual `sigma` values. Same-kind effects are not currently independently sampled within one patient.

### Seeds and Reproducibility

Monte Carlo requires a nonnegative `random_seed`; `None` and negative seeds are rejected. Each run creates a local generator with `np.random.default_rng(seed)` rather than using global NumPy or Python random state. The reproducibility invariant is:

```text
same inputs + same seed
→ same sampled patients
→ same public result
```

Latent responses are sampled row-major with shape `(n_trials, 2)`, which also provides prefix stability:

```text
same seed + 10 trials
==
first 10 rows of same seed + 100 trials
```

The number of random draws is independent of the number of treatment effects. The same seed can therefore represent the same simulated patient population across different treatment structures, supporting future fair treatment comparisons through common random numbers. Treatment comparison is not implemented here.

### Reference and Production Implementations

`simulate_trials_naive` and `simulate_many_naive` form the deliberately slow, readable reference path. It reuses the trusted Day 10 scalar primitives and is a permanent correctness oracle; it must not be deleted merely because it is slower.

`simulate_trials_vectorised` and `simulate_many` form the NumPy-vectorised production path. Both public paths share seed handling, sampling, percentile aggregation, and result construction. Only trial-state computation differs.

The trust chain is:

```text
Day 10 deterministic engine
→ special-case oracle checks
→ naive Monte Carlo
→ vectorised Monte Carlo
→ public percentile result
```

### Vectorised Representation

Using `T` for trials/patients, `E` for effects, `S` for time steps, and `M` for metrics, the main arrays are:

```text
log_responses          (T, 2)
selected responses     (T, E)
multipliers            (T, E)
progress table         (E, S)
contributions          (T, E, S)
deltas                 (T, S, M)
final states           (T, S, M)
```

The first axis of trial-state arrays identifies the simulated patient, the second identifies time, and the third identifies the skin metric. Effect-indexed arrays use the treatment's effect order.

Curve progress remains evaluated with the trusted scalar `progress(...)` function to build the small `(E, S)` table. This is intentional: patient count is the expensive dimension, while the number of effects and time points is comparatively small. There is no second vectorised implementation of the curve equations.

### Vectorisation Correctness Boundaries

Multiple effects may target the same metric. The vectorised implementation intentionally loops over effects and adds each full `(T, S)` contribution matrix to its target metric slice. This avoids incorrect repeated-index accumulation behavior from NumPy fancy indexing and should not be casually removed as an optimization.

Latent states are explicitly checked with `np.isfinite(...)` before final clipping. This ordering matters because `np.clip(np.nan, 0, 10)` still produces `nan`.

Naive and vectorised outputs must agree within:

```text
atol = 1e-10
rtol = 0
```

Tiny differences can arise from floating-point operation order even when the mathematics is equivalent. Other invariants are exact, including same-seed reproducibility, prefix stability, zero-uncertainty zero-width bands, and untargeted metrics remaining unchanged.

### Percentile Bands

Public bands are calculated across the patient/trial axis using:

```python
np.percentile(
    trial_states,
    (10, 50, 90),
    axis=0,
    method="linear",
)
```

The result contains p10, p50, and p90 at every time point and metric. These are **marginal percentiles**: the p10 value at Day 30 and the p10 value at Day 60 need not come from the same simulated patient. Percentile lines are therefore not fixed individual trajectories. For a metric being decreased, a lower state percentile can correspond to stronger responders.

Percentile estimates also have finite-sample Monte Carlo error, with rough scaling `error ~ 1 / sqrt(n_trials)`. This sampling error is separate from the between-patient variability represented by the bands.

### Performance and Memory

Step 6 development-machine measurements for the complete public paths were approximately:

| Trials | Vectorised | Naive |
|---:|---:|---:|
| 1,000 | 0.0068 s | 0.67 s |
| 10,000 | 0.1198 s | 6.80 s |
| 50,000 | 0.6345 s | not run |

These timings naturally vary by machine and system load. The Step 6 target of less than one second for 10,000 trials over the 90-day daily fixture passed comfortably.

The full raw trial-state array requires approximately:

```text
8 * T * S * M bytes
```

At the maximum theoretical grid used for inspection:

```text
50,000 trials × 731 time points × 17 metrics × 8 bytes
≈ 4.63 GiB
```

This excludes temporary and intermediate arrays. Current performance is sufficient for the 90-day daily fixture workload, but maximum-resolution configurations can become memory-heavy. Possible future mitigations include server-side limits, chunking, streaming aggregation, or other measured memory optimizations; none are implemented in Day 11.

### Fan-Chart Interpretation

The Step 6 fan chart displays p10–p90 as the middle 80% of simulated patient outcomes at each day, p50 as the Monte Carlo median, and the dashed deterministic line as the multiplier-1 reference responder. It confirms that delayed acne effects keep bands closed through the delay, uncertainty opens after effects begin, clamping can make bands asymmetric, and untargeted metrics remain flat with zero-width bands. For multi-kind metrics such as dryness, p50 can be near but not exactly equal to the deterministic reference.

---

## Calibration

Day 12 connects reviewed study observations to the existing simulation engine:

```text
notes/calibration/sources.md                 hand-written evidence ledger
    → notes/calibration/evidence/*.json      hand-written converted targets
    → notes/fit_treatment_parameters.py      development-only fitter
    → simulation/parameters/v1/*.json        generated runtime parameters
    → simulation.parameters loader
    → real simulation.engine.simulate
```

The fitter also generates `notes/calibration/fits/*.png` and `notes/calibration/fit_report.md`. Parameter JSON is reproducible from the evidence and fitting code in this repository. The six current treatment files each contain a published effect on `inflammatory_acne`; this is calibration to selected observations, not clinical validation of the simulator.

### Provenance and evidence selection

Every `TreatmentEffect` requires `Provenance`: `kind` distinguishes `published` from `fixture`; `source_url` locates the source; `citation` identifies the study and relevant location; `reported_figure` records the source values; and `derivation` explains conversion and fitting. `FIXTURE_PROVENANCE` is explicitly **NOT MEDICAL**. Shipped effects in `simulation/parameters/` require published provenance, and the parameter loader rejects fixture-kind effects.

This requirement makes each coefficient carry a provenance claim. It does not establish that a paper is correct or that a citation supports its interpretation. The evidence ledger and human review remain necessary.

Calibration uses **active-arm change from baseline**, not active-minus-vehicle. The product question is “what happens when someone uses this treatment?” Vehicle and other control observations remain in the ledger for later validation and interpretation. This is a model decision, not a universal clinical rule; the fitted effect may include changes that also occurred in a control arm.

Adverse-event incidence is not a severity magnitude: “20% experienced dryness” does not mean “dryness +2 points.” Only a usable numerical magnitude-over-time signal can become a calibrated skin-metric effect. The selected evidence has no complete graded side-effect trajectory, so current simulations may understate treatment burden.

### Response variability and median reference

For usable between-subject spread of **change** on the matching endpoint, Day 12 derives the coefficient of variation and log-scale spread as:

```text
CV = SD / mean
sigma = sqrt(ln(1 + CV^2))
uncertainty = sigma * mean_magnitude
```

Day 11 recovers `sigma = uncertainty / mean_magnitude` for its median-centered multiplicative response. Because the deterministic multiplier-1 response represents the median, a reported mean is converted **after deriving sigma**:

```text
median_referenced_target = reported_mean / exp(sigma^2 / 2)
```

A reported median receives no mean-to-median correction. When usable change-spread data are unavailable, sigma may be borrowed from the pooled directly-derived effects. The derivation must flag that fallback; it must not suggest the borrowed spread came from the same study. Baseline or endpoint count SD alone is not an SD of change.

### Curve fitting and residuals

The fitter enumerates legal `time_curve` and `delay_days` candidates, then uses SciPy least-squares fitting for the continuous `mean_magnitude` and `time_scale_days` values. It evaluates the actual `simulation.curves.progress` function and checks the fitted magnitude against the **bounded** closed-form least-squares optimum. An unconstrained optimum above the magnitude ceiling is recorded separately; a valid ceiling fit remains in RMSE ranking. The separate `TreatmentEffect` uncertainty limit can make a candidate ineligible for the final parameter. SciPy and Matplotlib are development dependencies, not runtime dependencies.

For each successful candidate, the fitter records RMSE, maximum absolute residual, and flags for magnitude or time-scale bound hits, nonpositive degrees of freedom, and asymptotes extrapolated beyond the observed duration. It records failed candidates separately. Selection uses deterministic RMSE tie-breaking. The fitter constructs and validates real `TreatmentEffect` and `TreatmentParameters` objects before writing JSON. The fit report records the selected curves, diagnostics, and any candidates excluded by model constraints.

Low RMSE means a curve lies close to the **converted** evidence points. It does not prove clinical validity or strong evidence quality. When degrees of freedom are nonpositive, residual quality is not informative in the usual sense. The parameter tests load generated JSON, run the real engine at each recorded observation time with a reference response, compare against the evidence targets using recorded residuals, and reject clamped target states. This verifies reproduction of the calibration targets, not external clinical accuracy.

### Known calibration limitations

- Observed response spread contains measurement error, natural fluctuation, adherence differences, vehicle response, and other study variation as well as biological variability. The derived or borrowed sigma may overestimate true between-patient biological response variability.
- Some fitted asymptotes extend beyond observed study duration where `g(t_max)` is low; the fit report flags these extrapolations.
- Parameters calibrated at reference baselines become absolute point changes in the engine. Applying them across different starting severities can be optimistic for mild states and conservative for severe states.
- Excluded or unmodeled side effects make the simulated treatment burden optimistic.

---

## Core Invariants

The simulation obeys these model, curve, deterministic-engine, and Monte Carlo rules:

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
- `simulation/` has no FastAPI, Supabase, OpenAI, network, environment-variable, clock, or database dependencies. Its only filesystem access is `simulation/parameters/` reading its own committed, read-only packaged data through `importlib.resources`, with no caller-supplied filesystem path. This preserves determinism and avoids hidden external state.
- Deterministic simulation modules have no randomness dependencies.
- Monte Carlo randomness comes only from a local seeded NumPy generator.
- Monte Carlo public results contain all metrics and only percentile bands, not raw trials.
- Naive and vectorised trial paths agree within the documented numerical tolerance.
- Every `TreatmentEffect` carries `Provenance`; every shipped effect in `simulation/parameters/` has published provenance, never fixture provenance.
- A parameter filename stem equals its `treatment_id`; `parameter_version` equals its containing version directory; IDs are unique within each version.
- Parameter version syntax is validated before filesystem access, and loading is deterministic and sorted by `treatment_id`.
- Calibrated parameters reproduce recorded source targets through the real engine within their recorded residuals.

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

## Scale Mapping

The skin metrics use a `0–10` scale, while studies may report global grades or lesion counts. Day 12 uses the following GlassSkin calibration conventions, **not universal clinical equivalences**.

For a usable observed global grade on a `0–4` scale:

| Global grade | GlassSkin points |
|---:|---:|
| 0 | 0 |
| 1 | 2.5 |
| 2 | 5 |
| 3 | 7.5 |
| 4 | 10 |

For an observed lesion-count baseline, the fixed anchors are:

| Band | Inflammatory lesions | Comedones | GlassSkin points |
|---|---:|---:|---:|
| Clear | 0 | 0 | 0 |
| Mild | 1–14 | 1–19 | 5 |
| Moderate | 15–50 | 20–100 | 7.5 |
| Severe | >50 | >100 | 10 |

Eligibility ranges are not observed baselines. The conversion rule has three branches:

1. If the source reports an absolute change on a `0–4` global grade, `delta_points = delta_grade * 2.5`.
2. Else if the source reports a percentage change in lesion count, `delta_points = fraction_change * B_ref`, where `B_ref` is that trial's mapped reference baseline.
3. Otherwise, record the endpoint but do not use it as a fitted target.

### Absolute versus proportional effects

The engine applies an absolute point effect calibrated at a reference baseline. A mildly affected user can therefore receive the same modeled point change as a more severely affected user. This may be over-optimistic for mild starting states and conservative for severe starting states. It is a known limitation to examine in Day 13.

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

Every numerical efficacy or side-effect coefficient entering the simulator needs a traceable source and derivation.

Development and test treatments explicitly use `FIXTURE_PROVENANCE` / **NOT MEDICAL**. Shipped calibrated effects require published provenance, and the runtime loader refuses fixture provenance in versioned parameter data.

The values in `notes/plot_curves.py` are arbitrary mathematical illustrations marked **FIXTURE** and **NOT MEDICAL**. They are not treatment parameters or medical claims.

The treatments used in `tests/test_engine.py` and `notes/plot_trajectory.py` are arbitrary fixtures marked NOT MEDICAL. The versioned `simulation/parameters/v1/` JSON files are the separate calibrated runtime data source.

---

## Deliberately Not Decided Yet

Days 10–12 fixed deterministic composition, Monte Carlo response sampling, and calibration for six treatments. The following parts remain intentionally unresolved for later work:

- curve choice and calibration for newly added treatments; curves for the currently calibrated six are fitted
- treatment interactions
- adherence
- treatment discontinuation and rebound
- clinical validation

Day 8 defines the simulation vocabulary and validation rules. Day 9 fixes the mathematical curve shapes and their invariants. Day 10 composes them into an absolute deterministic trajectory. Day 11 samples patient responses and produces percentile bands while preserving those rules. Day 12 records sourced published treatment evidence, fits calibrated parameters with provenance, loads versioned parameter data, and tests reproduction of the recorded targets through the real engine.
