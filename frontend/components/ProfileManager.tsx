"use client";

import { useEffect, useState } from "react";

import ProfileForm from "./ProfileForm";
import ProfileList from "./ProfileList";

import type { ApiSkinProfile, SkinProfile } from "@/types/SkinProfile";
import { apiUrl } from "@/lib/api";
import { normalizeProfile } from "@/lib/profiles";

export default function ProfileManager() {
  const [profiles, setProfiles] = useState<SkinProfile[]>([]);

  async function refreshProfiles() {
    const response = await fetch(apiUrl("/profiles"));

    if (!response.ok) {
      console.error("Failed to load profiles");
      return;
    }

    const data: ApiSkinProfile[] = await response.json();

    setProfiles(data.map(normalizeProfile));
  }

  useEffect(() => {
    async function loadInitialProfiles() {
      const response = await fetch(apiUrl("/profiles"));

      if (!response.ok) {
        console.error("Failed to load profiles");
        return;
      }

      const data: ApiSkinProfile[] = await response.json();

      setProfiles(data.map(normalizeProfile));
    }

    loadInitialProfiles();
  }, []);

  return (
    <div className="profile-manager">
      <ProfileList profiles={profiles} />

      <ProfileForm onProfileCreated={refreshProfiles} />
    </div>
  );
}
