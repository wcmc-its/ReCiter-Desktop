---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Pipeline Parity & Performance
status: defining_requirements
stopped_at: null
last_updated: "2026-04-05"
last_activity: 2026-04-05 -- Milestone v2.0 started
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.
**Current focus:** Defining requirements for v2.0

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-04-05 — Milestone v2.0 started

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

## Accumulated Context

### Decisions

- v1.0: MariaDB over SQLite — future compatibility with ReCiter Publication Manager
- v1.0: Docker Compose (3 containers) — isolation and consistent environment
- v1.0: SSE for long-running operations — real-time progress without polling complexity
- v1.0: Assertions imported as curations — activates feedback model, enables stats
- v1.1: stats_service: pr_baseline = actual positive rate (not 0.5)
- v1.1: stats_service: np.digitize for calibration bins (sklearn calibration_curve drops empty bins)
- v1.1: stats_service: per-researcher feedbackIdentity model selection done in Python not SQL
- v1.1: stats router is a thin delegation layer — all logic stays in stats_service.py

### Pending Todos

None yet.

### Blockers/Concerns

- `retrieval_log` table added to ORM but NOT in `schema.sql` — needs fixing (pre-existing)
- Current `core/pubmed.py:search_by_name()` is a simplified stub with retmax=2000 cap — must replicate ReCiter's actual retrieval strategy

## Session Continuity

Last session: 2026-04-05
Stopped at: Milestone v2.0 initialization
