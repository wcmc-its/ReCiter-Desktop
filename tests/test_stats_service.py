"""Unit tests for the stats service (TDD RED phase).

All tests import from api.services.stats_service and use synthetic numpy arrays.
No database or Docker required. Tests will fail with ImportError until Plan 02
implements the service.

Coverage: STATS-01 (ROC + bootstrap CI), STATS-02 (calibration bins),
STATS-03 (PR curve + baseline), STATS-04 (score distribution),
STATS-05 (disagreements), STATS-06 (viability flags).
"""

import numpy as np
import pytest
from api.services.stats_service import (
    compute_roc,
    compute_calibration,
    compute_pr,
    compute_distribution,
    compute_disagreements,
    check_viability,
)

# ---------------------------------------------------------------------------
# Module-level synthetic test data
# ---------------------------------------------------------------------------

# 10 scores on 0-1 scale (functions receive 0-1 scale for sklearn-compatible inputs)
SCORES_01 = np.array([0.95, 0.88, 0.72, 0.65, 0.45, 0.30, 0.20, 0.15, 0.10, 0.05])

# Same scores on 0-100 scale (for distribution and disagreements)
SCORES_100 = SCORES_01 * 100

# Binary labels: 4 positives (ACCEPTED), 6 negatives (REJECTED)
LABELS = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])

# Assertion strings corresponding to LABELS
ASSERTIONS = [
    "ACCEPTED", "ACCEPTED", "ACCEPTED", "ACCEPTED",
    "REJECTED", "REJECTED", "REJECTED", "REJECTED", "REJECTED", "REJECTED",
]

# Larger dataset for n>=50 viability tests
_rng = np.random.default_rng(42)
SCORES_01_LARGE = _rng.random(50)
LABELS_LARGE = np.array([1] * 25 + [0] * 25)

# ---------------------------------------------------------------------------
# STATS-01: ROC curve + AUC + bootstrap CI
# ---------------------------------------------------------------------------


def test_roc_output():
    """STATS-01: compute_roc returns dict with required keys and valid AUC."""
    result = compute_roc(SCORES_01, LABELS)
    assert isinstance(result, dict)
    assert "fpr" in result
    assert "tpr" in result
    assert "auc" in result
    assert "ci_lower" in result
    assert "ci_upper" in result
    assert "ci_degraded" in result
    assert isinstance(result["fpr"], list)
    assert isinstance(result["tpr"], list)
    assert 0 < result["auc"] <= 1.0
    assert result["ci_lower"] <= result["auc"] <= result["ci_upper"]


def test_bootstrap_ci():
    """STATS-01: Bootstrap CI is in [0, 1] with nonzero width."""
    result = compute_roc(SCORES_01, LABELS, n_resamples=1000)
    assert result["ci_lower"] >= 0.0
    assert result["ci_upper"] <= 1.0
    assert result["ci_upper"] - result["ci_lower"] > 0


def test_ci_degraded_flag():
    """STATS-01: ci_degraded is a bool; False for small fast dataset."""
    result = compute_roc(SCORES_01, LABELS, n_resamples=1000)
    assert isinstance(result["ci_degraded"], bool)
    # 10 samples + 1000 resamples should complete in well under 2 seconds
    assert result["ci_degraded"] is False


# ---------------------------------------------------------------------------
# STATS-02: Calibration bins (10 fixed buckets, n-per-bin counts)
# ---------------------------------------------------------------------------


def test_calibration_bins():
    """STATS-02: compute_calibration returns exactly 10 bins with required keys."""
    result = compute_calibration(SCORES_01, LABELS)
    assert isinstance(result, list)
    assert len(result) == 10
    expected_buckets = [
        "0-10", "10-20", "20-30", "30-40", "40-50",
        "50-60", "60-70", "70-80", "80-90", "90-100",
    ]
    for item, expected_bucket in zip(result, expected_buckets):
        assert isinstance(item, dict)
        assert "bucket" in item
        assert "mean_score" in item
        assert "fraction_positive" in item
        assert "n" in item
        assert item["bucket"] == expected_bucket


def test_calibration_n_per_bin():
    """STATS-02: n-per-bin counts sum to total n."""
    result = compute_calibration(SCORES_01, LABELS)
    assert sum(b["n"] for b in result) == len(SCORES_01)


def test_calibration_viable_flag():
    """STATS-02: check_viability returns viable=False and below_n_threshold=True for n<50."""
    # n=5, two classes but below threshold
    is_blocked, response = check_viability(5, ["ACCEPTED", "REJECTED", "ACCEPTED", "REJECTED", "ACCEPTED"])
    assert response.get("viable") is False
    assert response.get("below_n_threshold") is True
    # n=0 returns error
    is_blocked_empty, response_empty = check_viability(0, [])
    assert response_empty.get("error") == "no_data"


# ---------------------------------------------------------------------------
# STATS-03: Precision-Recall curve + prevalence-anchored baseline
# ---------------------------------------------------------------------------


def test_pr_baseline():
    """STATS-03: PR baseline equals actual positive rate (not 0.5)."""
    result = compute_pr(SCORES_01, LABELS)
    assert isinstance(result, dict)
    assert "precision" in result
    assert "recall" in result
    assert "auc_pr" in result
    assert "pr_baseline" in result
    # 4 positives out of 10 total -> baseline = 0.4, NOT 0.5
    assert result["pr_baseline"] == pytest.approx(4 / 10)
    assert 0 < result["auc_pr"] <= 1.0


# ---------------------------------------------------------------------------
# STATS-04: Score distribution histogram (ACCEPTED/REJECTED per bucket)
# ---------------------------------------------------------------------------


def test_distribution_buckets():
    """STATS-04: compute_distribution returns 10 buckets with required keys."""
    result = compute_distribution(SCORES_100, ASSERTIONS)
    assert isinstance(result, list)
    assert len(result) == 10
    expected_buckets = [
        "0-10", "10-20", "20-30", "30-40", "40-50",
        "50-60", "60-70", "70-80", "80-90", "90-100",
    ]
    for item, expected_bucket in zip(result, expected_buckets):
        assert isinstance(item, dict)
        assert "bucket" in item
        assert "accepted" in item
        assert "rejected" in item
        assert item["bucket"] == expected_bucket


def test_distribution_counts():
    """STATS-04: accepted + rejected counts across all buckets sum to n."""
    result = compute_distribution(SCORES_100, ASSERTIONS)
    total = sum(b["accepted"] + b["rejected"] for b in result)
    assert total == len(SCORES_100)


# ---------------------------------------------------------------------------
# STATS-05: Top-10 strongest disagreements
# ---------------------------------------------------------------------------


def test_disagreements_order():
    """STATS-05: compute_disagreements returns descending order by disagreement."""
    person_ids = ["p1"] * 10
    pmids = [f"pmid{i}" for i in range(10)]
    result = compute_disagreements(
        SCORES_100, ASSERTIONS, person_ids=person_ids, pmids=pmids, names=None
    )
    assert isinstance(result, list)
    assert len(result) == 10
    # Verify descending order
    assert result[0]["disagreement"] >= result[1]["disagreement"]
    # Verify required keys on each item
    required_keys = {"person_id", "pmid", "score", "assertion", "disagreement"}
    for item in result:
        assert required_keys.issubset(item.keys())


def test_disagreement_calculation():
    """STATS-05: Disagreement = |score - assertion_value| on 0-100 scale."""
    # score=95 (ACCEPTED=100) -> disagreement = |95 - 100| = 5
    # score=5  (REJECTED=0)   -> disagreement = |5  - 0|   = 5
    # But for known max disagreement cases:
    # score=95, assertion=REJECTED (0) -> |95 - 0| = 95.0
    # score=5,  assertion=ACCEPTED (100) -> |5 - 100| = 95.0
    two_scores = np.array([95.0, 5.0])
    two_assertions = ["REJECTED", "ACCEPTED"]
    two_person_ids = ["p1", "p2"]
    two_pmids = ["pmid0", "pmid1"]
    result = compute_disagreements(
        two_scores, two_assertions, person_ids=two_person_ids, pmids=two_pmids, names=None
    )
    # Both items should have disagreement of 95.0
    disagreements = {item["pmid"]: item["disagreement"] for item in result}
    assert disagreements["pmid0"] == pytest.approx(95.0)
    assert disagreements["pmid1"] == pytest.approx(95.0)


# ---------------------------------------------------------------------------
# STATS-06: Viability flags (no_data, single_class, below_n_threshold)
# ---------------------------------------------------------------------------


def test_no_data_error():
    """STATS-06: n=0 returns is_blocked=True with viable=False, error=no_data."""
    is_blocked, response = check_viability(0, [])
    assert is_blocked is True
    assert response.get("viable") is False
    assert response.get("error") == "no_data"
    assert response.get("below_n_threshold") is True


def test_single_class_error():
    """STATS-06: All same assertion returns is_blocked=True with error=single_class."""
    is_blocked, response = check_viability(10, ["ACCEPTED"] * 10)
    assert is_blocked is True
    assert response.get("viable") is False
    assert response.get("error") == "single_class"


def test_below_threshold_flags():
    """STATS-06: n=49 returns is_blocked=False, viable=False, below_n_threshold=True."""
    assertions = ["ACCEPTED"] * 25 + ["REJECTED"] * 24
    is_blocked, response = check_viability(49, assertions)
    assert is_blocked is False
    assert response.get("viable") is False
    assert response.get("below_n_threshold") is True


def test_at_threshold_viable():
    """STATS-06: n=50 returns is_blocked=False, viable=True, below_n_threshold=False."""
    assertions = ["ACCEPTED"] * 25 + ["REJECTED"] * 25
    is_blocked, response = check_viability(50, assertions)
    assert is_blocked is False
    assert response.get("viable") is True
    assert response.get("below_n_threshold") is False
