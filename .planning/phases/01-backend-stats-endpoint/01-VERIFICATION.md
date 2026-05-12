---
phase: 01-backend-stats-endpoint
verified: 2026-04-04T16:30:00Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 1: Backend Stats Endpoint Verification Report

**Phase Goal:** The `/api/stats` endpoint exists, returns statistically correct chart data for all four visualizations, and exposes viability flags that prevent misleading output
**Verified:** 2026-04-04T16:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /api/stats` returns ROC curve points, AUC scalar, and 95% bootstrap CI (1000 resamples) | VERIFIED | `compute_roc` in stats_service.py lines 119-158: fpr/tpr/auc/ci_lower/ci_upper/ci_degraded returned; n_resamples=1000 default; `test_roc_output`, `test_bootstrap_ci`, `test_ci_degraded_flag` all pass |
| 2 | Calibration bins use 10 uniform buckets; response includes n-per-bin counts and `calibration_viable` flag | VERIFIED | `compute_calibration` lines 161-189: np.linspace(0,1,11) produces exactly 10 bins with n-per-bin; `compute_stats` returns `calibration_viable: len(scores_01) >= 50`; `check_viability` returns `below_n_threshold` when n<50; 3 calibration tests pass |
| 3 | PR curve includes `pr_baseline` anchored to actual positive rate (`n_accepted / n_total`), not hardcoded 0.5 | VERIFIED | `compute_pr` line 199: `pr_baseline = float(labels_binary.mean())`; `test_pr_baseline` asserts `abs(result["pr_baseline"] - 0.4) < 1e-6` for 4/10 positives — passes |
| 4 | Score distribution response contains ACCEPTED and REJECTED counts per 10-point bucket covering 0–100 | VERIFIED | `compute_distribution` lines 209-229: np.arange(0,101,10) gives 10 buckets; each dict has `accepted`/`rejected` counts; `test_distribution_buckets` and `test_distribution_counts` pass |
| 5 | Top-10 disagreements ranked by `|score - assertion_value|` (ACCEPTED=100, REJECTED=0) with person_id, pmid, score, assertion | VERIFIED | `compute_disagreements` lines 232-269: assertion_values=100/0; np.argsort descending top 10; result has all required keys; `test_disagreements_order` and `test_disagreement_calculation` pass |
| 6 | Response includes `viable` flag and `below_n_threshold` warning when n<50; structured error for single-class | VERIFIED | `check_viability` lines 24-59: returns blocked response for n=0 (error:"no_data"), single-class (error:"single_class"), and below-threshold (viable:False, below_n_threshold:True); all 5 STATS-06 tests pass |

**Score: 6/6 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_stats_service.py` | Unit test suite, min 200 lines | VERIFIED | 318 lines, 18 test functions (plan specified 15; 3 additional coverage tests added) |
| `api/services/stats_service.py` | All 8 computation functions, min 150 lines | VERIFIED | 341 lines, 8 functions: check_viability, prepare_joined_data, compute_roc, compute_calibration, compute_pr, compute_distribution, compute_disagreements, compute_stats |
| `api/routers/stats.py` | HTTP layer, min 10 lines, contains `router = APIRouter` | VERIFIED | 12 lines, contains `router = APIRouter(prefix="/api/stats", tags=["stats"])` |
| `api/main.py` | Router registration, contains `stats.router` | VERIFIED | Contains `app.include_router(stats.router)` as 6th router; 6 total include_router calls |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `tests/test_stats_service.py` | `api/services/stats_service.py` | `from api.services.stats_service import` | WIRED | Import present; 18 tests call service functions directly with synthetic data; all pass |
| `api/services/stats_service.py` | `api/models.py` | `from api.models import PersonArticleScore, Curation, Identity` | WIRED | Line 17 confirmed; PersonArticleScore/Curation used in compute_stats JOIN query; Identity used for name lookup |
| `api/services/stats_service.py` | `sklearn.metrics` | `from sklearn.metrics import roc_curve, roc_auc_score, precision_recall_curve, average_precision_score` | WIRED | Lines 9-14 confirmed; all four functions used in compute_roc and compute_pr |
| `api/routers/stats.py` | `api/services/stats_service.py` | `from api.services.stats_service import compute_stats` | WIRED | Line 5 confirmed; `return compute_stats(db)` on line 12 |
| `api/routers/stats.py` | `api/database.py` | `from api.database import get_db` | WIRED | Line 4 confirmed; `Depends(get_db)` used in endpoint signature |
| `api/main.py` | `api/routers/stats.py` | `from api.routers import ... stats` | WIRED | Line 4 of main.py: `from api.routers import institution, researchers, articles, pipeline, scores, stats` |

---

### Data-Flow Trace (Level 4)

Level 4 data-flow trace applies to components that render dynamic data. The stats service is a computation layer (not a UI component); its data source is the database JOIN in `compute_stats`. The data flow from DB to response was verified by tracing `compute_stats`:

1. DB query: `db.query(PersonArticleScore, Curation).join(...)` — real JOIN, not a static return
2. Data prepared via `prepare_joined_data(rows)` — scales calibrated_score to 0-100, applies per-researcher model selection
3. Viability checked before any sklearn call
4. All five computation functions receive real numpy arrays derived from DB rows
5. Response dict merges viability flags with computed results — no hardcoded empty values

| Component | Data Variable | Source | Produces Real Data | Status |
|-----------|---------------|--------|--------------------|--------|
| `compute_stats` | `rows` | `db.query(PersonArticleScore, Curation).join(...)` | Yes — SQL JOIN | FLOWING |
| `compute_roc` | `scores_01, labels_binary` | `prepare_joined_data` output | Yes — derived from DB rows | FLOWING |
| `compute_calibration` | `scores_01, labels_binary` | `prepare_joined_data` output | Yes — derived from DB rows | FLOWING |
| `compute_pr` | `scores_01, labels_binary` | `prepare_joined_data` output | Yes — derived from DB rows | FLOWING |
| `compute_distribution` | `scores_100, assertions` | `prepare_joined_data` output | Yes — derived from DB rows | FLOWING |
| `compute_disagreements` | `scores_100, assertions, person_ids, pmids` | `prepare_joined_data` output + Identity lookup | Yes — derived from DB rows | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 18 unit tests pass | `venv/bin/pytest tests/test_stats_service.py -v` | 18 passed in 2.01s | PASS |
| Full suite passes without regressions | `venv/bin/pytest tests/ --ignore=tests/test_scoring.py -v` | 47 passed in 1.60s | PASS |
| `/api/stats` route registered | `python -c "from api.main import app; assert '/api/stats' in [r.path for r in app.routes]"` | exits 0, confirmed in route list | PASS |
| Router import chain resolves | `python -c "from api.routers.stats import router; print(router.prefix)"` | outputs `/api/stats` | PASS |
| 6 routers registered in main.py | `grep -c "include_router" api/main.py` | 6 | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| STATS-01 | 01-01, 01-02, 01-03 | Backend computes ROC curve points, AUC scalar value, and bootstrap 95% CI for AUC | SATISFIED | `compute_roc` with n_resamples=1000; ci_lower/ci_upper/ci_degraded in response; 3 tests pass |
| STATS-02 | 01-01, 01-02, 01-03 | Backend computes calibration bins (10 uniform bins, n-per-bin counts included), gated at n≥50 | SATISFIED | `compute_calibration` returns exactly 10 bins via np.digitize; n-per-bin in each dict; `calibration_viable` flag in response |
| STATS-03 | 01-01, 01-02, 01-03 | Backend computes PR curve points, AUC-PR scalar, and prevalence-anchored no-skill baseline value | SATISFIED | `compute_pr` returns `pr_baseline = float(labels_binary.mean())`; test asserts 0.4 not 0.5 for 4/10 dataset |
| STATS-04 | 01-01, 01-02, 01-03 | Backend returns score distribution binned by assertion (ACCEPTED/REJECTED counts per 10-point bucket, 0–100) | SATISFIED | `compute_distribution` with np.arange(0,101,10); each bucket has `accepted` and `rejected` int counts; 2 tests pass |
| STATS-05 | 01-01, 01-02, 01-03 | Backend returns top-10 strongest disagreements ranked by `|score − assertion_value|` with person_id, pmid, score, assertion | SATISFIED | `compute_disagreements` with assertion_values=100/0; top_indices via np.argsort descending; 3 tests including exact calculation check pass |
| STATS-06 | 01-01, 01-02, 01-03 | API returns viability flags; `below_n_threshold` when n<50; structured error for single-class | SATISFIED | `check_viability` covers all three conditions; response includes `viable`, `below_n_threshold`, `error` keys; 5 tests pass |

No orphaned requirements. All 6 Phase 1 requirements claimed in plans and verified implemented.

---

### Anti-Patterns Found

No anti-patterns detected in any of the three production files.

- No TODO/FIXME/PLACEHOLDER comments
- No stub return values (empty list/dict/null)
- No hardcoded empty props or disconnected state
- No console.log-only handlers

---

### Human Verification Required

None. All success criteria for Phase 1 are programmatically verifiable. The endpoint itself is a pure computation layer; no visual rendering or real-time behavior is involved at this phase.

---

### Gaps Summary

No gaps. All six success criteria from the ROADMAP.md are satisfied:

1. `GET /api/stats` route exists and returns the correct response structure
2. ROC computation uses 1000 bootstrap resamples with ci_degraded timing flag
3. Calibration always returns exactly 10 bins with n-per-bin counts; `calibration_viable` flag reflects n>=50
4. PR baseline equals actual positive rate via `labels_binary.mean()`
5. Score distribution covers 0-100 in 10-point buckets with ACCEPTED/REJECTED split
6. Top-10 disagreements ranked by `|score - assertion_value|` on 0-100 scale
7. Viability check gates on n=0 (no_data), single-class, and n<50 (below_n_threshold)

The only noted deviation from plans: the test file contains 18 tests rather than the planned 15 (3 additional tests added for `test_single_class_rejected`, `test_pr_output_keys`, `test_disagreements_top_10_limit`). This exceeds the requirement — not a gap.

---

_Verified: 2026-04-04T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
