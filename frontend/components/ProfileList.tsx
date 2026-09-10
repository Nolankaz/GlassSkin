"use client";

import Link from "next/link";
import type { SkinProfile } from "@/types/SkinProfile";

type ProfileListProps = {
  profiles: SkinProfile[];
};

const summaryMetrics = [
  ["Acne", "inflammatory_acne"],
  ["Redness", "redness"],
  ["Dryness", "dryness"],
  ["Oiliness", "oiliness"],
] as const;

export default function ProfileList({ profiles }: ProfileListProps) {
  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Profiles</span>
          <h2>Your Skin Profiles</h2>
        </div>
      </div>

      {profiles.length === 0 && (
        <div className="empty-state">
          Create your first skin profile to begin treatment research.
        </div>
      )}

      <div className="profile-list">
        {profiles.map((profile) => (
          <article className="profile-card" key={profile.id}>
            <div className="profile-card-top">
              <div>
                <Link href={`/profiles/${profile.id}`}>
                  <h3>{profile.name}</h3>
                </Link>
                <p className="meta">
                  Age {profile.age}
                  {profile.gender ? ` • ${profile.gender}` : ""}
                </p>
              </div>

              <Link className="button ghost" href={`/profiles/${profile.id}`}>
                View Profile
              </Link>
            </div>

            <div className="metric-chip-grid">
              {summaryMetrics.map(([label, key]) => (
                <div className="metric-chip" key={key}>
                  <span>{label}</span>
                  <strong>{profile[key]}/10</strong>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
