import type { SkinMetricName } from "@/types/SkinProfile";

// Metric labels for new UI; keep these aligned with backend metric names.
export const METRIC_LABELS: Record<SkinMetricName, string> = {
  inflammatory_acne: "Inflammatory Acne",
  cystic_nodular_acne: "Cystic / Nodular Acne",
  blackheads: "Blackheads",
  whiteheads: "Whiteheads",
  pie: "PIE",
  pih: "PIH",
  redness: "Redness",
  rosacea: "Rosacea",
  dryness: "Dryness",
  sensitivity: "Sensitivity",
  irritation: "Irritation",
  oiliness: "Oiliness",
  texture_irregularity: "Texture Irregularity",
  acne_scarring: "Acne Scarring",
  enlarged_pores: "Enlarged Pores",
  dark_circles: "Dark Circles",
  uneven_skin_tone: "Uneven Skin Tone",
};
