/**
 * Base URL of the FastAPI backend.
 *
 * Every component that talks to the backend imports this instead of hardcoding
 * a host, so that deploying the frontend is a matter of setting one
 * environment variable rather than editing component files.
 *
 * NEXT_PUBLIC_ prefixed variables are inlined into the client bundle at build
 * time, which is what makes them readable from "use client" components. That
 * also means they are public — never put a secret behind a NEXT_PUBLIC_ name.
 *
 * The fallback keeps `npm run dev` working with no .env.local file, matching
 * the default `uvicorn main:app --reload` address.
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** Build an absolute backend URL from a leading-slash path, e.g. "/profiles". */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
