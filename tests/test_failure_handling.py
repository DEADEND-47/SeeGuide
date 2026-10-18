"""Unit and Failure Handling Tests for SeeGuide
Tests FR-16 compliance: Model timeouts, pipeline failures, corrupted inputs,
and low-confidence observations must lead to safe fallback directives ("I'm not sure"),
and must NEVER emit confident hazard warnings.
"""

import time
import numpy as np
import pytest

from agent.policy import decide
from agent.state import BeliefState
from server.models import (
    CorridorMetrics,
    DetectedObject,
    MotionMetrics,
    QualityMetrics,
    TimingMetrics,
    VisionObservation,
)
from vision.pipeline import VisionPipeline


def make_observation(
    status: str = "ok",
    objects: list = None,
    blur: float = 85.0,
    brightness: float = 120.0,
) -> VisionObservation:
    """Helper creating VisionObservation with specified status and objects."""
    return VisionObservation(
        t=100.0,
        quality=QualityMetrics(blur=blur, brightness=brightness, stable=True),
        motion=MotionMetrics(corridor_divergence=0.1, ego_motion=0.2),
        corridor=CorridorMetrics(edge_density=0.15, blocked_score=0.1),
        objects=objects or [],
        text=None,
        timing_ms=TimingMetrics(fast=10.0, detect=40.0, ocr=None),
        status=status,
    )


def test_rule_0_uncertainty_fallback_on_degraded():
    """Pipeline degradation (e.g. model timeout) triggers 'I'm not sure' and suppresses hazard."""
    state = BeliefState(mode="walk")
    # Craft looming obstacle that would normally trigger P0
    looming_obj = DetectedObject(cls="person", conf=0.9, bbox=[200, 150, 400, 450], growth=1.35, zone="center")
    obs = make_observation(status="degraded", objects=[looming_obj])

    action = decide(obs, state)

    # Must NOT emit P0 hazard warning when pipeline is degraded (FR-16)
    assert action.priority != "P0"
    assert action.type == "speak"
    assert "I'm not sure" in action.text
    assert action.reason == "uncertainty_fallback"
    assert action.vibrate is False


def test_rule_0_uncertainty_fallback_on_error():
    """Pipeline error status triggers 'I'm not sure'."""
    state = BeliefState(mode="walk")
    obs = make_observation(status="error")

    action = decide(obs, state)
    assert action.type == "speak"
    assert "I'm not sure" in action.text
    assert action.reason == "uncertainty_fallback"


def test_rule_0_uncertainty_fallback_on_low_confidence():
    """When detected objects have very low confidence (< 0.35), agent safely demurs."""
    state = BeliefState(mode="walk")
    low_conf_obj = DetectedObject(cls="chair", conf=0.28, bbox=[100, 100, 200, 200], growth=1.0, zone="center")
    obs = make_observation(status="ok", objects=[low_conf_obj])

    action = decide(obs, state)
    assert action.type == "speak"
    assert "I'm not sure" in action.text
    assert action.reason == "uncertainty_fallback"


def test_pipeline_timeout_handling(monkeypatch):
    """Simulates detector execution exceeding timeout and verifies pipeline flags degraded status."""
    pipeline = VisionPipeline(timeout_ms=50.0)

    # Monkeypatch detector to sleep beyond timeout
    def mock_slow_detect(frame):
        time.sleep(0.06)  # 60ms > 50ms timeout
        return []

    monkeypatch.setattr(pipeline.detector, "detect", mock_slow_detect)

    dummy_frame = np.full((480, 640, 3), 120, dtype=np.uint8)
    obs = pipeline.process(dummy_frame, run_detector=True)

    assert obs.status == "degraded"
    assert obs.timing_ms.detect is not None
    assert obs.timing_ms.detect >= 50.0


def test_pipeline_detector_exception_containment(monkeypatch):
    """Simulates detector crashing with an exception and verifies pipeline catches it gracefully."""
    pipeline = VisionPipeline()

    def mock_crashing_detect(frame):
        raise RuntimeError("OpenCV DNN forward inference fatal crash")

    monkeypatch.setattr(pipeline.detector, "detect", mock_crashing_detect)

    dummy_frame = np.full((480, 640, 3), 120, dtype=np.uint8)
    obs = pipeline.process(dummy_frame, run_detector=True)

    # Pipeline remains alive, returns empty detections, and flags degraded
    assert obs.status == "degraded"
    assert obs.objects == []


def test_pipeline_corrupted_frame_input():
    """Passing corrupted/invalid image data raises ValueError for caller to handle."""
    pipeline = VisionPipeline()
    with pytest.raises(ValueError):
        pipeline.process("not-a-valid-base64-or-image", run_detector=True)


def test_pipeline_fast_tier_exception_handling(monkeypatch):
    """Simulates fast tier failure and verifies pipeline returns error status with safe default metrics."""
    pipeline = VisionPipeline()

    def mock_broken_fast(frame, prev_frame):
        raise RuntimeError("Fast tier OpenCV driver failure")

    monkeypatch.setattr("vision.pipeline.process_fast", mock_broken_fast)

    dummy_frame = np.full((480, 640, 3), 120, dtype=np.uint8)
    obs = pipeline.process(dummy_frame)

    assert obs.status == "error"
    assert obs.quality.stable is False
