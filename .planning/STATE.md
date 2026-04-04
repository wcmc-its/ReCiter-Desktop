---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Statistics & Validation View
status: executing
stopped_at: Phase 2 UI-SPEC approved
last_updated: "2026-04-04T19:05:39.707Z"
last_activity: 2026-04-04 -- Phase 02 execution started
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 5
  completed_plans: 3
  percent: 60
---

# State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-04)

**Core value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.
**Current focus:** Phase 02 — workflow-wiring-and-navigation

## Current Position

Phase: 02 (workflow-wiring-and-navigation) — EXECUTING
Plan: 1 of 2
Status: Executing Phase 02
Last activity: 2026-04-04 -- Phase 02 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 3
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | - | - |

*Updated after each plan completion*
| Phase 01-backend-stats-endpoint P02 | 257 | 2 tasks | 2 files |
| Phase 01-backend-stats-endpoint P03 | 169 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

- v1.0: MariaDB over SQLite — future compatibility with ReCiter Publication Manager
- v1.0: Docker Compose (3 containers) — isolation and consistent environment
- v1.0: SSE for long-running operations — real-time progress without polling complexity
- v1.0: Assertions imported as curations — activates feedback model, enables stats
- [Phase 01-backend-stats-endpoint]: stats_service: pr_baseline = actual positive rate (not 0.5) per STATS-03
- [Phase 01-backend-stats-endpoint]: stats_service: np.digitize for calibration bins (sklearn calibration_curve drops empty bins)
- [Phase 01-backend-stats-endpoint]: stats_service: per-researcher feedbackIdentity model selection done in Python not SQL (D-01)
- [Phase 01-backend-stats-endpoint]: stats router is a thin delegation layer — all logic stays in stats_service.py per D-07

### Pending Todos

None yet.

### Blockers/Concerns

- `retrieval_log` table added to ORM but NOT in `schema.sql` — needs fixing (pre-existing)
- Score column in DB may be 0.0–1.0 float; stats endpoint must multiply by 100 before binning — confirm with live DB query before writing endpoint
- Bootstrap CI (1000 resamples): verify completes under 2 seconds for n=100–500 assertions; cap at 500 resamples if needed

## Session Continuity

Last session: 2026-04-04T16:41:29.535Z
Stopped at: Phase 2 UI-SPEC approved
Resume file: .planning/phases/02-workflow-wiring-and-navigation/02-UI-SPEC.md
