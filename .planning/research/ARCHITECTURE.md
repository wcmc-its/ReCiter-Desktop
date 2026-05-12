# Architecture Research

**Domain:** v2.0 Pipeline Parity & Performance — Integration architecture for ReCiter Desktop
**Researched:** 2026-04-05
**Confidence:** HIGH (derived from direct codebase inspection, no speculation)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  Next.js 14 Frontend (port 3000)                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ WorkflowCtx  │  │ Results Page │  │ Pipeline Page│               │
│  │ /lib/workflow│  │ /results/[id]│  │ /pipeline    │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                  │ SSE stream            │
├─────────┼─────────────────┼──────────────────┼──────────────────────┤
│  FastAPI Backend (port 8000)                 │                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────┴──────────────┐       │
│  │ /api/scores  │  │ /api/stats   │  │ /api/pipeline/run    │       │
│  │ routers/     │  │ routers/     │  │ StreamingResponse    │       │
│  │ scores.py    │  │ stats.py     │  │ (SSE)                │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────────┘       │
│         │                 │                  │                       │
│  ┌──────▼─────────────────▼──────────────────▼───────────────────┐  │
│  │  api/services/pipeline_runner.py                               │  │
│  │  - run_pipeline() async generator → SSE events                │  │
│  │  - _process_one_researcher() sync → ThreadPoolExecutor        │  │
│  └──────┬──────────────────────────────────────────────────────┬─┘  │
│         │                                                       │    │
│  ┌──────▼──────────────────┐    ┌──────────────────────────────▼──┐ │
│  │  core/ (Python)         │    │  MariaDB tables                  │ │
│  │  pubmed.py              │    │  identity                        │ │
│  │  scoring.py             │    │  article                         │ │
│  │  feature_generator.py   │    │  person_article                  │ │
│  │  target_author.py       │    │  person_article_score            │ │
│  └─────────────────────────┘    │  retrieval_log                   │ │
│                                 │  curation                        │ │
│                                 │  pipeline_run  (NEW v2.0)        │ │
│                                 └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Current State |
|-----------|----------------|---------------|
| `core/pubmed.py` | PubMed E-utilities: esearch, efetch, rate limiting, strict/lenient cascade | Complete — `search_by_name()` fully implements the strategy |
| `api/services/pipeline_runner.py` | Orchestrates retrieval + scoring per researcher; emits SSE events | Mostly complete — awaits futures in submission order (not as_completed) |
| `api/routers/pipeline.py` | HTTP layer for SSE stream + `/status` endpoint | Complete |
| `api/routers/scores.py` | Per-researcher scores, CSV export | Complete — no filter params yet |
| `api/models.py` + `api/schema.sql` | SQLAlchemy models + DDL for all 6 tables | Complete — no `run_id` concept |
| `frontend/lib/workflow.tsx` | WorkflowContext: prerequisite gate state, pipeline running flag | Complete — no `lastRunId` |
| `frontend/app/results/[personId]/page.tsx` | Per-researcher article list with histogram, SHAP panel | Complete — no search/filter |
| `api/services/stats_service.py` | ROC/AUC, calibration, PR, distribution, disagreements | Complete — not run-scoped |

---

## Integration Points for v2.0 Features

### 1. Retrieval Strategy Parity

**Status of `core/pubmed.py`:** The implementation is already correct and complete. `search_by_name()` implements the full ReCiter cascading strategy:
- Lenient query: `LastName FirstInitial[au]`
- esearch count check against `lenient_threshold` (2000)
- If over threshold: strict query `LastName FullFirstName[au]`
- Strict count check against `strict_threshold` (1000)
- Compound name quoting for names with spaces or hyphens
- Incremental `mindate` filter already wired

**What is actually missing:**

The `search_by_name()` result dict (`query_type`, `lenient_count`, `strict_count`) is logged but never persisted. The current `RetrievalLog` model only stores `last_retrieval_date` and `articles_found`.

The `affiliation` parameter exists in `search_by_name()` but `_process_one_researcher()` never passes `core_identity.primary_institution` to it.

**Integration path — `_process_one_researcher()` in pipeline_runner.py:**

```python
# Current:
search_result = search_by_name(
    first_name=core_identity.first_name,
    last_name=core_identity.last_name,
    api_key=api_key or "",
    lenient_threshold=lenient_threshold,
    strict_threshold=strict_threshold,
    mindate=mindate,
)

# Target (add affiliation, persist metadata):
search_result = search_by_name(
    first_name=core_identity.first_name,
    last_name=core_identity.last_name,
    affiliation=core_identity.primary_institution,   # NEW
    api_key=api_key or "",
    lenient_threshold=lenient_threshold,
    strict_threshold=strict_threshold,
    mindate=mindate,
)
# After DB commit of articles, also update retrieval_log:
retrieval_log.query_type = search_result["query_type"]      # NEW
retrieval_log.lenient_count = search_result["lenient_count"] # NEW
retrieval_log.strict_count = search_result.get("strict_count") # NEW
```

Return dict from `_process_one_researcher()` should include `query_type` and `lenient_count` so the `complete_one` SSE event can report the strategy used. This costs nothing — just add keys to the existing return dict.

**Schema change for `retrieval_log`:**

```sql
ALTER TABLE retrieval_log
    ADD COLUMN query_type  ENUM('lenient', 'strict', 'skipped') DEFAULT NULL,
    ADD COLUMN lenient_count INT DEFAULT NULL,
    ADD COLUMN strict_count  INT DEFAULT NULL;
```

Additive, non-breaking. Existing rows keep NULL for the new columns.

---

### 2. Parallel Processing

**Current behavior:** `run_pipeline()` submits all futures to the `ThreadPoolExecutor`, then awaits them in the original `person_ids` submission order. Researchers that finish early are held waiting until all earlier-submitted researchers complete.

The specific code path (pipeline_runner.py lines 335–361):

```python
futures = {}
for pid in person_ids:
    future = loop.run_in_executor(executor, _process_one_researcher, ...)
    futures[pid] = future
    yield {"type": "queued", "person_id": pid}

for pid in person_ids:          # <-- iterates in submission order
    yield {"type": "processing", ...}
    result = await futures[pid] # <-- blocks until THIS pid is done
    yield {"type": "complete_one", ...}
```

**Target behavior — switch to `asyncio.as_completed`:**

```python
futures = {}
for pid in person_ids:
    future = loop.run_in_executor(executor, _process_one_researcher, ...)
    futures[pid] = future
    yield {"type": "queued", "person_id": pid}

# Invert the map so we can look up person_id from the future object
future_to_pid = {v: k for k, v in futures.items()}

async for done_future in asyncio.as_completed(list(futures.values())):
    pid = future_to_pid[done_future]
    result = await done_future
    completed += 1
    yield {
        "type": "complete_one",
        "person_id": pid,
        "completed": completed,
        "total": total,
        **result,
    }
```

The `processing` event (one per researcher before they complete) needs reconsideration — with `as_completed`, there is no longer a predictable "now running" signal per researcher before it starts. The `queued` event already signals submission. The `complete_one` event signals completion. The `processing` event can be dropped or replaced with a generic "N researchers in flight" count on `started`.

**Frontend safety:** The pipeline page frontend maps incoming SSE events by `person_id`, not position. Non-deterministic completion order is safe.

**Worker count:** `MAX_WORKERS = min(4, os.cpu_count() or 2)` is already dynamic. Consider exposing as a config key (e.g., `pipeline.max_workers`) in `default_config.yaml` so power users can tune it.

---

### 3. Historical Pipeline Runs

**Current state:** No `run_id` concept anywhere in the codebase. Each call to `/api/pipeline/run` upserts scores in `person_article_score` (update-if-exists). There is no record of when runs happened, how many researchers were included, or what mode was used.

**New table (additive):**

```sql
CREATE TABLE pipeline_run (
    run_id       INT AUTO_INCREMENT PRIMARY KEY,
    started_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    mode         ENUM('full', 'update', 'score_only') NOT NULL,
    total_researchers INT DEFAULT 0,
    scored_count INT DEFAULT 0,
    status       ENUM('running', 'completed', 'failed') DEFAULT 'running'
);
```

**Additive columns on existing tables (non-breaking — NULL = pre-v2.0):**

```sql
ALTER TABLE person_article_score
    ADD COLUMN run_id INT NULL,
    ADD INDEX idx_pas_run_id (run_id);

ALTER TABLE retrieval_log
    ADD COLUMN run_id INT NULL;
```

**Why not change the PersonArticleScore primary key:** The existing PK is `(person_id, pmid, model_type)`. Adding `run_id` to the PK would break the upsert semantics that `stats_service.py` and `scores.py` depend on. All queries that join or aggregate on `person_article_score` would require `GROUP BY` changes. Instead: keep the PK, add `run_id` as a nullable non-PK column. The upsert continues to overwrite the "current" score. Historical runs can be queried by filtering on `run_id`.

**run_id flow through pipeline_runner.py:**

```
POST /api/pipeline/run
  → run_pipeline() async generator
      → INSERT INTO pipeline_run (mode, total_researchers, status='running')
      → capture run_id from DB (use db.refresh() or LAST_INSERT_ID())
      → yield {type: "started", run_id: run_id, total: N}
      → pass run_id to _process_one_researcher()
          → score upsert: set run_id = current run_id
          → retrieval_log update: set run_id = current run_id
          → return includes run_id in result dict
      → after all complete:
          → UPDATE pipeline_run SET completed_at=NOW(), status='completed',
              scored_count=total_scored
      → yield {type: "finished", run_id: run_id, completed: N}
```

**Run creation must happen in a thread, not directly in the async generator.** The `pipeline_run` INSERT is a DB write — it must use `loop.run_in_executor(None, ...)` or be done in a short synchronous preamble. See anti-patterns section.

**New API endpoints needed:**

```
GET /api/pipeline/runs
    → list all pipeline_run rows, newest first
    → response: [{run_id, started_at, completed_at, mode, total_researchers, scored_count, status}]

GET /api/pipeline/runs/{run_id}
    → single run detail
```

**`/api/pipeline/status` additions:**

```json
{
  "last_run_id": 42,
  "last_run_mode": "full",
  "last_run_completed_at": "2026-04-05T14:22:00"
}
```

**WorkflowContext additions:**

```typescript
interface WorkflowState {
  // existing fields ...
  lastRunId: number | null;       // NEW
  lastRunMode: string | null;     // NEW
}
```

**Results and Stats scoping:** Add optional `run_id` query param to `GET /api/scores/{person_id}` and `GET /api/stats`. When `run_id` is omitted, behavior is unchanged (latest scores). When provided, filter to that run's scores.

---

### 4. Results Refinement (Search/Filter)

**Current state:** `GET /api/scores/{person_id}` returns all scored articles, ordered by score descending. No server-side filtering. Client sorts by score/year/journal in JavaScript.

**Extend the existing endpoint with optional query params:**

```python
@router.get("/{person_id}")
def get_scores(
    person_id: str,
    q: str | None = Query(None),           # text search on title + journal
    min_score: float | None = Query(None),
    max_score: float | None = Query(None),
    assertion: str | None = Query(None),   # ACCEPTED | REJECTED | none
    run_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
```

All params are optional. When omitted, behavior is identical to today — backward-compatible.

**Query construction additions:**

```python
if q:
    query = query.filter(Article.title.ilike(f"%{q}%"))
if min_score is not None:
    query = query.filter(PersonArticleScore.calibrated_score >= min_score / 100)
if max_score is not None:
    query = query.filter(PersonArticleScore.calibrated_score <= max_score / 100)
if assertion == "none":
    query = query.filter(Curation.assertion == None)
elif assertion in ("ACCEPTED", "REJECTED"):
    query = query.filter(Curation.assertion == assertion)
if run_id is not None:
    query = query.filter(PersonArticleScore.run_id == run_id)
```

Note: `calibrated_score` in DB is stored as 0–1 float; the `min_score`/`max_score` params use 0–100 scale (same as the UI) and are divided by 100 before filtering.

**Source labeling:** `PersonArticle.source` is `ENUM('upload', 'search')`. The scores endpoint's current query joins `PersonArticleScore + Article + Curation` but not `PersonArticle`. Add one more join:

```python
.outerjoin(PersonArticle, (PersonArticleScore.person_id == PersonArticle.person_id)
                         & (PersonArticleScore.pmid == PersonArticle.pmid))
```

Add `"source": s.PersonArticle.source if s.PersonArticle else None` to the response dict.

**Per-researcher export:** `GET /api/scores/export` already accepts `person_id`. Apply the same filter params. The existing CSV columns stay; add `source` as a new column.

**Frontend changes in `[personId]/page.tsx`:** Add a search input and filter controls. On change, append params to the `apiFetch` call. Client-side sort remains client-side (sorting the already-fetched+filtered array).

---

### 5. UI Polish Integration Points

**Institution name display:** Already fully wired. `workflow.tsx` reads `institution_label` from `/api/institution` and stores it as `state.institution: string | null`. Any component that calls `useWorkflow()` can display it. Work needed: identify the exact components (sidebar header, dashboard title, pipeline page) that should show it and add `{workflow.institution}` to their JSX.

**Last run type:** Not yet tracked. Requires `pipeline_run.mode` surfaced via `/api/pipeline/status` as `last_run_mode`. Then WorkflowContext exposes `lastRunMode`, and the pipeline page or dashboard can display "Last run: Full retrieval · 2026-04-04".

**SSE reconnection:** The `subscribeSSE()` utility in `frontend/lib/sse.ts` (or wherever it lives) does not appear to reconnect on network drop based on usage in `[personId]/page.tsx`. For the pipeline page (which runs for minutes), this is a real concern. Mitigation: wrap `EventSource` with a retry on `onerror` with exponential backoff, capped at 3 retries. The SSE `finished` event serves as the definitive termination signal.

**Dashboard metrics:** `/api/pipeline/status` already returns `high_confidence`, `review_band`, `unlikely`. These can be displayed on the dashboard (`/`) without any backend change — just wire them into the page component.

---

## Data Flow

### Pipeline Run with Historical Tracking

```
POST /api/pipeline/run {mode: "full", person_ids: [...]}
  ↓
pipeline_runner.run_pipeline(person_ids, mode)
  ↓ [in thread] INSERT INTO pipeline_run → run_id=42
  ↓ yield {type: "started", run_id: 42, total: N}
  ↓
  ThreadPoolExecutor (MAX_WORKERS threads)
  ↓
  _process_one_researcher(pid, mode, config, model_dir, run_id=42)
    ↓ search_by_name(first, last, affiliation, ...)
    ↓   → {pmids, query_type, lenient_count, strict_count}
    ↓ fetch_articles(new_pmids)
    ↓ INSERT/UPDATE article, person_article
    ↓ UPDATE retrieval_log SET run_id=42, query_type=..., lenient_count=...
    ↓ compute_features() → feature_rows
    ↓ score_articles() → scored_df
    ↓ UPSERT person_article_score SET run_id=42
    ↓ return {person_id, article_count, scored_count, query_type, ...}
  ↓
  asyncio.as_completed() → yield {type: "complete_one", person_id, ...} as each finishes
  ↓
  [in thread] UPDATE pipeline_run SET completed_at=NOW(), status='completed', scored_count=N
  ↓
  yield {type: "finished", run_id: 42, completed: N}
```

### Results Page with Run Selector

```
User selects run_id=42 from dropdown (or uses default "latest")
  ↓
GET /api/scores/{personId}?run_id=42&min_score=50&q=cancer
  ↓
scores.py: filter PersonArticleScore WHERE run_id=42
  ↓
return [{pmid, score, source, assertion, ...}]
  ↓
Frontend renders filtered list, client-side sort applied on top
```

### Stats Scoped to a Run

```
GET /api/stats?run_id=42
  ↓
stats_service.compute_stats(db, run_id=42)
  ↓ JOIN person_article_score + curation WHERE score.run_id=42
  ↓ same computation pipeline (roc, calibration, pr, distribution)
  ↓ return identical response shape with run_id in metadata
```

---

## New vs Modified Components

### New (no existing code to change)

| Component | Type | Purpose |
|-----------|------|---------|
| `api/models.py::PipelineRun` | SQLAlchemy model | New `pipeline_run` table |
| `api/routers/pipeline.py::GET /runs` | Endpoint | List historical runs |
| `api/routers/pipeline.py::GET /runs/{run_id}` | Endpoint | Single run detail |
| Schema migration block | DDL | `pipeline_run` table + nullable `run_id` columns |
| `frontend/app/results/components/RunSelector.tsx` | React component | Run selector dropdown |
| `frontend/app/results/components/SearchFilter.tsx` | React component | Search + filter bar |

### Modified (changes to existing files)

| Component | Change | Risk |
|-----------|--------|------|
| `api/models.py` | Add `PipelineRun` model; add nullable `run_id` to `PersonArticleScore` + `RetrievalLog`; add retrieval metadata columns to `RetrievalLog` | Low — additive only |
| `api/schema.sql` | Mirror model changes in DDL | Low |
| `api/services/pipeline_runner.py` | Create `pipeline_run` on start; pass `run_id` to thread func; switch to `asyncio.as_completed`; update `pipeline_run` on completion | Medium — changes SSE event order |
| `core/pubmed.py` | No code change — caller change only | Low |
| `api/routers/scores.py::GET /{person_id}` | Add `q`, `min_score`, `max_score`, `assertion`, `run_id` params; join `PersonArticle` for source | Low — all params optional |
| `api/routers/scores.py::GET /export` | Same filter params; add `source` column to CSV | Low |
| `api/routers/pipeline.py::GET /status` | Add `last_run_id`, `last_run_mode`, `last_run_completed_at` | Low — additive |
| `api/services/stats_service.py::compute_stats` | Add optional `run_id` param to scope JOIN | Low — None = existing behavior |
| `frontend/lib/workflow.tsx` | Add `lastRunId`, `lastRunMode` to WorkflowState | Low — additive |
| `frontend/app/results/[personId]/page.tsx` | Add `SearchFilter` + `RunSelector` components, source badge | Medium — UI logic addition |
| `frontend/app/stats/page.tsx` | Add run selector, pass `run_id` to stats fetch | Low |

---

## Suggested Build Order

```
Phase 1: Schema Foundation
    ↓ (unblocks run_id wiring everywhere)
Phase 3: Historical Runs (API + pipeline_runner.py)
    ↓                  ↓
Phase 4:           Phase 5:
Results Refinement Stats Scoping + UI Polish

Phase 2a: Retrieval Parity (independent — just needs schema Phase 1 for persisting metadata)
Phase 2b: Parallel Processing (fully independent)
```

### Phase 1: Schema Foundation

Add `pipeline_run` table. Add nullable `run_id` to `person_article_score` and `retrieval_log`. Add `query_type`, `lenient_count`, `strict_count` columns to `retrieval_log`. Update `api/models.py` and `api/schema.sql`.

No behavior change at this phase — all new columns are nullable. Existing code continues to work without modification.

### Phase 2a: Retrieval Parity (depends on Phase 1 for persistence)

In `_process_one_researcher()`: pass `affiliation=core_identity.primary_institution` to `search_by_name()`. After the DB commit for articles, update `retrieval_log` with `query_type`, `lenient_count`, `strict_count`. Add these fields to the return dict so the `complete_one` SSE event reports the strategy used.

### Phase 2b: Parallel Processing (independent)

Switch `run_pipeline()` from submission-order await to `asyncio.as_completed`. Test SSE event ordering on the pipeline page frontend. Drop or redesign the `processing` event. Consider exposing `MAX_WORKERS` in `default_config.yaml`.

### Phase 3: Historical Runs (depends on Phase 1)

Create `PipelineRun` SQLAlchemy model. Wire `run_id` creation at pipeline start (in a thread, not the async generator body). Pass `run_id` into `_process_one_researcher()`. Update `pipeline_run` on completion. Add `GET /api/pipeline/runs` and `GET /api/pipeline/runs/{run_id}` endpoints. Update `/api/pipeline/status` to include last run metadata. Update `WorkflowContext`.

### Phase 4: Results Refinement (filter params independent; run_id param depends on Phase 3)

Extend `GET /api/scores/{person_id}` with filter query params. Add `PersonArticle` join for `source`. Extend export. Build `SearchFilter` and `RunSelector` React components. Wire into results page.

### Phase 5: Stats Scoping + UI Polish (run_id param depends on Phase 3; polish items independent)

Add optional `run_id` param to `compute_stats()`. Add run selector to stats page. Implement institution name display (zero backend work — already in WorkflowContext). Add reconnection logic to SSE utility. Wire `high_confidence`/`review_band`/`unlikely` into dashboard.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Adding run_id to the PersonArticleScore Primary Key

**What people do:** Change `PRIMARY KEY (person_id, pmid, model_type)` to include `run_id` for true historical snapshots.

**Why it's wrong:** Every pipeline run inserts new rows instead of updating. Stats queries that join `PersonArticleScore + Curation` return duplicate rows per researcher unless rewritten with `DISTINCT` or `GROUP BY`. `stats_service.py`, `scores.py`, and `pipeline_runner.py` all rely on the upsert behavior. Row count grows unboundedly — a 50-researcher, 2000-article dataset generates 100K rows per run.

**Do this instead:** Keep the PK intact. Add `run_id` as a nullable non-PK column with an index. Upsert continues to overwrite the current score while tagging it with the latest `run_id`. Historical comparison queries filter on the `run_id` column.

### Anti-Pattern 2: Blocking DB Writes Inside the Async Generator

**What people do:** Call synchronous SQLAlchemy writes directly inside `run_pipeline()` (the async generator function) to create the `pipeline_run` record.

**Why it's wrong:** The async generator body runs on the event loop. Any synchronous blocking DB call in the generator body blocks the event loop and stalls all other async work, including the SSE response being streamed to the client.

**Do this instead:** Wrap the `pipeline_run` INSERT in `loop.run_in_executor(None, _create_run_record, mode, total)` and `await` it before the first yield. The `_process_one_researcher()` thread function (already synchronous) is the correct place for all heavy DB work.

### Anti-Pattern 3: Client-Side Text Search on the Full Article List

**What people do:** Fetch all scored articles for a researcher and filter by title keyword in JavaScript.

**Why it's wrong:** Researchers with 2000+ articles cause visible lag on filter keystrokes. The SHAP features JSON compounds the payload size significantly.

**Do this instead:** Use the server-side `q` query param for title/journal text search. `LIKE %q%` on `Article.title` is fast at desktop scale (hundreds to low thousands of articles per researcher). Client-side sort on the already-filtered result set is fine.

### Anti-Pattern 4: Overloading RetrievalLog as a Run Registry

**What people do:** Add `total_researchers`, `mode`, and `status` fields to `retrieval_log` to avoid creating the `pipeline_run` table.

**Why it's wrong:** `retrieval_log` is keyed on `person_id` — one row per researcher. It is physically incapable of storing run-level aggregates (total across all researchers, completion status, run mode) without violating its purpose. Adding a `run_id` FK to link a retrieval event back to a run is correct use of the table. Using it as the run registry itself is not.

**Do this instead:** Create the `pipeline_run` table for run-level metadata. `retrieval_log` gets a `run_id` FK column pointing to it.

### Anti-Pattern 5: Removing the processing Event Without Frontend Update

**What people do:** Drop the `processing` SSE event when switching to `asyncio.as_completed` without updating the pipeline page frontend.

**Why it's wrong:** If the pipeline page renders researcher rows in `processing` state and waits for `complete_one` to update them, removing `processing` will leave rows stuck in an indeterminate state for fast researchers that complete before slower ones emit their event.

**Do this instead:** Audit the pipeline page event handling before dropping `processing`. Options: keep the event (emit it immediately before submitting the future), or replace it with a `started` aggregate count, or remove it and rely only on `queued` + `complete_one`.

---

## Scaling Considerations

This is a local desktop application. Scaling is not a concern beyond the following practical limits.

| Scenario | Recommendation |
|----------|---------------|
| 1–50 researchers | Current architecture with v2.0 changes is sufficient |
| 50–500 researchers | Increase `MAX_WORKERS` via config; rate limiter handles PubMed |
| 500+ researchers | Would require persistent task queue (Celery/RQ) — out of scope |

The one practical concern is `person_article_score` row count as runs accumulate under the nullable `run_id` approach. Since scores are upserted (not inserted per run), row count stays bounded by `(researchers × articles_per_researcher × model_types)` regardless of run count. This is not a growth concern.

---

## Sources

- Direct inspection: `core/pubmed.py` — retrieval strategy confirmed complete and correct
- Direct inspection: `api/services/pipeline_runner.py` lines 335–361 — submission-order await pattern confirmed
- Direct inspection: `api/models.py` and `api/schema.sql` — 6 tables, no `run_id`, confirmed
- Direct inspection: `api/routers/scores.py` — no filter query params exist today, confirmed
- Direct inspection: `api/routers/pipeline.py` — SSE StreamingResponse pattern, confirmed
- Direct inspection: `frontend/lib/workflow.tsx` — WorkflowState fields, `institution` already present
- Direct inspection: `frontend/app/results/[personId]/page.tsx` — client-side sort only, confirmed
- Direct inspection: `api/services/stats_service.py` — not run-scoped, confirmed
- Direct inspection: `.planning/PROJECT.md` — milestone feature list confirmed

---

*Architecture research for: ReCiter Desktop v2.0 Pipeline Parity & Performance*
*Researched: 2026-04-05*
