# Stack Research

**Domain:** Desktop research disambiguation tool — v2.0 Pipeline Parity & Performance
**Researched:** 2026-04-05
**Confidence:** HIGH

## Summary

This is a stack delta document. The v1.0 stack (Next.js 14 + FastAPI + MariaDB + XGBoost 3.2.0) is validated and unchanged. This document covers only what is needed for the five new v2.0 feature areas. The answer is: almost nothing new is needed. The dominant work is logic changes and schema additions within the existing stack.

---

## Feature-by-Feature Stack Analysis

### 1. Retrieval Strategy Parity

**What's needed:** Replicate ReCiter's full compound-name detection and affiliation-augmented PubMed query construction.

**Verdict: No new libraries.** `core/pubmed.py` already has the correct strict/lenient decision tree with esearch count gating. The gaps are pure logic additions:

- **Compound name detection** — `AliasReCiterRetrievalEngine.identityAuthorNames()` detects compound surnames (spaces or hyphens where both parts are 4+ chars) and compound first names (spaces, dots, single-initial-with-middle). When detected, sets `useStrictQueryOnly=True` before the first esearch call, and all name terms are quoted: `"Garcia Marquez G"[au]` instead of `Garcia Marquez G[au]`.
- **Affiliation-augmented fallback** — When lenient count exceeds threshold, Java runs three additional query strategies in parallel: `AffiliationInDbRetrievalStrategy` (identity's institution list as `[affiliation]`), `AffiliationRetrievalStrategy` (configured home institution keywords as `[affiliation]`), and `FullNameRetrievalStrategy` (full first name instead of initial). Results are merged by PMID deduplication.
- **eSearchCount storage** — When lenient count exceeds threshold, Java stores the raw count for use by `ArticleSizeStrategy`'s `log(count)` scoring formula. In Desktop, this means adding an `esearch_count` column to `retrieval_log`.

**Source authority:** Java source at `AliasReCiterRetrievalEngine.java` lines 163, 247–276, and `PubMedQueryType.PubMedQueryBuilder.contsructAuthorQuery()` (lines 153–196) are the exact reference. The logic is already translated 80% into `_build_author_term()` — the quoting of compound names is already present, but the `useStrictQueryOnly` bypass (skip lenient entirely when compound name detected) is not yet wired.

**What to implement in Python (no new packages):**
- `detect_compound_name(last_name, first_name, middle_name) -> bool` — mirrors Java compound detection logic
- If compound detected: skip lenient query entirely, run strict query directly
- `build_affiliation_query(name_term, affiliation_keywords) -> str` — AND-combines name term with `[affiliation]` keywords
- Add `esearch_count` INTEGER to `retrieval_log` table (schema migration only)

---

### 2. Parallel Researcher Processing

**What's needed:** True as-completed concurrency so faster researchers complete visually before slower ones, and dynamic worker count.

**Verdict: No new libraries.** `asyncio.as_completed()` is stdlib. The current `pipeline_runner.py` already uses `asyncio + ThreadPoolExecutor` but waits for researchers in submission order (sequential `await futures[pid]` loop). The fix is mechanical:

```python
# Replace sequential await loop with as_completed
futures = {
    loop.run_in_executor(executor, _process_one_researcher, pid, mode, config, model_dir): pid
    for pid in person_ids
}
for coro in asyncio.as_completed(futures.keys()):
    result = await coro
    pid = futures[coro]  # map back to person_id
    # emit complete_one immediately
```

**Dynamic worker count** — Already at `min(4, os.cpu_count())`. The v2.0 improvement is exposing this as a configurable parameter in the pipeline request, with a sensible cap (e.g., `min(requested, os.cpu_count() * 2, 8)`). No new libraries.

**SSE stream ordering** — The frontend currently renders researchers in the order `complete_one` events arrive. This is already correct behavior; no frontend changes needed for as-completed to work visually.

---

### 3. Historical Pipeline Runs

**What's needed:** A `pipeline_run` table tracking each run with a `run_id`, and association of scores to their run so the UI can show a run selector on Results and Stats pages.

**New library needed: Alembic** — The project currently uses raw SQLAlchemy DDL (`Base.metadata.create_all`) with no migration tooling. Adding the `pipeline_run` table and a `run_id` foreign key to `person_article_score` requires a migration. Without Alembic, the only option is DROP/recreate which destroys existing scores. Alembic provides incremental, reversible schema migrations.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| alembic | 1.13.x | SQLAlchemy schema migrations | Only migration tool with first-class SQLAlchemy integration; `autogenerate` compares models to DB state and emits `ALTER TABLE` statements |

**Install:**
```bash
pip install alembic==1.13.3
alembic init alembic
```

**Schema additions (two migrations):**

Migration 1 — Add `pipeline_run` table:
```sql
CREATE TABLE pipeline_run (
    run_id            VARCHAR(36) PRIMARY KEY,  -- UUID
    mode              ENUM('full', 'update', 'score_only') NOT NULL,
    started_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at       TIMESTAMP NULL,
    total_researchers INT DEFAULT 0,
    scored_researchers INT DEFAULT 0,
    status            ENUM('running', 'complete', 'failed') DEFAULT 'running'
);
```

Migration 2 — Add `run_id` to `person_article_score`:
```sql
ALTER TABLE person_article_score
    ADD COLUMN run_id VARCHAR(36) NULL,
    ADD INDEX idx_pas_run_id (run_id);
-- FK is intentionally omitted: runs can be pruned without cascading score deletion
```

**run_id generation** — `uuid.uuid4()` in `pipeline_runner.py`, passed through to each worker via function argument. No new library (uuid is stdlib).

**Frontend run selector** — A `<select>` dropdown on Results and Stats pages populated from `GET /api/pipeline/runs`. No new frontend libraries; uses existing Tailwind/shadcn select pattern.

---

### 4. Results Page Refinement

**What's needed:** Search/filter on scored articles (by title, journal, score range, assertion status, source label).

**Verdict: No new libraries.** All filtering is client-side `useState` on the already-loaded article array. The results page fetches all scored articles for a researcher on mount. Filter state is local React state; no server-side query changes needed for the basic case.

**Pattern:**
```typescript
const [query, setQuery] = useState("");
const [minScore, setMinScore] = useState(0);
const filtered = articles.filter(a =>
    (a.title.toLowerCase().includes(query.toLowerCase()) ||
     a.journal.toLowerCase().includes(query.toLowerCase())) &&
    a.score >= minScore
);
```

UI components needed: `<Input>` (shadcn, already available), score range slider (shadcn `Slider` — verify installed via `components.json`), `<Select>` for assertion filter. All within existing shadcn + Tailwind setup.

**Per-researcher export** — The export endpoint already exists at `GET /api/results/{person_id}/export`. The UI just needs a button wired to `apiExportUrl(person_id)`. No backend changes.

**Source labeling** — `person_article.source` column already exists (`"upload"` | `"search"`). The results API endpoint needs to join and include this field; no schema changes.

---

### 5. UI Polish

**What's needed:** Institution name in header/sidebar, last run type badge, SSE reconnection logic, dashboard metric cards.

**Verdict: No new libraries.** All changes are within existing Next.js + Tailwind + shadcn stack.

- **Institution name** — `GET /api/institution/config` already returns `institution_label`. Display in sidebar header using existing layout.
- **Last run type** — Add `last_run_mode` to `GET /api/pipeline/status` response (query `pipeline_run` table for most recent row). Frontend shows a badge using existing `ScoreBadge` pattern.
- **SSE reconnection** — The existing `subscribeSSE()` in `frontend/lib/sse.ts` needs an exponential backoff reconnect loop. Standard EventSource pattern; no library needed.
- **Dashboard metrics** — Additional stat cards on the home page using data already available from `GET /api/pipeline/status`.

---

## Recommended Stack (Delta Only)

### New Library

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| alembic | 1.13.3 | SQLAlchemy database migrations | Only addition needed for v2.0; enables incremental schema changes without data loss as `pipeline_run` and `run_id` columns are added to an existing populated database |

### Unchanged Core Stack

| Technology | Version | Status |
|------------|---------|--------|
| Next.js | 14.2.35 | No change — keep pinned, do not upgrade to 15 |
| FastAPI | >=0.109.0 | No change |
| SQLAlchemy | >=2.0.0 | No change |
| MariaDB | (Docker) | Schema additions only |
| XGBoost | 3.2.0 | PINNED — exact version, never change |
| asyncio + ThreadPoolExecutor | stdlib | No change — use as_completed pattern fix |
| sse-starlette | >=1.6.0 | No change |
| Recharts | ^3.8.1 | No change — already installed |
| shadcn / Tailwind | current | No change |

---

## Installation

```bash
# Backend only — one new package
cd api
pip install alembic==1.13.3

# Initialize Alembic (one-time, in api/)
alembic init alembic
# Then configure alembic/env.py to import api.models.Base and read DATABASE_URL from env
```

No frontend package changes needed.

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| alembic | Manual `ALTER TABLE` scripts | No rollback, no state tracking, schema diverges between instances |
| alembic | Django-style auto-migrations | Django ORM is not used; Alembic is the SQLAlchemy-native answer |
| Client-side article filtering | Server-side filter endpoint | Unnecessary for expected data volumes (<5000 articles per researcher); adds API round-trip and query complexity |
| asyncio.as_completed (stdlib) | Celery / RQ | Massive overkill for in-process parallelism; introduces broker and worker daemon dependencies |
| uuid.uuid4() (stdlib) | nanoid or similar | UUID is sufficient for run IDs; no URL-shortening requirement |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Next.js 15 upgrade | App is stable on 14.2.35; async `params`/`searchParams` change in 15 requires auditing every dynamic route | Stay on 14.2.35 until a dedicated upgrade milestone |
| React Query / SWR | Adds complexity for what are simple one-shot fetches on mount; no cache invalidation requirement | Existing `useEffect + fetch` pattern is sufficient |
| Tanstack Table | Overkill for article list filtering; adds weight and API surface area | Client-side `Array.filter()` with controlled `useState` |
| Celery + Redis | Distributed task queue not needed; pipeline is local in-process | `asyncio + ThreadPoolExecutor` already handles concurrency |
| GraphQL | No query complexity that justifies schema overhead | FastAPI REST endpoints |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| alembic 1.13.x | SQLAlchemy >=1.4, fully supports 2.0 | No conflict with existing sqlalchemy>=2.0.0 pin |
| XGBoost 3.2.0 | scikit-learn >=1.3.0, numpy >=1.24.0 | PINNED — pip must not auto-upgrade xgboost during any install |
| Next.js 14.2.35 | React 18 | React 19 is incompatible with Next.js 14; do not upgrade react |

---

## Key Architecture Insight: Compound Name Detection

The most non-obvious retrieval parity gap is the `useStrictQueryOnly` flag in Java. When a researcher has a compound surname (e.g., "Garcia Marquez") or compound first name (e.g., "Wing Tak"), ReCiter skips the lenient query entirely and goes directly to the strict (full-name) query. This is because compound names are already highly specific — a lenient query would add almost no extra recall while returning an enormous and noisy result set.

The Python detection condition (from Java source, `AliasReCiterRetrievalEngine.java` lines 877–884):

```python
def is_compound_name(last_name: str, first_name: str, middle_name: str = "") -> bool:
    """Mirrors AliasReCiterRetrievalEngine.identityAuthorNames() compound detection."""
    # Compound last name: space or hyphen where both parts >= 4 chars
    if " " in last_name or "-" in last_name:
        parts = last_name.replace("-", " ").split(None, 1)
        if len(parts) == 2 and len(parts[0]) >= 4 and len(parts[1]) >= 4:
            return True
    # Compound first name: contains space or dot (e.g., "Wing Tak", "W. Clay")
    if " " in first_name or "." in first_name:
        return True
    # Single-initial first name with a middle name (e.g., first="W", middle="Clay")
    if len(first_name) == 1 and middle_name:
        return True
    return False
```

The affiliation-augmented query (only runs when lenient count > threshold OR compound name detected):

```python
# AffiliationRetrievalStrategy pattern — name[au] AND (kw1[affiliation] OR kw2[affiliation])
def build_affiliation_query(name_term: str, keywords: list[str]) -> str:
    affil_parts = " OR ".join(f"{kw}[affiliation]" for kw in keywords)
    return f"{name_term} AND ({affil_parts})"
```

---

## Sources

- ReCiter Java source `AliasReCiterRetrievalEngine.java` lines 163, 247–276, 863–961: compound name detection, `useStrictQueryOnly` logic, affiliation strategy cascade — HIGH confidence (read directly)
- ReCiter Java source `PubMedQueryType.PubMedQueryBuilder.contsructAuthorQuery()` lines 153–196: exact query string construction including compound-name quoting with `"..."[au]` — HIGH confidence (read directly)
- ReCiter Java source `AbstractRetrievalStrategy.retrievePubMedArticles()` lines 128–211: strict/lenient decision tree with `useStrictQueryOnly` bypass path — HIGH confidence (read directly)
- ReCiter `application.properties`: `searchStrategy-lenient-threshold=2000`, `searchStrategy-strict-threshold=1000` — HIGH confidence (read directly)
- `api/requirements.txt`: confirmed alembic is not present — HIGH confidence (read directly)
- `api/models.py`: confirmed `pipeline_run` table does not exist — HIGH confidence (read directly)
- `api/services/pipeline_runner.py` lines 346–361: confirmed sequential `await futures[pid]` loop, not as_completed — HIGH confidence (read directly)
- `frontend/package.json`: confirmed no new frontend dependencies needed; shadcn/Tailwind/Recharts already present — HIGH confidence (read directly)

---
*Stack research for: ReCiter Desktop v2.0 Pipeline Parity & Performance*
*Researched: 2026-04-05*
