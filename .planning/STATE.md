---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Pipeline Parity & Performance
status: planning
stopped_at: Phase 4 context gathered
last_updated: "2026-04-06T04:21:02.566Z"
last_activity: 2026-04-05 — v2.0 roadmap created (Phases 4-8, 19 requirements mapped)
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.
**Current focus:** Phase 4 — Schema Foundation + Parallel Processing

## Current Position

Phase: 4 of 8 (Schema Foundation + Parallel Processing)
Plan: Not started
Status: Ready to plan
Last activity: 2026-04-05 — v2.0 roadmap created (Phases 4-8, 19 requirements mapped)

Progress: [░░░░░░░░░░] 0%

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

- Phase 4 first task: verify `retrieval_log` DDL exists in `schema.sql` before writing any new code (known pre-existing gap)
- Phase 4: `run_id` migration to `person_article_score` must be atomic — test on a populated DB copy before applying
- Phase 5: `AffiliationInDbRetrievalStrategy` — decide single string vs. list for `CoreIdentity.institutions` before coding affiliation search
- Phase 5: audit `frontend/app/pipeline/page.tsx` for `processing` SSE event dependency before removing it in `asyncio.as_completed` switch

## Session Continuity

Last session: 2026-04-06T04:21:02.561Z
Stopped at: Phase 4 context gathered
Resume file: .planning/phases/04-schema-foundation-parallel-processing/04-CONTEXT.md
