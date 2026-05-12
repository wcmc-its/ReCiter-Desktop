"""Stats computation service for /api/stats endpoint.

All pure computation functions accept numpy arrays/Python lists directly
(testable without DB). The orchestrator compute_stats(db) handles the
DB query and delegates to these functions.
"""
import time
import numpy as np
from sklearn.metrics import (
    roc_curve,
    roc_auc_score,
    precision_recall_curve,
    average_precision_score,
)
from sqlalchemy.orm import Session

from api.models import PersonArticleScore, Curation, Identity


# ---------------------------------------------------------------------------
# Task 1: Viability check and data preparation
# ---------------------------------------------------------------------------

def check_viability(n: int, assertions: list) -> tuple:
    """Return (is_blocked, response_dict).

    is_blocked=True means the caller should return response_dict immediately
    without proceeding to statistical computation.

    Implements STATS-06 and D-06.
    """
    if n == 0:
        return True, {
            "viable": False,
            "below_n_threshold": True,
            "error": "no_data",
            "message": (
                "No joined (score, assertion) pairs found. "
                "Run the pipeline and import curations first."
            ),
        }

    unique_labels = set(assertions)
    if len(unique_labels) < 2:
        label_name = list(unique_labels)[0]
        return True, {
            "viable": False,
            "below_n_threshold": n < 50,
            "error": "single_class",
            "message": (
                f"All assertions are the same label: {label_name}. "
                "Cannot compute ROC or PR curves."
            ),
        }

    return False, {
        "viable": n >= 50,
        "below_n_threshold": n < 50,
    }


def prepare_joined_data(rows) -> tuple:
    """Apply per-researcher model selection and convert to 0-100 scale.

    Per D-01: For each person_id, if any row has model_type='feedbackIdentity',
    use only feedbackIdentity rows for that person; otherwise use identityOnly.

    Per D-03: Multiply calibrated_score * 100 to get 0-100 scale.

    Args:
        rows: Result of SQLAlchemy JOIN query — list of tuples with
              .PersonArticleScore and .Curation attributes.

    Returns:
        (scores_100, scores_01, labels_binary, assertions, selected_rows, person_ids, pmids)
        - scores_100: numpy array on 0-100 scale
        - scores_01: scores_100 / 100 for sklearn APIs
        - labels_binary: numpy array of 1 (ACCEPTED) / 0 (REJECTED)
        - assertions: list of "ACCEPTED" / "REJECTED" strings
        - selected_rows: filtered row list (for disagreements)
        - person_ids: list of person_id strings (parallel to scores)
        - pmids: list of pmid strings (parallel to scores)
    """
    if not rows:
        empty = np.array([], dtype=float)
        return empty, empty, np.array([], dtype=int), [], [], [], []

    # Step 1: determine best model per researcher (feedbackIdentity preferred)
    person_models: dict = {}
    for row in rows:
        pid = row.PersonArticleScore.person_id
        mt = row.PersonArticleScore.model_type
        if pid not in person_models or mt == "feedbackIdentity":
            person_models[pid] = mt

    # Step 2: filter to best model per researcher
    selected = [
        r for r in rows
        if r.PersonArticleScore.model_type == person_models[r.PersonArticleScore.person_id]
    ]

    # Step 3: convert to arrays (D-03: multiply by 100)
    scores_100 = np.array(
        [float(r.PersonArticleScore.calibrated_score or 0) * 100 for r in selected]
    )
    assertions = [r.Curation.assertion for r in selected]
    labels_binary = np.array([1 if a == "ACCEPTED" else 0 for a in assertions])
    scores_01 = scores_100 / 100  # for sklearn APIs
    person_ids = [r.PersonArticleScore.person_id for r in selected]
    pmids = [r.PersonArticleScore.pmid for r in selected]

    return scores_100, scores_01, labels_binary, assertions, selected, person_ids, pmids


# ---------------------------------------------------------------------------
# Task 2: Statistical computation functions
# ---------------------------------------------------------------------------

def compute_roc(
    scores_01: np.ndarray,
    labels_binary: np.ndarray,
    n_resamples: int = 1000,
) -> dict:
    """Compute ROC curve, AUC, and bootstrap 95% CI.

    Per STATS-01, D-04, D-05:
    - Always uses 1000 resamples (D-04)
    - Sets ci_degraded=True if bootstrap exceeds 2 seconds (D-05)
    - Skips single-class resamples to avoid ValueError (Pitfall 2)
    """
    fpr, tpr, _ = roc_curve(labels_binary, scores_01)
    auc_val = roc_auc_score(labels_binary, scores_01)

    rng = np.random.default_rng()
    n = len(scores_01)
    boot_aucs = []
    t0 = time.perf_counter()

    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        s = scores_01[idx]
        lbl = labels_binary[idx]
        if len(np.unique(lbl)) < 2:
            continue
        boot_aucs.append(roc_auc_score(lbl, s))

    elapsed = time.perf_counter() - t0
    ci = np.percentile(boot_aucs, [2.5, 97.5]) if boot_aucs else np.array([0.0, 0.0])
    ci_degraded = bool(elapsed > 2.0)

    return {
        "fpr": fpr.tolist(),
        "tpr": tpr.tolist(),
        "auc": float(auc_val),
        "ci_lower": float(ci[0]),
        "ci_upper": float(ci[1]),
        "ci_degraded": ci_degraded,
    }


def compute_calibration(scores_01: np.ndarray, labels_binary: np.ndarray) -> list:
    """Compute calibration bins (reliability diagram data).

    Per STATS-02: always returns exactly 10 uniform bins on 0-100 scale.
    Does NOT rely on sklearn's calibration_curve alone — that function drops
    empty bins. Uses np.digitize for per-bin counts (Pitfall 1).
    """
    cal_edges = np.linspace(0, 1, 11)  # 11 edges = 10 bins
    bin_idx = np.clip(np.digitize(scores_01, cal_edges) - 1, 0, 9)

    bins_out = []
    for b in range(10):
        mask = bin_idx == b
        n = int(mask.sum())
        bucket_label = f"{b * 10}-{(b + 1) * 10}"
        if n > 0:
            mean_score = float(scores_01[mask].mean() * 100)  # back to 0-100
            fraction_positive = float(labels_binary[mask].mean())
        else:
            mean_score = None
            fraction_positive = None
        bins_out.append({
            "bucket": bucket_label,
            "mean_score": mean_score,
            "fraction_positive": fraction_positive,
            "n": n,
        })

    return bins_out


def compute_pr(scores_01: np.ndarray, labels_binary: np.ndarray) -> dict:
    """Compute Precision-Recall curve, AUC-PR, and prevalence-anchored baseline.

    Per STATS-03: pr_baseline is the actual positive rate (NOT 0.5).
    """
    prec, rec, _ = precision_recall_curve(labels_binary, scores_01)
    auc_pr = average_precision_score(labels_binary, scores_01)
    pr_baseline = float(labels_binary.mean())  # actual positive rate

    return {
        "precision": prec.tolist(),
        "recall": rec.tolist(),
        "auc_pr": float(auc_pr),
        "pr_baseline": pr_baseline,
    }


def compute_distribution(scores_100: np.ndarray, assertions: list) -> list:
    """Compute score distribution binned by assertion outcome.

    Per STATS-04: 10-point buckets on 0-100 scale with ACCEPTED/REJECTED counts.
    Score exactly at 100 is clipped into the 90-100 bucket.
    """
    dist_edges = np.arange(0, 101, 10)  # 11 edges = 10 buckets
    bucket_idx = np.clip(np.digitize(scores_100, dist_edges) - 1, 0, 9)
    accepted_mask = np.array([a == "ACCEPTED" for a in assertions])
    rejected_mask = ~accepted_mask

    buckets = []
    for b in range(10):
        mask = bucket_idx == b
        buckets.append({
            "bucket": f"{b * 10}-{(b + 1) * 10}",
            "accepted": int((mask & accepted_mask).sum()),
            "rejected": int((mask & rejected_mask).sum()),
        })

    return buckets


def compute_disagreements(
    scores_100: np.ndarray,
    assertions: list,
    person_ids: list,
    pmids: list,
    names: dict | None = None,
    gap_threshold: float = 50.0,
) -> list:
    """Compute strongest disagreements between scores and assertions.

    Per STATS-05: assertion_value is 100 for ACCEPTED, 0 for REJECTED.
    Disagreement = |score - assertion_value| on 0-100 scale.

    Returns all pairs with disagreement >= gap_threshold, sorted descending.

    Args:
        scores_100: Scores on 0-100 scale.
        assertions: List of "ACCEPTED"/"REJECTED" strings (parallel to scores).
        person_ids: List of person_id strings (parallel to scores).
        pmids: List of pmid strings (parallel to scores).
        names: Optional dict of {person_id: {"first_name": str, "last_name": str}}.
               If None, first_name and last_name in results are None.
        gap_threshold: Minimum disagreement to include (default 50).
    """
    assertion_values = np.array([100.0 if a == "ACCEPTED" else 0.0 for a in assertions])
    disagreements = np.abs(scores_100 - assertion_values)
    indices = np.argsort(disagreements)[::-1]
    indices = [i for i in indices if disagreements[i] >= gap_threshold]

    result = []
    for i in indices:
        pid = person_ids[i]
        result.append({
            "person_id": pid,
            "pmid": pmids[i],
            "score": float(scores_100[i]),
            "assertion": assertions[i],
            "disagreement": float(disagreements[i]),
            "first_name": names.get(pid, {}).get("first_name") if names else None,
            "last_name": names.get(pid, {}).get("last_name") if names else None,
        })

    return result


def compute_stats(db: Session) -> dict:
    """Orchestrator: query DB, prepare data, compute all five stats.

    Called by the GET /api/stats router. Handles per-researcher model selection
    (D-01), score conversion (D-03), viability check (STATS-06), and delegates
    to all five stat computation functions.
    """
    # Step 1: Load all score+curation join pairs
    rows = (
        db.query(PersonArticleScore, Curation)
        .join(
            Curation,
            (PersonArticleScore.person_id == Curation.person_id)
            & (PersonArticleScore.pmid == Curation.pmid),
        )
        .all()
    )

    # Step 2: Apply per-researcher model selection and scale conversion
    scores_100, scores_01, labels_binary, assertions, selected_rows, person_ids, pmids = (
        prepare_joined_data(rows)
    )

    # Step 3: Viability check — must come before any sklearn call
    is_blocked, viability_flags = check_viability(len(scores_01), assertions)
    if is_blocked:
        return viability_flags

    # Step 4: Compute all five stats
    roc = compute_roc(scores_01, labels_binary)
    calibration = compute_calibration(scores_01, labels_binary)
    pr = compute_pr(scores_01, labels_binary)
    distribution = compute_distribution(scores_100, assertions)

    # Step 5: Disagreements — look up names for all qualifying person_ids
    assertion_values_arr = np.array(
        [100.0 if a == "ACCEPTED" else 0.0 for a in assertions]
    )
    disagreements_arr = np.abs(scores_100 - assertion_values_arr)
    qualifying_indices = [i for i in range(len(disagreements_arr)) if disagreements_arr[i] >= 50.0]
    top_person_ids = list({person_ids[i] for i in qualifying_indices})

    identity_rows = (
        db.query(Identity)
        .filter(Identity.person_id.in_(top_person_ids))
        .all()
    )
    names_dict = {
        ident.person_id: {
            "first_name": ident.first_name,
            "last_name": ident.last_name,
        }
        for ident in identity_rows
    }

    disagreements = compute_disagreements(
        scores_100, assertions, person_ids, pmids, names=names_dict
    )

    # Step 6: Merge viability flags with results
    return {
        **viability_flags,
        "n": len(scores_01),
        "roc": roc,
        "calibration": calibration,
        "calibration_viable": len(scores_01) >= 50,
        "pr": pr,
        "distribution": distribution,
        "disagreements": disagreements,
    }
