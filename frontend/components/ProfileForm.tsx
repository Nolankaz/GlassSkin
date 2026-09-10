"use client";

import { useState } from "react";
import SkinMetricInput from "./SkinMetricInput";
import { apiUrl } from "@/lib/api";
import { normalizeProfile } from "@/lib/profiles";
import type { ApiSkinProfile, SkinProfile } from "@/types/SkinProfile";

type ProfileFormProps = {
  onProfileCreated?: () => void;
};

export default function ProfileForm({ onProfileCreated }: ProfileFormProps) {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("Not specified");

  // Acne / clogged pores
  const [inflammatoryAcne, setInflammatoryAcne] = useState(0);
  const [cysticNodularAcne, setCysticNodularAcne] = useState(0);
  const [blackheads, setBlackheads] = useState(0);
  const [whiteheads, setWhiteheads] = useState(0);

  // Post-acne marks / pigmentation
  const [pie, setPie] = useState(0);
  const [pih, setPih] = useState(0);

  // Redness / inflammation
  const [redness, setRedness] = useState(0);
  const [rosacea, setRosacea] = useState(0);

  // Skin barrier / irritation
  const [dryness, setDryness] = useState(0);
  const [sensitivity, setSensitivity] = useState(0);
  const [irritation, setIrritation] = useState(0);

  // Oil production
  const [oiliness, setOiliness] = useState(0);

  // Texture / structural concerns
  const [textureIrregularity, setTextureIrregularity] = useState(0);
  const [acneScarring, setAcneScarring] = useState(0);

  // Other common concerns
  const [enlargedPores, setEnlargedPores] = useState(0);
  const [darkCircles, setDarkCircles] = useState(0);
  const [unevenSkinTone, setUnevenSkinTone] = useState(0);

  const [result, setResult] = useState<SkinProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generateProfile() {
    setError(null);

    try {
      const response = await fetch(apiUrl("/profile"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
          age: Number(age),
          gender: gender,

          inflammatory_acne: inflammatoryAcne,
          cystic_nodular_acne: cysticNodularAcne,
          blackheads: blackheads,
          whiteheads: whiteheads,

          pie: pie,
          pih: pih,

          redness: redness,
          rosacea: rosacea,

          dryness: dryness,
          sensitivity: sensitivity,
          irritation: irritation,

          oiliness: oiliness,

          texture_irregularity: textureIrregularity,
          acne_scarring: acneScarring,

          enlarged_pores: enlargedPores,
          dark_circles: darkCircles,
          uneven_skin_tone: unevenSkinTone,
        }),
      });

      if (!response.ok) {
        console.error("Failed to create profile");
        setError("Unable to create profile. Please check the backend logs.");
        return;
      }

      const data: ApiSkinProfile = await response.json();

      setResult(normalizeProfile(data));

      onProfileCreated?.();
    } catch (error) {
      console.error(error);
      setError("Unable to reach the backend. Make sure FastAPI is running.");
    }
  }

  const concernSections = [
    {
      title: "Acne / Clogged Pores",
      inputs: [
        { label: "Inflammatory Acne", value: inflammatoryAcne, onChange: setInflammatoryAcne },
        { label: "Cystic / Nodular Acne", value: cysticNodularAcne, onChange: setCysticNodularAcne },
        { label: "Blackheads", value: blackheads, onChange: setBlackheads },
        { label: "Whiteheads", value: whiteheads, onChange: setWhiteheads },
      ],
    },
    {
      title: "Post-Acne Marks / Pigmentation",
      inputs: [
        { label: "PIE", value: pie, onChange: setPie },
        { label: "PIH", value: pih, onChange: setPih },
      ],
    },
    {
      title: "Redness / Inflammation",
      inputs: [
        { label: "Redness", value: redness, onChange: setRedness },
      ],
    },
    {
      title: "Skin Barrier / Sensitivity",
      inputs: [
        { label: "Dryness", value: dryness, onChange: setDryness },
        { label: "Sensitivity", value: sensitivity, onChange: setSensitivity },
        { label: "Irritation", value: irritation, onChange: setIrritation },
        { label: "Oiliness", value: oiliness, onChange: setOiliness },
      ],
    },
    {
      title: "Texture / Structural Concerns",
      inputs: [
        { label: "Texture Irregularity", value: textureIrregularity, onChange: setTextureIrregularity },
        { label: "Acne Scarring", value: acneScarring, onChange: setAcneScarring },
      ],
    },
    {
      title: "Other Common Concerns",
      inputs: [
        { label: "Rosacea", value: rosacea, onChange: setRosacea },
        { label: "Enlarged Pores", value: enlargedPores, onChange: setEnlargedPores },
        { label: "Dark Circles", value: darkCircles, onChange: setDarkCircles },
        { label: "Uneven Skin Tone", value: unevenSkinTone, onChange: setUnevenSkinTone },
      ],
    },
  ];

  const resultSummary = result
    ? [
        ["Inflammatory Acne", result.inflammatory_acne],
        ["Cystic / Nodular Acne", result.cystic_nodular_acne],
        ["Blackheads", result.blackheads],
        ["Whiteheads", result.whiteheads],
        ["PIE", result.pie],
        ["PIH", result.pih],
        ["Redness", result.redness],
        ["Rosacea", result.rosacea],
        ["Dryness", result.dryness],
        ["Sensitivity", result.sensitivity],
        ["Irritation", result.irritation],
        ["Oiliness", result.oiliness],
        ["Texture Irregularity", result.texture_irregularity],
        ["Acne Scarring", result.acne_scarring],
        ["Enlarged Pores", result.enlarged_pores],
        ["Dark Circles", result.dark_circles],
        ["Uneven Skin Tone", result.uneven_skin_tone],
      ]
    : [];

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Assessment</span>
          <h2>Create Skin Profile</h2>
          <p>Score each concern from 0 to 10 to build a structured profile.</p>
        </div>
      </div>

      <div className="form-grid">
        <div className="field">
          <label>Profile Name</label>
          <input
            className="text-input"
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="My Skin"
          />
        </div>

        <div className="field">
          <label>Age</label>
          <input
            className="text-input"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            value={age}
            onChange={(event) => setAge(event.target.value)}
            placeholder="Enter age"
          />
        </div>

        <div className="field">
          <label>Gender</label>
          <select className="text-input" value={gender} onChange={(event) => setGender(event.target.value)}>
            <option value="Not specified">Not specified</option>
            <option value="Female">Female</option>
            <option value="Male">Male</option>
            <option value="Non-binary">Non-binary</option>
            <option value="Prefer not to say">Prefer not to say</option>
          </select>
        </div>
      </div>

      <div className="concern-grid section">
        {concernSections.map((section) => (
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
        <button className="button" onClick={generateProfile}>
          Generate Skin Profile
        </button>
      </div>

      {error && (
        <div className="error-card">
          <p>{error}</p>
        </div>
      )}

      {result && (
        <div className="notice section">
          <h3>Your Skin Profile</h3>
          <p>
            {result.name}, age {result.age}
            {result.gender ? `, ${result.gender}` : ""}
          </p>

          <div className="metric-chip-grid">
            {resultSummary.map(([label, value]) => (
              <div className="metric-chip" key={label}>
                <span>{label}</span>
                <strong>{value}/10</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
