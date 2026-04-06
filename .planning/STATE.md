---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: "Retrieve & Score — UX, Bugs & Robustness"
status: planning
stopped_at: Milestone initialized; Phase 9 ready to plan
last_updated: "2026-04-06T16:20:00.000Z"
last_activity: 2026-04-06 -- Milestone v2.1 started; requirements and roadmap already defined (phases 9-11)
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.
**Current focus:** Phase 04 — schema-foundation-parallel-processing

## Current Position

Milestone: v2.1 — Retrieve & Score: UX, Bugs & Robustness
Phase: 09 (parallel-write-race-fix) — READY TO PLAN
Plan: —
Status: Defining phase 9; requirements PIPE-01–07, FMT-01, DB-01 defined; phases 9-11 roadmapped
Last activity: 2026-04-06 -- Milestone v2.1 initialized

Progress: [░░░░░░░░░░] 0%

Note: v2.0 phases 5-8 (retrieval parity, historical runs, results refinement, UI polish) remain on the roadmap and will be executed after v2.1 ships.

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

- v1.0: MariaDB over SQLite — future compatibility with ReCiter Publication Manager
- v1.0: Docker Compose (3 containers) — isolation and consistent environment
- v1.0: SSE for long-running operations — real-time progress without polling complexity
- v1.0: Assertions imported as curations — activates feedback model, enables stats
- v1.1: stats_service: pr_baseline = actual positive rate (not 0.5)
- v1.1: stats_service: np.digitize for calibration bins (sklearn calibration_curve drops empty bins)
- v1.1: stats router is a thin delegation layer — all logic stays in stats_service.py
- v2.0: Alembic 1.13.3 added for schema migrations — only safe way to ALTER populated tables

### Pending Todos

None yet.

### Blockers/Concerns

- SQLAlchemy OperationalError 1020 (concurrent score writes) — generic-name researchers trigger race condition on `person_article_score`; fix is `INSERT ... ON DUPLICATE KEY UPDATE` or `no_autoflush` — captured in v2.1
- Phase 5: `AffiliationInDbRetrievalStrategy` — decide single string vs. list for `CoreIdentity.institutions` before coding affiliation search

## Session Continuity

Last session: 2026-04-06T16:20:00.000Z
Stopped at: Milestone v2.1 initialized; next action is plan Phase 9
Resume file: none
