import type { SkinMetricName } from "@/types/SkinProfile";

export type EffectKind = "therapeutic" | "side_effect";

export type EffectDirection = "increase" | "decrease";

export interface SimulationEffectSummary {
  target_metric: SkinMetricName;
  effect_kind: EffectKind;
  direction: EffectDirection;
  citation: string;
  source_url: string;
}

export interface SimulationTreatment {
  treatment_id: string;
  display_name: string;
  parameter_version: string;
  effects: SimulationEffectSummary[];
}

export interface SimulatedMetric {
  metric: SkinMetricName;
  baseline: number;
  effect_kinds: EffectKind[];
  p10: number[];
  p50: number[];
  p90: number[];
}

export interface ProfileSimulation {
  profile_id: number;
  treatment: SimulationTreatment;
  n_trials: number;
  random_seed: number;
  times_days: number[];
  metrics: SimulatedMetric[];
}
