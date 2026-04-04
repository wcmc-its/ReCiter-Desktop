---
phase: 1
slug: backend-stats-endpoint
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | none — Wave 0 creates test file |
| **Quick run command** | `venv/bin/python -m pytest tests/test_stats_service.py -x` |
| **Full suite command** | `venv/bin/python -m pytest tests/ --ignore=tests/test_scoring.py` |
| **Estimated runtime** | ~5 seconds |

**Note:** `tests/test_scoring.py` has a pre-existing `ImportError` (`cannot import name 'load_model'`) — out of scope for Phase 1. Always use `--ignore=tests/test_scoring.py` for full suite runs.

---

## Sampling Rate

- **After every task commit:** Run `venv/bin/python -m pytest tests/test_stats_service.py -x`
- **After every plan wave:** Run `venv/bin/python -m pytest tests/ --ignore=tests/test_scoring.py`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-W0-01 | W0 | 0 | STATS-01–06 | unit stubs | `pytest tests/test_stats_service.py -x` | ❌ W0 | ⬜ pending |
| 1-01-01 | 01 | 1 | STATS-01 | unit | `pytest tests/test_stats_service.py::test_roc_output -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | STATS-01 | unit | `pytest tests/test_stats_service.py::test_bootstrap_ci -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | STATS-01 | unit | `pytest tests/test_stats_service.py::test_ci_degraded_flag -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 01 | 1 | STATS-02 | unit | `pytest tests/test_stats_service.py::test_calibration_bins -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 01 | 1 | STATS-02 | unit | `pytest tests/test_stats_service.py::test_calibration_n_per_bin -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 01 | 1 | STATS-02 | unit | `pytest tests/test_stats_service.py::test_calibration_viable_flag -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 01 | 2 | STATS-03 | unit | `pytest tests/test_stats_service.py::test_pr_baseline -x` | ❌ W0 | ⬜ pending |
| 1-04-01 | 01 | 2 | STATS-04 | unit | `pytest tests/test_stats_service.py::test_distribution_buckets -x` | ❌ W0 | ⬜ pending |
| 1-04-02 | 01 | 2 | STATS-04 | unit | `pytest tests/test_stats_service.py::test_distribution_counts -x` | ❌ W0 | ⬜ pending |
| 1-05-01 | 01 | 2 | STATS-05 | unit | `pytest tests/test_stats_service.py::test_disagreements_order -x` | ❌ W0 | ⬜ pending |
| 1-05-02 | 01 | 2 | STATS-05 | unit | `pytest tests/test_stats_service.py::test_disagreement_calculation -x` | ❌ W0 | ⬜ pending |
| 1-06-01 | 01 | 3 | STATS-06 | unit | `pytest tests/test_stats_service.py::test_no_data_error -x` | ❌ W0 | ⬜ pending |
| 1-06-02 | 01 | 3 | STATS-06 | unit | `pytest tests/test_stats_service.py::test_single_class_error -x` | ❌ W0 | ⬜ pending |
| 1-06-03 | 01 | 3 | STATS-06 | unit | `pytest tests/test_stats_service.py::test_below_threshold_flags -x` | ❌ W0 | ⬜ pending |
| 1-06-04 | 01 | 3 | STATS-06 | unit | `pytest tests/test_stats_service.py::test_at_threshold_viable -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_stats_service.py` — unit test stubs for all STATS-01 through STATS-06 requirements above (pure unit tests, mock data passed directly to service functions — no DB or Docker required)

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
