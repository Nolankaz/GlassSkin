"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { ApiSkinProfile, SkinProfile } from "@/types/SkinProfile";
import Link from "next/link";
import SkinMetricBar from "@/components/SkinMetricBar";
import SkinMetricInput from "@/components/SkinMetricInput";
import TreatmentResearch from "@/components/TreatmentResearch";
import { apiUrl } from "@/lib/api";
import { normalizeProfile } from "@/lib/profiles";

export default function ProfilePage() {
  const params = useParams();
  const id = params.id;

  const [profile, setProfile] = useState<SkinProfile | null>(null);

  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [treatmentResearchKey, setTreatmentResearchKey] = useState(0);
  const [editGender, setEditGender] = useState("Not specified");

  const [editInflammatoryAcne, setEditInflammatoryAcne] = useState(0);
  const [editCysticNodularAcne, setEditCysticNodularAcne] = useState(0);
  const [editBlackheads, setEditBlackheads] = useState(0);
  const [editWhiteheads, setEditWhiteheads] = useState(0);

  const [editPie, setEditPie] = useState(0);
  const [editPih, setEditPih] = useState(0);
  
  const [editRedness, setEditRedness] = useState(0);
  const [editRosacea, setEditRosacea] = useState(0);
  
  const [editDryness, setEditDryness] = useState(0);
  const [editOiliness, setEditOiliness] = useState(0);
  const [editSensitivity, setEditSensitivity] = useState(0);
  const [editIrritation, setEditIrritation] = useState(0);

  const [editTextureIrregularity, setEditTextureIrregularity] = useState(0);
  const [editAcneScarring, setEditAcneScarring] = useState(0);
  const [editEnlargedPores, setEditEnlargedPores] = useState(0);

  const [editDarkCircles, setEditDarkCircles] = useState(0);
  const [editUnevenSkinTone, setEditUnevenSkinTone] = useState(0);

  function startEditing() {
    if (!profile) return;

    setEditError(null);
    setEditGender(profile.gender ?? "Not specified");

    setEditInflammatoryAcne(profile.inflammatory_acne);
    setEditCysticNodularAcne(profile.cystic_nodular_acne);
    setEditBlackheads(profile.blackheads);
    setEditWhiteheads(profile.whiteheads);

    setEditPie(profile.pie);
    setEditPih(profile.pih);
    setEditRedness(profile.redness);

    setEditRosacea(profile.rosacea);

    setEditDryness(profile.dryness);
    setEditSensitivity(profile.sensitivity);
    setEditIrritation(profile.irritation);

    setEditOiliness(profile.oiliness);

    setEditTextureIrregularity(profile.texture_irregularity);
    setEditAcneScarring(profile.acne_scarring);
    setEditEnlargedPores(profile.enlarged_pores);

    setEditDarkCircles(profile.dark_circles);
    setEditUnevenSkinTone(profile.uneven_skin_tone);

    setIsEditing(true);
  }

  async function saveChanges() {
    if (!profile) return;

    setEditError(null);

    const updateData: Record<string, string | number> = {};

    if (editGender !== (profile.gender ?? "Not specified")) {
      updateData.gender = editGender;
    }

    if (editInflammatoryAcne !== profile.inflammatory_acne) {
      updateData.inflammatory_acne = editInflammatoryAcne;
    }

    if (editCysticNodularAcne !== profile.cystic_nodular_acne) {
      updateData.cystic_nodular_acne = editCysticNodularAcne;
    }

    if (editBlackheads !== profile.blackheads) {
      updateData.blackheads = editBlackheads;
    }

    if (editWhiteheads !== profile.whiteheads) {
      updateData.whiteheads = editWhiteheads;
    }

    if (editPie !== profile.pie) {
      updateData.pie = editPie;
    }

    if (editPih !== profile.pih) {
      updateData.pih = editPih;
    }

    if (editRedness !== profile.redness) {
      updateData.redness = editRedness;
    }

    if (editRosacea !== profile.rosacea) {
      updateData.rosacea = editRosacea;
    }

    if (editDryness !== profile.dryness) {
      updateData.dryness = editDryness;
    }

    if (editSensitivity !== profile.sensitivity) {
      updateData.sensitivity = editSensitivity;
    }

    if (editIrritation !== profile.irritation) {
      updateData.irritation = editIrritation;
    }

    if (editOiliness !== profile.oiliness) {
      updateData.oiliness = editOiliness;
    }

    if (editTextureIrregularity !== profile.texture_irregularity) {
      updateData.texture_irregularity = editTextureIrregularity;
    }

    if (editAcneScarring !== profile.acne_scarring) {
      updateData.acne_scarring = editAcneScarring;
    }

    if (editEnlargedPores !== profile.enlarged_pores) {
      updateData.enlarged_pores = editEnlargedPores;
    }

    if (editDarkCircles !== profile.dark_circles) {
      updateData.dark_circles = editDarkCircles;
    }

    if (editUnevenSkinTone !== profile.uneven_skin_tone) {
      updateData.uneven_skin_tone = editUnevenSkinTone;
    }

    if (Object.keys(updateData).length === 0) {
      setIsEditing(false);
      return;
    }

    const response = await fetch(apiUrl(`/profiles/${profile.id}`), {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(updateData),
    });

    if (!response.ok) {
      console.error("Failed to update profile");
      setEditError("Unable to save profile changes. Please check the backend logs.");
      return;
    }

    const updatedProfile: ApiSkinProfile = await response.json();

    setProfile(normalizeProfile(updatedProfile));
    setIsEditing(false);
    setTreatmentResearchKey((key) => key + 1);
  }

  useEffect(() => {
    async function fetchProfile() {
      const response = await fetch(apiUrl(`/profiles/${id}`));

      if (!response.ok) {
        console.error("Failed to load profile");
        return;
      }

      const data: ApiSkinProfile = await response.json();

      setProfile(normalizeProfile(data));
    }

    if (id) {
      fetchProfile();
    }
  }, [id]);

  if (!profile) {
    return (
      <main className="app-shell">
        <div className="loading-card">Loading profile...</div>
      </main>
    );
  }

  const viewSections = [
    {
      title: "Acne / Clogged Pores",
      metrics: [
        ["Inflammatory Acne", profile.inflammatory_acne],
        ["Cystic / Nodular Acne", profile.cystic_nodular_acne],
        ["Blackheads", profile.blackheads],
        ["Whiteheads", profile.whiteheads],
      ],
    },
    {
      title: "Pigmentation / Red Marks",
      metrics: [
        ["PIE", profile.pie],
        ["PIH", profile.pih],
        ["Redness", profile.redness],
      ],
    },
    {
      title: "Skin Barrier / Sensitivity",
      metrics: [
        ["Dryness", profile.dryness],
        ["Sensitivity", profile.sensitivity],
        ["Irritation", profile.irritation],
        ["Oiliness", profile.oiliness],
      ],
    },
    {
      title: "Texture / Scarring / Pores",
      metrics: [
        ["Texture Irregularity", profile.texture_irregularity],
        ["Acne Scarring", profile.acne_scarring],
        ["Enlarged Pores", profile.enlarged_pores],
      ],
    },
    {
      title: "Other Concerns",
      metrics: [
        ["Rosacea", profile.rosacea],
        ["Dark Circles", profile.dark_circles],
        ["Uneven Skin Tone", profile.uneven_skin_tone],
      ],
    },
  ] as const;

  const editSections = [
    {
      title: "Acne / Clogged Pores",
      inputs: [
        { label: "Inflammatory Acne", value: editInflammatoryAcne, onChange: setEditInflammatoryAcne },
        { label: "Cystic / Nodular Acne", value: editCysticNodularAcne, onChange: setEditCysticNodularAcne },
        { label: "Blackheads", value: editBlackheads, onChange: setEditBlackheads },
        { label: "Whiteheads", value: editWhiteheads, onChange: setEditWhiteheads },
      ],
    },
    {
      title: "Pigmentation / Red Marks",
      inputs: [
        { label: "PIE", value: editPie, onChange: setEditPie },
        { label: "PIH", value: editPih, onChange: setEditPih },
        { label: "Redness", value: editRedness, onChange: setEditRedness },
      ],
    },
    {
      title: "Skin Barrier / Sensitivity",
      inputs: [
        { label: "Dryness", value: editDryness, onChange: setEditDryness },
        { label: "Sensitivity", value: editSensitivity, onChange: setEditSensitivity },
        { label: "Irritation", value: editIrritation, onChange: setEditIrritation },
        { label: "Oiliness", value: editOiliness, onChange: setEditOiliness },
      ],
    },
    {
      title: "Texture / Scarring / Pores",
      inputs: [
        { label: "Texture Irregularity", value: editTextureIrregularity, onChange: setEditTextureIrregularity },
        { label: "Acne Scarring", value: editAcneScarring, onChange: setEditAcneScarring },
        { label: "Enlarged Pores", value: editEnlargedPores, onChange: setEditEnlargedPores },
      ],
    },
    {
      title: "Other Concerns",
      inputs: [
        { label: "Rosacea", value: editRosacea, onChange: setEditRosacea },
        { label: "Dark Circles", value: editDarkCircles, onChange: setEditDarkCircles },
        { label: "Uneven Skin Tone", value: editUnevenSkinTone, onChange: setEditUnevenSkinTone },
      ],
    },
  ];

  return (
    <main className="app-shell">
      <Link className="back-link" href="/">
        ← Back to profiles
      </Link>

      <section className="profile-hero">
        <div>
          <span className="eyebrow">Skin profile</span>
          <h1>{profile.name}</h1>
          <p className="lead">
            Age {profile.age}
            {profile.gender ? ` • ${profile.gender}` : ""}
          </p>
        </div>

        <button className="button secondary" onClick={startEditing}>
          Edit Profile
        </button>
      </section>

      {isEditing && (
        <section className="panel edit-panel section">
          <div className="section-header">
            <div>
              <span className="eyebrow">Editing</span>
              <h2>Edit Profile Metrics</h2>
              <p>Adjust the profile values, then save or cancel your edits.</p>
            </div>
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Gender</label>
              <select className="text-input" value={editGender} onChange={(event) => setEditGender(event.target.value)}>
                <option value="Not specified">Not specified</option>
                <option value="Female">Female</option>
                <option value="Male">Male</option>
                <option value="Non-binary">Non-binary</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
            </div>
          </div>

          <div className="concern-grid section">
            {editSections.map((section) => (
              <div className="concern-section" key={section.title}>
                <h3>{section.title}</h3>

                {section.inputs.map((input) => (
                  <SkinMetricInput
                    key={input.label}
                    label={input.label}
                    value={input.value}
                    onChange={input.onChange}
                  />
                ))}
              </div>
            ))}
          </div>

          <div className="button-row">
            <button className="button" onClick={saveChanges}>
              Save Changes
            </button>

            <button className="button secondary" onClick={() => setIsEditing(false)}>
              Cancel
            </button>
          </div>

          {editError && (
            <div className="error-card">
              <p>{editError}</p>
            </div>
          )}
        </section>
      )}

      {!isEditing && (
        <section className="panel section">
          <div className="section-header">
            <div>
              <span className="eyebrow">Profile overview</span>
              <h2>Skin Concern Map</h2>
              <p>Grouped scores make the profile easier to scan before research.</p>
            </div>
          </div>

          <div className="profile-grid">
            {viewSections.map((section) => (
              <div className="concern-section" key={section.title}>
                <h3>{section.title}</h3>

                {section.metrics.map(([label, value]) => (
                  <SkinMetricBar key={label} label={label} value={value} />
                ))}
              </div>
            ))}
          </div>
        </section>
      )}

      {!isEditing && (
        <TreatmentResearch key={treatmentResearchKey} profileId={profile.id} />
      )}
    </main>
  );
}
