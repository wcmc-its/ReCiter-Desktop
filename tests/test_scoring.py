"""Tests for the scoring pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from core.scoring import load_model
from core.preprocessing import (
    IDENTITY_ONLY_BASE_FEATURES,
    FEEDBACK_IDENTITY_BASE_FEATURES,
    wilson_lower_bound,
)


def test_wilson_no_data():
    assert wilson_lower_bound(0, 0) == 0.5


def test_wilson_all_success():
    lb = wilson_lower_bound(100, 0)
    assert lb > 0.95


def test_wilson_all_failure():
    lb = wilson_lower_bound(0, 100)
    assert lb < 0.05


def test_wilson_small_sample():
    lb = wilson_lower_bound(4, 1)
    assert 0.3 < lb < 0.5  # Pulled toward 0.5


def test_identity_only_model_loads():
    model = load_model("wcm", "identityOnly")
    assert model.scaler is not None
    assert model.model is not None
    assert model.calibrator is not None


def test_identity_only_prediction():
    model = load_model("wcm", "identityOnly")
    data = {col: [0.0] for col in IDENTITY_ONLY_BASE_FEATURES}
    data["nameMatchFirstScore"] = [1.852]
    data["nameMatchLastScore"] = [0.664]
    data["emailMatchScore"] = [8.0]
    df = pd.DataFrame(data)
    result = model.predict(df)
    assert "calibrated_score" in result.columns
    assert 0 <= result["calibrated_score"].iloc[0] <= 1


def test_feedback_identity_model_loads():
    model = load_model("wcm", "feedbackIdentity")
    assert model.scaler is not None


def test_feedback_identity_prediction():
    model = load_model("wcm", "feedbackIdentity")
    data = {col: [0.0] for col in FEEDBACK_IDENTITY_BASE_FEATURES}
    data["nameMatchFirstScore"] = [1.852]
    data["countAccepted"] = [10]
    data["countRejected"] = [5]
    data["feedbackScoreJournal"] = [0.3]
    df = pd.DataFrame(data)
    result = model.predict(df)
    assert "calibrated_score" in result.columns
    assert 0 <= result["calibrated_score"].iloc[0] <= 1


def test_strong_vs_weak_scores():
    model = load_model("wcm", "identityOnly")

    # Strong match
    strong = {col: [0.0] for col in IDENTITY_ONLY_BASE_FEATURES}
    strong["nameMatchFirstScore"] = [1.852]
    strong["nameMatchLastScore"] = [0.664]
    strong["nameMatchMiddleScore"] = [1.588]
    strong["emailMatchScore"] = [8.0]

    # Weak match
    weak = {col: [0.0] for col in IDENTITY_ONLY_BASE_FEATURES}
    weak["nameMatchFirstScore"] = [-3.087]
    weak["nameMatchLastScore"] = [-0.996]

    strong_result = model.predict(pd.DataFrame(strong))
    weak_result = model.predict(pd.DataFrame(weak))

    assert strong_result["calibrated_score"].iloc[0] > weak_result["calibrated_score"].iloc[0]


if __name__ == "__main__":
    test_wilson_no_data()
    test_wilson_all_success()
    test_wilson_all_failure()
    test_wilson_small_sample()
    test_identity_only_model_loads()
    test_identity_only_prediction()
    test_feedback_identity_model_loads()
    test_feedback_identity_prediction()
    test_strong_vs_weak_scores()
    print("All scoring tests passed!")
