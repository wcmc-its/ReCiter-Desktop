---
phase: 09-parallel-write-race-condition-fix
plan: "01"
subsystem: test-infrastructure
tags: [pytest, asyncio, tdd, upsert, db-race-condition]
dependency_graph:
  requires: []
  provides: [pytest-asyncio infrastructure, RED-state upsert tests for DB-01]
  affects: [api/tests/test_pipeline_runner.py, api/services/pipeline_runner.py]
tech_stack:
  added: [pytest>=9.0.0, pytest-asyncio>=1.3.0]
  patterns: [TDD RED state, SQL statement compilation test, source inspection test]
key_files:
  created:
    - pytest.ini
    - api/tests/test_upsert_writes.py
  modified:
    - requirements.txt
decisions:
  - "Use absolute __file__-relative path in regression test to avoid pytest __pycache__ mismatch when running from main repo root against worktree files"
  - "Statement compilation tests (tests 1-3) test SQL generation directly and PASS in RED state; only test 4 fails because production code still uses SELECT+INSERT"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-06"
  tasks_completed: 2
  files_changed: 3
---

# Phase 09 Plan 01: Test Infrastructure (Wave 0) Summary

**One-liner:** pytest-asyncio infrastructure configured and 5-test upsert suite created in RED state — `test_no_article_select_in_process` fails confirming Wave 1 implementation target.

## What Was Built

### Task 1: pytest infrastructure
- Created `pytest.ini` at repo root with `asyncio_mode = auto`
- Added `pytest>=9.0.0` and `pytest-asyncio>=1.3.0` to `requirements.txt`
- Installed dependencies into the project venv
- **Result:** All 5 existing `test_pipeline_runner.py` async tests now pass (were failing before due to missing pytest-asyncio config)

### Task 2: RED-state upsert test suite
Created `api/tests/test_upsert_writes.py` with 5 tests across 3 test classes:

| Test | Class | Expected State | Actual State |
|------|-------|---------------|--------------|
| `test_article_upsert_stmt` | TestUpsertStatements | PASS | PASS |
| `test_person_article_upsert_stmt` | TestUpsertStatements | PASS | PASS |
| `test_score_upsert_stmt` | TestUpsertStatements | PASS | PASS |
| `test_no_article_select_in_process` | TestProductionCodePattern | FAIL (RED) | FAIL (RED) |
| `test_existing_pipeline_tests_pass` | TestRegression | PASS | PASS |

**Full suite result:** 30 passed, 1 failed (expected RED failure only).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pytest __pycache__ mismatch in regression test**
- **Found during:** Task 2 initial test run
- **Issue:** `pytest.main(["api/tests/test_pipeline_runner.py"])` used a relative path. When running from the main repo root (where the venv lives) against a worktree, pytest resolved the relative path to the main repo's `test_pipeline_runner.py` while the module was already imported from the worktree path — causing an `import file mismatch` error (ExitCode.INTERRUPTED: 2).
- **Fix:** Changed the regression test to use `os.path.join(os.path.dirname(__file__), "test_pipeline_runner.py")` so the absolute worktree path is always used.
- **Files modified:** `api/tests/test_upsert_writes.py`
- **Commit:** f820dbc (included in Task 2 commit)

## Verification Results

```
pytest.ini: EXISTS — asyncio_mode = auto
requirements.txt: includes pytest>=9.0.0 and pytest-asyncio>=1.3.0
pipeline_runner tests: 5/5 PASS
upsert tests: 4/5 pass, 1 fail (test_no_article_select_in_process — confirmed RED)
full api/tests suite: 30 passed, 1 failed
```

## Wave 1 Signal

The RED failure provides Wave 1's implementation target:

```
AssertionError: _process_one_researcher still contains db.query(Article).filter_by —
this SELECT+INSERT pattern is the root cause of the race condition (DB-01)
```

Wave 1 must replace the `db.query(Article).filter_by` + conditional `db.add()` pattern with `mysql_insert(...).on_duplicate_key_update(...)` bulk upserts. When that happens, `test_no_article_select_in_process` will turn GREEN.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| e634622 | chore | pytest.ini + pytest-asyncio in requirements.txt |
| f820dbc | test | RED-state upsert tests for DB-01 (4 pass, 1 fails) |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| pytest.ini exists with asyncio_mode = auto | FOUND |
| pytest-asyncio in requirements.txt | FOUND |
| api/tests/test_upsert_writes.py exists | FOUND |
| 09-01-SUMMARY.md exists | FOUND |
| Commit e634622 exists | FOUND |
| Commit f820dbc exists | FOUND |
