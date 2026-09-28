"""Adapt stored profiles and calibrated treatments to simulation API responses."""

from typing import Any, Mapping, cast

from schemas import ProfileSimulation, SimulatedMetric, SimulationEffectSummary, SimulationTreatment
from simulation.models import SKIN_METRIC_NAMES, SkinMetricName, SimulationConfig, SkinState, TreatmentParameters
from simulation.monte_carlo import simulate_many
from simulation.parameters import available_treatment_ids, load_treatment, load_treatment_parameters
from simulation.profile_adapter import skin_state_from_profile


SIMULATION_PARAMETER_VERSION = "v1"
SIMULATION_N_TRIALS = 10_000
SIMULATION_SEED = 42
SIMULATION_TIME_STEP_DAYS = 7
DEFAULT_DURATION_DAYS = 84
MIN_DURATION_DAYS = 28
MAX_DURATION_DAYS = 168


class UnknownTreatmentError(ValueError):
    """The requested treatment is absent from the current parameter catalogue."""

    def __init__(self, treatment_id: str, valid_ids: tuple[str, ...]):
        self.valid_ids = valid_ids
        super().__init__(f"unknown treatment_id {treatment_id!r}; valid ids: {valid_ids}")


def summarise_treatment(treatment: TreatmentParameters) -> SimulationTreatment:
    effects = [
        SimulationEffectSummary(target_metric=effect.target_metric, effect_kind=effect.effect_kind, direction=effect.direction, citation=effect.provenance.citation, source_url=effect.provenance.source_url)
        for effect in treatment.effects
    ]
    return SimulationTreatment(treatment_id=treatment.treatment_id, display_name=treatment.display_name, parameter_version=treatment.parameter_version, effects=effects)


def list_simulatable_treatments() -> list[SimulationTreatment]:
    return [summarise_treatment(treatment) for treatment in load_treatment_parameters(SIMULATION_PARAMETER_VERSION)]


def find_treatment(treatment_id: str) -> TreatmentParameters:
    valid_ids = available_treatment_ids(SIMULATION_PARAMETER_VERSION)
    if treatment_id not in valid_ids:
        raise UnknownTreatmentError(treatment_id, valid_ids)
    return load_treatment(treatment_id, SIMULATION_PARAMETER_VERSION)


def affected_metrics(treatment: TreatmentParameters) -> tuple[SkinMetricName, ...]:
    targets = {effect.target_metric for effect in treatment.effects}
    return cast(tuple[SkinMetricName, ...], tuple(metric for metric in SKIN_METRIC_NAMES if metric in targets))


def simulate_profile_treatment(profile_id: int, initial_state: SkinState, treatment: TreatmentParameters, duration_days: int) -> ProfileSimulation:
    config = SimulationConfig(duration_days=duration_days, time_step_days=SIMULATION_TIME_STEP_DAYS, n_trials=SIMULATION_N_TRIALS, random_seed=SIMULATION_SEED)
    result = simulate_many(initial_state, treatment, config)
    metrics = []
    for metric in affected_metrics(treatment):
        band = result.metric_band(metric)
        effect_kinds = list(dict.fromkeys(effect.effect_kind for effect in treatment.effects if effect.target_metric == metric))
        metrics.append(SimulatedMetric(metric=metric, baseline=getattr(initial_state, metric), effect_kinds=effect_kinds, p10=band.p10, p50=band.p50, p90=band.p90))
    return ProfileSimulation(profile_id=profile_id, treatment=summarise_treatment(treatment), n_trials=result.n_trials, random_seed=result.random_seed, times_days=result.times_days, metrics=metrics)


def run_profile_simulation(profile: Mapping[str, Any], treatment_id: str, duration_days: int) -> ProfileSimulation:
    initial_state = skin_state_from_profile(profile)
    treatment = find_treatment(treatment_id)
    return simulate_profile_treatment(profile["id"], initial_state, treatment, duration_days)
