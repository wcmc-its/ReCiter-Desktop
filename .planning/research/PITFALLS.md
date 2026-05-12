# Pitfalls Research

**Domain:** Adding retrieval parity, parallelism, and historical versioning to an existing PubMed + ML scoring pipeline (Next.js + FastAPI + MariaDB)
**Researched:** 2026-04-05
**Confidence:** HIGH — based on direct code inspection of `core/pubmed.py`, `api/services/pipeline_runner.py`, `api/schema.sql`, `api/models.py`, project memory files, the historical-pipeline-runs feature doc, and prior stats pitfalls research

---

## Critical Pitfalls

### Pitfall 1: `retrieval_log` Table Exists in ORM but Was Missing from `schema.sql`

**What goes wrong:**
Fresh Docker Compose installs — new users, CI environments, paper reproducibility runs — build the DB from `schema.sql`. The `RetrievalLog` SQLAlchemy model exists in `api/models.py` but the matching `CREATE TABLE` was never back-ported to `schema.sql`. SQLAlchemy does not fail at startup; it fails the first time `_process_one_researcher` reaches line 115 (`db.query(RetrievalLog).filter_by(person_id=person_id).first()`), raising `ProgrammingError: Table 'reciter_desktop.retrieval_log' doesn't exist`. The pipeline SSE stream emits an error event for every researcher and terminates. Users see a silent failure with no actionable message.

**Note:** `schema.sql` was verified to already contain `CREATE TABLE IF NOT EXISTS retrieval_log` as of 2026-04-05. However, project memory (`project_state.md` item #5) recorded this as a known gap, meaning it may have been added to the main branch but not to worktree or branch copies. Verify the current branch has the table before proceeding.

**Why it happens:**
The ORM model was added during active development against an already-running database. The `schema.sql` DDL was not updated at the same time. The dev environment masked the bug because the DB already had the table.

**How to avoid:**
Add a pre-flight check: every class in `api/models.py` inheriting from `Base` must have a matching `CREATE TABLE IF NOT EXISTS` in `schema.sql`. Run `docker compose down -v && docker compose up` and attempt a pipeline run as the literal first test of every phase. Treat schema/ORM drift as a blocking issue.

**Warning signs:**
- Pipeline SSE stream emits `error` events for all researchers simultaneously
- Error message contains `doesn't exist` or `no such table`
- Fresh `docker compose` install fails on first pipeline run but existing dev environments work

**Phase to address:**
Phase 1 (Parallel Processing) — verify before any other Phase 1 work. Parallel workers will all hit the same missing table simultaneously, producing confusing interleaved error events.

---

### Pitfall 2: `run_pipeline` Awaits Results in Submission Order, Negating Parallel Execution in the UI

**What goes wrong:**
All researchers are submitted to the `ThreadPoolExecutor` concurrently (correct), but the SSE event loop then iterates `for pid in person_ids` and does `result = await futures[pid]` — blocking on the first researcher until they finish before yielding the second `processing` event. Researcher #3 may finish in 2 seconds but the UI does not acknowledge their completion until researchers #1 and #2 have also finished. The pipeline wall-clock time is correct (parallel), but the progress display is serial. Users see one "Active" researcher at a time and perceive no speedup.

**Why it happens:**
The futures dict is keyed to submission order and awaited in that order. The code looks parallel (thread pool submission), but the `async for` generator serializes result collection. `asyncio.as_completed` is the correct fix and is explicitly named in the Phase 1 milestone goals, but the current code predates it.

**How to avoid:**
Replace the ordered await loop with `asyncio.as_completed`. Collect all futures as a list and iterate:
```python
all_futures = [futures[pid] for pid in person_ids]
for coro in asyncio.as_completed(all_futures):
    result = await coro
    completed += 1
    yield {"type": "complete_one", "person_id": result["person_id"], ...}
```
Note: `asyncio.as_completed` returns coroutines in completion order, so `result["person_id"]` must come from the result dict, not from the loop index.

**Warning signs:**
- Pipeline UI only shows one researcher as "Active" at a time even when `MAX_WORKERS >= 4`
- Adding timing logs shows all `_process_one_researcher` calls start within milliseconds of each other but SSE events arrive one at a time
- Removing the thread pool entirely produces identical perceived behavior

**Phase to address:**
Phase 1 (Parallel Processing) — this is the primary deliverable.

---

### Pitfall 3: Adding `run_id` to `person_article_score` Requires a Single Atomic `ALTER TABLE` — Multi-Step Migrations Break the PK

**What goes wrong:**
The current primary key on `person_article_score` is `(person_id, pmid, model_type)`. Adding `run_id` as a fourth PK component requires: adding the column, migrating existing rows to `run_id = 1`, and redefining the PK. If these are done as separate `ALTER TABLE` statements, the table has no PK between the `DROP PRIMARY KEY` and `ADD PRIMARY KEY` steps — a window where concurrent reads/writes during a live migration can produce inconsistent data. Additionally, `ADD COLUMN run_id INT NOT NULL` on a non-empty table fails in strict SQL mode without a DEFAULT.

**Why it happens:**
Developers write migrations as sequential `ALTER TABLE` calls, one concern per statement. MariaDB allows combining multiple `ALTER TABLE` clauses in a single statement, which is the safe approach, but it requires careful syntax and is often missed.

**How to avoid:**
Write the entire migration as a single `ALTER TABLE` statement:
```sql
ALTER TABLE person_article_score
  ADD COLUMN run_id INT NOT NULL DEFAULT 1 AFTER model_type,
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (person_id, pmid, model_type, run_id),
  ADD CONSTRAINT fk_pas_run FOREIGN KEY (run_id) REFERENCES pipeline_run(run_id);
```
`pipeline_run` must be created and have a row with `run_id = 1` inserted before this statement runs (FK target must exist). Test the full migration on a populated copy of the DB (not an empty test instance) before applying.

**Warning signs:**
- Migration script has separate `ALTER TABLE ... DROP PRIMARY KEY` and `ALTER TABLE ... ADD PRIMARY KEY` statements
- No `pipeline_run` row 1 inserted before the FK is added
- Migration runs only against empty test DB, not against populated dev DB

**Phase to address:**
Phase 3 (Historical Pipeline Runs) — write and test the migration as the absolute first task of this phase before any application code changes.

---

### Pitfall 4: `update` Mode `mindate` Is Silently Corrupted by Any Write to `retrieval_log`

**What goes wrong:**
`RetrievalLog.last_retrieval_date` has `onupdate=func.now()` in the ORM and `ON UPDATE CURRENT_TIMESTAMP` in the schema DDL. Any `UPDATE` statement touching the `retrieval_log` row — including updating `articles_found` at the end of a score-only run — advances `last_retrieval_date` to now. A subsequent `update` mode run uses this corrupted timestamp as `mindate`, missing all articles published since the last *full retrieval* but before the incidental write. The researcher appears up-to-date but their article set is stale.

**Why it happens:**
`ON UPDATE CURRENT_TIMESTAMP` fires on any `UPDATE` to the row, not just intentional timestamp sets. The pipeline runner updates `retrieval_log.articles_found` at line 180 in both `full` and `update` modes, which silently triggers the timestamp update.

**How to avoid:**
Either (a) add a separate `last_full_retrieval_date` column that is explicitly set only when a `full` or `update` retrieval run completes, or (b) remove `onupdate` from the ORM definition entirely and set the timestamp with an explicit `retrieval_log.last_retrieval_date = datetime.utcnow()` only in the retrieval branch. Score-only runs must not touch the `retrieval_log` table at all.

**Warning signs:**
- `update` mode runs after score-only runs retrieve far fewer articles than expected
- `retrieval_log.last_retrieval_date` advances even when the pipeline is run in `score_only` mode
- Researchers added recently are absent from `update` mode results

**Phase to address:**
Phase 2 (Retrieval Strategy Parity) — `update` mode is listed as "wired but untested end-to-end." Fixing the timestamp semantics must be part of the end-to-end test.

---

### Pitfall 5: Compound and Non-ASCII Last Names Break PubMed Query Construction Silently

**What goes wrong:**
`_build_author_term` in `core/pubmed.py` quotes the author term only when `" " in last_name or "-" in last_name`. PubMed E-utilities treats other characters as special: apostrophes (`O'Brien`), brackets, and names with Unicode diacritics that PubMed normalizes to ASCII (`López` → `Lopez`). An unquoted `O'Brien B[au]` will fail silently — PubMed may return 0 results or misparse the query. The pipeline logs `lenient_count = 0` and records the researcher as "no articles found" rather than "query error," making the bug invisible without a known-answer validation set.

**Why it happens:**
The quoting condition was written for the most common cases (hyphenated, two-word surnames). Apostrophes and diacritics were not encountered in the initial dev dataset (Fred Hutch, WCM).

**How to avoid:**
Broaden the quoting condition to always quote when the name contains any character outside `[A-Za-z]`:
```python
import re
needs_quoting = bool(re.search(r"[^A-Za-z ]", last_name)) or " " in last_name
```
Add a normalization step using `unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode()` to strip diacritics before building the query — matching PubMed's own normalization. Add unit tests covering `O'Brien`, `van der Berg`, `López`, `Müller`, and `St. John`.

**Warning signs:**
- Researchers with `'` in their last name return `lenient_count = 0` despite known publications
- No unit tests for `_build_author_term` with non-ASCII or punctuated names
- Paper validation set includes any WCM/Cornell researchers with hyphenated or non-ASCII names

**Phase to address:**
Phase 2 (Retrieval Strategy Parity) — directly affects paper validation correctness.

---

### Pitfall 6: Global `_TokenBucket` Is Thread-Safe but Not Process-Safe

**What goes wrong:**
`core/pubmed.py` uses a module-level `_bucket = _TokenBucket(rate=2.5)` with a `threading.Lock`. This correctly rate-limits concurrent threads within a single Python process. If the application is started with multiple Uvicorn workers (`--workers N`), each process has its own `_bucket`. With 4 workers × 4 threads, 16 concurrent PubMed requests can be made against a 3 req/sec NCBI limit. NCBI returns HTTP 429, which the current `except requests.RequestException` block swallows with `continue` — silently dropping article batches with no user notification.

**Why it happens:**
The bucket was designed for single-process operation, which is correct for the current Docker Compose setup. The pitfall is triggered if someone scales workers during performance investigation, or if `--workers 4` is added to the Dockerfile as a "performance improvement."

**How to avoid:**
Add an explicit comment to `api/main.py` and the Dockerfile that `--workers 1` is required for PubMed rate limiting. Do not use `--workers N > 1` without replacing the in-process token bucket with a Redis-backed shared rate limiter. The current `MAX_WORKERS` in `pipeline_runner.py` controls *threads*, not processes, and is safe.

**Warning signs:**
- Uvicorn started with `--workers 4` in `docker-compose.yml` or `Dockerfile`
- HTTP 429 responses appearing as `efetch failed` in logs
- Fetched article count systematically lower than `esearch_count` predicted

**Phase to address:**
Phase 1 (Parallel Processing) — document the constraint as a comment when `MAX_WORKERS` is increased.

---

### Pitfall 7: Concurrent DB Sessions Hold Connections Open for the Full Pipeline Duration

**What goes wrong:**
`_process_one_researcher` opens `db = SessionLocal()` at line 99 and holds the connection open through the entire retrieval + scoring pipeline — potentially 60+ seconds per researcher for large sets. With `MAX_WORKERS = 8` (Phase 1 goal for API-key users) plus FastAPI request handler connections, this approaches or exceeds SQLAlchemy's default pool (`pool_size=5`, `max_overflow=10`) under load. New requests block waiting for a connection.

**Why it happens:**
A single session for the full pipeline duration is the simplest pattern. The resource cost is invisible at 4 workers but becomes apparent at 8.

**How to avoid:**
Set pool parameters in `api/database.py` to match the expected `MAX_WORKERS`:
```python
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=MAX_WORKERS + 4, max_overflow=4)
```
Alternatively, shorten the session lifetime: close the session after the retrieval phase commits, then open a new session for the scoring phase. This releases connections back to the pool between the two most time-consuming phases.

**Warning signs:**
- `QueuePool limit of size X overflow Y reached` in FastAPI logs
- Pipeline stalls silently after a few researchers complete
- DB connection errors only manifest at high researcher counts (>10)

**Phase to address:**
Phase 1 (Parallel Processing) — connection pool sizing must be addressed alongside `MAX_WORKERS` changes.

---

### Pitfall 8: SSE Stream Has No Reconnect Semantics — Pipeline State Is Lost on Page Reload

**What goes wrong:**
The SSE `event_stream` generator in `pipeline.py` starts fresh on each POST to `/api/pipeline/run`. If the browser tab reloads or the SSE connection drops, the client receives no in-progress events and has no way to recover the run state. The pipeline continues in the backend but the frontend shows a stale "not running" state. The milestone doc explicitly flags "reconnection polling — verify it correctly detects completion for all edge cases" as an open gap.

**Why it happens:**
SSE generators are one-shot. Without a persistent run record, there is nothing to reconnect to.

**How to avoid:**
Phase 3's `pipeline_run` table provides the persistent state. A reconnecting client should poll `/api/runs/latest` to check if `status = "running"` or `"complete"`, then reconstruct the UI from the run record rather than re-subscribing to a new SSE stream. The SSE stream itself is ephemeral; the run record is the source of truth.

**Warning signs:**
- No `pipeline_run` table exists (Phase 3 prerequisite)
- Frontend has no logic to check for an in-progress run on mount
- Page reload during a pipeline run shows "no runs yet" state

**Phase to address:**
Phase 3 (Historical Pipeline Runs) — reconnect recovery depends on `pipeline_run` existing. Phase 5 polish (reconnection) is blocked on Phase 3.

---

### Pitfall 9: `retrieve_known` Mode May Score from Stale DB Metadata Instead of Fetching Fresh PubMed XML

**What goes wrong:**
The milestone doc flags: "Verify `retrieve_known` mode fetches PubMed XML for uploaded PMIDs before scoring (currently maps to `score_only` which may skip metadata fetch)." If PMIDs are uploaded but their `article` rows don't exist in the DB yet, `score_only` mode will query `db.query(Article).filter(Article.pmid.in_(pmids)).all()` and get an empty list, resulting in zero scored articles with no error. The user sees `article_count = 0, scored_count = 0` and assumes the pipeline ran successfully.

**Why it happens:**
`score_only` mode was designed for the case where articles are already in the DB (from a prior full run). The PMID-upload workflow adds `person_article` rows but may not populate the `article` table.

**How to avoid:**
After a PMID upload, check whether each uploaded PMID has a corresponding `article` row. If not, fetch the missing articles from PubMed before scoring. Add a specific mode flag (`retrieve_known`) distinct from `score_only` that guarantees a PubMed fetch step for any PMID missing from the `article` table.

**Warning signs:**
- PMID upload followed by pipeline run returns `scored_count = 0` for all researchers
- `article` table is empty after PMID upload
- No PubMed fetch log lines when `score_only` is used with freshly uploaded PMIDs

**Phase to address:**
Phase 2 (Retrieval Strategy Parity) — listed explicitly in the milestone doc.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| No migration framework (raw SQL in `schema.sql`) | Less setup, no Alembic dependency | Schema drift between ORM and DDL is undetectable; each change requires manual cross-check | Acceptable for MVP; add Alembic before Phase 3 migration lands |
| Swallowing PubMed errors with bare `continue` in `fetch_articles` | Pipeline does not abort on transient errors | Silently returns fewer articles than expected; user has no indication batches were dropped | Replace with retry + final error count reported in SSE events |
| Global `_model_cache` dict in `scoring.py` with no lock | Avoids repeated disk reads | Two threads may simultaneously load and write the cache on cold start (last write wins — benign but wasteful) | Add a `threading.Lock` around cache miss handling in Phase 1 |
| `ON UPDATE CURRENT_TIMESTAMP` for `last_retrieval_date` | No application code needed to track last write time | Corrupts the `mindate` used by `update` mode whenever any write touches the row | Never for retrieval-tracking columns — set timestamp explicitly |
| Awaiting futures in submission order | Simple code | Negates the user-visible benefit of parallelism; progress display is serial | Never — fix with `asyncio.as_completed` |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| PubMed E-utilities rate limiting | Using the published rate (3/sec, 10/sec) as the exact target | Stay slightly below: 2.5/sec without key, 9/sec with key. NCBI enforces at the burst level; hitting exactly 3/sec under concurrent requests triggers 429s |
| PubMed `esearch` with `rettype=count` | Assuming `<Count>` is always present and numeric | It is absent when the query syntax is invalid; `esearch_count()` returns 0 silently — add a query-validity log warning when count is 0 for a researcher with known publications |
| PubMed PDAT date filter | Using ISO 8601 format (`2025-01-15`) | PubMed requires `YYYY/MM/DD`: `("2025/01/15"[PDAT] : "3000"[PDAT])`. Current `strftime("%Y/%m/%d")` is correct but fragile — add a format assertion in tests |
| MariaDB JSON column reads | Assuming JSON columns always return Python dicts | PyMySQL returns JSON as dicts in MariaDB 10.5+ but as strings in some driver/version combinations. `_db_article_to_core` handles the dict case; add a `json.loads` fallback for string values |
| SSE and FastAPI `StreamingResponse` | Assuming stream is immediately flushed | Uvicorn may buffer SSE events unless `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers are set. Missing headers cause clients to receive all events at once on connection close |
| `asyncio.as_completed` with `run_in_executor` results | Assuming result dict contains `person_id` in correct order | With `as_completed`, completion order is non-deterministic. Always extract `person_id` from `result["person_id"]`, not from a parallel index variable |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading full `Article` rows for all researchers' PMIDs | `db.query(Article).filter(Article.pmid.in_(pmids)).all()` fetches abstracts, full JSON fields for every article | Use `.with_entities()` to select only the columns needed for feature generation | Breaks at ~1,000 articles per researcher; Fred Hutch full dataset (28k articles) hits this in batch mode |
| No index on `(person_id, run_id)` after adding `run_id` column | Queries filtering scores by researcher + run perform full table scans | Add composite index at migration time: `CREATE INDEX idx_pas_run ON person_article_score (person_id, run_id)` | Degrades immediately once run history accumulates; worst at 10+ runs |
| `MAX_WORKERS` set equal to CPU count for an I/O-bound workload | Workers idle on PubMed API waits; rate limit headroom unused | For API-key users: `MAX_WORKERS = 8`; without key: `min(4, int(rate_limit / 1.5))` | Under-provisioned from day one with the current `min(4, cpu_count())` formula |
| Pre-computing stats synchronously in the pipeline SSE path | Stats endpoint times out; pipeline SSE blocks on stat computation | Pre-compute `pipeline_run_stats` at run completion in a background task; stats page reads from cache | Breaks at ~500 curated articles (bootstrap CI is CPU-bound at that scale) |

---

## "Looks Done But Isn't" Checklist

- [ ] **`retrieval_log` in `schema.sql`**: Verify `CREATE TABLE IF NOT EXISTS retrieval_log` is present. Test: `docker compose down -v && docker compose up` then run a pipeline — must not error.
- [ ] **`update` mode end-to-end**: Verify second pipeline run with `mode=update` passes a non-empty `mindate` to `search_by_name` and the resulting PDAT filter string is syntactically valid for PubMed.
- [ ] **Compound name quoting**: Verify `_build_author_term` produces valid `[au]` terms for `O'Brien`, `van der Berg`, `López`, `Müller`, `St. John`. Each must return non-zero `esearch_count` for researchers with known publications.
- [ ] **`run_id` FK constraint**: Verify migration inserts `pipeline_run` row 1 *before* adding the FK to `person_article_score`. Test: migration must succeed on populated dev DB, not just empty test DB.
- [ ] **SSE headers**: Verify `StreamingResponse` in `pipeline.py` includes `Cache-Control: no-cache` so progress events arrive incrementally, not batched at stream close.
- [ ] **`asyncio.as_completed` result identity**: Verify `person_id` in emitted SSE events comes from `result["person_id"]`, not from the submission-order loop variable.
- [ ] **`retrieve_known` fetches XML**: Verify PMID-upload workflow fetches article metadata from PubMed for PMIDs not already in the `article` table before scoring.
- [ ] **`retrieval_log` not touched by score-only runs**: Verify `score_only` mode does not update `last_retrieval_date`. Test: run score-only, check that `retrieval_log` timestamp is unchanged.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| `retrieval_log` missing from `schema.sql` | LOW | Add DDL to `schema.sql`; run manually on existing DB or recreate from scratch |
| `run_id` migration fails mid-step | HIGH | Restore from pre-migration DB snapshot; rewrite as single atomic `ALTER TABLE`; re-apply |
| `update` mode `mindate` corrupted | MEDIUM | Manually null out `last_retrieval_date` in `retrieval_log` for affected researchers; re-run in `full` mode |
| PubMed 429s silently drop batches | MEDIUM | Add retry with exponential backoff in `fetch_articles`; re-run pipeline for researchers with unexpectedly low article counts |
| SSE stream lost on disconnect | LOW (with Phase 3) | Poll `/api/runs/latest` on reconnect; render final state from completed `pipeline_run` record |
| `update` mode fetches nothing for common names | MEDIUM | Check `lenient_count` log for unexpectedly low counts; verify PDAT filter syntax; test against PubMed directly |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| `retrieval_log` schema gap | Phase 1 (first task) | Fresh `docker compose down -v && up` + pipeline run succeeds without errors |
| `as_completed` ordering fix | Phase 1 | Multiple researchers show "Active" simultaneously in pipeline UI |
| Connection pool exhaustion | Phase 1 | Pipeline with 8 workers + 20 researchers completes without `QueuePool` errors |
| Global token bucket process-safety | Phase 1 (documentation) | `docker-compose.yml` and Dockerfile enforce `--workers 1` |
| `update` mode `mindate` corruption | Phase 2 | Score-only run does not advance `last_retrieval_date`; `update` mode passes correct `mindate` |
| Compound name quoting gaps | Phase 2 | Unit tests covering apostrophes, diacritics, multi-word names all pass |
| `retrieve_known` missing XML fetch | Phase 2 | PMID-upload + pipeline run produces non-zero `scored_count` for freshly uploaded PMIDs |
| `run_id` migration atomic DDL | Phase 3 (first task) | Migration runs on populated dev DB without errors; all existing scores have `run_id = 1` |
| Reconnect semantics | Phase 3 (enabled by `pipeline_run`) | Page reload during pipeline run shows correct status on reconnect via `pipeline_run.status` |

---

## Prior Research Coverage

The original `PITFALLS.md` (researched 2026-04-04) covers pitfalls for the Statistics page build (calibration plot small-n, AUC confidence intervals, PR curve baseline, Recharts SSR errors, disagreements framing, gating logic). Those pitfalls remain valid for the Stats page work. This file covers the v2.0 milestone additions: retrieval parity, parallelism, and historical runs.

---

## Sources

- Direct code inspection: `core/pubmed.py` (token bucket, query builder, esearch pagination logic), `api/services/pipeline_runner.py` (concurrency model, session lifecycle, retrieval log writes), `api/schema.sql` (DDL), `api/models.py` (ORM)
- Project memory: `.claude/projects/.../memory/project_retrieval_parity.md` — retrieval parity requirements and `retmax` cap history
- Project memory: `.claude/projects/.../memory/project_state.md` — `retrieval_log` schema gap (item #5), known remaining items
- Feature doc: `docs/feature-requests/historical-pipeline-runs.md` — `run_id` migration strategy, `pipeline_run` schema
- Milestone doc: `docs/milestones/milestone-2-pipeline-parity.md` — phase goals, open questions, `retrieve_known` gap flag
- NCBI E-utilities documentation: rate limits, PDAT date format, `rettype=count` behavior
- MariaDB documentation: `ON UPDATE CURRENT_TIMESTAMP` semantics, atomic multi-clause `ALTER TABLE`
- FastAPI SSE documentation: `StreamingResponse` buffering, required headers

---
*Pitfalls research for: ReCiter Desktop v2.0 — Pipeline Parity, Parallelism, and Historical Runs*
*Researched: 2026-04-05*
