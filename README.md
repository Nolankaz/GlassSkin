# GlassSkinAI

GlassSkinAI turns a structured 17-metric skin profile into evidence-sourced treatment research and calibrated simulation outcome ranges over time. Its current simulator shows how published-trial-based treatment effects vary across a simulated population.

> **Not medical advice.** Every output is informational. Treatment decisions
> belong to a licensed clinician.

## The problem

Skin treatment advice often reduces a changing response to a single point claim. A range over time shows how much simulated responses can differ under the same fixed treatment assumptions, without presenting one outcome as a personal forecast. Treatment options also need traceable medical sources so readers can inspect the evidence behind a rationale, benefit, or risk. GlassSkinAI pairs that research with a deliberately limited simulation whose calibration and disagreements with held-out evidence are visible.

## Features

- **Profiles:** Create, list, open, and partially edit profiles with 17 concern metrics scored 0–10.
- **AI treatment research:** Search an allowlist of medical domains and return structured options with linked evidence. Results are cached per profile and research version; changes to research-relevant profile fields invalidate the cache. Generation happens only after an explicit `POST /profiles/{id}/treatment-options` request.
- **Simulation:** Explore six calibrated treatments through p10/p50/p90 fan-chart ranges for the metrics each treatment affects. The UI shows citations, source links, parameter version, a low-baseline warning, and an “About this simulation” explanation.
- **Reliability:** Profile and research flows expose loading, empty, error-with-Retry, and not-found states where applicable.

<!-- Session 5 screenshots for docs/screenshots/: home; concern map; research cards; simulation chart with About open; mild/low-baseline warning. -->

## Architecture

```
┌──────────────────────────── frontend (Next.js 16, React 19) ─────────────────────────────┐
│  app/page.tsx ──────────── ProfileManager ──┬── ProfileList                              │
│                                             └── ProfileForm ── SkinMetricInput           │
│                                                                                          │
│  app/profiles/[id]/page.tsx ────────────────┬── SkinMetricBar / SkinMetricInput          │
│                                             ├── TreatmentResearch ── TreatmentOptionCard │
│                                             └── SimulationPanel ── TrajectoryChart       │
│                                                  └── SimulationAbout                     │
│  lib/api.ts  →  API_BASE_URL (NEXT_PUBLIC_API_URL)                                       │
└──────────────────────────────────────────┬───────────────────────────────────────────────┘
                                           │  fetch() — JSON over HTTP
                                           ▼
┌──────────────────────────── backend (FastAPI, Python 3.13) ──────────────────────────────┐
│  main.py: profile, treatment-research, and simulation routes                             │
│  schemas.py: Pydantic API contracts                  database.py: Supabase client        │
│                                                                                          │
│  Research: main.py ↔ Supabase profile/cache rows                                         │
│            main.py → services/treatment_research.py → OpenAI Responses API               │
│                                                       + allowlisted web search           │
│            Supabase: skin_profiles, treatment_research_results                           │
│                                                                                          │
│  Simulation API: GET /simulation/treatments                                              │
│                  GET /profiles/{profile_id}/simulations/{treatment_id}                   │
│              ↓ reads profile row from Supabase                                           │
│              services/treatment_simulation.py                                            │
│              ↓                                                                           │
│              pure simulation/ engine + profile_adapter + Monte Carlo                     │
│              ↑                                                                           │
│              packaged simulation/parameters/v1/*.json                                    │
│              (no OpenAI call; no Supabase write)                                         │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Treatment research request flow:**

1. `TreatmentResearch` loads `GET /profiles/{id}/treatment-options/saved`; a cache hit renders without a model call.
2. The user explicitly requests research with `POST /profiles/{id}/treatment-options`. The backend reads the profile and checks the current-version cache again.
3. On a miss, `services/treatment_research.py` searches allowlisted domains through the OpenAI Responses API, parses a structured `TreatmentResearchResult`, and best-effort caches it by profile and `RESEARCH_VERSION` before returning it.

**Simulation request flow:**

1. `SimulationPanel` loads the treatment catalogue, then requests a selected treatment's simulation for a saved profile. The backend reads that profile row from Supabase.
2. `simulation/profile_adapter.py` turns its 17 metrics into a `SkinState`; `services/treatment_simulation.py` loads packaged `v1` parameters and calls `simulate_many` with server-owned settings.
3. The API returns percentile bands only for metrics targeted by the treatment's effects. It recomputes the result without calling OpenAI or writing to Supabase.

## How the simulation works

- `SkinState` holds the 17 metric values at a moment in time. Provenance-bearing `TreatmentEffect` parameters define each affected metric, direction, magnitude, delay, uncertainty, and time curve.
- Time curves determine when an effect appears; the deterministic engine combines effects against the initial state at each time point and clamps metrics to 0–10.
- Monte Carlo runs 10,000 simulated patients with multiplicative log-normal response variation. The fan chart shows marginal p10, p50, and p90 bands at each time, representing simulated population ranges under fixed treatment assumptions, not an individual outcome.
- Six treatments have effects calibrated by least-squares fitting to published trial evidence. Every shipped effect coefficient carries provenance; only `inflammatory_acne` is currently calibrated, and `v1` parameters are frozen.
- Preregistered held-out week-12 comparisons disagreed with observed evidence: simulated mean improvement was about −7.97 percentage points for tretinoin and −7.78 for tazarotene relative to the reported means. These misses were reported without retuning `v1`.
- One-at-a-time sensitivity analysis and a baseline sweep probe model behavior; they do not establish clinical accuracy at other baselines. See the [simulation design](backend/SIMULATION_DESIGN.md), [validation report](backend/notes/validation/validation_report.md), and [notes index](backend/notes/README.md).

## Tech stack

| Layer      | Choice                                                          |
| ---------- | --------------------------------------------------------------- |
| Frontend   | Next.js 16 (App Router, Turbopack, React Compiler), React 19, TypeScript 5 (strict) |
| Styling    | Hand-written CSS custom properties + component classes in `app/globals.css`; Tailwind v4 is installed and imported but barely used |
| Backend    | FastAPI 0.141, Python 3.13, Pydantic v2                          |
| Database   | Supabase (Postgres) via `supabase-py` / PostgREST                |
| AI         | OpenAI Responses API (`gpt-5-mini`) with structured outputs and domain-filtered web search |
| Simulation | NumPy at runtime; SciPy and Matplotlib are development-only tools under `backend/notes/` |
| Tests      | pytest and FastAPI `TestClient`                                 |

---

## Local setup

Prerequisites for the full app: Python 3.13, Node.js 22+, a Supabase project, and an OpenAI API key. V1 is a local single-user demo.

### Supabase

[`backend/schema.sql`](backend/schema.sql) documents the current two-table schema; it is **not a runnable migration**. For a fresh project, configure both `id` columns as generated identity columns and add a foreign key from `treatment_research_results.profile_id` to `skin_profiles(id)`. The live identity kind, foreign-key target, and `ON DELETE` behavior remain unverified, so adapt the database setup rather than pasting the documented DDL as-is.

| Table | Purpose |
| --- | --- |
| `skin_profiles` | Profile identity, demographics, and the 17 concern metrics. |
| `treatment_research_results` | Versioned, structured treatment-research cache for a profile. |

RLS is enabled on both tables, but its policies and forced-RLS state have not been fully verified. The backend uses a privileged server key, so RLS must not be treated as proof of end-user isolation.

### Backend

From the repository root:

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
# Fill in the values in .env, then start the API from backend/:
./.venv/bin/uvicorn main:app --reload
```

`requirements-dev.txt` includes the runtime `requirements.txt` and adds pytest, SciPy, and Matplotlib for development. The API runs at `http://127.0.0.1:8000`; FastAPI's interactive API is at `http://127.0.0.1:8000/docs`.

### Frontend

From the repository root:

```bash
cd frontend
npm ci
# Optional when using a backend other than http://127.0.0.1:8000:
cp .env.local.example .env.local
npm run dev
```

The frontend runs at `http://localhost:3000`. Its `NEXT_PUBLIC_API_URL` setting is optional locally; the code defaults to `http://127.0.0.1:8000`. The backend currently permits the browser origins `http://localhost:3000` and `http://127.0.0.1:3000` through CORS.

## Environment variables

Never commit real values. `backend/.env` and `frontend/.env.local` are ignored; their `.example` files are templates. The backend test suite needs none of these credentials.

### `backend/.env`

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL used by the backend. |
| `SUPABASE_KEY` | Privileged server credential for database calls; keep it out of the browser. |
| `OPENAI_API_KEY` | Required when the treatment-research service is imported at backend startup; an uncached generation request incurs API cost. |

### `frontend/.env.local`

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Optional backend origin; `lib/api.ts` defaults to `http://127.0.0.1:8000`. `NEXT_PUBLIC_` values enter the browser bundle, so do not put a secret here. |

## Running tests

From `backend/`, run the full backend suite:

```bash
./.venv/bin/python -m pytest -q
```

The suite currently passes 597 tests. It needs **no credentials, no `.env`, and no network**: test setup supplies dummy environment values, and route tests use a fake database. Coverage includes simulation invariants, calibration and validation integrity, the simulation service, and HTTP routes.

From `frontend/`, run the static checks and production build:

```bash
npm run lint
npx tsc --noEmit
npm run build
```

The build may require network access to fetch `next/font` Google fonts. There is currently no frontend test framework.

## API

Base URL: `http://127.0.0.1:8000`. V1 has no end-user authentication.

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/` | Health check. |
| `GET` | `/profiles` | List profile rows. |
| `GET` | `/profiles/{profile_id}` | Fetch one profile; `404` if absent. |
| `POST` | `/profile` | Create a validated profile. |
| `PATCH` | `/profiles/{profile_id}` | Partially edit a profile; `404` if absent. Research-relevant changes invalidate cached research; a name-only change does not. |
| `GET` | `/profiles/{profile_id}/treatment-options/saved` | Read current-version cached research only; returns `result: null` on a miss and never calls OpenAI. |
| `POST` | `/profiles/{profile_id}/treatment-options` | Return cached research or generate and best-effort cache it; `404` if the profile is absent, `502` on a research failure. |
| `GET` | `/simulation/treatments` | List packaged calibrated treatments and their effects. |
| `GET` | `/profiles/{profile_id}/simulations/{treatment_id}` | Return p10/p50/p90 bands for the saved profile and treatment. `duration_days` defaults to 84 and accepts 28–168; `404` for an unknown profile or treatment, `422` for an out-of-range duration or a profile that cannot be converted to simulation metrics. |

FastAPI's `/docs` shows the request and response schemas.

## Limitations

### Clinical / modelling limitations

- Only `inflammatory_acne` is calibrated. Treatment side effects are not modelled, so the simulation does not quantify their potential burden.
- The frozen `v1` model under-predicted mean improvement by about 8 percentage points at week 12 for the evaluated held-out tretinoin and tazarotene comparisons. Simulated spread was narrower than the reported trial SDs; three treatments borrow pooled response spread (`sigma`) rather than treatment-specific estimates.
- The engine applies absolute-point effects. They can saturate at low starting scores, where floor clamping prevents further improvement near zero. The UI warns for affected scores above zero and below 5.
- Positive response multipliers cannot represent worsening. The p10/p50/p90 bands describe a simulated population under fixed model assumptions, not an individual's likely outcome.

### Software limitations

- V1 is a local single-user demo with no end-user authentication. The backend uses a privileged Supabase key, and the RLS policies and forced-RLS state are not fully verified.
- Research generation can incur API cost on a cache miss. There is no backend concurrency guard, so two tabs can miss the cache and generate twice.
- A failed cache read on the generation path is treated as a miss and can fall through to paid generation.
- Database outages or errors in profile routes currently surface as unhandled `500` responses rather than a mapped `503`.
- Frontend types mirror backend contracts by hand. There is no frontend test framework.
- `backend/schema.sql` documents the live schema but is not a runnable migration.

## V1 status and what's next

V1 includes profile creation, listing, detail and partial editing; evidence-sourced treatment research with versioned caching; calibrated simulation ranges; a backend test suite; and a [validation report](backend/notes/validation/validation_report.md) that records the held-out disagreements.

**What's next:** Clinical work could add baseline-aware effects, a response model that can represent non-response, side effects, and more treatments evaluated with a new holdout. Product work could add treatment comparison, authentication with verified RLS, and deployment.
