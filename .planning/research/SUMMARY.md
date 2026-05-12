# Project Research Summary

**Project:** ReCiter Desktop v2.0 — Pipeline Parity & Performance
**Domain:** Author disambiguation desktop application — retrieval parity and historical versioning milestone
**Researched:** 2026-04-05
**Confidence:** HIGH

## Executive Summary

ReCiter Desktop v2.0 is a focused feature milestone on top of a working v1.0 stack (Next.js 14 + FastAPI + MariaDB + XGBoost 3.2.0). The milestone has one driving objective: produce scoring results that are reproducible and comparable to the Java ReCiter baseline, which requires closing specific gaps in retrieval strategy logic and adding a persistent run concept. Research was conducted by reading Java source code directly alongside the existing Python codebase, giving unusually high confidence — the gaps are precisely located, not inferred.

The recommended approach is almost entirely additive. Only one new library is needed (Alembic for DB migrations). The five feature areas — retrieval parity, parallel processing, historical runs, results refinement, and UI polish — each require changes to existing files rather than new infrastructure. The largest single risk is schema migration: adding `run_id` to `person_article_score` on a live populated database requires a carefully written atomic `ALTER TABLE` statement, and getting it wrong could destroy existing score data. The second highest risk is the `ON UPDATE CURRENT_TIMESTAMP` trap in `retrieval_log`, which silently corrupts the `mindate` used by `update` mode if any non-retrieval write touches that row.

The `asyncio.as_completed` fix (parallel processing visible in the UI) is a two-line change with zero risk and should ship first as a confidence-building win. The retrieval parity work (affiliation strategies, compound name detection) is the paper-validation critical path and can run in parallel with schema foundation work. Historical runs must follow schema foundation because `run_id` is a prerequisite for the run selector UI on Results and Stats pages. SSE reconnection recovery depends on the `pipeline_run` table existing, so it cannot ship until Phase 3 is complete.

---

## Key Findings

### Recommended Stack

The v1.0 stack requires only one addition for v2.0: **Alembic 1.13.3** for SQLAlchemy-native schema migrations. Without Alembic, the only way to add the `pipeline_run` table and `run_id` columns to a populated database is DROP/recreate, which destroys existing scores. All other changes are logic additions and UI component wiring within the existing Next.js + FastAPI + MariaDB + shadcn/Tailwind stack. XGBoost 3.2.0 is hard-pinned and must not be touched.

**Core technologies:**
- **Next.js 14.2.35**: Frontend framework — stay pinned; do not upgrade to 15 (async params/searchParams change requires route auditing across every dynamic route)
- **FastAPI + sse-starlette**: Backend API + SSE streaming — no pattern changes needed; modification is in the pipeline orchestrator
- **SQLAlchemy 2.0 + MariaDB**: Data persistence — additive schema changes only; FK and index discipline required on migration
- **Alembic 1.13.3**: Schema migrations — new addition; the only way to safely add `run_id` to a populated `person_article_score` table
- **XGBoost 3.2.0**: ML scoring — hard-pinned; cross-version loading causes score drift amplified by the isotonic calibrator
- **asyncio + ThreadPoolExecutor (stdlib)**: Concurrency — switch from submission-order await to `asyncio.as_completed`; no new libraries needed
- **Recharts + shadcn/Tailwind**: Frontend components — already installed; run selector and search filter use existing component patterns

### Expected Features

Research produced a precise gap analysis by comparing Java source code line-by-line to the Python implementation. See `FEATURES.md` for the full retrieval strategy reference table.

**Must have (P1 — paper validation):**
- **Affiliation-filtered search (AffiliationRetrievalStrategy)** — single largest retrieval gap between Desktop and Java for researchers at named institutions; triggered when lenient count > 2000
- **Compound/derived name detection + strict-only mode** — names with hyphens or spaces trigger `useStrictQueryOnly=true` in Java; without this, researchers like "Garcia Lopez" run a noisy lenient search returning thousands of unrelated results
- **`retrieve_known` mode PubMed fetch** — PMID-upload workflow currently maps to `score_only`, which skips PubMed XML fetch; uploaded researchers score with zero articles
- **`asyncio.as_completed` ordering** — two-line change; pipeline UI currently shows one active researcher at a time even with 4+ workers because futures are awaited in submission order
- **Dynamic `MAX_WORKERS` based on API key** — with API key: 8 workers (9 req/sec budget); without: 3 workers (2.5 req/sec budget); prevents silent 429 throttling
- **Historical `pipeline_run` table** — required for paper reproducibility claims; also unblocks run selector UI on Results and Stats pages

**Should have (P2 — milestone completeness):**
- **Run selector on Results and Stats pages** — dropdown to scope scores and statistics to a specific pipeline run
- **`update` mode end-to-end validation** — code is present at `pipeline_runner.py` lines 119–122 but described as untested; needs integration test with a known researcher on a second run
- **Per-researcher export button** — backend export endpoint already exists; needs a UI button on the results listing row
- **Source labeling (candidate vs known)** — `person_article.source` column already stores `"search"` vs `"upload"`; just needs inclusion in the scores response and display as a chip
- **Search/filter on Results listing** — server-side `q` param for title/journal text search and score range filter; use server-side not client-side to avoid keystroke lag at 2000+ articles
- **Dashboard surfaced metrics** — `high_confidence`, `review_band`, `unlikely` already in `/api/pipeline/status`; frontend wiring only

**Defer (P3 — future milestone):**
- Full 8-strategy retrieval cascade (grant, department, known relationships) — marginal recall gain; requires fields not in current identity CSV schema
- Run comparison view with overlaid ROC curves — high complexity; requires historical runs stable first
- DepartmentRetrievalStrategy — requires `organizational_units` field not currently in the identity model

### Architecture Approach

The system is a local single-tenant desktop application: Next.js frontend communicates with a FastAPI backend via REST and SSE; the backend orchestrates retrieval and scoring via a `ThreadPoolExecutor`; all state lives in MariaDB. The v2.0 work adds one new table (`pipeline_run`), two nullable FK columns on existing tables, and two new API endpoints, while modifying the core pipeline orchestrator to emit run IDs and switch to completion-order SSE events. No new services, no new infrastructure.

**Major components and their v2.0 changes:**

1. **`core/pubmed.py`** — Retrieval strategy implementation. Already correct for basic strict/lenient cascade. Caller change only: pass `affiliation` param from `_process_one_researcher`; compound name detection runs in the caller before the search call.
2. **`api/services/pipeline_runner.py`** — Pipeline orchestrator. Three changes: (a) create `pipeline_run` record at run start in a thread executor (not in the async generator body), (b) switch to `asyncio.as_completed` for SSE event ordering, (c) pass `run_id` to thread workers for persistence.
3. **`api/models.py` + `api/schema.sql`** — Schema. New `pipeline_run` table; nullable `run_id` on `person_article_score` and `retrieval_log`; retrieval metadata columns (`query_type`, `lenient_count`, `strict_count`) on `retrieval_log`.
4. **`api/routers/scores.py`** — Scores API. Add optional filter params (`q`, `min_score`, `max_score`, `assertion`, `run_id`); add `PersonArticle` join for `source` field; all params optional for backward compatibility.
5. **`api/services/stats_service.py`** — Stats computation. Add optional `run_id` param to scope joins; behavior unchanged when omitted.
6. **Frontend results + stats pages** — Add `RunSelector` dropdown and `SearchFilter` component; wire `WorkflowContext` with `lastRunId` and `lastRunMode`.

### Critical Pitfalls

1. **Schema/ORM drift for `retrieval_log`** — The `RetrievalLog` ORM model exists but was at one point missing from `schema.sql`. Fresh `docker compose down -v && up` installations silently fail the first pipeline run with `ProgrammingError: Table doesn't exist`. Verify the current branch has the DDL before writing any new code.

2. **Non-atomic `run_id` migration destroys data** — Adding `run_id` to `person_article_score` requires adding the column, migrating existing rows to `run_id = 1`, and adjusting FK — all as a single `ALTER TABLE` statement. Multi-step migrations leave the table without a PK between statements; `ADD COLUMN run_id INT NOT NULL` without a DEFAULT fails in strict mode on non-empty tables. Write and test the migration on a populated DB before any application changes.

3. **`ON UPDATE CURRENT_TIMESTAMP` corrupts `update` mode `mindate`** — `retrieval_log.last_retrieval_date` fires on any `UPDATE` to the row, including writing `articles_found` during a `score_only` run. A subsequent `update` mode run uses the corrupted timestamp as `mindate` and misses all articles published since the last full retrieval. Remove `onupdate` from the ORM and set the timestamp explicitly only during retrieval runs; `score_only` mode must not touch `retrieval_log` at all.

4. **`asyncio.as_completed` result identity** — With completion-order iteration, `person_id` must be extracted from `result["person_id"]` in the worker's return dict, not from a submission-order loop index. Audit the pipeline page `processing` SSE event handler before removing that event; if any renderer depends on it for row state initialization, removing it leaves rows in an indeterminate state.

5. **Compound name quoting gaps** — `_build_author_term` only quotes names with spaces or hyphens. Apostrophes (`O'Brien`), brackets, and Unicode diacritics (`López`) produce silently malformed PubMed queries returning `lenient_count = 0` with no error. Broaden quoting to trigger on any non-`[A-Za-z ]` character and add a unicode normalization step before query construction.

---

## Implications for Roadmap

Based on the dependency graph from architecture and features research, the natural phase structure is:

### Phase 1: Schema Foundation + Parallel Processing
**Rationale:** Schema changes are purely additive (all new columns nullable) and unblock everything downstream. Parallel processing (`asyncio.as_completed`) is independent of everything and zero-risk — ship it immediately as a confidence-building win alongside the schema. Neither change breaks existing behavior.
**Delivers:** `pipeline_run` table and nullable `run_id` columns in schema; visible parallel progress in pipeline UI; correct SSE event ordering; higher `MAX_WORKERS` with connection pool sized to match.
**Addresses:** Pitfall 1 (`retrieval_log` schema gap — verify first, before any code), Pitfall 2 (submission-order await), Pitfall 7 (connection pool exhaustion at higher worker counts).
**First task:** Run `docker compose down -v && docker compose up` and execute a pipeline run. If `retrieval_log` is missing from `schema.sql`, add it before writing any other code.

### Phase 2: Retrieval Strategy Parity
**Rationale:** Independent of `run_id` wiring. Delivers the paper-validation-critical features: affiliation strategies, compound name detection, `retrieve_known` PubMed fetch, `update` mode validation, and name quoting hardening. The most impactful work for paper correctness.
**Delivers:** Retrieval parity with Java ReCiter for the paper validation test set. Dynamic `MAX_WORKERS`. Fixed `mindate` semantics for `update` mode. Compound name detection pre-processing step.
**Addresses:** Pitfall 3 (`ON UPDATE CURRENT_TIMESTAMP` — fix first within this phase as a correctness bug in existing code), Pitfall 5 (non-ASCII name quoting), Pitfall 9 (`retrieve_known` missing PubMed XML fetch).
**Implementation order within phase:** (a) Fix `mindate` corruption — remove `onupdate` from ORM, guard `score_only` from touching `retrieval_log`. (b) Add compound name detection pre-processing in `_process_one_researcher`. (c) Wire `affiliation` param to `search_by_name`. (d) Add `retrieve_known` mode branch with PubMed XML fetch. (e) Harden name quoting with regex and unicode normalization. (f) Integration-test `update` mode with a known researcher on second run.

### Phase 3: Historical Pipeline Runs
**Rationale:** Depends on Phase 1 schema (`pipeline_run` table must exist). Wires the business logic: creating a `pipeline_run` record at run start, threading `run_id` through pipeline workers, updating the record at completion, and exposing the run list via two new API endpoints. Prerequisite for run selector UI and SSE reconnect recovery.
**Delivers:** `pipeline_run` records created per run; `run_id` propagated to `person_article_score` and `retrieval_log`; `GET /api/pipeline/runs` endpoint; `pipeline_run.status` available for reconnect polling; `WorkflowContext` updated with `lastRunId`/`lastRunMode`.
**Avoids:** Pitfall 3 (non-atomic migration — write and test on populated DB as the absolute first task of this phase), blocking DB writes inside the async generator (use `loop.run_in_executor` for the `pipeline_run` INSERT).

### Phase 4: Results Refinement
**Rationale:** Filter params and source labeling are independent of run history, but the `run_id` filter param requires Phase 3. Build the filter bar and source chip first; add the run selector once Phase 3 lands. Backward-compatible because all filter params are optional.
**Delivers:** Server-side `q`/`min_score`/`max_score`/`assertion` filtering on `GET /api/scores/{person_id}`; `source` field in scores response; `RunSelector` dropdown; `SearchFilter` component; per-researcher export button with source column in CSV.
**Avoids:** Client-side text search anti-pattern — use server-side `q` param; at 2000+ articles per researcher with SHAP JSON payloads, client-side filtering causes visible keystroke lag.

### Phase 5: Stats Scoping + UI Polish
**Rationale:** Stats run-scoping requires Phase 3 (`run_id` on scores). UI polish items (institution name display, SSE reconnection, dashboard metrics) are independent but logically complete the milestone. Reconnect recovery requires `pipeline_run.status` from Phase 3.
**Delivers:** Optional `run_id` param on `GET /api/stats`; run selector on Stats page; SSE reconnect with exponential backoff (max 3 retries); institution name in sidebar header; last run mode badge; dashboard metric cards from existing `/api/pipeline/status` data.
**Avoids:** Pitfall 8 (SSE stream lost on page reload) — reconnect polls `/api/runs/latest` and reconstructs state from `pipeline_run.status`; requires Phase 3.

### Phase Ordering Rationale

- **Schema first:** All nullable column additions are non-breaking. Running them first means Phases 2–5 can each reference the columns without migration conflicts arising mid-phase.
- **Parity and history can run in parallel:** Retrieval parity (Phase 2) and historical runs (Phase 3) both need the Phase 1 schema but neither blocks the other. If multiple developers are available, Phase 2 and Phase 3 can be developed concurrently.
- **Run selector last:** The `RunSelector` UI in Phases 4 and 5 depends on `pipeline_run` rows existing from Phase 3. Building it before Phase 3 requires mock data.
- **`asyncio.as_completed` in Phase 1:** Zero-risk, high-visibility change. Shipping it early validates the SSE event flow before Phase 3 modifies the pipeline orchestrator more substantially.

### Research Flags

Phases needing attention during planning:

- **Phase 2 (Retrieval Parity):** The `AffiliationInDbRetrievalStrategy` gap requires a decision: Java's `identity.getInstitutions()` is a list, but Desktop `CoreIdentity` only has `primary_institution` as a single string. If the paper validation set includes researchers with multiple institutional affiliations on record, a `List[str] institutions` field must be added to `CoreIdentity` and the identity CSV schema must be extended. This was identified but not resolved in research.
- **Phase 3 (Historical Runs):** The atomic `ALTER TABLE` migration for `run_id` must be tested on a populated database copy, not an empty test instance. This is a one-time verification task, not a research problem, but skipping it risks data loss.

Phases with standard patterns (skip research-phase):

- **Phase 1 (Schema + Parallel):** Alembic setup, `asyncio.as_completed` pattern, and nullable column additions are well-documented standard patterns with no ambiguity.
- **Phase 4 (Results Refinement):** SQLAlchemy optional filter params and shadcn `Input`/`Slider`/`Select` component composition are established patterns within the existing codebase.
- **Phase 5 (UI Polish):** EventSource reconnect with exponential backoff is a documented standard; institution name display and dashboard metrics are pure wiring tasks against data already available in WorkflowContext.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Java and Python sources read directly; every gap and its file/line location identified precisely; no inference needed |
| Features | HIGH | Gap table derived from direct Java source comparison; thresholds confirmed numerically; retrieval cascade logic read from source |
| Architecture | HIGH | All component boundaries derived from direct code inspection; no speculation |
| Pitfalls | HIGH | Each pitfall identifies the exact file and line number where the problem manifests; trigger conditions confirmed by reading live code |

**Overall confidence:** HIGH

### Gaps to Address

- **`AffiliationInDbRetrievalStrategy` — single vs. list of institutions:** Java uses `identity.getInstitutions()` (a list); Desktop `CoreIdentity` has only `primary_institution` (a single string). During Phase 2 planning, decide whether to add `List[str] institutions` to `CoreIdentity` (requires identity CSV schema change and migration) or treat `primary_institution` as a single-element list. The choice depends on whether the paper validation test set includes researchers with multiple institutional affiliations on record.

- **`processing` SSE event removal:** ARCHITECTURE.md flags that dropping the `processing` event when switching to `asyncio.as_completed` requires auditing `frontend/app/pipeline/page.tsx` to verify no renderer depends on it for row state initialization. This is a quick single-file audit but must happen before the change lands.

- **Alembic initialization:** The project has never used Alembic. Initializing it (`alembic init alembic`, configuring `alembic/env.py` to import `api.models.Base` and read `DATABASE_URL`) is a one-time setup task that must happen before Phase 3 migration scripts are written. No research gap — just an explicit setup step that must not be skipped.

---

## Sources

### Primary (HIGH confidence — read directly from source)
- `AliasReCiterRetrievalEngine.java` (lines 163, 247–276, 863–961) — compound name detection, `useStrictQueryOnly` logic, full retrieval cascade with all conditional branches
- `AbstractRetrievalStrategy.java` (lines 75, 81) — `DEFAULT_THRESHOLD=2000`, `STRICT_THRESHOLD=1000` confirmed
- `PubMedQueryType.java` `contsructAuthorQuery()` (lines 153–196) — exact PubMed query string construction including compound-name quoting rules
- `AffiliationRetrievalStrategy.java`, `AffiliationInDbRetrievalStrategy.java` — home institution and per-researcher institution query construction
- `api/services/pipeline_runner.py` (lines 334–361) — submission-order await pattern confirmed; sequential `await futures[pid]` loop identified
- `api/models.py` and `api/schema.sql` — 6-table schema, no `run_id` concept, confirmed
- `core/pubmed.py` — token bucket, query builder, strict/lenient cascade confirmed correct; `affiliation` param exists but is never called with a value
- `api/services/stats_service.py` — not run-scoped, confirmed
- `frontend/lib/workflow.tsx` — WorkflowState fields; `institution` already present, `lastRunId` absent
- `docs/milestones/milestone-2-pipeline-parity.md` — milestone goals and open questions including `retrieve_known` gap flag
- `.planning/PROJECT.md` — project context and out-of-scope constraints

### Secondary (MEDIUM confidence — documentation)
- NCBI E-utilities documentation — rate limits (3/sec without key, 10/sec with), PDAT date format (`YYYY/MM/DD`), `rettype=count` behavior; used to confirm Desktop token bucket rates (2.5/sec, 9/sec with headroom)
- MariaDB documentation — `ON UPDATE CURRENT_TIMESTAMP` semantics, atomic multi-clause `ALTER TABLE` syntax
- FastAPI SSE documentation — `StreamingResponse` buffering, `Cache-Control: no-cache` and `X-Accel-Buffering: no` requirements
- Alembic 1.13.x documentation — `autogenerate` against SQLAlchemy 2.0 models; confirmed no version conflict with `sqlalchemy>=2.0.0`

---
*Research completed: 2026-04-05*
*Ready for roadmap: yes*
