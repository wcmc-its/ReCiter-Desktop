"""
Unit tests for api/services/stats_service.py

All tests are pure unit tests — no DB or Docker required.
Data is passed directly as numpy arrays / Python lists.
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# STATS-06: Viability checks
# ---------------------------------------------------------------------------

def test_no_data_error():
    """check_viability with n=0 returns blocked response with no_data error."""
    from api.services.stats_service import check_viability

    is_blocked, response = check_viability(0, [])

    assert is_blocked is True
    assert response["viable"] is False
    assert response["below_n_threshold"] is True
    assert response["error"] == "no_data"
    assert "message" in response
    assert len(response["message"]) > 0


def test_single_class_error():
    """check_viability with single-class assertions returns blocked response."""
    from api.services.stats_service import check_viability

    assertions = ["ACCEPTED"] * 10
    is_blocked, response = check_viability(10, assertions)

    assert is_blocked is True
    assert response["viable"] is False
    assert response["error"] == "single_class"
    assert "message" in response
    assert "ACCEPTED" in response["message"]


def test_single_class_rejected():
    """check_viability with all REJECTED also returns single_class error."""
    from api.services.stats_service import check_viability

    assertions = ["REJECTED"] * 5
    is_blocked, response = check_viability(5, assertions)

    assert is_blocked is True
    assert response["error"] == "single_class"
    assert "REJECTED" in response["message"]


def test_below_threshold_flags():
    """check_viability with n=49 (two-class) returns viable=False, below_n_threshold=True."""
    from api.services.stats_service import check_viability

    assertions = ["ACCEPTED"] * 25 + ["REJECTED"] * 24
    is_blocked, response = check_viability(49, assertions)

    assert is_blocked is False
    assert response["viable"] is False
    assert response["below_n_threshold"] is True


def test_at_threshold_viable():
    """check_viability with n=50 (two-class) returns viable=True."""
    from api.services.stats_service import check_viability

    assertions = ["ACCEPTED"] * 25 + ["REJECTED"] * 25
    is_blocked, response = check_viability(50, assertions)

    assert is_blocked is False
    assert response["viable"] is True
    assert response["below_n_threshold"] is False


# ---------------------------------------------------------------------------
# STATS-01: ROC Curve + Bootstrap AUC CI
# ---------------------------------------------------------------------------

def _make_test_data(n_accepted=30, n_rejected=20, seed=42):
    """Generate reproducible synthetic score + label arrays."""
    rng = np.random.default_rng(seed)
    accepted_scores = rng.uniform(0.6, 1.0, n_accepted)
    rejected_scores = rng.uniform(0.0, 0.5, n_rejected)
    scores_01 = np.concatenate([accepted_scores, rejected_scores])
    labels = np.array([1] * n_accepted + [0] * n_rejected)
    return scores_01, labels


def test_roc_output():
    """compute_roc returns dict with expected keys and valid value ranges."""
    from api.services.stats_service import compute_roc

    scores_01, labels = _make_test_data()
    result = compute_roc(scores_01, labels)

    assert isinstance(result, dict)
    assert "fpr" in result
    assert "tpr" in result
    assert "auc" in result
    assert "ci_lower" in result
    assert "ci_upper" in result
    assert "ci_degraded" in result

    # Lists (JSON-serializable)
    assert isinstance(result["fpr"], list)
    assert isinstance(result["tpr"], list)

    # AUC is a float between 0 and 1
    assert isinstance(result["auc"], float)
    assert 0.0 <= result["auc"] <= 1.0

    # CI bounds are floats between 0 and 1
    assert isinstance(result["ci_lower"], float)
    assert isinstance(result["ci_upper"], float)
    assert 0.0 <= result["ci_lower"] <= 1.0
    assert 0.0 <= result["ci_upper"] <= 1.0

    # ci_degraded is a bool
    assert isinstance(result["ci_degraded"], bool)


def test_bootstrap_ci():
    """Bootstrap CI bounds are ordered and contain the point AUC estimate."""
    from api.services.stats_service import compute_roc

    scores_01, labels = _make_test_data()
    result = compute_roc(scores_01, labels)

    assert result["ci_lower"] <= result["auc"]
    assert result["auc"] <= result["ci_upper"]
    assert result["ci_lower"] <= result["ci_upper"]


def test_ci_degraded_flag():
    """ci_degraded flag is False for small dataset (bootstrap finishes fast)."""
    from api.services.stats_service import compute_roc

    scores_01, labels = _make_test_data(n_accepted=5, n_rejected=5)
    result = compute_roc(scores_01, labels, n_resamples=10)

    # With only 10 resamples, this cannot take > 2 seconds
    assert result["ci_degraded"] is False


# ---------------------------------------------------------------------------
# STATS-02: Calibration
# ---------------------------------------------------------------------------

def test_calibration_bins():
    """compute_calibration returns exactly 10 bins."""
    from api.services.stats_service import compute_calibration

    scores_01, labels = _make_test_data()
    result = compute_calibration(scores_01, labels)

    assert isinstance(result, list)
    assert len(result) == 10


def test_calibration_n_per_bin():
    """Sum of n across all calibration bins equals total input length."""
    from api.services.stats_service import compute_calibration

    scores_01, labels = _make_test_data()
    result = compute_calibration(scores_01, labels)

    total_n = sum(item["n"] for item in result)
    assert total_n == len(scores_01)


def test_calibration_viable_flag():
    """Calibration bin structure is present even when n < 50 (gating is router's job)."""
    from api.services.stats_service import compute_calibration

    scores_01, labels = _make_test_data(n_accepted=5, n_rejected=5)
    result = compute_calibration(scores_01, labels)

    # Still returns 10 bins — viability gating is handled by check_viability
    assert len(result) == 10
    # Each bin has required keys
    for item in result:
        assert "bucket" in item
        assert "mean_score" in item
        assert "fraction_positive" in item
        assert "n" in item


# ---------------------------------------------------------------------------
# STATS-03: Precision-Recall Curve
# ---------------------------------------------------------------------------

def test_pr_baseline():
    """PR baseline equals the actual positive rate (4 positives out of 10 = 0.4)."""
    from api.services.stats_service import compute_pr

    # Construct exact 4 ACCEPTED / 6 REJECTED
    scores_01 = np.array([0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1, 0.05, 0.02])
    labels = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])

    result = compute_pr(scores_01, labels)

    assert "pr_baseline" in result
    assert abs(result["pr_baseline"] - 0.4) < 1e-6  # exactly 4/10


def test_pr_output_keys():
    """compute_pr returns dict with precision, recall, auc_pr, and pr_baseline."""
    from api.services.stats_service import compute_pr

    scores_01, labels = _make_test_data()
    result = compute_pr(scores_01, labels)

    assert "precision" in result
    assert "recall" in result
    assert "auc_pr" in result
    assert "pr_baseline" in result

    assert isinstance(result["precision"], list)
    assert isinstance(result["recall"], list)
    assert isinstance(result["auc_pr"], float)
    assert isinstance(result["pr_baseline"], float)


# ---------------------------------------------------------------------------
# STATS-04: Score Distribution
# ---------------------------------------------------------------------------

def test_distribution_buckets():
    """compute_distribution returns exactly 10 buckets covering 0-100."""
    from api.services.stats_service import compute_distribution

    scores_100 = np.array([5, 15, 25, 35, 45, 55, 65, 75, 85, 95], dtype=float)
    assertions = ["ACCEPTED"] * 5 + ["REJECTED"] * 5

    result = compute_distribution(scores_100, assertions)

    assert isinstance(result, list)
    assert len(result) == 10

    # Check bucket labels cover 0-100
    expected_buckets = [f"{b*10}-{(b+1)*10}" for b in range(10)]
    actual_buckets = [item["bucket"] for item in result]
    assert actual_buckets == expected_buckets


def test_distribution_counts():
    """Sum of accepted + rejected across all buckets equals total n."""
    from api.services.stats_service import compute_distribution

    scores_100, _ = _make_test_data()
    scores_100_scaled = scores_100 * 100  # _make_test_data returns 0-1 scale
    assertions = ["ACCEPTED"] * 30 + ["REJECTED"] * 20

    result = compute_distribution(scores_100_scaled, assertions)

    total = sum(item["accepted"] + item["rejected"] for item in result)
    assert total == 50


# ---------------------------------------------------------------------------
# STATS-05: Disagreements
# ---------------------------------------------------------------------------

def test_disagreements_order():
    """compute_disagreements returns items sorted by descending disagreement."""
    from api.services.stats_service import compute_disagreements

    # Construct 5 items with known disagreements
    scores_100 = np.array([95.0, 80.0, 50.0, 20.0, 5.0])
    assertions = ["REJECTED", "REJECTED", "ACCEPTED", "ACCEPTED", "ACCEPTED"]
    person_ids = ["p1", "p2", "p3", "p4", "p5"]
    pmids = ["100", "101", "102", "103", "104"]

    result = compute_disagreements(scores_100, assertions, person_ids, pmids)

    # Should be sorted descending by disagreement
    disagreements = [item["disagreement"] for item in result]
    assert disagreements == sorted(disagreements, reverse=True)


def test_disagreement_calculation():
    """Disagreement for score=95, assertion=REJECTED is |95 - 0| = 95.0."""
    from api.services.stats_service import compute_disagreements

    scores_100 = np.array([95.0, 10.0])
    assertions = ["REJECTED", "ACCEPTED"]
    person_ids = ["p1", "p2"]
    pmids = ["100", "101"]

    result = compute_disagreements(scores_100, assertions, person_ids, pmids)

    # First item should be p1 with score=95, assertion=REJECTED, disagreement=95
    assert result[0]["person_id"] == "p1"
    assert result[0]["score"] == 95.0
    assert result[0]["assertion"] == "REJECTED"
    assert result[0]["disagreement"] == 95.0

    # Second item: score=10, assertion=ACCEPTED, disagreement=|10-100|=90
    assert result[1]["disagreement"] == 90.0


def test_disagreements_top_10_limit():
    """compute_disagreements returns at most 10 items."""
    from api.services.stats_service import compute_disagreements

    n = 20
    scores_100 = np.random.uniform(0, 100, n)
    assertions = (["ACCEPTED"] * 10 + ["REJECTED"] * 10)
    person_ids = [f"p{i}" for i in range(n)]
    pmids = [str(i) for i in range(n)]

    result = compute_disagreements(scores_100, assertions, person_ids, pmids)

    assert len(result) <= 10
