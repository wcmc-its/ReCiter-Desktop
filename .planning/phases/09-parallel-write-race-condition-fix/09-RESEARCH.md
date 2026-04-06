# Phase 9: Parallel Write Race Condition Fix - Research

**Researched:** 2026-04-06
**Domain:** SQLAlchemy concurrent writes, MariaDB upsert, Python ThreadPoolExecutor
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DB-01 | Concurrent parallel workers writing scores to `person_article_score` do not produce SQLAlchemy autoflush race condition errors (MariaDB error 1020 / stale record) | Root cause confirmed: shared-table SELECT+INSERT pattern is non-atomic; `INSERT ... ON DUPLICATE KEY UPDATE` eliminates both error modes atomically |

</phase_requirements>

---

## Summary

The `_process_one_researcher` function in `api/services/pipeline_runner.py` uses a SELECT-then-INSERT pattern for three tables: `article`, `person_article`, and `person_article_score`. This pattern is not atomic across concurrent workers and produces two failure modes: (1) a SQLAlchemy autoflush error when one worker has a pending `db.add()` in its session and then issues a query — SQLAlchemy's autoflush fires an early INSERT that conflicts with another worker's committed row; (2) a StaleDataError (MariaDB error 1020) when the UPDATE branch of the score-save path finds that the row was already modified by another concurrent transaction.

The fix is surgical and confined to a single file: replace all three SELECT+conditional-INSERT/UPDATE loops in `_process_one_researcher` with `INSERT ... ON DUPLICATE KEY UPDATE` statements executed via SQLAlchemy's MySQL dialect helper. The upsert is atomic at the MariaDB level, so no concurrent worker can observe or produce inconsistency. No schema migrations are needed; the existing composite primary keys on all three tables already define the uniqueness constraints required by upsert semantics.

A Wave 0 gap must be addressed first: `pytest-asyncio` is not installed and `pytest.ini` does not exist at the repo root, causing the five existing async tests in `api/tests/test_pipeline_runner.py` to fail. The Wave 0 task installs `pytest-asyncio`, adds `pytest.ini`, and updates `requirements.txt`.

**Primary recommendation:** Replace the three SELECT+INSERT loops in `_process_one_researcher` with bulk `INSERT ... ON DUPLICATE KEY UPDATE` via `sqlalchemy.dialects.mysql.insert`. Scope is `api/services/pipeline_runner.py` only. No migrations.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.49 (installed) | ORM + connection management | Project standard; already in use |
| PyMySQL | 1.1.2 (installed) | MariaDB driver for SQLAlchemy | Project standard; `mysql+pymysql` connection string |
| MariaDB | 11.8.6 (running container) | Database | Project standard; Docker Compose service |
| pytest | 9.0.2 (installed) | Test runner | Project standard |
| pytest-asyncio | 1.3.0 (available, NOT installed) | Async test support | Required for existing async pipeline tests |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy.dialects.mysql.insert` | Ships with SQLAlchemy 2.0 | MySQL/MariaDB `INSERT ... ON DUPLICATE KEY UPDATE` | Upsert on any MySQL/MariaDB table |
| `sqlalchemy.text` | Ships with SQLAlchemy 2.0 | Raw SQL fragments in ORM expressions | `scored_at=text('NOW()')` in upsert clause |

**Installation (Wave 0 only):**
```bash
pip install pytest-asyncio==1.3.0
# Add to requirements.txt: pytest-asyncio>=1.3.0
```

---

## Architecture Patterns

### Recommended Project Structure

No structural changes. All changes confined to:
```
api/
└── services/
    └── pipeline_runner.py   # Three upsert replacements + one new import
```

### Pattern 1: MySQL Dialect Upsert (INSERT ... ON DUPLICATE KEY UPDATE)

**What:** Issue an INSERT that automatically updates existing rows if the primary key conflicts, using a single atomic MariaDB statement.

**When to use:** Any table write where another concurrent worker may already have written the same primary key — specifically `article`, `person_article`, and `person_article_score`.

**Example — article no-op upsert (never overwrite existing article data):**
```python
# Source: SQLAlchemy 2.0 MySQL dialect docs
from sqlalchemy.dialects.mysql import insert as mysql_insert

stmt = mysql_insert(Article.__table__).values(article_rows)
stmt = stmt.on_duplicate_key_update(pmid=stmt.inserted.pmid)  # no-op
db.execute(stmt)
```
Produces: `INSERT INTO article (...) VALUES (...) ON DUPLICATE KEY UPDATE pmid = VALUES(pmid)`

**Example — score upsert (update scores on re-run):**
```python
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy import text

stmt = mysql_insert(PersonArticleScore.__table__).values(score_rows)
stmt = stmt.on_duplicate_key_update(
    calibrated_score=stmt.inserted.calibrated_score,
    raw_score=stmt.inserted.raw_score,
    features=stmt.inserted.features,
    run_id=stmt.inserted.run_id,
    scored_at=text('NOW()'),
)
db.execute(stmt)
```
Produces: `INSERT INTO person_article_score (...) VALUES (...) ON DUPLICATE KEY UPDATE calibrated_score = VALUES(calibrated_score), ...`

**Example — bulk multi-row insert (pass list of dicts):**
```python
score_rows = [
    dict(person_id=person_id, pmid=pmid, model_type=model_type,
         calibrated_score=score_val, raw_score=raw_val, features=features_dict, run_id=run_id)
    for _, row in scored_df.iterrows()
    ...
]
if score_rows:
    # Execute bulk upsert in one round-trip
    stmt = mysql_insert(PersonArticleScore.__table__).values(score_rows)
    ...
    db.execute(stmt)
```

### Pattern 2: Build-then-Execute (avoid autoflush)

**What:** Collect all rows into Python lists, then issue a single `db.execute()` per table. No pending `db.add()` objects accumulate in the session, so SQLAlchemy autoflush never fires during subsequent queries.

**When to use:** Any worker-thread DB code where queries follow writes to the same session. Replacing `db.add()` + `db.query()` interleaving with this pattern eliminates the autoflush race class entirely.

**Example:**
```python
# OLD: SELECT + conditional db.add() interleaved with db.query() -> autoflush risk
for art in articles:
    existing_art = db.query(Article).filter_by(pmid=str(art.pmid)).first()  # autoflush fires here!
    if not existing_art:
        db.add(Article(...))  # pending in session
    existing_pa = db.query(PersonArticle).filter_by(...).first()  # autoflush again
    if not existing_pa:
        db.add(PersonArticle(...))

# NEW: build lists, upsert once, no pending session state
article_rows = []
pa_rows = []
for art in articles:
    article_rows.append(dict(pmid=str(art.pmid), title=art.title, ...))
    pa_rows.append(dict(person_id=person_id, pmid=str(art.pmid), source="search"))

if article_rows:
    stmt = mysql_insert(Article.__table__).values(article_rows)
    db.execute(stmt.on_duplicate_key_update(pmid=stmt.inserted.pmid))

if pa_rows:
    stmt = mysql_insert(PersonArticle.__table__).values(pa_rows)
    db.execute(stmt.on_duplicate_key_update(source=stmt.inserted.source))
```

### Pattern 3: Guard on Empty List

**What:** Always check `if rows:` before calling `mysql_insert(...).values(rows)` because `values([])` produces `INSERT INTO t () VALUES ()` which is invalid SQL.

**Example:**
```python
if article_rows:
    db.execute(mysql_insert(Article.__table__).values(article_rows).on_duplicate_key_update(...))
```

### Anti-Patterns to Avoid

- **SELECT + conditional INSERT across concurrent sessions:** The non-atomic gap between the SELECT returning None and the INSERT executing is the root cause. Eliminated entirely by upsert.
- **`db.add()` followed by `db.query()` in the same session:** Triggers SQLAlchemy autoflush, which can produce an IntegrityError if a concurrent worker already committed the same row. Eliminated by using `db.execute(insert_stmt)` instead of `db.add()`.
- **`session.merge()` on rows from a stale read:** Can produce StaleDataError (1020) when another worker modified the row between the read and the merge. Not needed with upsert.
- **`no_autoflush` as a fix:** This suppresses the symptom (autoflush) but the underlying duplicate-key failure still occurs at commit time. The upsert approach eliminates the root cause.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic INSERT-or-UPDATE | Custom locking, retry loops, `SELECT FOR UPDATE` | `INSERT ... ON DUPLICATE KEY UPDATE` | Single atomic MariaDB statement; no deadlock risk; one round-trip |
| Concurrent write coordination | Mutexes, queues between workers | Upsert semantics at DB layer | DB-level atomicity is more robust than application-level coordination |
| Duplicate detection | `try/except IntegrityError` with retry | `ON DUPLICATE KEY UPDATE` | Exception-path retries are fragile and slower under load |

**Key insight:** The database's upsert primitive is the correct tool for this problem class. Application-level coordination (locks, queues, retry loops) adds complexity without solving the underlying non-atomicity.

---

## Root Cause Analysis

### Confirmed Race Condition Mechanism

The `_process_one_researcher` function runs in a `ThreadPoolExecutor` thread. Each worker creates its own `SessionLocal()` session, so there is no cross-session autoflush in the traditional sense. The race condition arises because:

1. **Worker A** and **Worker B** both retrieve the same PMID (common for generic-name researchers with large candidate pools — e.g., "Chen, James" triggers lenient search returning 2000+ articles, many shared by multiple researchers).

2. Both workers issue `db.query(Article).filter_by(pmid='12345').first()` → both get `None`.

3. Both workers call `db.add(Article(pmid='12345', ...))` — this object is now **pending** in each worker's session, not yet flushed to the DB.

4. Worker A's session proceeds to `db.query(PersonArticle).filter_by(...)`. SQLAlchemy's **autoflush** fires, flushing the pending `Article` INSERT before executing the SELECT. Worker A's `Article(pmid='12345')` commits successfully.

5. Worker B's session reaches the same `db.query(PersonArticle)` — autoflush fires for Worker B too, attempting `INSERT article (pmid='12345', ...)`. MariaDB returns **IntegrityError: Duplicate entry '12345' for key 'PRIMARY'**. This is the "SQLAlchemy autoflush error" referenced in STATE.md.

6. The `except Exception` in `_process_one_researcher` catches this, returns an error dict, and the worker's scored articles are silently dropped (violating success criterion 2).

### Secondary Failure Mode (StaleDataError / 1020)

The score-save loop (lines 249–271) uses the **SELECT + UPDATE** branch when `existing_score` is not `None`. On a re-run, multiple workers would never write the same `(person_id, pmid, model_type)` tuple simultaneously because each person is processed by exactly one worker. However, if the same `person_id` appears twice in `person_ids` (a defensive edge case), or in rare retry scenarios, SQLAlchemy's ORM UPDATE checks `rowcount == 1` and raises `StaleDataError` when another transaction modified the row first. The upsert removes this code path entirely.

---

## Common Pitfalls

### Pitfall 1: `values([])` produces invalid SQL
**What goes wrong:** `mysql_insert(t).values([])` generates `INSERT INTO t () VALUES ()` — invalid syntax.
**Why it happens:** SQLAlchemy does not validate that the list is non-empty at construction time.
**How to avoid:** Always guard with `if rows: db.execute(...)`.
**Warning signs:** `ProgrammingError: (pymysql.err.ProgrammingError)` on the execute call.

### Pitfall 2: `scored_at` column not refreshed on re-run
**What goes wrong:** `PersonArticleScore.scored_at` has `server_default=func.now()` but no `onupdate`. Without explicit inclusion in the `ON DUPLICATE KEY UPDATE` clause, re-runs leave stale timestamps.
**Why it happens:** `server_default` only fires on INSERT; `ON DUPLICATE KEY UPDATE` is a pure UPDATE.
**How to avoid:** Include `scored_at=text('NOW()')` in the `on_duplicate_key_update()` call.
**Warning signs:** `scored_at` timestamps don't advance after a re-run.

### Pitfall 3: `created_at` overwritten on duplicate article
**What goes wrong:** Including `created_at` in the Article upsert's `ON DUPLICATE KEY UPDATE` clause overwrites the original insertion timestamp.
**Why it happens:** `ON DUPLICATE KEY UPDATE` fires for all columns listed.
**How to avoid:** Do NOT include `created_at` in the Article `on_duplicate_key_update()` clause. The column has `server_default=func.now()` which fires on INSERT and is irrelevant on UPDATE.
**Warning signs:** Article `created_at` jumps to the current run's time on re-run.

### Pitfall 4: Session identity map is not updated by `db.execute()`
**What goes wrong:** After `db.execute(mysql_insert(...))`, `db.query(Article).filter_by(pmid='12345').first()` may return the ORM object if it was previously loaded into the session's identity map — or may return a fresh DB row if not. The identity map is NOT populated by a dialect-level execute.
**Why it happens:** `db.execute()` bypasses the ORM's identity map tracking.
**How to avoid:** This is not an issue for this codebase because `_process_one_researcher` creates a fresh `SessionLocal()` per call. No pre-loaded identity map exists at the point of upsert.
**Warning signs:** Would appear as stale data if using a session that previously loaded the same rows; not applicable here.

### Pitfall 5: `features` JSON field requires no manual serialization
**What goes wrong:** Manually calling `json.dumps(features_dict)` before passing to the upsert values dict causes the JSON to be stored as a string-of-string, not parsed JSON.
**Why it happens:** Confusion between ORM JSON handling and raw SQL execution.
**How to avoid:** Pass Python dict directly — SQLAlchemy's `JSON` column type and PyMySQL serialize it automatically.
**Warning signs:** JSON column values appear as escaped strings in the database.

---

## Code Examples

Verified patterns from local environment testing (SQLAlchemy 2.0.49, MariaDB 11.8.6):

### Article no-op upsert (preserve existing data)
```python
# Source: verified locally with sqlalchemy.dialects.mysql
from sqlalchemy.dialects.mysql import insert as mysql_insert

article_rows = [
    dict(pmid=str(art.pmid), title=art.title, journal=art.journal_title,
         pub_year=art.pub_year, doi=art.doi, abstract_text=art.abstract,
         authors=[...], mesh_headings=[...], keywords=art.keywords or [],
         grants=art.grants or [], publication_types=art.publication_types or [])
    for art in articles
]
if article_rows:
    stmt = mysql_insert(Article.__table__).values(article_rows)
    db.execute(stmt.on_duplicate_key_update(pmid=stmt.inserted.pmid))
```
Generates: `INSERT INTO article (...) VALUES (...) ON DUPLICATE KEY UPDATE pmid = VALUES(pmid)`

### PersonArticle no-op upsert
```python
pa_rows = [
    dict(person_id=person_id, pmid=str(art.pmid), source="search")
    for art in articles
    # (target_author_index stays at default -1; updated in Phase 2 of the function)
]
if pa_rows:
    stmt = mysql_insert(PersonArticle.__table__).values(pa_rows)
    db.execute(stmt.on_duplicate_key_update(source=stmt.inserted.source))
```
Generates: `INSERT INTO person_article (...) VALUES (...) ON DUPLICATE KEY UPDATE source = VALUES(source)`

### PersonArticleScore upsert (update on re-run)
```python
from sqlalchemy import text

score_rows = []
for _, row in scored_df.iterrows():
    pmid = str(row["pmid"])
    score_val = float(row.get("calibrated_score", 0))
    shap = row.get("shap_values")
    features_dict = {"shap": dict(shap)} if isinstance(shap, dict) else {}
    score_rows.append(dict(
        person_id=person_id, pmid=pmid, model_type=model_type,
        calibrated_score=score_val, raw_score=float(row.get("raw_score", 0)),
        features=features_dict, run_id=run_id,
    ))
if score_rows:
    stmt = mysql_insert(PersonArticleScore.__table__).values(score_rows)
    db.execute(stmt.on_duplicate_key_update(
        calibrated_score=stmt.inserted.calibrated_score,
        raw_score=stmt.inserted.raw_score,
        features=stmt.inserted.features,
        run_id=stmt.inserted.run_id,
        scored_at=text('NOW()'),
    ))
```

### Required imports (additions to pipeline_runner.py)
```python
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy import text
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `db.add()` + `db.query()` interleaving | `db.execute(insert_stmt)` without pending session state | This phase | Eliminates autoflush race |
| SELECT + conditional INSERT/UPDATE | `INSERT ... ON DUPLICATE KEY UPDATE` | This phase | Eliminates duplicate-key errors and StaleDataError |

**Deprecated/outdated:**
- The `existing_art = db.query(Article).filter_by(pmid=...).first(); if not existing_art: db.add(...)` pattern: correct for single-threaded code, broken under concurrent writes.

---

## Scope Boundaries

### What changes (Phase 9)

| Location | Change |
|----------|--------|
| `api/services/pipeline_runner.py` | Replace 3 SELECT+INSERT/UPDATE loops with upsert; add 2 imports |
| `requirements.txt` | Add `pytest-asyncio>=1.3.0` |
| `pytest.ini` (new file, repo root) | `[pytest]\nasyncio_mode = auto` |

### What does NOT change

- `api/models.py` — No model changes, no new columns, no schema migration
- `api/migrations/` — No new Alembic migration needed
- `api/database.py` — Session factory unchanged
- `api/routers/pipeline.py` — Pipeline router unchanged
- Frontend — No frontend changes
- `core/` or `features/` — Scoring logic unchanged (success criterion 3)

### RetrievalLog (intentionally excluded)

`RetrievalLog` has `person_id` as its sole primary key. Each worker processes exactly one researcher, so no two workers ever write the same `RetrievalLog` row concurrently. The existing `if retrieval_log: update else: db.add()` pattern is safe and is left unchanged.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pytest.ini` at repo root (Wave 0: must create) |
| Quick run command | `python -m pytest api/tests/test_upsert_writes.py -q` |
| Full suite command | `python -m pytest api/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DB-01 | Upsert stmt for `article` is no-op on duplicate | unit | `pytest api/tests/test_upsert_writes.py::test_article_upsert_stmt -x` | Wave 0 |
| DB-01 | Upsert stmt for `person_article` is no-op on duplicate | unit | `pytest api/tests/test_upsert_writes.py::test_person_article_upsert_stmt -x` | Wave 0 |
| DB-01 | Upsert stmt for `person_article_score` updates all score fields | unit | `pytest api/tests/test_upsert_writes.py::test_score_upsert_stmt -x` | Wave 0 |
| DB-01 | `_process_one_researcher` contains no `db.query(Article).filter_by` call | unit | `pytest api/tests/test_upsert_writes.py::test_no_article_select_in_process -x` | Wave 0 |
| DB-01 | Existing pipeline ordering tests still pass | regression | `pytest api/tests/test_pipeline_runner.py -q` | Exists (broken pre-existing — Wave 0 gap) |

### Sampling Rate

- **Per task commit:** `python -m pytest api/tests/test_upsert_writes.py api/tests/test_models.py -q`
- **Per wave merge:** `python -m pytest api/tests/ -q`
- **Phase gate:** Full `api/tests/` suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `pytest.ini` at repo root — `asyncio_mode = auto` — fixes pre-existing async test failures
- [ ] `requirements.txt` — add `pytest-asyncio>=1.3.0`
- [ ] `api/tests/test_upsert_writes.py` — covers DB-01 (4 unit tests for upsert statement generation + 1 regression check)

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| MariaDB | Upsert target | Yes (Docker) | 11.8.6 | — |
| SQLAlchemy MySQL dialect | `mysql_insert()` | Yes | 2.0.49 | — |
| PyMySQL | DB driver | Yes | 1.1.2 | — |
| pytest-asyncio | Async test support | No | 1.3.0 available | Install in Wave 0 |

**Missing dependencies with fallback:**
- `pytest-asyncio`: Not installed. Install in Wave 0. Without it, the 5 pre-existing pipeline runner tests fail. The new upsert unit tests do not use async and do not depend on this package.

---

## Open Questions

1. **`scored_at` precision on re-run**
   - What we know: including `scored_at=text('NOW()')` in the upsert refreshes the timestamp on duplicate.
   - What's unclear: whether there is a product requirement to preserve the original `scored_at` of the first-ever score.
   - Recommendation: refresh `scored_at` on re-run (matches intent of "scored_at = when it was most recently scored"). If preservation is needed, omit `scored_at` from the `on_duplicate_key_update` clause.

2. **`target_author_index` in PersonArticle upsert**
   - What we know: `target_author_index` is updated in a separate loop after the article upsert. The initial upsert inserts with `-1` (the model default); the subsequent per-row update sets the real index.
   - What's unclear: whether folding `target_author_index` computation into the initial upsert would be a meaningful optimization.
   - Recommendation: leave the two-phase update as-is for Phase 9 (minimal change); the second pass is per-person and not race-prone.

---

## Sources

### Primary (HIGH confidence)

- Local environment verification: `sqlalchemy.dialects.mysql.insert`, `on_duplicate_key_update`, `session.execute()` — all verified with SQLAlchemy 2.0.49 + MariaDB 11.8.6
- `api/services/pipeline_runner.py` — direct source code inspection (line-by-line race condition analysis)
- `api/models.py` — composite PK structures confirmed: `(person_id, pmid, model_type)` on `PersonArticleScore`, `(person_id, pmid)` on `PersonArticle`, `pmid` on `Article`

### Secondary (MEDIUM confidence)

- SQLAlchemy 2.0 MySQL dialect documentation pattern: `insert().on_duplicate_key_update()` — matches verified local behavior

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages version-verified against running environment
- Architecture: HIGH — root cause confirmed by direct code tracing and local execution tests
- Pitfalls: HIGH — pitfalls 1, 2, 3, 5 verified by local Python execution

**Research date:** 2026-04-06
**Valid until:** 2026-07-06 (stable — SQLAlchemy 2.x and MariaDB 11.x change infrequently)
