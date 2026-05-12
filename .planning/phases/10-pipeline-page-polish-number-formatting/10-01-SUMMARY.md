---
phase: 10-pipeline-page-polish-number-formatting
plan: 01
subsystem: frontend
tags: [pipeline, ux, bugfix, css, eta, formatting]
dependency_graph:
  requires: []
  provides: [PIPE-01, PIPE-02, PIPE-03, FMT-01-partial]
  affects: [frontend/app/pipeline/page.tsx, frontend/app/globals.css]
tech_stack:
  added: []
  patterns: [useRef for SSE inter-completion delta, .toLocaleString() for number formatting]
key_files:
  created: []
  modified:
    - frontend/app/pipeline/page.tsx
    - frontend/app/globals.css
decisions:
  - "Inter-completion delta ETA via useRef avoids stale closure issues and never counts up between completions"
  - "lastCompletionTimeRef initialized on 'started' SSE event (not pipeline button press) so first delta is from actual work start"
  - "Pre-existing test_scoring.py ImportError (load_model not found) is out of scope — 50 other tests pass"
metrics:
  duration: ~8 minutes
  completed_date: "2026-04-06T19:27:52Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 10 Plan 01: Pipeline Page Polish — Heading, ETA Fix, Animation Direction Summary

**One-liner:** Fixed pipeline page heading to "Retrieve & Score", replaced cumulative ETA with inter-completion delta rolling average via `useRef`, corrected CSS stripe animation to left-to-right, and added `.toLocaleString()` comma formatting to progress counters.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Fix heading, subtitle, ETA computation, and progress number formatting | `6b1813e` | `frontend/app/pipeline/page.tsx` |
| 2 | Fix animation direction in globals.css | `3fe7da7` | `frontend/app/globals.css` |

## Changes Made

### Task 1 — pipeline/page.tsx (4 changes)

**Change 1 — Heading (PIPE-01):**
- Before: `Processing Pipeline`
- After: `Retrieve & Score`

**Change 2 — Subtitle (PIPE-01):**
- Before: `...for each researcher.`
- After: `...for each researcher's candidate articles.`

**Change 3 — ETA computation (PIPE-02):**
- Added `const lastCompletionTimeRef = useRef<number | null>(null)` at component top level
- Reset to `null` in `startPipeline()` alongside other state resets
- Initialized to `Date.now()` in `started` SSE event handler
- Deleted old cumulative ETA block (`elapsed / completedCount` — counted up between completions)
- Replaced with inter-completion delta rolling average:
  ```typescript
  const now = Date.now();
  if (lastCompletionTimeRef.current !== null) {
    const delta = now - lastCompletionTimeRef.current;
    setAvgTimePerResearcher((prev) => prev === 0 ? delta : (prev + delta) / 2);
  }
  lastCompletionTimeRef.current = now;
  ```
- `startTime` state preserved (still used for "Elapsed:" display)

**Change 4 — Number formatting (FMT-01 partial):**
- `totalArticles` → `totalArticles.toLocaleString()` in progress stats line
- `totalScored` → `totalScored.toLocaleString()` in progress stats line

### Task 2 — globals.css (1 change)

**Change — Keyframe direction (PIPE-03):**
- Before: `from { background-position: 40px 0; } to { background-position: 0 0; }` (right-to-left)
- After: `from { background-position: 0 0; } to { background-position: 40px 0; }` (left-to-right)

## Verification Results

| Check | Result |
|-------|--------|
| Heading "Retrieve & Score" present | PASS (line 278) |
| Subtitle contains "candidate articles" | PASS (line 280) |
| `lastCompletionTimeRef` declared + used (6 occurrences) | PASS |
| Old ETA `elapsed / completedCount` removed | PASS (0 occurrences) |
| Rolling average formula present | PASS (line 180) |
| `totalArticles.toLocaleString()` in progress stats | PASS (line 350) |
| `totalScored.toLocaleString()` in progress stats | PASS (line 351) |
| CSS `from` = `background-position: 0 0` | PASS |
| CSS `to` = `background-position: 40px 0` | PASS |
| Backend tests (50 tests) | PASS |

## Deviations from Plan

None — plan executed exactly as written.

**Note on test_scoring.py:** Pre-existing `ImportError: cannot import name 'load_model' from 'core.scoring'` in `tests/test_scoring.py` is unrelated to this plan's frontend-only changes. All 50 remaining backend tests pass.

## Known Stubs

None. All progress stats display live runtime data from SSE events. No placeholder values or hardcoded stubs exist in the modified files.

## Self-Check: PASSED

Files exist:
- `frontend/app/pipeline/page.tsx` — FOUND
- `frontend/app/globals.css` — FOUND

Commits exist:
- `6b1813e` — FOUND (feat(10-01): fix heading, subtitle, ETA computation...)
- `3fe7da7` — FOUND (fix(10-01): correct pipeline-stripe keyframe...)
