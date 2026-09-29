"use client";

import { useEffect, useState } from "react";

import ProfileForm from "./ProfileForm";
import ProfileList, { type ProfileListStatus } from "./ProfileList";

import type { ApiSkinProfile, SkinProfile } from "@/types/SkinProfile";
import { apiUrl } from "@/lib/api";
import { normalizeProfile } from "@/lib/profiles";

export default function ProfileManager() {
  const [profiles, setProfiles] = useState<SkinProfile[]>([]);
  const [status, setStatus] = useState<ProfileListStatus>("loading");
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function loadProfiles() {
      try {
        const response = await fetch(apiUrl("/profiles"));
        if (!response.ok) throw new Error(`Unable to load profiles (${response.status})`);

        const data: ApiSkinProfile[] = await response.json();
        if (ignore) return;
        setProfiles(data.map(normalizeProfile));
        setStatus("ready");
      } catch (error) {
        if (ignore) return;
        console.error("Failed to load profiles", error);
        setStatus("error");
      }
    }

    loadProfiles();
    return () => { ignore = true; };
  }, [loadAttempt]);

  function retry() {
    setStatus("loading");
    setLoadAttempt((attempt) => attempt + 1);
  }

  return (
    <div className="profile-manager">
      <ProfileList profiles={profiles} status={status} onRetry={retry} />

      <ProfileForm onProfileCreated={() => setLoadAttempt((attempt) => attempt + 1)} />
    </div>
  );
}
