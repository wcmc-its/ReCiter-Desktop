---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Statistics & Validation View
status: planning
stopped_at: Completed 01-02-PLAN.md (stats_service implementation)
last_updated: "2026-04-04T15:51:26.781Z"
last_activity: 2026-04-04 — Roadmap created for v1.1 Statistics & Validation View
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 3
  completed_plans: 0
  percent: 0
---

# State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-04)

**Core value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.
**Current focus:** v1.1 Phase 1 — Backend Stats Endpoint

## Current Position

Phase: 1 of 3 (Backend Stats Endpoint)
Plan: — (not yet planned)
Status: Ready to plan
Last activity: 2026-04-04 — Roadmap created for v1.1 Statistics & Validation View

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

*Updated after each plan completion*
| Phase 01-backend-stats-endpoint P02 | 257 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

- v1.0: MariaDB over SQLite — future compatibility with ReCiter Publication Manager
- v1.0: Docker Compose (3 containers) — isolation and consistent environment
- v1.0: SSE for long-running operations — real-time progress without polling complexity
- v1.0: Assertions imported as curations — activates feedback model, enables stats
- [Phase 01-backend-stats-endpoint]: stats_service: pr_baseline = actual positive rate (not 0.5) per STATS-03
- [Phase 01-backend-stats-endpoint]: stats_service: np.digitize for calibration bins (sklearn calibration_curve drops empty bins)
- [Phase 01-backend-stats-endpoint]: stats_service: per-researcher feedbackIdentity model selection done in Python not SQL (D-01)

### Pending Todos

None yet.

### Blockers/Concerns

- `retrieval_log` table added to ORM but NOT in `schema.sql` — needs fixing (pre-existing)
- Score column in DB may be 0.0–1.0 float; stats endpoint must multiply by 100 before binning — confirm with live DB query before writing endpoint
- Bootstrap CI (1000 resamples): verify completes under 2 seconds for n=100–500 assertions; cap at 500 resamples if needed

## Session Continuity

Last session: 2026-04-04T15:51:26.779Z
Stopped at: Completed 01-02-PLAN.md (stats_service implementation)
Resume file: None
