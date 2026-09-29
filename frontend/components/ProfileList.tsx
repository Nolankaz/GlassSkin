"use client";

import Link from "next/link";
import type { SkinProfile } from "@/types/SkinProfile";

export type ProfileListStatus = "loading" | "error" | "ready";

type ProfileListProps = {
  profiles: SkinProfile[];
  status: ProfileListStatus;
  onRetry: () => void;
};

const summaryMetrics = [
  ["Acne", "inflammatory_acne"],
  ["Redness", "redness"],
  ["Dryness", "dryness"],
  ["Oiliness", "oiliness"],
] as const;

export default function ProfileList({ profiles, status, onRetry }: ProfileListProps) {
  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Profiles</span>
          <h2>Your Skin Profiles</h2>
        </div>
      </div>

      {status === "loading" && <div className="loading-card">Loading profiles...</div>}

      {status === "error" && (
        <div className="error-card">
          <p>Unable to load profiles. Check that the backend is running and try again.</p>
          <button className="button" onClick={onRetry}>Retry</button>
        </div>
      )}

      {status === "ready" && profiles.length === 0 && (
        <div className="empty-state">
          Create your first skin profile to begin treatment research.
        </div>
      )}

      {status === "ready" && profiles.length > 0 && <div className="profile-list">
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
      </div>}
    </section>
  );
}
