"""Unit tests for SeeGuide Hazard Evaluation
Verifies corridor edge density scoring, obstacle zone localization, and looming growth assessment.
"""

from vision.hazard import estimate_hazard


def test_hazard_clear_path():
    """Verify that low edge density and no objects produces low blocked score."""
    fast_metrics = {
        "corridor": {"edge_density": 0.05, "blocked_score": 0.0},
    }
    tracked_objects = []

    res = estimate_hazard(fast_metrics, tracked_objects)
    assert res["blocked_score"] <= 0.15
    assert res["looming_hazard"] is False
    assert res["hazard_reason"] is None
    assert fast_metrics["corridor"]["blocked_score"] == res["blocked_score"]


def test_hazard_high_edge_density():
    """Verify high edge density increases blocked score."""
    fast_metrics = {
        "corridor": {"edge_density": 0.65, "blocked_score": 0.0},
    }
    tracked_objects = []

    res = estimate_hazard(fast_metrics, tracked_objects)
    assert res["blocked_score"] >= 0.8
    assert res["looming_hazard"] is False


def test_hazard_lateral_non_threatening():
    """Verify object on lateral side without extreme growth does not flag center looming hazard."""
    fast_metrics = {
        "corridor": {"edge_density": 0.1, "blocked_score": 0.0},
    }
    tracked_objects = [
        {"cls": "chair", "conf": 0.8, "bbox": [10, 100, 80, 200], "growth": 1.05, "zone": "left"}
    ]

    res = estimate_hazard(fast_metrics, tracked_objects)
    assert res["looming_hazard"] is False
