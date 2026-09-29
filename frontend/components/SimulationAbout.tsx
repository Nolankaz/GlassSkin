import { METRIC_LABELS } from "@/lib/metrics";
import type { SimulationTreatment } from "@/types/Simulation";

const VALIDATION_REPORT_URL = "https://github.com/Nolankaz/GlassSkin/blob/main/backend/notes/validation/validation_report.md";

export default function SimulationAbout({ treatments }: { treatments: SimulationTreatment[] }) {
  const effects = treatments.flatMap((treatment) => treatment.effects);
  const therapeuticMetrics = new Set(effects.filter((effect) => effect.effect_kind === "therapeutic").map((effect) => effect.target_metric));
  const calibratedMetricLabels = [...therapeuticMetrics].map((metric) => METRIC_LABELS[metric]);
  const calibratedMetricList = calibratedMetricLabels.length > 1 ? `${calibratedMetricLabels.slice(0, -1).join(", ")} and ${calibratedMetricLabels.at(-1)}` : calibratedMetricLabels[0];
  const modelsSideEffects = effects.some((effect) => effect.effect_kind === "side_effect");
  const parameterVersions = new Set(treatments.map((treatment) => treatment.parameter_version));

  return (
    <details className="simulation-about">
      <summary>About this simulation</summary>
      <p>These ranges describe outcomes across a simulated population modeled on clinical-trial participants, not a personal forecast for this profile. Real responses depend on factors the model does not include.</p>
      {calibratedMetricLabels.length > 0 ? (
        <p>Therapeutic effects for {calibratedMetricList} are calibrated against published trial data. Profile concerns without catalogue effects are not simulated.</p>
      ) : (
        <p>No therapeutic skin metrics are calibrated against published trial data in this catalogue.</p>
      )}
      {!modelsSideEffects && <p>Side effects such as dryness or irritation are not modeled, so this simulation does not show those potential downsides.</p>}
      {parameterVersions.has("v1") && <p>The v1 parameters were tested at week 12 against a separate replicate trial that was not used to fit them. For both tretinoin lotion and tazarotene lotion, the model under-predicted average improvement by about 8 percentage points. This result was reported, and the parameters were not retuned afterward to match it.</p>}
      <p><a href={VALIDATION_REPORT_URL} target="_blank" rel="noopener noreferrer">Read the v1 validation report</a></p>
    </details>
  );
}
