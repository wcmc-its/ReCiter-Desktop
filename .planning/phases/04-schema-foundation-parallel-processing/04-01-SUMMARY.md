---
phase: 04-schema-foundation-parallel-processing
plan: 01
subsystem: database
tags: [alembic, sqlalchemy, mariadb, migrations, pipeline_run, fastapi, lifespan]

# Dependency graph
requires: []
provides:
  - PipelineRun SQLAlchemy model with 10 columns (run_id PK, mode, status enums, 4 count columns, 3 timestamps)
  - nullable run_id FK on PersonArticleScore and RetrievalLog
  - Alembic migrations infrastructure at api/migrations/ (env.py, script.py.mako)
  - Migration 001: no-op baseline stamp for existing schema.sql installs
  - Migration 002: pipeline_run table creation + run_id FK columns + synthetic run#1 backfill
  - FastAPI lifespan handler running alembic upgrade head on startup
affects: [04-02-parallel-processing, phase-06-historical-runs]

# Tech tracking
tech-stack:
  added: [alembic>=1.13.3]
  patterns:
    - Alembic programmatic Config() with set_main_option (no alembic.ini file needed)
    - FastAPI lifespan handler for zero-friction startup migrations
    - Migration backfill using conn = op.get_bind() + sa.text() with named parameters
    - PipelineRun model placed before dependent models in models.py (FK target exists first)

key-files:
  created:
    - api/migrations/env.py
    - api/migrations/script.py.mako
    - api/migrations/versions/001_baseline.py
    - api/migrations/versions/002_pipeline_run.py
  modified:
    - api/requirements.txt
    - api/models.py
    - api/main.py
    - api/tests/test_models.py

key-decisions:
  - "Alembic programmatic Config() — no alembic.ini file, eliminates Docker volume mount requirement"
  - "Migration 001 is a no-op pass — existing schema.sql installs remain intact"
  - "Migration 002 backfill sets all existing scores/retrievals to run_id=1 synthetic run"
  - "Synthetic run#1 timestamps derived from MIN/MAX(scored_at) in person_article_score"
  - "NullPool used in online migration mode to avoid connection leaks in FastAPI lifespan"

patterns-established:
  - "Pattern: Alembic env.py reads DATABASE_URL from os.environ with same fallback as database.py"
  - "Pattern: New SQLAlchemy models with FK dependencies placed BEFORE their dependents in models.py"
  - "Pattern: Migration DML uses sa.text() with named parameters — no string interpolation of user data"

requirements-completed: [HIST-01, HIST-02]

# Metrics
duration: 8min
completed: 2026-04-06
---

# Phase 4 Plan 01: Schema Foundation Summary

**Alembic migration infrastructure with PipelineRun model, nullable run_id FKs on score/retrieval tables, and auto-migrate on FastAPI startup via lifespan handler**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-06T12:25:00Z
- **Completed:** 2026-04-06T12:25:37Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments

- PipelineRun model with 5-state lifecycle enum (PENDING/RUNNING/COMPLETED/PARTIAL/FAILED) and full/update/score_only mode enum
- Alembic migration 001 (no-op baseline) + migration 002 (pipeline_run table + run_id FK columns + synthetic run#1 backfill for existing installations)
- FastAPI lifespan handler runs `alembic upgrade head` at every startup — zero-friction for Docker Compose users
- All 21 tests pass (10 model tests + 11 pre-existing), zero regressions

## Task Commits

TDD task with RED + GREEN commits:

1. **RED — test(04-01): add failing tests for PipelineRun model and run_id FK columns** - `9223675`
2. **GREEN — feat(04-01): Alembic setup, PipelineRun model, run_id FK columns, lifespan auto-migrate** - `7909d45`

## Files Created/Modified

- `api/requirements.txt` — added `alembic>=1.13.3`
- `api/models.py` — added PipelineRun model before existing models; run_id nullable FK on PersonArticleScore and RetrievalLog
- `api/main.py` — replaced bare FastAPI() constructor with lifespan handler running alembic upgrade head
- `api/migrations/env.py` — Alembic env reading DATABASE_URL from os.environ, targeting Base.metadata, NullPool online mode
- `api/migrations/script.py.mako` — standard Alembic revision template
- `api/migrations/versions/001_baseline.py` — no-op baseline stamp (schema.sql installs remain intact)
- `api/migrations/versions/002_pipeline_run.py` — creates pipeline_run table, inserts synthetic run#1 (MIN/MAX scored_at timestamps), adds run_id FK columns, backfills existing rows
- `api/tests/test_models.py` — 6 new tests: pipeline_run_columns, pipeline_run_pk, status_enum, mode_enum, run_id_on_person_article_score, run_id_on_retrieval_log

## Decisions Made

- Alembic programmatic `Config()` with `set_main_option` instead of alembic.ini — eliminates extra Docker volume mount
- Migration 001 is a no-op `pass` — preserves data for installations already running from schema.sql
- NullPool in Alembic online mode — avoids connection leaks in the FastAPI lifespan context
- Synthetic run#1 backfill: timestamps derived from MIN/MAX(scored_at) if data exists, otherwise placeholder zeros

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. Alembic runs automatically on FastAPI startup.

## Next Phase Readiness

- PipelineRun model and migration infrastructure ready for Phase 6 (Historical Pipeline Runs)
- Plan 04-02 (parallel processing refactor) can proceed independently — no schema dependencies
- The `run_id` column on PersonArticleScore/RetrievalLog is in place for the pipeline runner to populate in Phase 04-02

---
*Phase: 04-schema-foundation-parallel-processing*
*Completed: 2026-04-06*
