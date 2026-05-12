---
phase: "01"
plan: "02"
subsystem: "api/services"
tags: ["stats", "roc", "calibration", "pr-curve", "distribution", "disagreements", "xgboost", "sklearn"]
dependency_graph:
  requires: ["01-01"]
  provides: ["stats_service — all statistical computation for /api/stats"]
  affects: ["api/routers/stats.py (plan 01-03)"]
tech_stack:
  added: []
  patterns:
    - "Pure computation functions accepting numpy arrays (testable without DB)"
    - "Bootstrap CI via numpy random.default_rng().integers() — 1000 resamples"
    - "np.digitize for fixed 10-bin calibration (sklearn calibration_curve drops empty bins)"
    - "Per-researcher feedbackIdentity model selection in Python, not SQL (D-01)"
key_files:
  created:
    - "api/services/stats_service.py"
    - "tests/test_stats_service.py"
  modified: []
decisions:
  - "Implemented all 8 functions in one commit alongside tests (TDD RED then full GREEN)"
  - "Installed sqlalchemy + pymysql into local Streamlit venv to enable unit test import chain"
  - "ci_degraded uses wall-clock check (time.perf_counter > 2.0) per D-05"
  - "pr_baseline = labels_binary.mean() not 0.5 (STATS-03 mandate)"
  - "Calibration uses np.digitize (not sklearn calibration_curve alone) to ensure exactly 10 bins"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-04"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 01 Plan 02: Stats Service Implementation Summary

**One-liner:** Complete stats computation service with ROC+bootstrap CI, 10-bin calibration, PR curve, score distribution, and top-10 disagreements using sklearn/numpy, backed by 18 unit tests.

## What Was Built

`api/services/stats_service.py` implements all statistical computations that power the `GET /api/stats` endpoint. All pure computation functions accept numpy arrays directly, making them testable without a database connection.

### Functions Implemented (8 total)

| Function | Requirement | Description |
|----------|-------------|-------------|
| `check_viability(n, assertions)` | STATS-06 | Returns (is_blocked, dict) for n=0, single-class, and n<50 conditions |
| `prepare_joined_data(rows)` | D-01, D-03 | Per-researcher feedbackIdentity model selection, score×100 conversion |
| `compute_roc(scores_01, labels_binary, n_resamples=1000)` | STATS-01 | ROC curve, AUC, bootstrap 95% CI with ci_degraded flag |
| `compute_calibration(scores_01, labels_binary)` | STATS-02 | Exactly 10 bins with n-per-bin counts via np.digitize |
| `compute_pr(scores_01, labels_binary)` | STATS-03 | PR curve, AUC-PR, pr_baseline = actual positive rate |
| `compute_distribution(scores_100, assertions)` | STATS-04 | 10-point buckets with ACCEPTED/REJECTED counts |
| `compute_disagreements(scores_100, assertions, ...)` | STATS-05 | Top-10 ranked by descending |score - assertion_value| |
| `compute_stats(db)` | All | Orchestrator: DB query → model selection → viability → 5 stats |

## Test Results

All 18 unit tests pass:
- 5 STATS-06 viability tests (test_no_data_error, test_single_class_error, test_single_class_rejected, test_below_threshold_flags, test_at_threshold_viable)
- 3 ROC tests (test_roc_output, test_bootstrap_ci, test_ci_degraded_flag)
- 3 calibration tests (test_calibration_bins, test_calibration_n_per_bin, test_calibration_viable_flag)
- 2 PR tests (test_pr_baseline, test_pr_output_keys)
- 2 distribution tests (test_distribution_buckets, test_distribution_counts)
- 3 disagreement tests (test_disagreements_order, test_disagreement_calculation, test_disagreements_top_10_limit)

Full suite (47 tests, ignoring test_scoring.py): all pass, no regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] sqlalchemy and pymysql missing from local venv**
- **Found during:** Task 1, first test run
- **Issue:** `api/services/stats_service.py` imports `from sqlalchemy.orm import Session` which triggers `api/database.py` → `create_engine` → requires `pymysql`. The Streamlit venv only has Streamlit dependencies; the API runs in Docker.
- **Fix:** Installed `sqlalchemy` and `pymysql` into the local venv so the import chain succeeds during unit tests. Pure computation tests do not actually open a DB connection.
- **Files modified:** None (pip install only)
- **Commit:** Not committed (pip install only)

### Notes

- All 8 functions were implemented together in a single file write (Task 1 commit), as the plan called for a single file. The Task 1 and Task 2 commits represent the TDD RED and GREEN phases respectively.
- 18 tests were written vs. the 15 specified in the plan (3 additional coverage tests added: test_single_class_rejected, test_pr_output_keys, test_disagreements_top_10_limit).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| TDD RED | 259aead | test(01-02): add failing tests for stats_service |
| Task 1+2 GREEN | aafae97 | feat(01-02): implement all 8 stats_service functions |

## Known Stubs

None — all functions are fully implemented with real computation logic.

## Self-Check: PASSED
