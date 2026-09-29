"use client";

import { useEffect, useRef, useState } from "react";

import { apiUrl } from "@/lib/api";
import { METRIC_LABELS } from "@/lib/metrics";
import type { EffectKind, ProfileSimulation, SimulationTreatment } from "@/types/Simulation";
import SimulationAbout from "@/components/SimulationAbout";
import TrajectoryChart from "@/components/TrajectoryChart";

interface SimulationPanelProps {
  profileId: number;
}

type CatalogueStatus = "loading" | "error" | "ready";
type RunStatus = "idle" | "running" | "error" | "done";

const EFFECT_KIND_LABELS: Record<EffectKind, string> = {
  therapeutic: "therapeutic",
  side_effect: "side effect",
};

// Below 5 is beneath every v1 calibration baseline (5.0–7.5); see the Day 13 baseline sweep.
const LOW_BASELINE_THRESHOLD = 5;

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") return body.detail;
  } catch {
    return fallback;
  }

  return fallback;
}

function SimulationResult({ simulation }: { simulation: ProfileSimulation }) {
  const last = simulation.times_days.length - 1;
  const week = simulation.times_days[last] / 7;

  return (
    <div className="section">
      <div className="section-header">
        <div>
          <h3>{simulation.treatment.display_name}</h3>
          <div className="badge-row">
            <span className="badge">Parameters {simulation.treatment.parameter_version}</span>
            <span className="badge">{simulation.n_trials.toLocaleString()} simulated patients</span>
          </div>
        </div>
      </div>

      {simulation.metrics.map((metric) => {
        const label = METRIC_LABELS[metric.metric];
        const hasDecreasingEffect = simulation.treatment.effects.some((effect) => effect.target_metric === metric.metric && effect.direction === "decrease");
        const nothingToReduce = hasDecreasingEffect && metric.baseline === 0;
        const lowBaseline = hasDecreasingEffect && metric.baseline > 0 && metric.baseline < LOW_BASELINE_THRESHOLD;

        return (
          <div className="section" key={metric.metric}>
            <h4>{label}</h4>
            {nothingToReduce ? (
              <div className="notice simulation-empty-notice">This profile scores 0 for {label}, so there is nothing for this treatment to reduce.</div>
            ) : (
              <>
                {lowBaseline && <div className="notice simulation-low-warning">This starting score is below the range used to calibrate the model. Results are least reliable at mild starting points: many simulated patients can reach 0 because the model clamps scores at the floor, but that does not mean clearing should be expected.</div>}
                <TrajectoryChart timesDays={simulation.times_days} p10={metric.p10} p50={metric.p50} p90={metric.p90} baseline={metric.baseline} label={label} />
                <p>{label}: {metric.baseline.toFixed(1)} at the start → median {metric.p50[last].toFixed(1)} at week {week}</p>
                <p>80% of simulated outcomes at week {week} land between {metric.p10[last].toFixed(1)} and {metric.p90[last].toFixed(1)}.</p>
              </>
            )}
            <div className="badge-row">
              {metric.effect_kinds.map((kind, index) => <span className="badge" key={`${kind}-${index}`}>{EFFECT_KIND_LABELS[kind]}</span>)}
            </div>
          </div>
        );
      })}

      <div className="evidence-list">
        <h4>Sources</h4>
        {simulation.treatment.effects.map((effect, index) => (
          <div className="evidence-card" key={`${effect.target_metric}-${index}`}>
            <p className="meta">{METRIC_LABELS[effect.target_metric]} · {EFFECT_KIND_LABELS[effect.effect_kind]}</p>
            <p>{effect.citation}</p>
            <a href={effect.source_url} target="_blank" rel="noopener noreferrer">View source</a>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SimulationPanel({ profileId }: SimulationPanelProps) {
  const [treatments, setTreatments] = useState<SimulationTreatment[]>([]);
  const [catalogueStatus, setCatalogueStatus] = useState<CatalogueStatus>("loading");
  const [catalogueAttempt, setCatalogueAttempt] = useState(0);
  const [selectedId, setSelectedId] = useState("");
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [simulation, setSimulation] = useState<ProfileSimulation | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const runInFlightRef = useRef(false);

  useEffect(() => {
    async function loadTreatments() {
      try {
        const response = await fetch(apiUrl("/simulation/treatments"));
        if (!response.ok) throw new Error(`Unable to load calibrated treatments (${response.status})`);

        const data: SimulationTreatment[] = await response.json();
        setTreatments(data);
        setCatalogueStatus("ready");
      } catch (error) {
        console.error("Failed to load calibrated treatments", error);
        setCatalogueStatus("error");
      }
    }

    loadTreatments();
  }, [catalogueAttempt]);

  function retryCatalogue() {
    setCatalogueStatus("loading");
    setCatalogueAttempt((attempt) => attempt + 1);
  }

  function changeSelection(id: string) {
    setSelectedId(id);
    setSimulation(null);
    setRunError(null);
    setRunStatus("idle");
  }

  async function runSimulation() {
    if (!selectedId || runInFlightRef.current) return;
    runInFlightRef.current = true;

    setRunStatus("running");
    setSimulation(null);
    setRunError(null);

    try {
      const response = await fetch(apiUrl(`/profiles/${profileId}/simulations/${encodeURIComponent(selectedId)}`));

      if (!response.ok) {
        const message = await readErrorDetail(response, "Unable to run the simulation. Please try again.");
        console.error("Simulation request failed", response.status, message);
        setRunError(message);
        setRunStatus("error");
        return;
      }

      const data: ProfileSimulation = await response.json();
      setSimulation(data);
      setRunStatus("done");
    } catch (error) {
      console.error("Failed to reach the simulation backend", error);
      setRunError("Unable to reach the simulation backend. Check the connection and try again.");
      setRunStatus("error");
    } finally {
      runInFlightRef.current = false;
    }
  }

  return (
    <section className="panel research-panel">
      <div className="research-hero">
        <div>
          <span className="eyebrow">Calibrated simulation</span>
          <h2>Treatment Simulation</h2>
          <p>This shows a range across simulated patients, not a prediction for this specific person.</p>
        </div>
      </div>

      {catalogueStatus === "loading" && <div className="loading-card">Loading calibrated treatments...</div>}

      {catalogueStatus === "error" && (
        <div className="error-card">
          <p>Unable to load calibrated treatments. Please try again.</p>
          <button className="button" onClick={retryCatalogue}>Retry</button>
        </div>
      )}

      {catalogueStatus === "ready" && (treatments.length === 0 ? (
        <div className="notice">No calibrated treatments are available.</div>
      ) : (
        <div className="section">
          <div className="field">
            <label htmlFor="simulation-treatment">Treatment</label>
            <select id="simulation-treatment" className="text-input" value={selectedId} onChange={(event) => changeSelection(event.target.value)} disabled={runStatus === "running"}>
              <option value="" disabled>Choose a treatment</option>
              {treatments.map((treatment) => (
                <option key={treatment.treatment_id} value={treatment.treatment_id}>{treatment.display_name}</option>
              ))}
            </select>
          </div>
          <button className="button" onClick={runSimulation} disabled={!selectedId || runStatus === "running"}>Run simulation</button>
        </div>
      ))}

      {runStatus === "idle" && <div className="empty-state">Choose a treatment to see a simulated range.</div>}
      {runStatus === "running" && <div className="loading-card">Running simulation...</div>}
      {runStatus === "error" && (
        <div className="error-card">
          <p>{runError}</p>
          <button className="button" onClick={runSimulation}>Try again</button>
        </div>
      )}
      {runStatus === "done" && simulation && <SimulationResult simulation={simulation} />}

      {catalogueStatus === "ready" && treatments.length > 0 && <SimulationAbout treatments={treatments} />}

      <p className="disclaimer">This simulation is informational, describes simulated populations, and is not medical advice.</p>
    </section>
  );
}
