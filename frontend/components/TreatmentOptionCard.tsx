"use client";

import { useState } from "react";

import type { TreatmentOption } from "@/types/TreatmentResearch";

interface TreatmentOptionCardProps { option: TreatmentOption; }

export default function TreatmentOptionCard({ option, }: TreatmentOptionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const confidenceLabel = `${option.confidence} confidence`;

  return (
    <article className="treatment-card">
      <div className="treatment-card-header">
        <div>
          <h3>{option.treatment_name}</h3>

          <div className="badge-row">
            <span className="badge primary">{option.treatment_type}</span>
            <span className={option.prescription_required ? "badge warning" : "badge"}>
              {option.prescription_required
                ? "Prescription required"
                : "Non-prescription"}
            </span>
            <span className="badge">{confidenceLabel}</span>
          </div>
        </div>

        <button className="button secondary" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? "Hide Details" : "View Details"}
        </button>
      </div>

      <div className="why-fit">
        <h4>Why it may fit</h4>
        <p>{option.why_it_may_fit}</p>
      </div>

      {isExpanded && (
        <div>
          <div className="details-grid">
            <div>
              <h4>Benefits</h4>

              <ul className="detail-list">
                {option.key_benefits.map((benefit, index) => (
                  <li key={index}>{benefit}</li>
                ))}
              </ul>
            </div>

            <div>
              <h4>Risks / limitations</h4>

              <ul className="detail-list">
                {option.key_risks.map((risk, index) => (
                  <li key={index}>{risk}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="evidence-list">
            <h4>Evidence</h4>

            {option.evidence_sources.map((source, index) => (
              <div className="evidence-card" key={index}>
                <p className="meta">{source.source_name}</p>

                <p>{source.title}</p>

                <a href={source.url} target="_blank" rel="noopener noreferrer">
                  View source
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}
