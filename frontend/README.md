# GlassSkinAI — frontend

Next.js 16 (App Router) + React 19 + TypeScript client for GlassSkinAI.

The project-level documentation — architecture, backend setup, Supabase schema,
environment variables, development workflow — lives in the repository root:

**[../README.md](../README.md)**

## Quick start

```bash
npm install
cp .env.local.example .env.local   # optional; defaults to http://127.0.0.1:8000
npm run dev                        # http://localhost:3000
```

The backend must be running separately (see the root README) or every page will
render its empty/loading state.

## Checks

```bash
npm run lint        # eslint (eslint-config-next: core-web-vitals + typescript)
npx tsc --noEmit    # type check only
npm run build       # production build; also type checks
```

## Layout

| Path              | Contents                                                        |
| ----------------- | --------------------------------------------------------------- |
| `app/`            | Routes. `page.tsx` is the profile list/create page; `profiles/[id]/page.tsx` is the profile detail page. |
| `components/`     | Client components (profile form/list, metric inputs, treatment research UI). |
| `types/`          | Hand-maintained TypeScript mirrors of the backend Pydantic schemas. |
| `lib/api.ts`      | `API_BASE_URL` / `apiUrl()` — the single place the backend host is defined. |
| `app/globals.css` | The entire design system: CSS custom properties plus hand-written component classes. |
