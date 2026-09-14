"""Compose a starting SkinState, treatment effects, PatientResponse, and Day 9
progress() into one deterministic Trajectory.

Every state is computed directly from the starting SkinState and its t_days;
clamping happens only in clamp_metric, and there is no randomness here.
TreatmentEffect.uncertainty, SimulationConfig.n_trials, and random_seed are
deliberately ignored because they belong to the Monte Carlo layer. This
module contains no real medical treatment values.
"""

import math
from typing import Mapping, Sequence

from simulation.curves import progress
from simulation.models import (
    METRIC_MAX,
    METRIC_MIN,
    SKIN_METRIC_NAMES,
    EffectDirection,
    EffectKind,
    PatientResponse,
    SimulationConfig,
    SkinState,
    Trajectory,
    TreatmentEffect,
    TreatmentParameters,
)


# Direction owns the sign because TreatmentEffect.mean_magnitude is always positive.
DIRECTION_SIGN: dict[EffectDirection, float] = {
    "increase": 1.0,
    "decrease": -1.0,
}

# Effect kind selects the corresponding multiplier on PatientResponse.
MULTIPLIER_FIELD_BY_KIND: dict[EffectKind, str] = {
    "therapeutic": "response_multiplier",
    "side_effect": "side_effect_multiplier",
}


def build_time_grid(duration_days: int, time_step_days: int) -> list[float]:
    if duration_days <= 0:
        raise ValueError("duration_days must be greater than zero")
    if time_step_days <= 0:
        raise ValueError("time_step_days must be greater than zero")

    times = [float(index * time_step_days) for index in range(duration_days // time_step_days + 1)]
    # Always include the endpoint; an uneven final interval is safe because each state depends only on t.
    if times[-1] != float(duration_days):
        times.append(float(duration_days))
    return times


def clamp_metric(value: float) -> float:
    """Enforce the metric range at the engine's single clamping boundary."""

    if not math.isfinite(value):
        raise ValueError(f"metric value must be finite; got {value}")
    return min(max(value, METRIC_MIN), METRIC_MAX)


def effect_multiplier(effect_kind: EffectKind, patient_response: PatientResponse) -> float:
    return getattr(patient_response, MULTIPLIER_FIELD_BY_KIND[effect_kind])


def effect_contribution(effect: TreatmentEffect, t_days: float, patient_response: PatientResponse) -> float:
    # This explicit scalar order is the reference for vectorized implementation.
    return DIRECTION_SIGN[effect.direction] * effect.mean_magnitude * effect_multiplier(effect.effect_kind, patient_response) * progress(effect.time_curve, t_days, effect.delay_days, effect.time_scale_days)


def metric_deltas(effects: Sequence[TreatmentEffect], t_days: float, patient_response: PatientResponse) -> dict[str, float]:
    # This layer represents no effects even though TreatmentParameters requires one.
    # fsum avoids ordinary order-dependent accumulation.
    contributions: dict[str, list[float]] = {metric: [] for metric in SKIN_METRIC_NAMES}
    for effect in effects:
        contributions[effect.target_metric].append(effect_contribution(effect, t_days, patient_response))
    return {metric: math.fsum(contributions[metric]) for metric in SKIN_METRIC_NAMES}


def apply_deltas(initial_state: SkinState, deltas: Mapping[str, float]) -> SkinState:
    expected_keys = set(SKIN_METRIC_NAMES)
    actual_keys = set(deltas)
    if actual_keys != expected_keys:
        missing_keys = sorted(expected_keys - actual_keys)
        unknown_keys = sorted(actual_keys - expected_keys)
        raise ValueError(f"deltas must contain exactly the skin metrics; missing keys: {missing_keys}; unknown keys: {unknown_keys}")

    values = {metric: clamp_metric(getattr(initial_state, metric) + deltas[metric]) for metric in SKIN_METRIC_NAMES}
    return SkinState(**values)


def state_at(initial_state: SkinState, treatment: TreatmentParameters, t_days: float, patient_response: PatientResponse) -> SkinState:
    """Compute directly from the original state and time, never a previous state."""

    return apply_deltas(initial_state, metric_deltas(treatment.effects, t_days, patient_response))


def simulate(initial_state: SkinState, treatment: TreatmentParameters, config: SimulationConfig, patient_response: PatientResponse) -> Trajectory:
    """Return one deterministic trajectory, raising on invalid arithmetic or structure."""

    times = build_time_grid(config.duration_days, config.time_step_days)
    states = [state_at(initial_state, treatment, t_days, patient_response) for t_days in times]
    return Trajectory(treatment_id=treatment.treatment_id, parameter_version=treatment.parameter_version, patient_response=patient_response, times_days=times, states=states)
