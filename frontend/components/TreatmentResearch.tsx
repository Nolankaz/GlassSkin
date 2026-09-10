"use client";

import { useEffect, useState } from "react";

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

  useEffect(() => {
    async function loadSavedResearch() {
      setIsLoadingSavedResearch(true);

      try {
        const response = await fetch(apiUrl(`/profiles/${profileId}/treatment-options/saved`));

        if (!response.ok) {
          return;
        }

        const data: SavedTreatmentResearchResponse = await response.json();

        if (data.result) {
          setResearch(data.result);
        }
      } catch (error) {
        console.error(error);
      } finally {
        setIsLoadingSavedResearch(false);
      }
    }

    loadSavedResearch();
  }, [profileId]);

  async function researchTreatments() {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(apiUrl(`/profiles/${profileId}/treatment-options`));

      if (!response.ok) {
        throw new Error("Unable to research treatment options");
      }

      const data: TreatmentResearchResponse = await response.json();

      setResearch(data.result);
    } catch (error) {
      console.error(error);

      setError("Unable to research treatment options. Please try again.");
    } finally {
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

        {!research && !isLoading && !isLoadingSavedResearch && !error && (
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
