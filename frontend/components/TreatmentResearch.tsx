"use client";

import { useEffect, useRef, useState } from "react";

import TreatmentOptionCard from "./TreatmentOptionCard";

import type {
  SavedTreatmentResearchResponse,
  TreatmentResearchResult,
  TreatmentResearchResponse,
} from "@/types/TreatmentResearch";
import { apiUrl } from "@/lib/api";

interface TreatmentResearchProps {
  profileId: number;
}

export default function TreatmentResearch({ profileId, }: TreatmentResearchProps) {
  const [research, setResearch] = useState<TreatmentResearchResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingSavedResearch, setIsLoadingSavedResearch] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savedLoadError, setSavedLoadError] = useState(false);
  const [savedLoadAttempt, setSavedLoadAttempt] = useState(0);
  const [hasNoSavedResearch, setHasNoSavedResearch] = useState(false);
  const researchInFlightRef = useRef(false);

  useEffect(() => {
    let ignore = false;

    async function loadSavedResearch() {
      setIsLoadingSavedResearch(true);

      try {
        const response = await fetch(apiUrl(`/profiles/${profileId}/treatment-options/saved`));
        if (ignore) return;

        if (!response.ok) {
          throw new Error(`Unable to check saved treatment research (HTTP ${response.status})`);
        }

        const data: SavedTreatmentResearchResponse = await response.json();
        if (ignore) return;
        setSavedLoadError(false);
        setHasNoSavedResearch(data.result === null);

        if (data.result) {
          setResearch(data.result);
        }
      } catch (error) {
        if (ignore) return;
        console.error(error);
        setSavedLoadError(true);
      } finally {
        if (!ignore) setIsLoadingSavedResearch(false);
      }
    }

    loadSavedResearch();
    return () => { ignore = true; };
  }, [profileId, savedLoadAttempt]);

  function retrySavedLoad() {
    setSavedLoadError(false);
    setHasNoSavedResearch(false);
    setIsLoadingSavedResearch(true);
    setSavedLoadAttempt((attempt) => attempt + 1);
  }

  async function researchTreatments() {
    if (researchInFlightRef.current) return;
    researchInFlightRef.current = true;
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(apiUrl(`/profiles/${profileId}/treatment-options`), { method: "POST" });

      if (!response.ok) {
        throw new Error("Unable to research treatment options");
      }

      const data: TreatmentResearchResponse = await response.json();

      setResearch(data.result);
    } catch (error) {
      console.error(error);

      setError("Unable to research treatment options. Please try again.");
    } finally {
      researchInFlightRef.current = false;
      setIsLoading(false);
    }
  }

  return (
    <section className="panel research-panel">
      <div className="research-hero">
        <div>
          <span className="eyebrow">AI treatment research</span>
          <h2>Treatment Research</h2>
          <p>
            Research treatment candidates based on this skin profile, with
            rationale, tradeoffs, confidence, and evidence sources.
          </p>
        </div>

        {!research && hasNoSavedResearch && !isLoading && !isLoadingSavedResearch && !savedLoadError && !error && (
          <button className="button" onClick={researchTreatments}>
            Explore Treatment Options
          </button>
        )}
      </div>

      {isLoadingSavedResearch && (
        <div className="loading-card">
          <h3>Checking saved treatment research...</h3>
        </div>
      )}

      {savedLoadError && !isLoadingSavedResearch && (
        <div className="error-card">
          <p>Saved treatment research could not be checked. Make sure the backend is running and try again.</p>
          <button className="button" onClick={retrySavedLoad}>Retry</button>
        </div>
      )}

      {isLoading && (
        <div className="loading-card">
          <h3>Researching treatment options...</h3>

          <ul className="loading-list">
            <li>Reviewing dermatology guidance</li>
            <li>Comparing profile characteristics</li>
            <li>Evaluating treatment tradeoffs</li>
            <li>Building treatment candidates</li>
          </ul>
        </div>
      )}

      {error && (
        <div className="error-card">
          <p>{error}</p>

          <button className="button" onClick={researchTreatments}>
            Try Again
          </button>
        </div>
      )}

      {research && (
        <div className="section">
          <div className="section-header">
            <div>
              <h3>Treatment Options</h3>
              <p>
                {research.options.length} candidates saved for this profile.
              </p>
            </div>
          </div>

          <div className="treatment-list">
            {research.options.map((option, index) => (
              <TreatmentOptionCard key={index} option={option} />
            ))}
          </div>
        </div>
      )}

      <p className="disclaimer">
        Treatment research is informational and does not replace care from a
        licensed medical professional. Confirm prescriptions, contraindications,
        and care plans with a clinician.
      </p>
    </section>
  );
}
