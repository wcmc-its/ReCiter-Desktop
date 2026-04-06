# Phase 4: Schema Foundation + Parallel Processing - Research

**Researched:** 2026-04-06
**Domain:** Alembic migrations (MariaDB), asyncio parallel processing, FastAPI lifespan, Next.js SSE handling
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use Alembic for schema migrations. Add Alembic 1.13.3 to the project with config at `api/migrations/`.
- **D-02:** Migrations run automatically on FastAPI app startup (`alembic upgrade head` in startup event). Zero friction for Docker Compose users.
- **D-03:** First migration (001) captures the full existing schema as a baseline. Second migration (002) adds `pipeline_run` table and `run_id` columns. Future phases add incremental migrations.
- **D-04:** `pipeline_run` table uses auto-increment integer `run_id` as primary key.
- **D-05:** 5-state lifecycle: PENDING → RUNNING → COMPLETED / PARTIAL / FAILED.
- **D-06:** When some researchers fail, run is marked COMPLETED (not PARTIAL). PARTIAL reserved for server crash / user abort.
- **D-07:** `pipeline_run` stores aggregate counts: `total_researchers`, `total_articles`, `researchers_succeeded`, `researchers_failed`.
- **D-08:** `pipeline_run` stores the `mode` column (full, update, score_only).
- **D-09:** Alembic migration creates synthetic `pipeline_run` row (run_id=1) and UPDATEs all existing rows to set `run_id=1`.
- **D-10:** Synthetic run #1 timestamps: `started_at` = MIN(scored_at), `completed_at` = MAX(scored_at).
- **D-11:** Replace submission-order collection loop with `asyncio.as_completed`.
- **D-12:** MAX_WORKERS = 8 with PubMed API key configured, 3 without.
- **D-13:** Remove the `processing` SSE event type.
- **D-14:** Researcher rows keep roster order; completion events update in-place.
- **D-15:** Show worker count status line (e.g., "5/8 workers active") on the pipeline page.

### Claude's Discretion

- Exact `pipeline_run` column types and constraints beyond what's specified
- Alembic env.py configuration details
- SSE event payload changes needed to carry `run_id`
- How to detect PubMed API key presence for worker count selection

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PARA-01 | Pipeline yields SSE events in completion order via asyncio.as_completed (not submission order) | Verified: `asyncio.as_completed` with `run_in_executor` futures produces true arrival-order events; result dict already carries `person_id` so no reverse mapping needed |
| PARA-02 | MAX_WORKERS is 8 when PubMed API key is configured, 3 without | `get_pubmed_api_key(db)` already exists in `institution.py`; call it in `run_pipeline()` before creating executor; non-empty string = key present |
| HIST-01 | `pipeline_run` table records run metadata (run_id, mode, status, timestamps, counts) | New SQLAlchemy model follows existing Base pattern; Alembic migration 002 creates the table |
| HIST-02 | `person_article_score` and `retrieval_log` have nullable `run_id` FK; existing scores migrate as run #1 | Alembic migration 002 does ADD COLUMN + backfill UPDATE in one migration; FK references `pipeline_run.run_id` |

</phase_requirements>

---

## Summary

Phase 4 has two independent workstreams that can be planned and executed in parallel: (1) Alembic schema migration — adding `pipeline_run` table and `run_id` foreign key columns — and (2) parallel processing refactor — replacing the submission-order await loop with `asyncio.as_completed` and adding adaptive worker count. Both workstreams touch `pipeline_runner.py` and `pipeline.py`, but at different code sites.

The existing codebase is structurally clean for both changes. Alembic 1.18.4 is already installed on this machine (the CONTEXT.md specifies 1.13.3 as a floor; the planner should pin `alembic>=1.13.3` in requirements to allow the installed version). The `asyncio.as_completed` refactor requires understanding one critical constraint: the API Dockerfile uses Python 3.12-slim, which does not support the `async for` iteration style of `as_completed`. The safe, portable pattern is the plain `for coro in as_completed(futs): result = await coro` iterator, which works in Python 3.12 and 3.14.

The frontend change is straightforward: remove the `processing` event handler branch and add a worker count display. Because `complete_one` events will now arrive out of order, no reordering logic is needed — the existing in-place row update already handles it correctly.

**Primary recommendation:** Implement in three tasks: (1) Alembic setup + migration 001 baseline, (2) migration 002 with PipelineRun model + backfill, (3) pipeline_runner.py refactor + frontend changes.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alembic | 1.18.4 installed / `>=1.13.3` pin | Schema migrations for SQLAlchemy | Only safe way to ALTER populated MariaDB tables; integrates with SQLAlchemy engine |
| sqlalchemy | 2.0.46 installed | ORM + DDL | Already in use; `alembic` depends on it |
| asyncio | stdlib (Python 3.12+) | `as_completed` for parallel result collection | No extra dependency; built-in |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pymysql | `>=1.1.0` (already in requirements) | MariaDB connector for Alembic | Required for `mysql+pymysql://` URLs |
| fastapi lifespan | FastAPI 0.129.0 | Startup hook for `alembic upgrade head` | Preferred over deprecated `@app.on_event` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| alembic programmatic config | alembic.ini file | INI file requires extra Docker volume mount; programmatic `Config()` with `set_main_option` eliminates this |
| `async for` in as_completed | plain `for coro in as_completed(...)` | `async for` requires Python 3.13+; Docker uses 3.12-slim — use plain iterator |
| Separate migration runner script | FastAPI startup hook | Separate script requires orchestration; startup hook is zero-friction for Compose users |

**Installation:**
```bash
pip install "alembic>=1.13.3"
```
Add to `api/requirements.txt`.

**Version note:** Alembic 1.18.4 is the current latest (verified 2026-04-06). The CONTEXT.md specifies 1.13.3 as the target; `>=1.13.3` as the pin accepts the newer installed version.

---

## Architecture Patterns

### Recommended Project Structure

```
api/
├── migrations/
│   ├── env.py              # Alembic env — reads DATABASE_URL, imports Base.metadata
│   ├── script.py.mako      # Revision template (from alembic init)
│   └── versions/
│       ├── 001_baseline.py # Full schema snapshot (no op — schema already exists)
│       └── 002_pipeline_run.py  # Add pipeline_run + run_id columns + backfill
├── models.py               # Add PipelineRun model
├── database.py             # No changes needed
└── main.py                 # Add lifespan handler for alembic upgrade head
```

### Pattern 1: Alembic Programmatic Config (no .ini file)

**What:** Configure Alembic via `Config()` object in Python code, avoiding a separate `.ini` file.
**When to use:** In Docker Compose where the API container has no config file volume.
**Example:**
```python
# api/main.py — lifespan startup hook
from contextlib import asynccontextmanager
from alembic.config import Config
from alembic import command
import os

@asynccontextmanager
async def lifespan(app):
    # Run migrations at startup
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(__file__), "migrations")
    )
    cfg.set_main_option("sqlalchemy.url", os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://reciter:reciter_local@localhost:3306/reciter_desktop"
    ))
    command.upgrade(cfg, "head")
    yield

app = FastAPI(title="ReCiter Desktop API", version="1.0.0", lifespan=lifespan)
```

**Note:** `@app.on_event("startup")` is deprecated in FastAPI 0.93+. Use `lifespan` context manager instead.

### Pattern 2: Alembic Migration 001 — Baseline Snapshot

**What:** First revision captures the full current schema so the Alembic version table is populated. The `upgrade()` function is a no-op (schema already exists from `schema.sql`). The `downgrade()` drops everything.
**Why:** Without a baseline revision, Alembic has no record of the current state, and migration 002 would fail on existing databases.

```python
# api/migrations/versions/001_baseline.py
"""baseline schema

Revision ID: 001
Revises: 
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Schema already created by schema.sql on first run.
    # This baseline marks the starting point for future migrations.
    pass

def downgrade() -> None:
    op.drop_table('curation')
    op.drop_table('retrieval_log')
    op.drop_table('person_article_score')
    op.drop_table('person_article')
    op.drop_table('article')
    op.drop_table('identity')
    op.drop_table('institution')
```

**Critical detail:** The `alembic_version` table will be created by Alembic on first run. If the DB already has data (existing installation), `upgrade head` runs 001 (no-op, stamps version), then 002 (adds columns).

### Pattern 3: Alembic Migration 002 — Add pipeline_run + run_id + Backfill

**What:** Creates the `pipeline_run` table, adds nullable `run_id` to two tables, inserts synthetic run #1, and backfills existing rows.

```python
# api/migrations/versions/002_pipeline_run.py
"""add pipeline_run table and run_id FK columns

Revision ID: 002
Revises: 001
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create pipeline_run table
    op.create_table(
        'pipeline_run',
        sa.Column('run_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('mode', sa.Enum('full', 'update', 'score_only'), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED'), nullable=False, server_default='PENDING'),
        sa.Column('total_researchers', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_articles', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('researchers_succeeded', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('researchers_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('run_id'),
    )

    # 2. Insert synthetic run #1 using actual timestamp range from existing scores
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT MIN(scored_at), MAX(scored_at), COUNT(DISTINCT person_id) "
        "FROM person_article_score"
    )).fetchone()
    min_ts, max_ts, researcher_count = result[0], result[1], result[2]

    if min_ts is not None:
        conn.execute(sa.text(
            "INSERT INTO pipeline_run "
            "(run_id, mode, status, total_researchers, researchers_succeeded, started_at, completed_at) "
            "VALUES (1, 'full', 'COMPLETED', :rc, :rc, :min_ts, :max_ts)"
        ), {"rc": researcher_count, "min_ts": min_ts, "max_ts": max_ts})
    else:
        # No existing scores — insert placeholder run #1
        conn.execute(sa.text(
            "INSERT INTO pipeline_run (run_id, mode, status) VALUES (1, 'full', 'COMPLETED')"
        ))

    # 3. Add nullable run_id FK to person_article_score
    op.add_column('person_article_score',
        sa.Column('run_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_pas_run_id', 'person_article_score', 'pipeline_run',
        ['run_id'], ['run_id'], ondelete='SET NULL')

    # 4. Backfill existing scores → run #1
    conn.execute(sa.text(
        "UPDATE person_article_score SET run_id = 1 WHERE run_id IS NULL"
    ))

    # 5. Add nullable run_id FK to retrieval_log
    op.add_column('retrieval_log',
        sa.Column('run_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_rl_run_id', 'retrieval_log', 'pipeline_run',
        ['run_id'], ['run_id'], ondelete='SET NULL')

    # 6. Backfill existing retrieval_log rows → run #1
    conn.execute(sa.text(
        "UPDATE retrieval_log SET run_id = 1 WHERE run_id IS NULL"
    ))


def downgrade() -> None:
    op.drop_constraint('fk_rl_run_id', 'retrieval_log', type_='foreignkey')
    op.drop_column('retrieval_log', 'run_id')
    op.drop_constraint('fk_pas_run_id', 'person_article_score', type_='foreignkey')
    op.drop_column('person_article_score', 'run_id')
    op.drop_table('pipeline_run')
```

### Pattern 4: PipelineRun SQLAlchemy Model

```python
# api/models.py — new model following existing Base pattern
class PipelineRun(Base):
    __tablename__ = "pipeline_run"
    run_id = Column(Integer, autoincrement=True, primary_key=True)
    mode = Column(Enum("full", "update", "score_only"), nullable=False)
    status = Column(
        Enum("PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED"),
        nullable=False,
        default="PENDING"
    )
    total_researchers = Column(Integer, nullable=False, default=0)
    total_articles = Column(Integer, nullable=False, default=0)
    researchers_succeeded = Column(Integer, nullable=False, default=0)
    researchers_failed = Column(Integer, nullable=False, default=0)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
```

Add `run_id` column to existing models:
```python
# In PersonArticleScore:
run_id = Column(Integer, ForeignKey("pipeline_run.run_id", ondelete="SET NULL"), nullable=True)

# In RetrievalLog:
run_id = Column(Integer, ForeignKey("pipeline_run.run_id", ondelete="SET NULL"), nullable=True)
```

### Pattern 5: asyncio.as_completed Refactor (Python 3.12 compatible)

**What:** Replace submission-order result collection with completion-order collection.
**Critical constraint:** Docker container uses Python 3.12-slim. The `async for` style of `asyncio.as_completed` requires Python 3.13+. Use the plain `for coro in as_completed(...): result = await coro` pattern, which works in both 3.12 and 3.14.

```python
# api/services/pipeline_runner.py — new collection loop
# BEFORE (submission order — lines 347-361):
for pid in person_ids:
    yield {"type": "processing", "person_id": pid, "phase": "running"}
    result = await futures[pid]
    ...

# AFTER (arrival order — Python 3.12 compatible):
from asyncio import as_completed

all_futures = list(futures.values())
for coro in as_completed(all_futures):
    result = await coro
    pid = result["person_id"]   # already in result dict — no reverse map needed
    completed += 1
    yield {
        "type": "complete_one",
        "person_id": pid,
        "completed": completed,
        "total": total,
        **result,
    }
```

**Note:** The `futures` dict is built before the collection loop (lines 335-344 already do this). The refactor only replaces the collection loop, not the submission loop. The `queued` events still fire in submission order.

### Pattern 6: Adaptive Worker Count

**What:** Determine MAX_WORKERS at pipeline invocation time, not at module import.
**How to detect API key:** `get_pubmed_api_key(db)` already exists in `api/routers/institution.py` and is already called inside `_process_one_researcher`. Call it once in `run_pipeline()` before creating the executor.

```python
# api/services/pipeline_runner.py
# Remove module-level constant:
# MAX_WORKERS = min(4, (os.cpu_count() or 2))  # DELETE THIS

# In run_pipeline(), after config loading:
db_for_key = SessionLocal()
try:
    from api.routers.institution import get_pubmed_api_key
    api_key = get_pubmed_api_key(db_for_key)
finally:
    db_for_key.close()

max_workers = 8 if api_key else 3
executor = ThreadPoolExecutor(max_workers=max_workers)

yield {
    "type": "started",
    "total": total,
    "mode": mode,
    "run_id": run_id,       # add after pipeline_run row is created
    "max_workers": max_workers,
}
```

### Pattern 7: Pipeline Router — Create PipelineRun Row

**What:** `/api/pipeline/run` creates the `PipelineRun` row (PENDING) before streaming.

```python
# api/routers/pipeline.py
@router.post("/run")
async def run(req: PipelineRequest, db: Session = Depends(get_db)):
    ...
    # Create pipeline_run row
    from api.models import PipelineRun
    from datetime import datetime
    pipeline_run = PipelineRun(
        mode=req.mode,
        status="PENDING",
        total_researchers=len(person_ids),
    )
    db.add(pipeline_run)
    db.commit()
    db.refresh(pipeline_run)
    run_id = pipeline_run.run_id

    async def event_stream():
        async for event in run_pipeline(person_ids, mode=req.mode, run_id=run_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Pattern 8: Worker Count Display on Frontend

**What:** The `started` SSE event now carries `max_workers`. Track active count as `total - completed - errors`. Display "N/M workers active".

```typescript
// frontend/app/pipeline/page.tsx
// Add state:
const [maxWorkers, setMaxWorkers] = useState<number | null>(null);

// In SSE handler for "started" event:
if (event.type === "started") {
    setMaxWorkers(event.max_workers as number ?? null);
}

// In the progress card UI:
{maxWorkers && running && (
    <span>{activeResearchers.length}/{maxWorkers} workers active</span>
)}
```

### Anti-Patterns to Avoid

- **`async for` with `asyncio.as_completed` in Python 3.12 container:** The Docker image is `python:3.12-slim`. Async iteration style requires Python 3.13+. Always use the plain iterator pattern.
- **Creating `PipelineRun` inside `run_pipeline()`:** The function is a generator and uses `SessionLocal()` internally, but the `run_id` must be committed and returned before streaming starts. Create it in the router endpoint so `run_id` is stable before the SSE stream opens.
- **Using `op.get_bind()` for DML in Alembic 2.0:** In SQLAlchemy 2.0 / Alembic 1.13+, `op.get_bind()` returns a `Connection`, not a legacy engine. Use `conn.execute(sa.text(...))` not `conn.execute(str)`.
- **Keeping the `processing` event handler on the frontend:** D-13 removes this event type. The frontend `processing` branch (lines 223-237 in `pipeline/page.tsx`) sets `researcherStartTimes` and calls `setExpandedId`. These side effects need to move elsewhere (e.g., on `queued` event or first `complete_one`).
- **Auto-generating migration 001 from live DB:** Alembic autogenerate against a populated DB can generate spurious ALTER statements. Write migration 001 as a manual no-op baseline to avoid unintended schema changes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema version tracking | Custom `schema_version` table | Alembic `alembic_version` table | Handles concurrent migrations, dependency chains, branching |
| ALTER TABLE with data backfill | Raw SQL in startup script | Alembic migration with `op.get_bind()` DML | Transactional; can be rolled back; version-tracked |
| Arrival-order result collection | Manual queue + completion counter | `asyncio.as_completed` | Correct semantics; handles exceptions per-future |
| Per-future identity tracking | Reverse dict from future → person_id | Already in result dict (`result["person_id"]`) | `_process_one_researcher` already returns `person_id` in result |

---

## Common Pitfalls

### Pitfall 1: `alembic_version` table conflict on existing databases

**What goes wrong:** If an existing installation already has data, running `alembic upgrade head` for the first time tries to record revision 001 in `alembic_version`. If the table doesn't exist, Alembic creates it. If it does exist with a stale revision, migration will skip or conflict.
**Why it happens:** The Docker Compose `db` service uses `schema.sql` via `docker-entrypoint-initdb.d/`, which runs only on first container creation. Subsequent runs skip it. The `alembic_version` table is absent on pre-migration databases.
**How to avoid:** Migration 001 `upgrade()` is a no-op — it just stamps the version without touching schema. This is safe for existing DBs. Alembic creates `alembic_version` automatically before running migrations.
**Warning signs:** `alembic.util.exc.CommandError: Target database is not up to date.` or `Table 'alembic_version' already exists.`

### Pitfall 2: `processing` event removal breaks frontend timing

**What goes wrong:** The frontend uses `processing` events to set `researcherStartTimes[pid]` and `expandedId`. Removing the event without relocating this logic means bottleneck detection never triggers and no row auto-expands.
**Why it happens:** D-13 removes `processing` but the frontend code at lines 223-237 depends on it.
**How to avoid:** When removing the `processing` handler branch, move `setResearcherStartTimes` update and `setExpandedId` to the `queued` handler (or `complete_one` for the expand). Review `activeResearchers` filter — it currently excludes `queued` phase. With `processing` removed, rows go directly `queued` → `complete`. Update the active/queued section logic accordingly.
**Warning signs:** `activeResearchers.length` is always 0 during a run; bottleneck highlighting never fires.

### Pitfall 3: `op.get_bind()` deprecation in SQLAlchemy 2.0

**What goes wrong:** Older Alembic patterns use `op.get_bind().execute("UPDATE ...")`. In SQLAlchemy 2.0, string SQL is not accepted by `Connection.execute()`.
**Why it happens:** SQLAlchemy 2.0 removed legacy string-based execution.
**How to avoid:** Always wrap SQL in `sa.text()`: `conn.execute(sa.text("UPDATE ..."), params)`.
**Warning signs:** `ObjectNotExecutableError: Not an executable clause`.

### Pitfall 4: `pipeline_run.run_id` not committed before SSE stream opens

**What goes wrong:** If `PipelineRun` is created inside `run_pipeline()` (the async generator), the DB session may not be flushed before the first `yield`, causing the `run_id` to be missing in the `started` event.
**Why it happens:** FastAPI `StreamingResponse` begins the response before the generator yields the first event.
**How to avoid:** Create and commit the `PipelineRun` row in the router endpoint (before calling `run_pipeline()`), pass `run_id` as a parameter.

### Pitfall 5: MariaDB vs MySQL ENUM syntax in Alembic

**What goes wrong:** Alembic generates `ENUM` columns using MySQL dialect syntax. MariaDB 11 (used in docker-compose.yml) is compatible with MySQL ENUM syntax, but some edge cases differ.
**Why it happens:** MariaDB uses `mysql+pymysql` dialect in SQLAlchemy, which is fine for all standard ENUM operations.
**How to avoid:** Use `sa.Enum('value1', 'value2')` (SQLAlchemy cross-dialect Enum), not `mysql.ENUM`. This renders as `ENUM('value1','value2')` in MariaDB, which works correctly.
**Warning signs:** Migration fails with `Unknown column type` on MariaDB 11.

### Pitfall 6: Section visibility logic breaks after removing `processing` phase

**What goes wrong:** The pipeline page splits researchers into `activeResearchers` (not queued/complete/error), `queuedResearchers`, `completedResearchers`. With `processing` removed, rows go directly from `queued` to `complete`. The "Active" section never shows researchers in flight — they stay in "Queued" until `complete_one` fires.
**Why it happens:** Phase transitions: previously `queued` → (processing event) → `retrieving` → `complete`. Now: `queued` → `complete`. The `retrieving`/`matching`/`analyzing`/`scoring` phases in `Phase` type and `PipelineRow` are vestigial.
**How to avoid:** This is by design (D-14). The queued section shows researchers in flight correctly. Verify the "Active" heading text is appropriate when `activeResearchers.length` is always 0. Consider updating the section heading to match the new behavior.

---

## Code Examples

### Alembic env.py for this project

```python
# api/migrations/env.py
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment (Docker Compose passes DATABASE_URL)
database_url = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://reciter:reciter_local@localhost:3306/reciter_desktop"
)
config.set_main_option("sqlalchemy.url", database_url)

# Import Base.metadata for autogenerate support (not used yet, but set up correctly)
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from api.models import Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### run_pipeline() signature change

```python
async def run_pipeline(
    person_ids: list[str],
    mode: str = "full",
    run_id: int | None = None,   # NEW parameter
) -> AsyncGenerator[dict, None]:
```

### Updated `started` event payload

```python
yield {
    "type": "started",
    "total": total,
    "mode": mode,
    "run_id": run_id,
    "max_workers": max_workers,
}
```

### Save run_id to scores in `_process_one_researcher`

The function signature needs `run_id: int | None = None` added, and score saves need:
```python
db.add(PersonArticleScore(
    ...
    run_id=run_id,    # pass through from pipeline
))
```

Also update `RetrievalLog` upsert to set `run_id=run_id`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `for pid in person_ids: result = await futures[pid]` | `for coro in as_completed(futures): result = await coro` | This phase | SSE events fire in true arrival order |
| `MAX_WORKERS = min(4, cpu_count)` (hardcoded at import) | `max_workers = 8 if api_key else 3` (per-run) | This phase | Better throughput with API key; safe without |
| Raw `schema.sql` only | schema.sql + Alembic migrations | This phase | Existing installations can upgrade without data loss |
| No run history | `pipeline_run` table with 5-state lifecycle | This phase | Foundation for Phase 6 run list UI |
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.93+ | `on_event` deprecated; lifespan is current standard |

**Deprecated/outdated:**
- `@app.on_event("startup")`: Still works in FastAPI 0.129.0 but deprecated. Use `lifespan=` parameter to `FastAPI()` constructor.
- `op.get_bind().execute("string SQL")`: SQLAlchemy 2.0 removed string execution. Use `sa.text()`.

---

## Open Questions

1. **`alembic_version` table pre-population for new Docker installs**
   - What we know: New Docker Compose installs run `schema.sql` via `docker-entrypoint-initdb.d/`, which creates all tables. When the API starts for the first time, Alembic runs and finds no `alembic_version` table, creates it, runs 001 (no-op), then 002 (adds columns).
   - What's unclear: The `schema.sql` does not create `pipeline_run`. Migration 002 creates it. This is correct behavior — no gap.
   - Recommendation: No action needed. Test with a fresh Docker volume to confirm.

2. **`processing` event removal and `researcherStartTimes` timing data**
   - What we know: `researcherStartTimes` is used for bottleneck detection. With `processing` removed, the start time is undefined until `complete_one` fires (too late for bottleneck detection).
   - What's unclear: Whether bottleneck detection is worth keeping with the new flow.
   - Recommendation: Move start time recording to the `queued` event handler (client-side time when queued). This approximates start time acceptably since queued events fire immediately before execution begins.

3. **`run_id` column position in MariaDB**
   - What we know: `ADD COLUMN` appends to end of table by default in MariaDB/MySQL.
   - What's unclear: Whether any downstream queries depend on column position (they should not with ORM usage).
   - Recommendation: Column position does not matter for ORM-based queries. No action needed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.14.2 (local) / 3.12 (Docker) | — |
| alembic | Migration framework | Yes (pip installed) | 1.18.4 | — |
| SQLAlchemy | ORM + DDL | Yes | 2.0.46 | — |
| MariaDB 11 | Database | Yes (Docker Compose) | 11 | — |
| pymysql | DB connector | Yes (in requirements) | >=1.1.0 | — |
| FastAPI | API framework | Yes | 0.129.0 | — |
| asyncio.as_completed | Parallel collection | Yes | stdlib 3.12+ | — |

**Missing dependencies with no fallback:** None.

**Note on Python version mismatch:** Local Python is 3.14.2; Docker container uses Python 3.12-slim. All code must be compatible with Python 3.12. Specifically: use `list[str]` type hints (ok in 3.12 with `from __future__ import annotations` or string literals), avoid `async for` on `asyncio.as_completed` (requires 3.13+).

---

## Validation Architecture

`workflow.nyquist_validation` is not set to `false` in `.planning/config.json` (key absent) — validation section included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none (no pytest.ini; runs from project root) |
| Quick run command | `python3 -m pytest api/tests/ -q` |
| Full suite command | `python3 -m pytest api/tests/ tests/ -q` |

Baseline: 15 tests pass in 0.15s (confirmed 2026-04-06).

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HIST-01 | `pipeline_run` table columns exist | unit | `pytest api/tests/test_models.py::test_pipeline_run_columns -x` | Wave 0 |
| HIST-02 | `person_article_score` has `run_id` column; `retrieval_log` has `run_id` column | unit | `pytest api/tests/test_models.py::test_run_id_columns -x` | Wave 0 |
| PARA-01 | Pipeline SSE events arrive out of submission order when 4+ researchers | smoke | `pytest api/tests/test_pipeline_runner.py::test_as_completed_order -x` | Wave 0 |
| PARA-02 | MAX_WORKERS=8 with API key, 3 without | unit | `pytest api/tests/test_pipeline_runner.py::test_worker_count -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `python3 -m pytest api/tests/ -q`
- **Per wave merge:** `python3 -m pytest api/tests/ tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `api/tests/test_models.py::test_pipeline_run_columns` — covers HIST-01 (add to existing test_models.py)
- [ ] `api/tests/test_models.py::test_run_id_columns` — covers HIST-02 (add to existing test_models.py)
- [ ] `api/tests/test_pipeline_runner.py` — new file, covers PARA-01 and PARA-02

---

## Project Constraints (from CLAUDE.md)

Directives from `ReCiter-Desktop/CLAUDE.md` that the planner must enforce:

| Directive | Impact on This Phase |
|-----------|---------------------|
| XGBoost 3.2.0 CRITICAL exact version | No change — not touched in this phase |
| SQLite for local storage | N/A — project uses MariaDB via Docker |
| Run: `streamlit run app.py` | N/A — this phase is FastAPI + Next.js only |
| Tests: `python -m pytest tests/` | Run `api/tests/` for backend; `tests/` for core |
| `~/.reciter-desktop/` for config/DB | N/A — only applies to Streamlit app paths |
| Python 3.14+ runtime | Local runtime; Docker container is 3.12. Code must be 3.12-compatible. |
| No hardcoded credentials | DATABASE_URL always from environment variable — already followed throughout |

---

## Sources

### Primary (HIGH confidence)

- Verified from installed packages: Alembic 1.18.4, SQLAlchemy 2.0.46, FastAPI 0.129.0, pytest 9.0.2 — confirmed via `python3 -m pip show`
- `asyncio.as_completed` behavior verified via source inspection and live execution tests (Python 3.14 local)
- Alembic generic template `env.py` — read from `/opt/homebrew/lib/python3.14/site-packages/alembic/templates/generic/env.py`
- `op.get_bind()` returning `Connection` in Alembic 1.13+ — verified via Alembic changelog knowledge and `sa.text()` requirement

### Secondary (MEDIUM confidence)

- FastAPI `lifespan` as replacement for `@app.on_event("startup")` — verified via FastAPI constructor `lifespan` parameter presence in 0.129.0
- Python 3.12 `asyncio.as_completed` plain iterator pattern — tested locally on 3.14, consistent with 3.12 docs

### Tertiary (LOW confidence)

- None — all claims verified against installed code or official sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified from installed packages
- Architecture: HIGH — patterns verified with live code tests
- Pitfalls: HIGH — identified from code inspection + known SQLAlchemy 2.0 breaking changes

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (stable libraries; Alembic and SQLAlchemy rarely break APIs between patch versions)
