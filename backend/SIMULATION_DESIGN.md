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
- the type of time curve used

Therapeutic effects and side effects use the same model because both are changes to a skin metric.

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

## Core Invariants

The simulation should always obey these rules:

- Every skin metric must remain between `0` and `10`.
- `mean_magnitude` must always be positive.
- `direction` determines whether an effect increases or decreases a metric.
- `SKIN_METRIC_NAMES`, `SkinState`, and the metric fields in `SkinProfileRequest` must always match.
- The simulation package should remain pure and independent from FastAPI, Supabase, OpenAI, and environment variables.

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

---

## Deliberately Not Decided Yet

The following parts of the simulation are intentionally left for later days:

- real treatment effect sizes
- response probability distributions
- exact curve choice for each treatment
- treatment interactions
- adherence
- treatment discontinuation
- mapping clinical study outcomes onto the `0–10` scale

Day 8 only defines the simulation vocabulary and validation rules. The actual simulation mathematics begins next.
