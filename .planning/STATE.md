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

## Accumulated Context

### Decisions

- v1.0: MariaDB over SQLite — future compatibility with ReCiter Publication Manager
- v1.0: Docker Compose (3 containers) — isolation and consistent environment
- v1.0: SSE for long-running operations — real-time progress without polling complexity
- v1.0: Assertions imported as curations — activates feedback model, enables stats

### Pending Todos

None yet.

### Blockers/Concerns

- `retrieval_log` table added to ORM but NOT in `schema.sql` — needs fixing (pre-existing)
- Score column in DB may be 0.0–1.0 float; stats endpoint must multiply by 100 before binning — confirm with live DB query before writing endpoint
- Bootstrap CI (1000 resamples): verify completes under 2 seconds for n=100–500 assertions; cap at 500 resamples if needed

## Session Continuity

Last session: 2026-04-04
Stopped at: Roadmap written; no plans created yet
Resume file: None
