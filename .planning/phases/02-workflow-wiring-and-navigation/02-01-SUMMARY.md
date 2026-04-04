---
phase: 02-workflow-wiring-and-navigation
plan: 01
subsystem: backend-api + frontend-context
tags: [assertion-count, pipeline-status, workflow-context, tdd]
dependency_graph:
  requires: []
  provides: [assertion_count-api-field, assertionCount-context-value]
  affects: [sidebar-gate, pipeline-cta, stats-page-gate]
tech_stack:
  added: []
  patterns: [SQLAlchemy-JOIN-distinct, helper-function-extraction, WorkflowContext-extension]
key_files:
  created:
    - tests/test_pipeline_status.py
  modified:
    - api/routers/pipeline.py
    - frontend/lib/workflow.tsx
decisions:
  - "get_assertion_count extracted as standalone helper function for direct unit testability (same pattern as stats_service)"
  - "JOIN on PersonArticleScore + Curation with .distinct() prevents double-counting when both model_type rows exist for same (person_id, pmid)"
  - "assertionCount defaults to 0 in all three WorkflowState initialization sites so TypeScript is always satisfied even when API is unavailable"
metrics:
  duration_minutes: 3
  completed_date: "2026-04-04"
  tasks_completed: 2
  files_changed: 3
---

# Phase 02 Plan 01: assertion_count Backend + WorkflowContext Summary

**One-liner:** assertion_count via SQLAlchemy JOIN+distinct on PersonArticleScore/Curation, exposed as assertionCount in WorkflowContext.

## What Was Built

### Task 1: Backend assertion_count field (TDD)

Added `get_assertion_count(db)` helper to `api/routers/pipeline.py`. The function performs an INNER JOIN of `PersonArticleScore` onto `Curation` on `(person_id, pmid)`, then calls `.distinct().count()` to return the number of unique article-researcher pairs that have both a score and a curation. This is the single source of truth for the stats page gate (D-01, D-02).

The helper is called from the `status` endpoint and `assertion_count` is added to the JSON response dict.

Three unit tests cover the edge cases:
- `test_assertion_count_no_curations`: empty tables → 0
- `test_assertion_count_with_curations`: 3 pairs → 3
- `test_assertion_count_distinct`: 1 pair with 2 model_type rows + 1 curation → 1 (not 2)

### Task 2: WorkflowContext assertionCount

Extended `frontend/lib/workflow.tsx` at all 5 required locations:
1. `WorkflowState` interface: `assertionCount: number`
2. `createContext` default: `assertionCount: 0`
3. `useState` initial value: `assertionCount: 0`
4. `apiFetch` type annotation: `assertion_count: number`
5. `setState` mapping: `assertionCount: status.assertion_count`

TypeScript compiles cleanly (verified from main frontend project with installed node_modules).

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1: Backend assertion_count | cfa0858 | api/routers/pipeline.py, tests/test_pipeline_status.py |
| 2: WorkflowContext assertionCount | 21603c8 | frontend/lib/workflow.tsx |

## Verification Results

1. `pytest tests/test_pipeline_status.py -x -v` — 3/3 passed
2. `pytest tests/ --ignore=tests/test_scoring.py` — 50/50 passed (no regressions)
3. `tsc --noEmit` from main frontend — exits 0 (no errors)
4. `grep -c "assertionCount" frontend/lib/workflow.tsx` — 4 (interface + createContext + useState + setState)
5. `grep -c "assertion_count" api/routers/pipeline.py` — 3 (helper function body x2 + return dict)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — assertionCount is wired end-to-end: DB query → API response field → WorkflowContext value. No placeholder values in the data path.

## Deferred Items

- `tests/test_scoring.py` fails with `ImportError: cannot import name 'load_model' from 'core.scoring'` — pre-existing, unrelated to this plan. Logged to deferred-items.

## Self-Check: PASSED

- FOUND: tests/test_pipeline_status.py
- FOUND: api/routers/pipeline.py
- FOUND: frontend/lib/workflow.tsx
- FOUND: 02-01-SUMMARY.md
- FOUND: commit cfa0858 (Task 1)
- FOUND: commit 21603c8 (Task 2)
