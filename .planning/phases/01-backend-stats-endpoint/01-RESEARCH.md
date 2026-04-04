# Phase 01: Backend Stats Endpoint - Research

**Researched:** 2026-04-04
**Domain:** FastAPI endpoint + scikit-learn statistical metrics (ROC, PR, calibration, bootstrap)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Per-researcher model priority: use `feedbackIdentity` scores if they exist for that researcher, else fall back to `identityOnly`. Mixed model types across researchers in the same aggregate stat set is acceptable.
- **D-02:** No run-level consistency enforcement — best available model per researcher.
- **D-03:** Use **0–100 everywhere** in the API response. Multiply `calibrated_score × 100` at data load time before all stat computations. Consistent with rest of app. Calibration bins become `[0, 10, 20, ..., 100]`.
- **D-04:** Always run **1000 resamples** as specified in STATS-01.
- **D-05:** If bootstrap runtime exceeds ~2 seconds, include `"ci_degraded": true` in the response (alongside the CI result — don't skip the CI).
- **D-06:** No caching — always compute fresh from current DB state on every request.
- **D-07:** New `api/routers/stats.py` (HTTP layer) + `api/services/stats_service.py` (all computation). Follows existing routers/ + services/ pattern.
- **D-08:** One combined `stats_service.py` for all stat computations.
- **D-09:** Register new router in `api/main.py` following the same pattern as the other 5 routers already there.

### Claude's Discretion

- Exact bootstrap implementation (numpy vs scipy.stats.bootstrap — either is fine)
- How to detect "single-class" error condition (all assertions the same label)
- Internal data structures for passing joined data between functions
- Error response format (consistent with other routers in the project)

### Deferred Ideas (OUT OF SCOPE)

- Historical run comparison (stats snapshots per pipeline run)
- Per-researcher stats drill-down
- In-memory cache invalidated on pipeline run
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATS-01 | Backend computes ROC curve points, AUC scalar value, and bootstrap 95% CI for AUC | Verified: `roc_curve`, `roc_auc_score` from sklearn; numpy bootstrap benchmarked at 0.36–0.41s for n=50–500 (well under 2s limit) |
| STATS-02 | Backend computes calibration bins (10 uniform bins, n-per-bin counts included), gated at n≥50 joined pairs | Verified: custom `np.digitize` binning on 0-100 scale for counts; `calibration_curve(n_bins=10, strategy='uniform')` for fraction-positive values |
| STATS-03 | Backend computes PR curve points, AUC-PR scalar, and prevalence-anchored no-skill baseline | Verified: `precision_recall_curve`, `average_precision_score`; baseline = `n_accepted / n_total` (positive rate) |
| STATS-04 | Backend returns score distribution binned by assertion (ACCEPTED/REJECTED counts per 10-point bucket, 0–100) | Verified: `np.digitize` with `np.arange(0, 101, 10)` on 0-100 scale scores; separate accept/reject counts per bucket |
| STATS-05 | Backend returns top-10 strongest disagreements ranked by `|score - assertion_value|` (ACCEPTED→100, REJECTED→0) | Verified: `np.argsort(disagreements)[::-1][:10]` pattern; assertion_value mapping confirmed |
| STATS-06 | API returns viability flags (below-n-threshold warning when n<50, single-class-only error when all assertions are the same label) | Verified: `viable = n >= 50`, `below_n_threshold = n < 50`; single-class = `len(set(assertions)) < 2` |
</phase_requirements>

---

## Summary

Phase 1 adds a `GET /api/stats` endpoint to the existing FastAPI application. The endpoint joins `person_article_score` and `curation` tables, applies per-researcher model selection (feedbackIdentity preferred), and computes five statistical outputs: ROC curve + bootstrap AUC CI, calibration plot with n-per-bin counts, PR curve, score distribution histogram, and top-10 disagreements. Viability flags gate misleading output when data is insufficient.

All required dependencies (scikit-learn, numpy, scipy) are already in `api/requirements.txt`. The code structure follows an established pattern: a thin `api/routers/stats.py` delegates all computation to `api/services/stats_service.py`. The new router is registered as the 6th entry in `api/main.py`. No new packages are needed.

Key verified facts from live testing: bootstrap 1000 resamples completes in 0.36–0.41 seconds across n=50–500 (far under the 2s `ci_degraded` threshold). All numpy arrays must be converted to Python native types (`.tolist()`, `float()`) before FastAPI returns them. The `calibration_curve` sklearn function does NOT return n-per-bin counts — those require a separate `np.digitize` pass.

**Primary recommendation:** Implement the two-file service pattern (router + service module). Load all joined pairs in one query, apply per-researcher model selection in Python (not SQL), convert scores to 0–100 upfront, then compute all five stats from that single prepared dataset.

---

## Standard Stack

### Core
| Library | Version (verified) | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| scikit-learn | 1.8.0 (installed) | `roc_curve`, `roc_auc_score`, `precision_recall_curve`, `average_precision_score`, `calibration_curve` | Project already uses; functions verified working |
| numpy | 2.4.2 (installed) | Bootstrap resampling, binning, array ops | Already in requirements; fastest for vectorized ops |
| FastAPI | >=0.109.0 (requirements.txt) | HTTP router and dependency injection | Existing framework |
| SQLAlchemy | >=2.0.0 (requirements.txt) | ORM query for JOIN | Existing ORM |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy | 1.17.1 (installed) | Alternative bootstrap via `scipy.stats.bootstrap` | Optional — numpy manual bootstrap benchmarked as sufficient |
| time (stdlib) | — | Measuring bootstrap duration for `ci_degraded` flag | Always |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Numpy manual bootstrap | `scipy.stats.bootstrap` | scipy version is cleaner API but adds one import level; numpy is already in scope and equally fast |
| Custom calibration binning | `calibration_curve` only | sklearn's `calibration_curve` omits n-per-bin counts — must supplement with `np.digitize` pass for STATS-02 compliance |

**Installation:**
```bash
# No new packages needed — all dependencies already in api/requirements.txt
```

---

## Architecture Patterns

### Recommended Project Structure

```
api/
├── main.py                   # Add stats router import + include_router (6th router)
├── routers/
│   ├── stats.py              # NEW: HTTP layer only — one GET /api/stats endpoint
│   └── scores.py             # Reference pattern to replicate
└── services/
    ├── stats_service.py      # NEW: all computation logic
    └── pipeline_runner.py    # Reference pattern for service structure
```

### Pattern 1: Router delegates to service

The existing pattern in `scores.py` and `pipeline.py` — router performs DB injection, calls service, returns dict.

**What:** `stats.py` router receives the `db` session via `Depends(get_db)`, calls `compute_stats(db)` from `stats_service.py`, returns the result dict directly.
**When to use:** Always — matches all 5 existing routers.

```python
# api/routers/stats.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.stats_service import compute_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])

@router.get("")
def get_stats(db: Session = Depends(get_db)):
    return compute_stats(db)
```

### Pattern 2: Per-researcher model selection (D-01)

Load all scores from DB, then apply model selection in Python — not SQL — because the per-researcher priority rule is awkward to express in a single ORM query.

**What:** Fetch all `PersonArticleScore` rows joined to `Curation`. For each `person_id`, if any row has `model_type='feedbackIdentity'`, use only feedbackIdentity rows for that person; otherwise use identityOnly rows.

```python
# In stats_service.py — model selection step
from collections import defaultdict

# Step 1: determine best model per researcher
person_models = {}
for row in all_score_rows:
    pid = row.PersonArticleScore.person_id
    if pid not in person_models:
        person_models[pid] = row.PersonArticleScore.model_type
    elif row.PersonArticleScore.model_type == "feedbackIdentity":
        person_models[pid] = "feedbackIdentity"

# Step 2: filter to best model
selected = [r for r in all_score_rows
            if r.PersonArticleScore.model_type == person_models[r.PersonArticleScore.person_id]]
```

### Pattern 3: Score scale conversion (D-03)

Always multiply `calibrated_score * 100` immediately after loading from DB. All downstream computations use 0–100 scale. sklearn metrics need 0–1 input: divide back by 100 only for sklearn calls.

```python
# Conversion at data prep step
score_100 = float(row.PersonArticleScore.calibrated_score or 0) * 100
score_01 = score_100 / 100  # for roc_curve, precision_recall_curve, calibration_curve
```

### Pattern 4: Router registration in main.py

```python
# api/main.py — add to existing imports and include_router calls
from api.routers import institution, researchers, articles, pipeline, scores, stats

app.include_router(stats.router)
```

### Pattern 5: Numpy type conversion before return

All numpy scalars and arrays returned by sklearn are NOT JSON-serializable. Convert explicitly:

```python
# Correct
return {
    "auc": float(auc_val),           # np.float64 -> float
    "fpr": fpr.tolist(),             # np.ndarray -> list
    "ci_lower": float(ci[0]),
    "ci_upper": float(ci[1]),
    "n_per_bin": counts.tolist(),
}
```

### Anti-Patterns to Avoid

- **Using `calibration_curve` alone for n-per-bin counts:** sklearn's `calibration_curve` returns `fraction_of_positives` and `mean_predicted_value` arrays — it does NOT return bin counts. Must do a separate `np.digitize` pass to get n-per-bin.
- **Returning numpy types from FastAPI:** FastAPI's default JSON encoder does not serialize `np.float64`, `np.int64`, or `np.ndarray`. Will raise `TypeError`. Always call `.tolist()` on arrays and `float()`/`int()` on scalars.
- **Binning on 0–1 scale when spec says 0–100:** STATS-02 and STATS-04 require 10-point buckets covering 0–100. Binning on 0–1 scale (10 bins of 0.1) is numerically identical but the bucket labels and API contract must reflect 0–100.
- **Running sklearn metrics on single-class data:** `roc_auc_score` raises `ValueError` if only one class is present in `y_true`. Must check for single-class before calling any metric (STATS-06). Return structured error response instead.
- **SQL-level model selection:** Expressing the feedbackIdentity-over-identityOnly rule in SQL requires a correlated subquery per person_id that is harder to verify and test. Python-level filtering on the loaded result set is clearer and correct.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ROC curve computation | Custom FPR/TPR loop | `sklearn.metrics.roc_curve` | Handles ties, edge cases, `drop_intermediate` |
| AUC calculation | Trapezoid integral | `sklearn.metrics.roc_auc_score` | Numerically stable, handles edge cases |
| PR curve | Custom precision/recall loop | `sklearn.metrics.precision_recall_curve` | Correct monotonic handling |
| AUC-PR | Custom area under PR | `sklearn.metrics.average_precision_score` | Proper interpolation |
| Calibration fraction-positive | Manual per-bin label averaging | `sklearn.calibration.calibration_curve` | Well-tested; use `strategy='uniform'` for equal-width bins |
| Bootstrap resampling | Custom sampling loop | `numpy.random.default_rng().integers()` | Fast; no need for scipy.stats.bootstrap overhead |

**Key insight:** All five statistical computations have production-quality sklearn/numpy implementations already installed. The entire stats_service is "glue code" connecting the DB query output to library functions.

---

## Common Pitfalls

### Pitfall 1: calibration_curve drops empty bins silently
**What goes wrong:** `calibration_curve` with `strategy='uniform'` skips bins with no samples — returns fewer than `n_bins` values without warning. The returned arrays are not aligned to the 10 fixed buckets.
**Why it happens:** sklearn compresses empty bins by design.
**How to avoid:** Do NOT rely on `calibration_curve` for per-bucket data. Instead: use `np.digitize(scores_01, np.linspace(0, 1, 11))` to assign bucket indices, then compute fraction-positive and n-per-bin separately for each of the 10 fixed buckets. Use `calibration_curve` only to double-check or not at all.
**Warning signs:** Response has fewer than 10 calibration items; bucket indices don't align with 0–10–20 labels.

### Pitfall 2: Bootstrap with single-class resamples
**What goes wrong:** Bootstrap resamples are random — some resamples will contain only one class by chance, especially with small n. `roc_auc_score` on a single-class resample raises `ValueError`.
**Why it happens:** With n=50 and a 40/10 class split, probability of a resample having 0 minority class is non-negligible.
**How to avoid:** In the bootstrap loop, check `if len(np.unique(resample_labels)) < 2: continue`. Do not count the skipped resample — just skip it. The CI is computed from however many valid resamples complete.
**Warning signs:** Bootstrap raises ValueError mid-computation; CI array is empty.

### Pitfall 3: Score scale mismatch in disagreement ranking
**What goes wrong:** assertion_value is 100 (ACCEPTED) or 0 (REJECTED), but scores were not multiplied by 100 before the disagreement calculation — producing max disagreement of ~1.0 instead of ~100.
**Why it happens:** D-03 requires 0–100 everywhere, but it's easy to forget to apply the conversion before the disagreement step.
**How to avoid:** Enforce the 0–100 conversion immediately after loading from DB. Use a single `prepare_data()` function that converts and validates scale before passing to any computation function.
**Warning signs:** Top-10 disagreements all have `|score - assertion_value|` near 100 when most should be smaller; or values are < 1.0 when they should be 0–100.

### Pitfall 4: Non-JSON-serializable return from FastAPI
**What goes wrong:** FastAPI raises `ValueError: Object of type float64 is not JSON serializable` when returning numpy types.
**Why it happens:** `roc_auc_score` returns `np.float64`; `roc_curve` returns `np.ndarray`.
**How to avoid:** Convert all numpy types before returning from the service function. Use a helper: `float(x)` for scalars, `x.tolist()` for arrays, `int(x)` for integer counts.
**Warning signs:** 500 error on GET /api/stats; traceback mentions `json.dumps` and `float64`.

### Pitfall 5: n=0 or missing curation data crash
**What goes wrong:** If no `(score, assertion)` join pairs exist (e.g., pipeline hasn't run or no curations imported), `roc_curve` and `roc_auc_score` will crash with empty arrays.
**Why it happens:** The endpoint should return a structured "no data" response, but computation is invoked before the viability check.
**How to avoid:** Check `n == 0` first and return `{"viable": false, "below_n_threshold": true, "error": "No joined score+assertion pairs found"}` immediately — before any sklearn call. The viability check must be the very first thing after the DB query.
**Warning signs:** 500 errors when no curations exist; frontend shows error state instead of "run pipeline first" message.

### Pitfall 6: pr_baseline hardcoded as 0.5
**What goes wrong:** STATS-03 explicitly requires PR baseline anchored to actual positive rate (`n_accepted / n_total`), not 0.5.
**Why it happens:** 0.5 is a common default used in tutorials.
**How to avoid:** Compute `pr_baseline = labels_binary.sum() / len(labels_binary)` from actual data. Include in response as `pr_baseline`.
**Warning signs:** `pr_baseline` always equals 0.5 regardless of dataset.

---

## Code Examples

Verified patterns from live testing in project venv (Python 3.14, sklearn 1.8.0, numpy 2.4.2):

### DB Join Query (SQLAlchemy ORM)
```python
# Source: models.py + scores.py pattern — verified in codebase
from api.models import PersonArticleScore, Curation, Identity

# Load all score+curation join pairs
rows = (
    db.query(PersonArticleScore, Curation)
    .join(Curation, (PersonArticleScore.person_id == Curation.person_id) &
                    (PersonArticleScore.pmid == Curation.pmid))
    .all()
)
# Access: row.PersonArticleScore.calibrated_score, row.Curation.assertion
```

### Data Preparation (D-01 + D-03)
```python
import numpy as np

def prepare_joined_data(rows):
    """Apply per-researcher model selection and convert to 0-100 scale."""
    # Step 1: determine best model per researcher
    person_models = {}
    for row in rows:
        pid = row.PersonArticleScore.person_id
        mt = row.PersonArticleScore.model_type
        if pid not in person_models or mt == "feedbackIdentity":
            person_models[pid] = mt

    # Step 2: filter to best model per researcher
    selected = [r for r in rows
                if r.PersonArticleScore.model_type == person_models[r.PersonArticleScore.person_id]]

    # Step 3: convert to arrays (D-03: multiply by 100)
    scores_100 = np.array([float(r.PersonArticleScore.calibrated_score or 0) * 100 for r in selected])
    assertions = [r.Curation.assertion for r in selected]
    labels_binary = np.array([1 if a == "ACCEPTED" else 0 for a in assertions])
    scores_01 = scores_100 / 100  # For sklearn APIs

    return scores_100, scores_01, labels_binary, assertions, selected
```

### ROC Curve + Bootstrap AUC CI (STATS-01)
```python
# Source: verified in project venv — 0.36-0.41s for n=50-500
import time
from sklearn.metrics import roc_curve, roc_auc_score

def compute_roc(scores_01, labels_binary, n_resamples=1000):
    fpr, tpr, _ = roc_curve(labels_binary, scores_01)
    auc_val = roc_auc_score(labels_binary, scores_01)

    rng = np.random.default_rng()
    n = len(scores_01)
    boot_aucs = []
    t0 = time.perf_counter()

    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        s, l = scores_01[idx], labels_binary[idx]
        if len(np.unique(l)) < 2:
            continue
        boot_aucs.append(roc_auc_score(l, s))

    elapsed = time.perf_counter() - t0
    ci = np.percentile(boot_aucs, [2.5, 97.5]) if boot_aucs else np.array([0.0, 0.0])

    return {
        "fpr": fpr.tolist(),
        "tpr": tpr.tolist(),
        "auc": float(auc_val),
        "ci_lower": float(ci[0]),
        "ci_upper": float(ci[1]),
        "ci_degraded": elapsed > 2.0,   # D-05
    }
```

### Calibration Bins with n-per-bin (STATS-02)
```python
# Source: verified in project venv — np.digitize on 0.0-1.0 input
from sklearn.calibration import calibration_curve

def compute_calibration(scores_01, labels_binary):
    # n-per-bin via custom binning (calibration_curve does NOT provide this)
    cal_bins = np.linspace(0, 1, 11)  # 11 edges -> 10 bins
    bin_idx = np.clip(np.digitize(scores_01, cal_bins) - 1, 0, 9)
    n_per_bin = np.bincount(bin_idx, minlength=10).tolist()

    # Fraction positive per bin
    bins_out = []
    for b in range(10):
        mask = bin_idx == b
        bucket_label = f"{b*10}-{(b+1)*10}"
        if mask.sum() > 0:
            bins_out.append({
                "bucket": bucket_label,
                "mean_score": float(scores_01[mask].mean() * 100),   # back to 0-100 for display
                "fraction_positive": float(labels_binary[mask].mean()),
                "n": int(mask.sum()),
            })
        else:
            bins_out.append({
                "bucket": bucket_label,
                "mean_score": None,
                "fraction_positive": None,
                "n": 0,
            })
    return bins_out
```

### PR Curve (STATS-03)
```python
from sklearn.metrics import precision_recall_curve, average_precision_score

def compute_pr(scores_01, labels_binary):
    prec, rec, _ = precision_recall_curve(labels_binary, scores_01)
    auc_pr = average_precision_score(labels_binary, scores_01)
    pr_baseline = float(labels_binary.mean())   # actual positive rate — NOT 0.5
    return {
        "precision": prec.tolist(),
        "recall": rec.tolist(),
        "auc_pr": float(auc_pr),
        "pr_baseline": pr_baseline,
    }
```

### Score Distribution (STATS-04)
```python
def compute_distribution(scores_100, assertions):
    dist_bins = np.arange(0, 101, 10)   # 10 buckets: 0-10, 10-20, ..., 90-100
    bucket_idx = np.clip(np.digitize(scores_100, dist_bins) - 1, 0, 9)
    accepted_mask = np.array([a == "ACCEPTED" for a in assertions])
    rejected_mask = ~accepted_mask

    buckets = []
    for b in range(10):
        mask = bucket_idx == b
        buckets.append({
            "bucket": f"{b*10}-{(b+1)*10}",
            "accepted": int((mask & accepted_mask).sum()),
            "rejected": int((mask & rejected_mask).sum()),
        })
    return buckets
```

### Top-10 Disagreements (STATS-05)
```python
def compute_disagreements(scores_100, assertions, rows, db):
    """rows must contain PersonArticleScore rows with person_id and pmid."""
    assertion_values = np.array([100.0 if a == "ACCEPTED" else 0.0 for a in assertions])
    disagreements = np.abs(scores_100 - assertion_values)

    # Top 10 by disagreement magnitude
    top_indices = np.argsort(disagreements)[::-1][:10]

    # Need person name — join to Identity
    person_ids = [rows[i].PersonArticleScore.person_id for i in top_indices]
    identities = {
        ident.person_id: ident
        for ident in db.query(Identity).filter(Identity.person_id.in_(person_ids)).all()
    }

    result = []
    for i in top_indices:
        row = rows[i]
        pid = row.PersonArticleScore.person_id
        ident = identities.get(pid)
        result.append({
            "person_id": pid,
            "pmid": row.PersonArticleScore.pmid,
            "score": float(scores_100[i]),
            "assertion": assertions[i],
            "disagreement": float(disagreements[i]),
            "first_name": ident.first_name if ident else None,
            "last_name": ident.last_name if ident else None,
        })
    return result
```

### Viability Check (STATS-06)
```python
def check_viability(n, assertions):
    """Returns (is_blocked, response_dict).
    is_blocked=True means caller should return response_dict immediately.
    """
    if n == 0:
        return True, {
            "viable": False,
            "below_n_threshold": True,
            "error": "no_data",
            "message": "No joined (score, assertion) pairs found. Run the pipeline and import curations first.",
        }
    unique_labels = set(assertions)
    if len(unique_labels) < 2:
        return True, {
            "viable": False,
            "below_n_threshold": n < 50,
            "error": "single_class",
            "message": f"All assertions are the same label: {list(unique_labels)[0]}. Cannot compute ROC or PR curves.",
        }
    return False, {
        "viable": n >= 50,
        "below_n_threshold": n < 50,
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| scipy.stats.bootstrap (2-line) | numpy manual bootstrap loop | — | Manual loop is faster and avoids scipy overhead; equal accuracy |
| `calibration_curve` alone | `calibration_curve` + `np.digitize` | sklearn never returned counts | Must use both for STATS-02 compliance |

**Deprecated/outdated:**
- PR baseline of 0.5: common in literature but wrong for imbalanced datasets; STATS-03 mandates actual positive rate.

---

## Open Questions

1. **What happens when `calibrated_score` is NULL in DB?**
   - What we know: `PersonArticleScore.calibrated_score` is a Float column with no `NOT NULL` constraint; `pipeline_runner.py` sets it via `float(row.get("calibrated_score", 0))` which can produce 0.0 but not NULL.
   - What's unclear: Whether any import path or partial-run could leave calibrated_score as NULL.
   - Recommendation: Guard with `float(row.calibrated_score or 0)` in data prep. If score is 0.0, it participates in stats as a valid low score.

2. **Score at exactly 100: which bucket?**
   - What we know: `np.digitize([100], np.arange(0, 101, 10))` returns index 10 (out of range for 0-9 buckets). The `np.clip(..., 0, 9)` guard assigns it to bucket 9 (90-100).
   - What's unclear: Whether this is the intended behavior vs. a separate 100-exactly bucket.
   - Recommendation: Clip to bucket 9 (90–100) is correct — 100 is an inclusive upper bound of the last bucket. Document this clearly.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| scikit-learn | STATS-01 through STATS-03 | ✓ | 1.8.0 (venv) | — |
| numpy | All STATS requirements | ✓ | 2.4.2 (venv) | — |
| scipy | Optional bootstrap alternative | ✓ | 1.17.1 (venv) | numpy manual bootstrap (already validated) |
| FastAPI | Router layer | ✓ (api/requirements.txt) | >=0.109.0 | — |
| SQLAlchemy | DB queries | ✓ (api/requirements.txt) | >=2.0.0 | — |
| MariaDB / Docker | Integration tests | ✓ (docker-compose.yml) | MariaDB 11 | — |

**Note:** The `venv/` at project root contains the Streamlit dependencies (Python 3.14). The API runs in a Docker container using `api/requirements.txt` and Python 3.12. The scikit-learn/numpy/scipy versions available in the API container are whatever `pip install` resolves against the pinned requirements — the versions above reflect what's installed in the local venv (close approximation).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none — no pytest.ini found |
| Quick run command | `venv/bin/python -m pytest tests/test_stats_service.py -x` |
| Full suite command | `venv/bin/python -m pytest tests/ --ignore=tests/test_scoring.py` |

**Pre-existing issue:** `tests/test_scoring.py` fails to collect due to `ImportError: cannot import name 'load_model' from 'core.scoring'`. The function was removed or renamed. This is out of scope for Phase 1 but the test file must be ignored in test runs to avoid breaking the suite.

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATS-01 | ROC curve points + AUC + 95% CI returned | unit | `pytest tests/test_stats_service.py::test_roc_output -x` | ❌ Wave 0 |
| STATS-01 | Bootstrap CI is correct width (2.5th–97.5th percentile) | unit | `pytest tests/test_stats_service.py::test_bootstrap_ci -x` | ❌ Wave 0 |
| STATS-01 | `ci_degraded` flag triggers when bootstrap exceeds 2s | unit (mock time) | `pytest tests/test_stats_service.py::test_ci_degraded_flag -x` | ❌ Wave 0 |
| STATS-02 | Calibration returns exactly 10 bins | unit | `pytest tests/test_stats_service.py::test_calibration_bins -x` | ❌ Wave 0 |
| STATS-02 | n-per-bin counts sum to n | unit | `pytest tests/test_stats_service.py::test_calibration_n_per_bin -x` | ❌ Wave 0 |
| STATS-02 | `calibration_viable: false` when n < 50 | unit | `pytest tests/test_stats_service.py::test_calibration_viable_flag -x` | ❌ Wave 0 |
| STATS-03 | PR baseline equals actual positive rate (not 0.5) | unit | `pytest tests/test_stats_service.py::test_pr_baseline -x` | ❌ Wave 0 |
| STATS-04 | Distribution covers all 10 buckets (0–100) | unit | `pytest tests/test_stats_service.py::test_distribution_buckets -x` | ❌ Wave 0 |
| STATS-04 | ACCEPTED/REJECTED counts sum to n | unit | `pytest tests/test_stats_service.py::test_distribution_counts -x` | ❌ Wave 0 |
| STATS-05 | Top-10 ranked by descending disagreement | unit | `pytest tests/test_stats_service.py::test_disagreements_order -x` | ❌ Wave 0 |
| STATS-05 | Disagreement = |score - assertion_value| on 0-100 scale | unit | `pytest tests/test_stats_service.py::test_disagreement_calculation -x` | ❌ Wave 0 |
| STATS-06 | n=0 returns structured error, not crash | unit | `pytest tests/test_stats_service.py::test_no_data_error -x` | ❌ Wave 0 |
| STATS-06 | Single-class returns structured error | unit | `pytest tests/test_stats_service.py::test_single_class_error -x` | ❌ Wave 0 |
| STATS-06 | n=49 returns `viable: false, below_n_threshold: true` | unit | `pytest tests/test_stats_service.py::test_below_threshold_flags -x` | ❌ Wave 0 |
| STATS-06 | n=50 returns `viable: true` | unit | `pytest tests/test_stats_service.py::test_at_threshold_viable -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `venv/bin/python -m pytest tests/test_stats_service.py -x`
- **Per wave merge:** `venv/bin/python -m pytest tests/ --ignore=tests/test_scoring.py`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_stats_service.py` — covers all STATS-01 through STATS-06 requirements above (pure unit tests, no DB required — pass mock data directly to service functions)

*(All tests should be pure unit tests operating on numpy arrays / Python lists — no DB or Docker required for the test suite.)*

---

## Sources

### Primary (HIGH confidence)
- Live code inspection: `api/routers/scores.py`, `api/main.py`, `api/models.py`, `api/schema.sql`, `api/database.py`, `api/services/pipeline_runner.py`
- Live benchmark: numpy bootstrap 1000 resamples, n=50/100/200/500 — measured 0.36–0.41s (project venv, Python 3.14, M-series Mac)
- Live function signatures: `roc_curve`, `precision_recall_curve`, `roc_auc_score`, `average_precision_score`, `calibration_curve` — verified via `inspect.signature()` on installed sklearn 1.8.0
- Live smoke tests: all 5 stat computations verified end-to-end with synthetic data; JSON serialization pitfall confirmed

### Secondary (MEDIUM confidence)
- `api/requirements.txt` — confirmed: sklearn, numpy, scipy, fastapi, sqlalchemy all already declared
- `docker-compose.yml` — confirmed API runs on port 8090, MariaDB on 3306

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries installed and function signatures verified live
- Architecture: HIGH — directly derived from 5 existing routers in codebase
- Pitfalls: HIGH — each pitfall confirmed by live execution (not theoretical)
- Test plan: HIGH — test functions map 1:1 to requirement success criteria

**Research date:** 2026-04-04
**Valid until:** 2026-07-04 (scikit-learn 1.8.0 API is stable; numpy 2.x has stable array API)

---

## Project Constraints (from CLAUDE.md)

Directives the planner must verify compliance with:

| Directive | Source | Impact on Phase 1 |
|-----------|--------|-------------------|
| Never hardcode credentials or `localhost` for DB connections | CLAUDE.md (global) | `api/database.py` already uses `DATABASE_URL` env var — no new DB connection code needed |
| XGBoost 3.2.0 exact version | CLAUDE.md (project) | Not touched in this phase — stats endpoint doesn't invoke scoring pipeline |
| All routers return plain dicts (not Pydantic models) | CONTEXT.md code_context | Confirmed by scores.py pattern; stats router must do the same |
| SQLAlchemy ORM queries with `.join()` and `.filter()` — no raw SQL | CONTEXT.md code_context | JOIN pattern verified against PersonArticleScore + Curation models |
| Router registered in `api/main.py` following same pattern | CONTEXT.md D-09 | Import + `include_router` call |
| `scikit-learn`, `scipy`, `numpy` already in `api/requirements.txt` | CONTEXT.md code_context | Confirmed — no new dependencies needed |
