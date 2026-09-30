# GlassSkin agent guide

## Line-breaking / formatting rule

**This repository strongly prefers compact code.**

DO NOT break a single statement, function call, assignment, condition, return statement, or expression across multiple lines unless doing so is genuinely necessary for readability, line length, nested structure, or clarity.

Do not mechanically apply formatter-style line wrapping just because arguments exist. If a statement is clear and readable on one line, KEEP IT ON ONE LINE.

Bad:

```ts
setError(
  "Unable to research treatment options. Please try again."
);
```

Good:

```ts
setError("Unable to research treatment options. Please try again.");
```

Multiline formatting is good when the structure is genuinely clearer, such as a meaningful Supabase chain:

```python
response = (
    supabase
    .table("skin_profiles")
    .select("*")
    .eq("id", profile_id)
    .execute()
)
```

Apply these principles:

- Prefer one line when the entire operation is naturally readable as one unit.
- Use multiple lines for meaningful chaining, nesting, long structured expressions, or whenever multiline layout materially improves clarity.
- Do not create vertical whitespace inside a simple function call.
- Do not put one short argument per line unnecessarily.
- Do not split simple JSX, TypeScript, JavaScript, or Python expressions merely because an automated formatter might.
- Preserve existing compact formatting whenever it is already clean.
- Never sacrifice correctness merely to force an operation onto one line.
- Be conservative: if a multiline structure is genuinely easier to understand, leave it multiline.

## Project overview

GlassSkin is a health-adjacent full-stack application for creating structured digital skin profiles and generating evidence-grounded treatment research. It is informational and is not medical advice. The current product supports profile creation, listing, detail viewing, partial editing, AI-assisted treatment research, and cached research results. Calibrated Monte Carlo treatment simulation is implemented through two GET routes and displayed on the profile page; its V1 parameter data is frozen.

## Repository layout and Git topology

- `backend/`: FastAPI application, Pydantic contracts, Supabase access, treatment-research service, dependencies, and database documentation.
  - `main.py`: route definitions and orchestration for profiles, cache lookup/invalidation, treatment research, and simulation.
  - `schemas.py`: Pydantic request/update models and structured AI response models. Treat these as the authoritative HTTP and AI-output contract.
  - `models.py`: the current `SkinProfile` domain object used during profile creation.
  - `database.py`: process-wide Supabase client initialized from environment variables.
  - `services/treatment_research.py`: profile-to-prompt mapping, trusted-domain allowlist, OpenAI Responses API call, output parsing, and `RESEARCH_VERSION`.
  - `services/treatment_simulation.py`: simulation service boundary with server-owned settings and affected metrics derived from treatment effects.
  - `simulation/`: pure simulation package, independent of FastAPI, Supabase, OpenAI, network access, and environment loading.
  - `simulation/parameters/v1/`: frozen packaged treatment parameter data.
  - `tests/`: backend tests; `tests/conftest.py` supplies dummy credentials before route imports, and route tests use a fake database.
  - `notes/`: development evidence, calibration, validation, plots, and benchmarks; see `backend/notes/README.md` before running any script.
  - `SIMULATION_DESIGN.md`: simulator design, calibration, validation, and API documentation.
  - `schema.sql`: documentation of the live Supabase schema. It explicitly separates verified facts, unverified facts, and proposed changes; it is not currently a safe blind migration script.
  - `requirements.txt`: pinned direct Python dependencies.
  - `requirements-dev.txt`: development dependencies, including runtime requirements.
  - `pytest.ini`: backend pytest configuration.
- `frontend/`: Next.js 16 App Router application using React 19 and strict TypeScript.
  - `app/page.tsx`: home route; profile list and create flow via `ProfileManager`.
  - `app/profiles/[id]/page.tsx`: client-rendered profile detail/edit route with treatment research and simulation.
  - `components/`: profile form/list, metric controls, research state UI, and treatment cards.
  - `components/SimulationPanel.tsx`: treatment selection, simulation requests, results, and state UI.
  - `components/TrajectoryChart.tsx`: SVG percentile fan chart.
  - `components/SimulationAbout.tsx`: limitations and validation explanation in the simulation UI.
  - `types/`: hand-maintained TypeScript mirrors of backend/Pydantic response shapes.
  - `types/Simulation.ts`: simulation API response types.
  - `lib/api.ts`: the only frontend definition of the backend base URL.
  - `lib/metrics.ts`: shared frontend labels for skin metrics.
  - `lib/profiles.ts`: normalizes raw API profile rows at the frontend boundary.
  - `app/globals.css`: hand-written design tokens, component classes, and responsive rules. Tailwind v4 is imported but the application mostly uses these CSS classes.
- `plans/`: gitignored, local-only roadmap and implementation plans that may be absent in a fresh clone. When present, the per-day plan wins if it conflicts with the broader roadmap.
- `README.md`: current architecture, setup, API, schema caveats, and project-status documentation.

`frontend/` is ordinary tracked source in the root Git repository. Inspect `git status --short` before and after changes, and preserve unrelated/pre-existing changes.

Generated and local-only directories include `backend/.venv/`, `__pycache__/`, `.pytest_cache/`, `frontend/node_modules/`, `frontend/.next/`, and TypeScript build-info files. Do not edit or commit them. Never read out, expose, or commit real values from `backend/.env` or `frontend/.env.local`.

## Runtime architecture and data flow

The browser talks directly to FastAPI with JSON `fetch()` requests. Client components build URLs through `frontend/lib/api.ts`, which uses `NEXT_PUBLIC_API_URL` and falls back to `http://127.0.0.1:8000`. FastAPI CORS currently allows only `localhost:3000` and `127.0.0.1:3000`. There are no Next.js API routes and no authentication layer.

FastAPI uses the singleton in `backend/database.py` to access Supabase/PostgREST. The backend is run from `backend/`, and its imports intentionally use flat package paths such as `from schemas import ...` and `from services...`; preserve that convention unless a separately scoped architecture change says otherwise.

The active routes are:

- `GET /`: health response.
- `GET /profiles`: list all profile rows.
- `GET /profiles/{profile_id}`: fetch one profile or return `404`.
- `POST /profile`: validate and create a profile.
- `PATCH /profiles/{profile_id}`: partial update using `model_dump(exclude_unset=True)`; return `404` if absent.
- `GET /profiles/{profile_id}/treatment-options/saved`: return current-version cached research or `result: null`; never call OpenAI.
- `POST /profiles/{profile_id}/treatment-options`: return current cached research, or generate and best-effort cache a new result; return `404` for an unknown profile and `502` for a research failure.
- `GET /simulation/treatments`: list the calibrated treatment catalogue.
- `GET /profiles/{profile_id}/simulations/{treatment_id}`: simulate an existing profile with a catalogue treatment; return `404` for an unknown profile or treatment and `422` for invalid duration or profile conversion failure.

The treatment-generation endpoint is a `POST` with side effects: a cache miss can call OpenAI and spend money, and may write a research result to Supabase. There is no backend concurrency guard, so concurrent cache misses can generate more than once. Preserve its behavior unless the requested change explicitly addresses that design.

The simulation routes read the profile but do not call OpenAI or write to Supabase.

## Data contracts and Supabase rules

`skin_profiles` contains identifiers/timestamps, name, age, gender, and 17 integer concern metrics: `inflammatory_acne`, `cystic_nodular_acne`, `blackheads`, `whiteheads`, `pie`, `pih`, `redness`, `rosacea`, `dryness`, `sensitivity`, `irritation`, `oiliness`, `texture_irregularity`, `acne_scarring`, `enlarged_pores`, `dark_circles`, and `uneven_skin_tone`. API profile creation and partial updates both validate age from 0 to 120 and every metric from 0 to 10.

Keep the metric names synchronized across `backend/schemas.py`, `backend/models.py`, `backend/main.py`, `backend/services/treatment_research.py`, `backend/simulation/profile_adapter.py`, `backend/simulation/models.py` (`SKIN_METRIC_NAMES`), `frontend/types/SkinProfile.ts`, `frontend/lib/metrics.ts`, and profile form/edit UI. The frontend intentionally accepts `cystic_nodular_acne: number | null` only in `ApiSkinProfile`, then converts nullish legacy data to `0` in `normalizeProfile()` so application-level `SkinProfile` remains strict.

`treatment_research_results` caches structured JSONB by `profile_id` and `research_version`. The current read path selects the latest matching version. Bumping `RESEARCH_VERSION` invalidates old cache entries without deleting them. A profile name change keeps cached research; changes to age, gender, or any metric delete all cached rows for that profile on a best-effort basis. Do not alter these cache semantics accidentally.

`schema.sql` records that both tables have RLS enabled, but policy definitions, forced-RLS state, ID identity details, one check expression, and the research foreign key target/delete behavior remain explicitly unverified. The server key is privileged and there is no end-user auth, so never claim that current data is user-isolated. Resolve the documented unknowns with read-only database queries before writing migrations that depend on them.

## Treatment research and medical-safety conventions

`generate_treatment_options()` uses `AsyncOpenAI.responses.parse` with `gpt-5-mini`, the web-search tool, a fixed allowlist of professional medical domains, and `TreatmentResearchResult` as the structured output schema. Each result contains one to five treatment options with type, rationale, prescription flag, benefits, risks, evidence sources, and confidence.

- Preserve the trusted-source allowlist and the informational/not-medical-advice framing unless explicitly directed otherwise.
- Do not invent efficacy percentages, medical claims, treatment coefficients, or simulation parameters.
- AI treatment-research output is descriptive evidence research; it must not be treated as provenance for numerical simulation coefficients.
- If the model, prompt, or output schema changes in a cache-incompatible way, consider whether `RESEARCH_VERSION` must be bumped.
- `OPENAI_API_KEY` is required at service import time, and uncached requests cost money. Validation should not call live research endpoints unless explicitly authorized.

## Simulation rules

- `backend/simulation/parameters/v1/*.json` is frozen V1 data. Never manually edit it or rerun `backend/notes/fit_treatment_parameters.py` against V1. Recalibration must write to a new parameter-version directory; change the active version through `SIMULATION_PARAMETER_VERSION` in `backend/services/treatment_simulation.py` instead of overwriting V1.
- Trial count, random seed, time grid, and parameter version are server-owned settings in `backend/services/treatment_simulation.py`. Clients must not provide arbitrary coefficients or model-changing simulation configuration.
- Derive affected metrics from `treatment.effects` in the service and UI; do not hard-code `inflammatory_acne` or another metric when the treatment defines its effect targets.
- `backend/notes/validate_simulation.py` and the current validation tests deliberately assert one effect per treatment. Do not silently generalize that assumption.
- Keep `backend/simulation/` independent of FastAPI, Supabase/database access, OpenAI, network calls, and environment-variable loading so the package remains reusable and testable without infrastructure.
- After running any `backend/notes/` script in the future, inspect `git status --short backend/simulation backend/notes` before committing; the fitter currently writes directly into frozen V1.

## Frontend conventions

- Components that use hooks or browser fetching are client components with `"use client"`.
- Use the `@/*` TypeScript path alias and `apiUrl()` rather than hardcoding backend origins.
- Normalize raw profile JSON with `normalizeProfile()` before storing it in `SkinProfile` state.
- Profile creation sends the complete form payload. Profile editing compares each editable value and sends only fields that changed.
- Editing a research-relevant field remounts `SimulationPanel` and `TreatmentResearch` through their keys so simulation results reset and saved research reloads after backend invalidation.
- Keep backend Pydantic models and frontend TypeScript types aligned; there is no generated client or shared schema.
- Reuse the existing CSS variables and semantic component classes. Preserve focus styles and the responsive layouts at 860px and 620px.

## Safe modification workflow

1. Read the root README, relevant source files, this guide, and `git status --short` before changing code.
2. Treat existing working-tree changes as user-owned. Make narrowly scoped edits and never discard, reset, or overwrite unrelated changes.
3. Do not refactor architecture, rename fields, modify database semantics, or “fix” documented contract drift as part of an unrelated task.
4. Do not edit generated/vendor/dependency artifacts. Update dependency manifests and lockfiles only when dependency work is explicitly in scope.
5. Keep changes compact and local. Preserve useful Supabase method chains, structured data, and complex JSX as multiline when that layout communicates structure.
6. Inspect the complete repository diff before handoff. Confirm that no code or comments disappeared unintentionally.
7. Do not run destructive database operations or live OpenAI research merely as a validation step.

## Verification expectations

Run backend pytest from `backend/`; it must stay green. The suite needs no credentials, no `.env`, and no network: `tests/conftest.py` supplies dummy environment values, and route tests use a fake database. Tests must never reach real network services. Validate in proportion to the change:

```bash
# Backend tests, from backend/
cd backend
./.venv/bin/python -m pytest -q

# Backend syntax/import-independent compilation; keep bytecode out of the worktree
PYTHONPYCACHEPREFIX=/tmp/glassskin-validation-pycache ./.venv/bin/python -m py_compile database.py main.py models.py schemas.py services/__init__.py services/treatment_research.py services/treatment_simulation.py

# Frontend static checks
cd ../frontend
npm run lint
npx tsc --noEmit
npm run build
```

Run all relevant checks after source changes and report exactly what ran. Backend import/runtime checks can require real environment variables and initialize external clients; prefer compile-only validation for formatting or isolated code changes. The production Next build may require network access for `next/font` depending on cache/environment, so distinguish environmental failures from source failures.

No repository formatter is configured. ESLint uses `eslint-config-next` core-web-vitals and TypeScript presets but does not define a line-wrapping policy. Do not introduce or run Prettier, Black, Ruff formatting, or another bulk formatter without checking that it preserves this repository's compact-code rule.
