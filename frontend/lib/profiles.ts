import type { ApiSkinProfile, SkinProfile } from "@/types/SkinProfile";

/**
 * Turn a raw profile row from the backend into a SkinProfile.
 *
 * The only difference between the two shapes is `cystic_nodular_acne`, which
 * can be NULL on profile rows created before that column was added. Reading it
 * as 0 matches what the backend already does when it builds the research
 * prompt (`profile.get("cystic_nodular_acne", 0)` in
 * services/treatment_research.py).
 *
 * Doing it here — at the single boundary where API JSON becomes application
 * state — means no component has to remember the legacy case, and the
 * SkinProfile type can stay honest about what a profile contains.
 */
export function normalizeProfile(raw: ApiSkinProfile): SkinProfile {
  return {
    ...raw,
    cystic_nodular_acne: raw.cystic_nodular_acne ?? 0,
  };
}
