# GlassSkinAI

A digital skin-profile system that turns a structured self-assessment into
evidence-grounded treatment research, and — as the project continues — into a
probabilistic simulation of how those treatments might play out over time.

> **Not medical advice.** Every output is informational. Treatment decisions
> belong to a licensed clinician.

---

## Current capabilities

What actually works today, end to end:

- **Create a digital skin profile.** 17 skin-concern metrics scored 0–10
  (acne, pigmentation, redness, barrier, texture, other), plus name, age and
  gender. Validated by Pydantic on the way in and persisted to Supabase.
- **List and open profiles.** A profile list on the home page, and a detail
  page per profile with the metrics grouped and rendered as bars.
- **Edit a profile.** The detail page sends a partial `PATCH` containing only
  the fields that actually changed.
- **AI treatment research.** The backend sends the profile to OpenAI's
  Responses API with web search restricted to a fixed allowlist of medical
  domains (PubMed/NCBI, NIH, FDA, ClinicalTrials.gov, AAD, NICE) and parses
  the reply into a strict `TreatmentResearchResult` schema — up to five
  options, each with rationale, benefits, risks, prescription flag,
  confidence, and source URLs.
- **Structured treatment UI.** Expandable cards with badges for treatment
  type, prescription requirement and confidence, plus linked evidence.
- **Cached research.** Results are stored in Supabase keyed by profile and
  `research_version`. Reopening a profile shows saved research instantly
  instead of paying for a second model call. Editing a profile invalidates
  its cache so the research cannot silently describe a stale profile.

## Planned direction

Treatment **simulation** is the next major subsystem: represent skin as a
state vector that evolves over time, model treatment effects with delay,
magnitude and uncertainty, run many randomized trajectories, and compare
treatments on outcome distributions rather than single predictions. After
that: cost/constraint filtering, and image-derived skin features.

See `plans/` for the day-by-day roadmap.

---

## Architecture

```
┌──────────────────────────── frontend (Next.js 16, React 19) ────────────────────────────┐
│  app/page.tsx ──────────── ProfileManager ──┬── ProfileList                             │
│                                             └── ProfileForm ── SkinMetricInput          │
│                                                                                          │
│  app/profiles/[id]/page.tsx ────────────────┬── SkinMetricBar / SkinMetricInput         │
│                                             └── TreatmentResearch ── TreatmentOptionCard│
│                                                                                          │
│  lib/api.ts  →  API_BASE_URL (NEXT_PUBLIC_API_URL)                                      │
└──────────────────────────────────────────┬───────────────────────────────────────────────┘
                                           │  fetch() — plain JSON over HTTP, CORS-allowed
                                           ▼
┌──────────────────────────── backend (FastAPI, Python 3.13) ─────────────────────────────┐
│  main.py        routes + orchestration                                                   │
│  schemas.py     Pydantic request/response models (the API contract)                      │
│  models.py      SkinProfile domain object                                                │
│  database.py    Supabase client singleton                                                │
│  services/treatment_research.py   prompt, domain allowlist, OpenAI call, RESEARCH_VERSION│
└───────────────┬──────────────────────────────────────────────┬───────────────────────────┘
                │                                              │
                ▼                                              ▼
       Supabase (Postgres)                           OpenAI Responses API
       skin_profiles                                 gpt-5-mini + web_search
       treatment_research_results                    (allowed_domains filter)
```

**Request flow for treatment research** (the most interesting path in the app):

1. `TreatmentResearch.tsx` mounts and calls
   `GET /profiles/{id}/treatment-options/saved`. If a cached result exists it
   renders immediately — no model call, no cost.
2. Otherwise the user clicks *Explore Treatment Options*, which calls
   `GET /profiles/{id}/treatment-options`.
3. The backend loads the profile from Supabase, re-checks the cache, and on a
   miss calls `generate_treatment_options()`.
4. `services/treatment_research.py` flattens the profile into a text block,
   sends it to the Responses API with `text_format=TreatmentResearchResult`,
   and OpenAI returns JSON that is *guaranteed* to match that Pydantic schema.
5. The result is written to `treatment_research_results` with the current
   `RESEARCH_VERSION` and returned to the browser.

**Why `research_version` exists:** it is a cache-busting key. Change the
prompt, model or output schema, bump the constant, and every previously
cached row stops matching the read query — old research is neither served nor
destroyed.

---

## Tech stack

| Layer      | Choice                                                          |
| ---------- | --------------------------------------------------------------- |
| Frontend   | Next.js 16 (App Router, Turbopack, React Compiler), React 19, TypeScript 5 (strict) |
| Styling    | Hand-written CSS custom properties + component classes in `app/globals.css`; Tailwind v4 is installed and imported but barely used |
| Backend    | FastAPI 0.141, Python 3.13, Pydantic v2                          |
| Database   | Supabase (Postgres) via `supabase-py` / PostgREST                |
| AI         | OpenAI Responses API (`gpt-5-mini`) with structured outputs and domain-filtered web search |
| Planned    | NumPy for the simulation engine; PyTorch later if a learned model earns its place |

---

## Project structure

```
GlassSkin/
├── README.md                       ← you are here
├── .gitignore
├── backend/
│   ├── main.py                     FastAPI app: routes, CORS, cache orchestration
│   ├── schemas.py                  Pydantic models — the HTTP + AI output contract
│   ├── models.py                   SkinProfile domain object
│   ├── database.py                 Supabase client created from env vars
│   ├── services/
│   │   └── treatment_research.py   OpenAI prompt, allowlist, RESEARCH_VERSION
│   ├── schema.sql                  Live Supabase schema, verified by query — see file header
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                        (git-ignored — real secrets)
├── frontend/
│   ├── app/                        App Router pages
│   ├── components/                 Client components
│   ├── types/                      TS mirrors of the Pydantic schemas
│   ├── lib/api.ts                  Backend base URL
│   └── .env.local.example
└── plans/                          Development roadmap + per-day implementation plans
```

---

## Local setup

Prerequisites: Python 3.13, Node.js 22+, and a Supabase project.

### 1. Supabase

`backend/schema.sql` documents the live schema. Its VERIFIED LIVE SCHEMA
section was transcribed from read-only queries against the project; its
UNVERIFIED section lists what those queries did not establish, with the query
to resolve each. Do not run the file blind against a fresh project — the
identity definitions, the foreign key's ON DELETE action and one CHECK
expression are still unverified. The two tables are:

| Table                        | Purpose                                                        |
| ---------------------------- | -------------------------------------------------------------- |
| `skin_profiles`              | One row per digital skin profile: `id`, `created_at`, `name`, `age`, `gender`, and the 17 metric columns. |
| `treatment_research_results` | Cached AI research: `id`, `created_at`, `profile_id` (foreign key; referenced column unverified), `research_version`, `result` (`jsonb`). |

Row Level Security is enabled on both tables (verified). The policies behind
it have not been inspected, and the backend connects with a privileged server
key, so do not treat RLS as currently providing user isolation — that is
Day 20's job. See the RLS notes in `schema.sql`.

### 2. Backend

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp .env.example .env      # then fill in real values
./.venv/bin/uvicorn main:app --reload
```

Runs on **http://127.0.0.1:8000**. Interactive API docs at
http://127.0.0.1:8000/docs — FastAPI generates them from the Pydantic
schemas, which makes it the fastest way to exercise an endpoint without the
frontend.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on **http://localhost:3000**. The backend's CORS middleware allows
`localhost:3000` and `127.0.0.1:3000` only; add any new origin to
`allow_origins` in `backend/main.py`.

---

## Environment variables

Never commit real values. `backend/.env` and `frontend/.env.local` are
git-ignored; the `.example` files next to them are the committed templates.

### `backend/.env`

| Variable         | Purpose                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| `SUPABASE_URL`   | Project URL, e.g. `https://<ref>.supabase.co`.                           |
| `SUPABASE_KEY`   | API key used for every database call. There is no end-user auth yet, so this key is the only access control that exists. |
| `OPENAI_API_KEY` | Read at import time by `services/treatment_research.py`; the module raises at startup if it is missing. Every cache miss costs money. |

### `frontend/.env.local`

| Variable              | Purpose                                                                |
| --------------------- | ---------------------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL` | Backend origin. Optional locally — `lib/api.ts` falls back to `http://127.0.0.1:8000`. `NEXT_PUBLIC_` values are inlined into the browser bundle, so never put a secret behind that prefix. |

---

## API

Base URL `http://127.0.0.1:8000`. No authentication.

| Method  | Path                                          | Description                                                                 |
| ------- | --------------------------------------------- | --------------------------------------------------------------------------- |
| `GET`   | `/`                                           | Health check.                                                                |
| `GET`   | `/profiles`                                   | All profiles.                                                                |
| `GET`   | `/profiles/{id}`                              | One profile; `404` if missing.                                               |
| `POST`  | `/profile`                                    | Create a profile from a `SkinProfileRequest`; returns the inserted row.      |
| `PATCH` | `/profiles/{id}`                              | Partial update (`SkinProfileUpdate`, `exclude_unset`). Also deletes that profile's cached research. `404` if missing. |
| `GET`   | `/profiles/{id}/treatment-options/saved`      | Cached research only. `result` is `null` on a miss — never calls OpenAI.     |
| `GET`   | `/profiles/{id}/treatment-options`            | Returns cached research, or generates and caches it. `404` unknown profile, `502` if research fails. |

Full schemas, including every field of `TreatmentOption`, are browsable at
`/docs`.

---

## Development workflow

```bash
# Backend
cd backend
./.venv/bin/uvicorn main:app --reload
./.venv/bin/python -m compileall -q .     # syntax check

# Frontend
cd frontend
npm run dev
npm run lint
npx tsc --noEmit
npm run build
```

There is **no automated test suite yet**. Adding one to the backend is
scheduled early in the roadmap — it is the main thing standing between the
current app and safe refactoring.

---

## Current project status

Days 1–7 of the roadmap are complete: full-stack profile CRUD, Supabase
persistence, structured AI treatment research, and research caching.

Known gaps, in rough order of how much they will hurt later:

1. **`frontend/` is a separate git repository whose application code is not
   committed anywhere.** The outer repo stores only a gitlink to the original
   `create-next-app` commit; `components/`, `types/` and `app/profiles/` are
   untracked. Fix this before writing another line of frontend code.
2. No tests, so nothing catches a regression.
3. No authentication. RLS is enabled on both tables (verified), but its
   policies are uninspected and the backend uses a privileged server key, so
   user isolation is unestablished. Scheduled for Day 20.
4. `GET /profiles/{id}/treatment-options` has side effects (spends money,
   writes rows) and has no concurrency guard.
5. Frontend and backend types are mirrored by hand and have already drifted.

See `plans/glassSkin_revised_roadmap.md` for how these are sequenced.
