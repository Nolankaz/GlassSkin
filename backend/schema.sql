-- GlassSkinAI — Supabase / Postgres schema
--
-- STATUS: the CURRENT-SCHEMA sections below are transcribed from read-only
-- queries run against the live Supabase project. They are evidence, not
-- reconstruction. Anything the queries did not establish is marked UNVERIFIED
-- and is listed together at the end, with the exact query that would settle it.
--
-- Evidence used (all read-only):
--   1. information_schema.columns  — names, types, nullability, defaults
--   2. information_schema.table_constraints (+ key_column_usage)
--                                  — constraint names, types, key columns
--   3. pg_indexes                  — index definitions
--   4. pg_tables.rowsecurity       — whether RLS is enabled
--
-- Column order below follows the order the column query returned.
--
-- THIS FILE IS DOCUMENTATION FIRST. Do not assume it can recreate the project
-- unmodified: the identity definition for `id`, the foreign key's referenced
-- table and ON DELETE action, and one CHECK expression are all UNVERIFIED, so
-- a fresh project built from this file would differ from the live one in ways
-- this file cannot currently state.


-- ===========================================================================
-- VERIFIED LIVE SCHEMA
-- Types, nullability and defaults below are exactly what the live database
-- reports. Every column in both tables is NOT NULL.
-- ===========================================================================

-- One row per digital skin profile.
-- Written by  POST   /profile
-- Read by     GET    /profiles, GET /profiles/{id}
-- Updated by  PATCH  /profiles/{id}
create table public.skin_profiles (
    -- Auto-generated. column_default is NULL, which rules out a serial
    -- (a serial would report nextval(...)). The identity definition itself
    -- is UNVERIFIED — see the Unverified section.
    id          bigint      not null,
    created_at  timestamptz not null default now(),

    name        text        not null,

    -- smallint, not integer. Range -32768..32767, which comfortably contains
    -- the 0-120 that SkinProfileRequest allows.
    age         smallint    not null,

    -- The 16 metrics stored as smallint, in the order the database returned
    -- them. All NOT NULL with a database-side default of 0.
    inflammatory_acne     smallint not null default 0,
    blackheads            smallint not null default 0,
    whiteheads            smallint not null default 0,
    pie                   smallint not null default 0,
    pih                   smallint not null default 0,
    redness               smallint not null default 0,
    rosacea               smallint not null default 0,
    dryness               smallint not null default 0,
    sensitivity           smallint not null default 0,
    irritation            smallint not null default 0,
    oiliness              smallint not null default 0,
    texture_irregularity  smallint not null default 0,
    acne_scarring         smallint not null default 0,
    enlarged_pores        smallint not null default 0,
    dark_circles          smallint not null default 0,
    uneven_skin_tone      smallint not null default 0,

    -- The 17th metric. Differs from the other 16 in three verified ways:
    -- it is `integer` rather than `smallint`, it is the only column carrying a
    -- named CHECK constraint, and it is returned after the 16 smallint metrics
    -- rather than among them. It is NOT NULL with a default of 0 — a profile
    -- row cannot hold NULL here.
    cystic_nodular_acne   integer  not null default 0,

    -- Also returned after the metric block. NOT NULL with a database-side
    -- default, so the application never has to supply it.
    gender      text        not null default 'Not specified'::text,

    constraint skin_profiles_pkey primary key (id)

    -- Also present on this table: a CHECK constraint named
    -- skin_profiles_cystic_nodular_acne_check. Its expression was not returned
    -- by the constraint query and is NOT reproduced here. See Unverified.
);


-- Cached AI treatment-research output, one row per generated research run.
--
-- `result` stores a serialized schemas.TreatmentResearchResult:
--   { "options": [ { treatment_name, treatment_type, why_it_may_fit,
--                    prescription_required, key_benefits[], key_risks[],
--                    evidence_sources[{title,url,source_name}],
--                    confidence }, ... ] }
--
-- `research_version` matches services/treatment_research.RESEARCH_VERSION.
-- Bumping that constant in Python invalidates every older cached row without
-- deleting it, because the read query filters on the current version.
--
-- Written by  GET    /profiles/{id}/treatment-options  (on cache miss)
-- Read by     GET    /profiles/{id}/treatment-options/saved
-- Deleted by  PATCH  /profiles/{id}, when a research-relevant field changed
create table public.treatment_research_results (
    -- Same situation as skin_profiles.id: no column_default, identity
    -- definition UNVERIFIED.
    id                bigint      not null,
    profile_id        bigint      not null,
    research_version  text        not null,
    result            jsonb       not null,
    created_at        timestamptz not null default now(),

    constraint treatment_research_results_pkey primary key (id)

    -- Also present: a FOREIGN KEY named
    -- treatment_research_results_profile_id_fkey, whose key column is
    -- profile_id. The referenced table/column and the ON DELETE action were
    -- NOT returned by the constraint query, so the full definition is
    -- deliberately not written here. See Unverified.
);


-- ===========================================================================
-- VERIFIED DATABASE FEATURES
-- ===========================================================================

-- --- Indexes (transcribed verbatim from pg_indexes) ------------------------
--
-- CREATE UNIQUE INDEX skin_profiles_pkey
--     ON public.skin_profiles USING btree (id);
--
-- CREATE UNIQUE INDEX treatment_research_results_pkey
--     ON public.treatment_research_results USING btree (id);
--
-- CREATE INDEX treatment_research_results_profile_version_idx
--     ON public.treatment_research_results
--     USING btree (profile_id, research_version, created_at DESC);
--
-- The third index already serves the cache read in
-- get_saved_treatment_research():
--     where profile_id = ? and research_version = ?
--     order by created_at desc limit 1
-- Its column order matches the query exactly — the two equality columns first,
-- then created_at descending, so the "latest" row is the first index entry
-- scanned rather than something found by sorting a filtered set.
--
-- Because profile_id is this index's leading column, it also covers the
-- foreign key. No additional index is needed for either purpose, and adding a
-- second lookup index would be redundant.


-- --- Row Level Security ----------------------------------------------------
--
-- VERIFIED: pg_tables.rowsecurity reports true for both tables.
--
--     public.skin_profiles                rowsecurity = true
--     public.treatment_research_results   rowsecurity = true
--
-- RLS is therefore ENABLED. That fact alone does not describe the security
-- posture, and two things must not be read into it:
--
--   1. Which policies exist, and what they permit, is UNVERIFIED. pg_policies
--      was not queried. Enabled-with-no-policies and enabled-with-permissive-
--      policies are very different situations and this evidence cannot tell
--      them apart.
--
--   2. The backend authenticates to Supabase with a secret server key. Keys of
--      that class are privileged, so RLS should not be assumed to constrain
--      requests made through the backend. Whether it does has not been tested
--      here, and no claim is made either way.
--
-- Designing and validating authorization is Day 20 of the roadmap. Nothing in
-- this file should be read as saying the current arrangement does or does not
-- isolate users.


-- ===========================================================================
-- UNVERIFIED
-- Facts the supplied read-only outputs do not establish. Each entry names the
-- query that would settle it. Nothing below is guessed.
-- ===========================================================================
--
-- U1. The expression of skin_profiles_cystic_nodular_acne_check.
--     The constraint exists and is of type CHECK. What it checks is unknown.
--     It could be a range check, a sign check, or something else, and its name
--     does not constrain its contents.
--
-- U2. Whether any CHECK constrains the ranges of age or the 16 smallint
--     metrics. No separately-named CHECK for those columns was returned, but
--     because no CHECK expressions were returned at all, their absence is not
--     established. U1 and U2 are answered by the same query:
--
--       select conname, pg_get_constraintdef(oid) as definition
--       from pg_constraint
--       where conrelid in (
--                 'public.skin_profiles'::regclass,
--                 'public.treatment_research_results'::regclass)
--         and contype = 'c'
--       order by conrelid::regclass::text, conname;
--
-- U3. The foreign key's referenced table/column and ON DELETE action.
--     treatment_research_results_profile_id_fkey exists on profile_id; its
--     target and delete behavior were not returned. This matters concretely:
--     whether deleting a profile cascades to its cached research, errors, or
--     orphans rows is a real behavioral difference, and the roadmap adds a
--     profile delete endpoint on Day 19.
--
--       select conname, pg_get_constraintdef(oid) as definition
--       from pg_constraint
--       where conrelid = 'public.treatment_research_results'::regclass
--         and contype = 'f';
--
-- U4. The identity definition of both id columns. column_default is NULL, so
--     neither is a serial. Whether they are GENERATED ALWAYS or GENERATED BY
--     DEFAULT AS IDENTITY, and their start/increment, is unknown.
--
--       select table_name, column_name, is_identity, identity_generation,
--              identity_start, identity_increment
--       from information_schema.columns
--       where table_schema = 'public' and column_name = 'id'
--         and table_name in ('skin_profiles', 'treatment_research_results');
--
-- U5. RLS policy definitions, and whether RLS is FORCED in addition to
--     enabled. Forcing matters because it changes whether the table owner is
--     itself subject to policies.
--
--       select schemaname, tablename, policyname, permissive, roles, cmd,
--              qual, with_check
--       from pg_policies
--       where schemaname = 'public'
--       order by tablename, policyname;
--
--       select relname, relrowsecurity, relforcerowsecurity
--       from pg_class
--       where relnamespace = 'public'::regnamespace
--         and relname in ('skin_profiles', 'treatment_research_results');
--
-- U6. A minor bookkeeping discrepancy worth resolving before anyone reasons
--     from constraint counts: information_schema.columns reports 22 columns on
--     skin_profiles and all 22 as NOT NULL, but only 21 synthesized
--     "<oid>_<attnum>_not_null" CHECK entries were returned (attnums 1-21).
--     Nullability above is taken from information_schema.columns, which is
--     unambiguous; this note exists only so the count mismatch is not later
--     mistaken for a finding.
--
--       select attname, attnum, attnotnull
--       from pg_attribute
--       where attrelid = 'public.skin_profiles'::regclass
--         and attnum > 0 and not attisdropped
--       order by attnum;


-- ===========================================================================
-- PROPOSED FUTURE CHANGES
-- Nothing in this section has been applied. Nothing in this section should be
-- applied without first resolving the UNVERIFIED item it depends on.
-- ===========================================================================
--
-- P1. Metric range CHECK constraints — BLOCKED ON U1/U2, roadmap Day 20.
--
--     The 0-10 scale is currently enforced by Pydantic on the API path only.
--     Anything writing by another route — the SQL editor, a future backfill
--     script, a Day 14 job — bypasses it. The database types permit far wider
--     values: smallint reaches 32767.
--
--     Whether such a constraint is actually absent is UNVERIFIED. Run the U1/U2
--     query first. If the checks already exist, this item is void.
--
--     If they are absent and you decide to add them, verify no existing row
--     violates the rule first, then add one table-level constraint rather than
--     17 separate ones so the failure message names the whole rule:
--
--       -- 1. check for violations, expect zero rows
--       -- select id from public.skin_profiles
--       -- where age not between 0 and 120
--       --    or least(inflammatory_acne, blackheads, whiteheads, pie, pih,
--       --             redness, rosacea, dryness, sensitivity, irritation,
--       --             oiliness, texture_irregularity, acne_scarring,
--       --             enlarged_pores, dark_circles, uneven_skin_tone,
--       --             cystic_nodular_acne) < 0
--       --    or greatest(inflammatory_acne, blackheads, whiteheads, pie, pih,
--       --                redness, rosacea, dryness, sensitivity, irritation,
--       --                oiliness, texture_irregularity, acne_scarring,
--       --                enlarged_pores, dark_circles, uneven_skin_tone,
--       --                cystic_nodular_acne) > 10;
--       --
--       -- 2. only if the above returns nothing
--       -- alter table public.skin_profiles
--       --   add constraint skin_profiles_metrics_in_range check (
--       --     least(...) >= 0 and greatest(...) <= 10
--       --   );
--
-- P2. simulation_runs table — roadmap Day 14.
--
--     Days 8-13 build the simulation engine entirely in Python and touch no
--     database. Day 14 is the first day that persists a simulation, and the
--     shape of what gets stored is not decided until the engine returns it.
--     Creating the table before then would be guessing at a schema.
--
--     Expected shape, to be finalized on Day 14, mirroring the caching pattern
--     treatment_research_results already establishes:
--       profile_id, treatment_id, parameter_version, config jsonb,
--       result jsonb, created_at
--
-- P3. User ownership and RLS policies — roadmap Day 20.
--
--     skin_profiles has no user_id column. Adding one, backfilling it,
--     writing policies against it, and testing that two accounts cannot see
--     each other's data is Day 20's whole job. RLS being enabled today is a
--     useful starting position, not a substitute for that work.
--
-- P4. Uniqueness on (profile_id, research_version) — roadmap Day 14.
--
--     There is no unique constraint on that pair, so two concurrent cache
--     misses for the same profile can both insert. The read takes
--     `order by created_at desc limit 1`, so duplicates are wasteful rather
--     than incorrect. Day 14 addresses request concurrency; decide then
--     whether to deduplicate with a constraint or leave history intact
--     deliberately, since more than one row per (profile, version) is also
--     what a research-history feature would want.
