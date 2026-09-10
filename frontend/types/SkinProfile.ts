/**
 * A skin profile as the rest of the app is allowed to assume it looks.
 *
 * `cystic_nodular_acne` is REQUIRED here because the backend requires it:
 * SkinProfileRequest in backend/schemas.py declares it `int` with no default,
 * so every profile created through POST /profile has a value.
 *
 * Rows written before that column existed can still hold NULL (see the note on
 * the column in backend/schema.sql). That is a property of the raw API payload,
 * not of a profile, so it is described by ApiSkinProfile below and resolved
 * once by normalizeProfile() in lib/profiles.ts — never by weakening this type.
 */
export type SkinProfile = {
  id: number;
  name: string;
  age: number;
  gender?: string;

  inflammatory_acne: number;
  cystic_nodular_acne: number;
  blackheads: number;
  whiteheads: number;

  pie: number;
  pih: number;
  redness: number;

  rosacea: number;

  dryness: number;
  sensitivity: number;
  irritation: number;

  oiliness: number;

  texture_irregularity: number;
  acne_scarring: number;
  enlarged_pores: number;

  dark_circles: number;
  uneven_skin_tone: number;
};

/**
 * A profile exactly as the backend returns it.
 *
 * Derived from SkinProfile rather than written out again, so the 17 metric
 * names stay in one place: only the one field whose nullability differs is
 * restated. Use this as the type of `await response.json()`, then pass it
 * through normalizeProfile() before it reaches component state.
 */
export type ApiSkinProfile = Omit<SkinProfile, "cystic_nodular_acne"> & {
  cystic_nodular_acne: number | null;
};
