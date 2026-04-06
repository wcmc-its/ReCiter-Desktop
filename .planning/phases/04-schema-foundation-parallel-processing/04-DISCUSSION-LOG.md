# Phase 4: Schema Foundation + Parallel Processing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 04-schema-foundation-parallel-processing
**Areas discussed:** Migration strategy, Run lifecycle & status, Run #1 backfill, Frontend ordering

---

## Migration Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic | Versioned migration scripts. Runs automatically on startup or via CLI. Standard for SQLAlchemy apps. | ✓ |
| Docker entrypoint SQL | Raw ALTER TABLE in startup script. No version tracking. | |
| SQLAlchemy create_all only | Cannot add columns to existing tables. Requires data loss. | |

**User's choice:** Alembic
**Notes:** STATE.md already flagged Alembic as the v2.0 plan.

| Option | Description | Selected |
|--------|-------------|----------|
| Auto on startup | Alembic upgrade runs when FastAPI boots. Zero friction. | ✓ |
| Manual CLI step | User runs 'alembic upgrade head' before starting. | |

**User's choice:** Auto on startup

| Option | Description | Selected |
|--------|-------------|----------|
| Full baseline first | Migration 001 captures current schema. Migration 002 adds new tables/columns. | ✓ |
| Only new changes | Alembic only tracks new additions. Incomplete schema picture. | |

**User's choice:** Full baseline first

| Option | Description | Selected |
|--------|-------------|----------|
| api/migrations/ | Alembic directory inside api/ alongside models.py. | ✓ |
| Root-level migrations/ | Alembic directory at project root. | |
| You decide | Claude picks. | |

**User's choice:** api/migrations/

---

## Run Lifecycle & Status

| Option | Description | Selected |
|--------|-------------|----------|
| Simple 3-state | RUNNING → COMPLETED / FAILED | |
| Detailed 4-state | PENDING → RUNNING → COMPLETED / FAILED | |
| 5-state with partial | PENDING → RUNNING → COMPLETED / PARTIAL / FAILED | ✓ |

**User's choice:** 5-state with partial

| Option | Description | Selected |
|--------|-------------|----------|
| Mark COMPLETED, log errors | Run is COMPLETED as long as it ran to the end. Per-researcher errors captured separately. | ✓ |
| Mark PARTIAL_FAILURE | Distinct status for mixed results. | |
| Mark FAILED if any error | Any researcher error = whole run FAILED. | |

**User's choice:** Mark COMPLETED, log errors per-researcher
**Notes:** PARTIAL reserved for interrupted runs (crash, abort), not mixed researcher results.

| Option | Description | Selected |
|--------|-------------|----------|
| Store counts | Aggregate counts in pipeline_run row. Fast Phase 6 queries. | ✓ |
| Compute on read | Calculate from related tables. Normalized but slower. | |

**User's choice:** Store counts

| Option | Description | Selected |
|--------|-------------|----------|
| Store mode | Column for mode string. | ✓ |
| Infer from data | Don't store, infer. Fragile. | |

**User's choice:** Store mode

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-increment integer | Simple, human-readable. | ✓ |
| UUID | Globally unique, overkill for local app. | |

**User's choice:** Auto-increment integer

| Option | Description | Selected |
|--------|-------------|----------|
| Use PENDING now | Create row as PENDING, transition to RUNNING. | ✓ |
| Skip for now | Create directly as RUNNING. | |

**User's choice:** Use PENDING now

---

## Run #1 Backfill

| Option | Description | Selected |
|--------|-------------|----------|
| Migration-time UPDATE | Create synthetic run #1, UPDATE existing rows. No NULLs after migration. | ✓ |
| NULL means pre-history | Don't backfill. Every query needs NULL handling. | |
| Lazy backfill on first query | Defer work. Unpredictable latency, race conditions. | |

**User's choice:** Migration-time UPDATE

| Option | Description | Selected |
|--------|-------------|----------|
| Earliest scored_at | started_at = MIN(scored_at), completed_at = MAX(scored_at). | ✓ |
| Migration timestamp | Use migration execution time. | |
| You decide | Claude picks. | |

**User's choice:** Earliest scored_at

---

## Frontend Ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Keep roster order, update in place | Rows stay in upload order. Completions update in place. | ✓ |
| Sort completed to top | Completed researchers bubble up. | |
| Two sections | In Progress / Completed split. | |

**User's choice:** Keep roster order, update in place

| Option | Description | Selected |
|--------|-------------|----------|
| Show worker count | Status line: "5/8 workers active". | ✓ |
| No worker info | Don't expose parallelism details. | |
| You decide | Claude picks. | |

**User's choice:** Show worker count

| Option | Description | Selected |
|--------|-------------|----------|
| Remove processing event | With as_completed, all researchers run simultaneously. Event is meaningless. | ✓ |
| Keep but fire at submit time | Fire for all researchers after queued. Redundant. | |
| You decide | Claude picks. | |

**User's choice:** Remove processing event

---

## Claude's Discretion

- Exact pipeline_run column types and constraints
- Alembic env.py configuration details
- SSE event payload changes to carry run_id
- PubMed API key detection for worker count selection

## Deferred Ideas

None — discussion stayed within phase scope.
