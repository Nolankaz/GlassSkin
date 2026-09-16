"""Turn one treatment and initial skin state into bands across patients.

Each trial samples one therapeutic and one side-effect latent response while
treatment parameters and the time grid stay fixed. Response multipliers are
median-1 log-normal: sigma = uncertainty / mean_magnitude and multiplier =
exp(sigma * z). All composition rules come from Day 10's deterministic engine.

Randomness comes only from a local numpy.random.Generator seeded by
SimulationConfig.random_seed. simulate_many_naive is the readable reference
implementation and remains alongside the vectorised production path. No medical
values are defined here.
"""

import math
from typing import Callable, Sequence

import numpy as np

from simulation.curves import progress
from simulation.engine import DIRECTION_SIGN, MULTIPLIER_FIELD_BY_KIND, apply_deltas, build_time_grid, effect_contribution
from simulation.models import (
    METRIC_MAX,
    METRIC_MIN,
    SKIN_METRIC_NAMES,
    EffectKind,
    MonteCarloResult,
    PatientResponse,
    PercentileBand,
    SimulationConfig,
    SkinState,
    TreatmentEffect,
    TreatmentParameters,
)


BAND_PERCENTILES: tuple[float, ...] = (10.0, 50.0, 90.0)

# Columns in each latent-response row follow PatientResponse's field order.
RESPONSE_FIELDS: tuple[str, ...] = tuple(PatientResponse.model_fields)

# Numerical and model-validity guard, not a medical value.
MAX_RESPONSE_LOG_SD = 2.0


def require_seed(config: SimulationConfig) -> int:
    if config.random_seed is None:
        raise ValueError("Monte Carlo runs must be reproducible; pass random_seed")
    if config.random_seed < 0:
        raise ValueError("random_seed must be non-negative")
    return config.random_seed


def response_log_sd(effect: TreatmentEffect) -> float:
    log_sd = effect.uncertainty / effect.mean_magnitude
    if log_sd > MAX_RESPONSE_LOG_SD:
        raise ValueError(f"response log-scale standard deviation for {effect.target_metric} {effect.effect_kind} effect is {log_sd}, above maximum {MAX_RESPONSE_LOG_SD}")
    return log_sd


def response_column(effect_kind: EffectKind) -> int:
    return RESPONSE_FIELDS.index(MULTIPLIER_FIELD_BY_KIND[effect_kind])


def sample_log_responses(n_trials: int, rng: np.random.Generator) -> np.ndarray:
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a numpy.random.Generator")
    if n_trials < 1:
        raise ValueError("n_trials must be at least 1")
    # Row-major sampling preserves patient prefixes when n_trials grows for the same seed.
    return rng.standard_normal((n_trials, len(RESPONSE_FIELDS)))


def check_log_responses(log_responses: np.ndarray) -> None:
    if not isinstance(log_responses, np.ndarray):
        raise ValueError("log_responses must be a numpy array")
    if log_responses.ndim != 2:
        raise ValueError(f"log_responses must be 2-dimensional; got ndim={log_responses.ndim}")
    if log_responses.shape[1] != len(RESPONSE_FIELDS):
        raise ValueError(f"log_responses must have {len(RESPONSE_FIELDS)} columns; got shape {log_responses.shape}")
    if log_responses.shape[0] < 1:
        raise ValueError("log_responses must contain at least one trial")
    if log_responses.dtype != np.float64:
        raise ValueError(f"log_responses must have dtype float64; got {log_responses.dtype}")
    if not np.isfinite(log_responses).all():
        raise ValueError("log_responses must contain only finite values")


def effective_response(log_response: Sequence[float], log_sd: float) -> PatientResponse:
    """Represent one simulated patient as seen by one effect with this spread."""

    values = {field: math.exp(log_sd * float(log_response[index])) for index, field in enumerate(RESPONSE_FIELDS)}
    return PatientResponse(**values)


def simulate_trials_naive(initial_state: SkinState, treatment: TreatmentParameters, times_days: Sequence[float], log_responses: np.ndarray) -> np.ndarray:
    """Return deliberately slow trial states with axes (trials, time, metrics)."""

    check_log_responses(log_responses)
    effect_log_sds = [response_log_sd(effect) for effect in treatment.effects]
    trial_states = np.full((log_responses.shape[0], len(times_days), len(SKIN_METRIC_NAMES)), np.nan, dtype=np.float64)

    for trial_index, log_response in enumerate(log_responses):
        effect_responses = [(effect, effective_response(log_response, log_sd)) for effect, log_sd in zip(treatment.effects, effect_log_sds)]
        for time_index, t_days in enumerate(times_days):
            # This is Day 10's metric_deltas composition with one response per
            # effect because effects of the same kind may have different sigma.
            # Later tests pin it to simulate() when one response describes a trial:
            # all uncertainty == 0 or all uncertainty == mean_magnitude.
            contributions: dict[str, list[float]] = {metric: [] for metric in SKIN_METRIC_NAMES}
            for effect, response in effect_responses:
                contributions[effect.target_metric].append(effect_contribution(effect, t_days, response))
            deltas = {metric: math.fsum(contributions[metric]) for metric in SKIN_METRIC_NAMES}
            state = apply_deltas(initial_state, deltas)
            trial_states[trial_index, time_index] = [getattr(state, metric) for metric in SKIN_METRIC_NAMES]

    return trial_states


def simulate_trials_vectorised(initial_state: SkinState, treatment: TreatmentParameters, times_days: Sequence[float], log_responses: np.ndarray) -> np.ndarray:
    """Return vectorised trial states with axes (trials, time, metrics)."""

    check_log_responses(log_responses)
    effect_log_sds = np.array([response_log_sd(effect) for effect in treatment.effects], dtype=np.float64)

    n_trials = log_responses.shape[0]
    n_effects = len(treatment.effects)
    n_steps = len(times_days)
    n_metrics = len(SKIN_METRIC_NAMES)

    response_columns = np.array([response_column(effect.effect_kind) for effect in treatment.effects], dtype=np.intp)
    signed_magnitudes = np.array([DIRECTION_SIGN[effect.direction] * effect.mean_magnitude for effect in treatment.effects], dtype=np.float64)

    # Select the shared latent response for each effect: (T, 2) -> (T, E).
    selected_log_responses = log_responses[:, response_columns]
    multipliers = np.exp(selected_log_responses * effect_log_sds)

    # Curve math stays scalar and trusted; this small table has shape (E, S).
    progress_table = np.full((n_effects, n_steps), np.nan, dtype=np.float64)
    for effect_index, effect in enumerate(treatment.effects):
        for time_index, t_days in enumerate(times_days):
            progress_table[effect_index, time_index] = progress(effect.time_curve, t_days, effect.delay_days, effect.time_scale_days)

    # Broadcast (1, E, 1) * (T, E, 1) * (1, E, S) -> (T, E, S).
    contributions = signed_magnitudes[None, :, None] * multipliers[:, :, None] * progress_table[None, :, :]
    deltas = np.zeros((n_trials, n_steps, n_metrics), dtype=np.float64)
    metric_indices = {metric: index for index, metric in enumerate(SKIN_METRIC_NAMES)}

    # Loop over effects so duplicate metric targets accumulate correctly while
    # every patient and time point remains vectorised.
    for effect_index, effect in enumerate(treatment.effects):
        deltas[:, :, metric_indices[effect.target_metric]] += contributions[:, effect_index, :]

    baseline = np.array([getattr(initial_state, metric) for metric in SKIN_METRIC_NAMES], dtype=np.float64)
    latent_states = baseline + deltas
    if not np.isfinite(latent_states).all():
        raise ValueError("simulation produced non-finite values before clamping")
    return np.clip(latent_states, METRIC_MIN, METRIC_MAX)


def percentile_bands(trial_states: np.ndarray) -> np.ndarray:
    """Take percentiles across patients while preserving time and metrics.

    Axis 0 is the patient/trial axis. The first output axis follows
    BAND_PERCENTILES order.
    """

    if not isinstance(trial_states, np.ndarray) or trial_states.ndim != 3:
        raise ValueError("trial_states must be a 3-dimensional numpy array")
    if trial_states.shape[0] < 1:
        raise ValueError("trial_states must contain at least one trial")
    return np.percentile(trial_states, BAND_PERCENTILES, axis=0, method="linear")


def build_result(treatment: TreatmentParameters, config: SimulationConfig, seed: int, times_days: list[float], bands: np.ndarray) -> MonteCarloResult:
    metric_bands = {
        metric: PercentileBand(
            p10=bands[0, :, metric_index].tolist(),
            p50=bands[1, :, metric_index].tolist(),
            p90=bands[2, :, metric_index].tolist(),
        )
        for metric_index, metric in enumerate(SKIN_METRIC_NAMES)
    }
    return MonteCarloResult(
        treatment_id=treatment.treatment_id,
        parameter_version=treatment.parameter_version,
        n_trials=config.n_trials,
        random_seed=seed,
        times_days=times_days,
        bands=metric_bands,
    )


def _run(initial_state: SkinState, treatment: TreatmentParameters, config: SimulationConfig, trials_function: Callable[[SkinState, TreatmentParameters, Sequence[float], np.ndarray], np.ndarray]) -> MonteCarloResult:
    seed = require_seed(config)
    times = build_time_grid(config.duration_days, config.time_step_days)
    rng = np.random.default_rng(seed)
    log_responses = sample_log_responses(config.n_trials, rng)
    trials = trials_function(initial_state, treatment, times, log_responses)
    bands = percentile_bands(trials)
    return build_result(treatment, config, seed, times, bands)


def simulate_many_naive(initial_state: SkinState, treatment: TreatmentParameters, config: SimulationConfig) -> MonteCarloResult:
    """Run the slow reference implementation, which must not be deleted.

    The vectorised implementation must agree with it within an absolute
    tolerance of 1e-10.
    """

    return _run(initial_state, treatment, config, simulate_trials_naive)


def simulate_many(initial_state: SkinState, treatment: TreatmentParameters, config: SimulationConfig) -> MonteCarloResult:
    """Run the vectorised production Monte Carlo implementation."""

    return _run(initial_state, treatment, config, simulate_trials_vectorised)
