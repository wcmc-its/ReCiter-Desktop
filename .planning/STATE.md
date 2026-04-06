---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Pipeline Parity & Performance
status: verifying
stopped_at: Phase 10 context gathered (discuss mode)
last_updated: "2026-04-06T18:05:52.559Z"
last_activity: 2026-04-06 -- Phase 09 complete (upsert implementation verified)
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 4
  completed_plans: 4
  percent: 100
---

# State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.
**Current focus:** Phase 10 — pipeline-page-polish-and-number-formatting (next)

## Current Position

Milestone: v2.1 — Retrieve & Score: UX, Bugs & Robustness
Phase: 09 (parallel-write-race-condition-fix) — COMPLETE
Next Phase: 10 (Pipeline Page Polish + Number Formatting)
Status: Phase 09 verified; ready to begin Phase 10
Last activity: 2026-04-06 -- Phase 09 complete (upsert implementation verified)

Progress: [███░░░░░░░] 33%

Note: v2.0 phases 5-8 (retrieval parity, historical runs, results refinement, UI polish) remain on the roadmap and will be executed after v2.1 ships.

## Performance Metrics

**Velocity:**

- Total plans completed: 2 (09-01, 09-02)
- Average duration: ~8 minutes per plan
- Total execution time: ~16 minutes

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
- v2.1: DB-01 fix: `mysql_insert(...).on_duplicate_key_update(...)` replaces SELECT+INSERT loops in `_process_one_researcher`; no-op upsert for article/person_article tables, full-update upsert for person_article_score; created_at excluded from all on_duplicate_key_update clauses

### Pending Todos

None.

### Blockers/Concerns

- Phase 5: `AffiliationInDbRetrievalStrategy` — decide single string vs. list for `CoreIdentity.institutions` before coding affiliation search

## Session Continuity

Last session: 2026-04-06T18:05:52.556Z
Stopped at: Phase 10 context gathered (discuss mode)
Resume file: .planning/phases/10-pipeline-page-polish-number-formatting/10-CONTEXT.md
