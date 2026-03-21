"""Tests for feedback scoring."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.feedback import sigmoid_score, informed_absence_penalty, determine_feedback_score


def test_sigmoid_equal_counts():
    assert sigmoid_score(5, 5) == 0.0


def test_sigmoid_all_accepted():
    score = sigmoid_score(10, 0)
    assert score > 0.4  # should be close to 0.5


def test_sigmoid_all_rejected():
    score = sigmoid_score(0, 10)
    assert score < -0.4  # should be close to -0.5


def test_sigmoid_zero():
    assert sigmoid_score(0, 0) == 0.0


def test_sigmoid_range():
    for acc in range(20):
        for rej in range(20):
            score = sigmoid_score(acc, rej)
            assert -0.5 <= score <= 0.5, f"Score {score} out of range for ({acc}, {rej})"


def test_informed_absence_no_accepted():
    assert informed_absence_penalty(0, 1.0) == 0.0


def test_informed_absence_negative():
    penalty = informed_absence_penalty(20, 1.0)
    assert penalty < 0, f"Expected negative penalty, got {penalty}"


def test_informed_absence_scales_with_strength():
    p1 = informed_absence_penalty(20, 0.5)
    p2 = informed_absence_penalty(20, 1.0)
    assert abs(p2) > abs(p1), "Higher strength should give larger penalty"


def test_determine_feedback_score_accepted():
    # If article is ACCEPTED, leave it out of accepted count
    score = determine_feedback_score("ACCEPTED", 5, 2)
    expected = sigmoid_score(4, 2)  # 5-1=4
    assert score == expected


def test_determine_feedback_score_rejected():
    score = determine_feedback_score("REJECTED", 5, 2)
    expected = sigmoid_score(5, 1)  # 2-1=1
    assert score == expected


def test_determine_feedback_score_unasserted():
    score = determine_feedback_score("", 5, 2)
    expected = sigmoid_score(5, 2)
    assert score == expected


if __name__ == "__main__":
    test_sigmoid_equal_counts()
    test_sigmoid_all_accepted()
    test_sigmoid_all_rejected()
    test_sigmoid_zero()
    test_sigmoid_range()
    test_informed_absence_no_accepted()
    test_informed_absence_negative()
    test_informed_absence_scales_with_strength()
    test_determine_feedback_score_accepted()
    test_determine_feedback_score_rejected()
    test_determine_feedback_score_unasserted()
    print("All feedback tests passed!")
