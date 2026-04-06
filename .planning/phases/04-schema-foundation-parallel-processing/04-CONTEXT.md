# Phase 4: Schema Foundation + Parallel Processing - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a `pipeline_run` table with run metadata, nullable `run_id` foreign keys on `person_article_score` and `retrieval_log`, and switch the pipeline to emit SSE events in true completion order using `asyncio.as_completed`. Existing data migrates as run #1. The run list API and run selector UI are Phase 6 — this phase only lays the schema foundation and fixes parallel processing ordering.

</domain>

<decisions>
## Implementation Decisions

### Migration Strategy
- **D-01:** Use Alembic for schema migrations. Add Alembic 1.13.3 to the project with config at `api/migrations/`.
- **D-02:** Migrations run automatically on FastAPI app startup (`alembic upgrade head` in startup event). Zero friction for Docker Compose users.
- **D-03:** First migration (001) captures the full existing schema as a baseline. Second migration (002) adds `pipeline_run` table and `run_id` columns. Future phases add incremental migrations.

### Run Lifecycle & Status
- **D-04:** `pipeline_run` table uses auto-increment integer `run_id` as primary key.
- **D-05:** 5-state lifecycle: PENDING → RUNNING → COMPLETED / PARTIAL / FAILED. A run is created as PENDING when `/api/pipeline/run` is called, transitions to RUNNING when the first researcher starts processing.
- **D-06:** When some researchers fail but others succeed, the run is marked COMPLETED (not PARTIAL). Individual researcher errors are logged per-researcher in the SSE event stream and in the result data. PARTIAL is reserved for cases where the run itself is interrupted (e.g., server crash, user abort).
- **D-07:** `pipeline_run` stores aggregate counts: `total_researchers`, `total_articles`, `researchers_succeeded`, `researchers_failed`.
- **D-08:** `pipeline_run` stores the `mode` column (full, update, score_only) used for the run.

### Run #1 Backfill
- **D-09:** Alembic migration creates a synthetic `pipeline_run` row (run_id=1, status=COMPLETED, mode='full') and UPDATEs all existing `person_article_score` and `retrieval_log` rows to set `run_id=1`. After migration, no NULL run_id values exist.
- **D-10:** Synthetic run #1 timestamps: `started_at` = MIN(scored_at) from existing scores, `completed_at` = MAX(scored_at). Reflects the actual time range of original scoring.

### Parallel Processing
- **D-11:** Replace submission-order result collection (`for pid in person_ids: await futures[pid]`) with `asyncio.as_completed` so SSE events fire in true completion order.
- **D-12:** MAX_WORKERS = 8 when PubMed API key is configured, 3 without. Replace current hardcoded `min(4, cpu_count)`.
- **D-13:** Remove the `processing` SSE event type. With `as_completed`, all researchers run simultaneously after being queued — the per-researcher "processing" event is meaningless. Frontend transitions directly from queued → complete.

### Frontend Changes
- **D-14:** Researcher rows keep their original roster (upload) order. When a completion event arrives out-of-order, that row updates in place (queued → complete). No reordering or section splitting.
- **D-15:** Show worker count status line (e.g., "5/8 workers active") on the pipeline page during execution.

### Claude's Discretion
- Exact `pipeline_run` column types and constraints beyond what's specified above
- Alembic env.py configuration details
- SSE event payload changes needed to carry `run_id`
- How to detect PubMed API key presence for worker count selection

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Schema & Models
- `api/models.py` — Current SQLAlchemy models (Identity, Article, PersonArticle, PersonArticleScore, RetrievalLog, Curation). No PipelineRun model yet. PersonArticleScore and RetrievalLog need run_id column additions.
- `api/database.py` — SQLAlchemy engine/session setup. Auto-migrate hook will be added here.

### Pipeline Backend
- `api/services/pipeline_runner.py` — Current pipeline orchestration. Lines 36 (MAX_WORKERS), 331-363 (submission-order collection loop). Must be refactored for as_completed and run_id tracking.
- `api/routers/pipeline.py` — Pipeline HTTP endpoints. `/run` endpoint needs to create pipeline_run row and pass run_id downstream.

### Pipeline Frontend
- `frontend/app/pipeline/page.tsx` — Pipeline UI with SSE event handling. Must handle removal of `processing` event and add worker count display.
- `frontend/components/pipeline-row.tsx` — Individual researcher row component.

### Requirements
- `.planning/REQUIREMENTS.md` — PARA-01, PARA-02, HIST-01, HIST-02 define the acceptance criteria for this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/models.py` SQLAlchemy ORM pattern: all models inherit from `Base`, use `TIMESTAMP` with `func.now()` server defaults. New `PipelineRun` model follows same pattern.
- `api/services/pipeline_runner.py` `_process_one_researcher()` function: already isolated per-researcher logic in a thread-safe function. No changes needed for as_completed switch — only the collection loop in `run_pipeline()` changes.
- `frontend/lib/sse.ts` `subscribeSSE()` utility: already handles SSE stream subscription. Worker count can be derived from existing event data.

### Established Patterns
- ThreadPoolExecutor with `loop.run_in_executor` for CPU-bound scoring work (pipeline_runner.py:332). Stays the same — only the await pattern changes.
- SSE event types: started, queued, complete_one, finished. Remove `processing`, keep others. Add `run_id` to `started` event payload.
- Docker Compose with 3 containers (frontend, api, mariadb). Alembic auto-migrate fits naturally in the API container startup.

### Integration Points
- `api/main.py` — Startup event hook for Alembic auto-migration.
- `api/routers/pipeline.py` `/run` endpoint — Creates `PipelineRun` row before calling `run_pipeline()`.
- `docker-compose.yml` — May need `alembic` added to API container dependencies.
- `requirements.txt` — Add `alembic>=1.13.0`.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-schema-foundation-parallel-processing*
*Context gathered: 2026-04-06*
