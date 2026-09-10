export type ConfidenceLevel = "low" | "moderate" | "high";

export type TreatmentType = "topical" | "oral" | "procedural" | "skincare" | "other";

export interface EvidenceSource {
  title: string;
  url: string;
  source_name: string;
}

export interface TreatmentOption {
  treatment_name: string;
  treatment_type: TreatmentType;
  why_it_may_fit: string;
  prescription_required: boolean;
  key_benefits: string[];
  key_risks: string[];
  evidence_sources: EvidenceSource[];
  confidence: ConfidenceLevel;
}

export interface TreatmentResearchResult {
  options: TreatmentOption[];
}

export interface TreatmentResearchResponse {
  profile_id: number;
  result: TreatmentResearchResult;
  research_version: string;
}

export interface SavedTreatmentResearchResponse {
  profile_id: number;
  result: TreatmentResearchResult | null;
  research_version: string;
}
