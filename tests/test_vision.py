"""Unit tests for SeeGuide Core Vision Pipeline
Validates fast-tier perception, tracker growth calculations, hazard estimation,
privacy blur, and VisionPipeline orchestration using synthetic NumPy arrays.
"""

import base64
import cv2
import numpy as np
import pytest
from server.models import VisionObservation
from vision.detector import ObjectDetector
from vision.fast_tier import process_fast
from vision.hazard import estimate_hazard
from vision.ocr import TextRecognizer
from vision.pipeline import VisionPipeline
from vision.privacy import blur_faces
from vision.tracker import Tracker, compute_iou, get_horizontal_zone


def generate_synthetic_frame(
    width: int = 640,
    height: int = 480,
    with_patterns: bool = True,
) -> np.ndarray:
    """Generates a synthetic BGR frame for deterministic unit testing."""
    frame = np.full((height, width, 3), fill_value=120, dtype=np.uint8)
    if with_patterns:
        # Add high-contrast lines and shapes inside corridor
        cv2.rectangle(frame, (200, 150), (440, 450), (255, 255, 255), -1)
        cv2.line(frame, (100, 0), (200, 480), (0, 0, 0), 3)
        cv2.line(frame, (540, 0), (440, 480), (0, 0, 0), 3)
    return frame


def frame_to_b64(frame: np.ndarray) -> str:
    """Encodes a BGR frame as a JPEG base64 string."""
    _, buffer = cv2.imencode(".jpg", frame)
    return base64.b64encode(buffer).decode("utf-8")


# ====================================================================
# Fast Tier Tests
# ====================================================================

def test_fast_tier_single_frame():
    """Verify process_fast produces valid quality, motion, and corridor fields."""
    frame = generate_synthetic_frame()
    metrics = process_fast(frame=frame, prev_frame=None)

    assert "quality" in metrics
    assert "motion" in metrics
    assert "corridor" in metrics

    assert isinstance(metrics["quality"]["blur"], float)
    assert isinstance(metrics["quality"]["brightness"], float)
    assert isinstance(metrics["quality"]["stable"], bool)
    assert metrics["motion"]["ego_motion"] == 0.0
    assert metrics["motion"]["corridor_divergence"] == 0.0
    assert 0.0 <= metrics["corridor"]["edge_density"] <= 1.0


def test_fast_tier_optical_flow():
    """Verify process_fast computes non-zero motion when frames shift."""
    frame1 = generate_synthetic_frame()
    # Shift image horizontally
    frame2 = np.roll(frame1, shift=15, axis=1)

    metrics = process_fast(frame=frame2, prev_frame=frame1)
    assert metrics["motion"]["ego_motion"] > 0.0


# ====================================================================
# Tracker Tests
# ====================================================================

def test_tracker_growth_calculation():
    """Verify Tracker assigns IDs, calculates growth, and sets zones."""
    tracker = Tracker()

    # Frame 1: obstacle at center (area = 100 x 100 = 10,000)
    det_f1 = [{
        "cls": "person",
        "conf": 0.9,
        "bbox": [270.0, 190.0, 370.0, 290.0],
    }]
    tracks_f1 = tracker.update(det_f1, frame_width=640, frame_height=480)
    assert len(tracks_f1) == 1
    assert tracks_f1[0]["growth"] == 1.0
    assert tracks_f1[0]["zone"] == "center"

    # Frame 2: obstacle looms closer (area = 120 x 120 = 14,400 -> growth = 1.44)
    det_f2 = [{
        "cls": "person",
        "conf": 0.92,
        "bbox": [260.0, 180.0, 380.0, 300.0],
    }]
    tracks_f2 = tracker.update(det_f2, frame_width=640, frame_height=480)
    assert len(tracks_f2) == 1
    assert tracks_f2[0]["growth"] == 1.44
    assert tracks_f2[0]["zone"] == "center"


def test_tracker_zone_classification():
    """Verify horizontal zone assignment (left, center, right)."""
    assert get_horizontal_zone([10.0, 100.0, 100.0, 200.0], frame_width=640) == "left"
    assert get_horizontal_zone([250.0, 100.0, 390.0, 200.0], frame_width=640) == "center"
    assert get_horizontal_zone([500.0, 100.0, 600.0, 200.0], frame_width=640) == "right"


def test_compute_iou():
    """Verify IoU calculation on overlapping and disjoint boxes."""
    b1 = [0.0, 0.0, 10.0, 10.0]
    b2 = [0.0, 0.0, 10.0, 10.0]
    assert compute_iou(b1, b2) == 1.0

    b3 = [10.0, 10.0, 20.0, 20.0]
    assert compute_iou(b1, b3) == 0.0


# ====================================================================
# Hazard Estimator Tests
# ====================================================================

def test_hazard_estimation_looming():
    """Verify looming hazard detection when center obstacle growth > 1.25."""
    fast_metrics = {
        "corridor": {"edge_density": 0.15, "blocked_score": 0.0},
    }
    tracked_objects = [
        {"cls": "person", "conf": 0.88, "bbox": [220, 140, 380, 470], "growth": 1.35, "zone": "center"}
    ]
    hazard = estimate_hazard(fast_metrics, tracked_objects)

    assert hazard["looming_hazard"] is True
    assert hazard["hazard_reason"] == "approaching_person_in_corridor"
    assert fast_metrics["corridor"]["blocked_score"] >= 0.75


# ====================================================================
# Privacy Blur Tests
# ====================================================================

def test_privacy_blur_pass_through():
    """Verify blur_faces operates without error even in offline dummy mode."""
    frame = generate_synthetic_frame()
    anonymized = blur_faces(frame)
    assert anonymized.shape == frame.shape
    assert anonymized.dtype == np.uint8


# ====================================================================
# Vision Pipeline Orchestrator Tests
# ====================================================================

def test_vision_pipeline_orchestration():
    """Verify VisionPipeline processes frames and returns valid VisionObservation."""
    pipeline = VisionPipeline()
    frame1 = generate_synthetic_frame()
    b64_str = frame_to_b64(frame1)

    # Process frame 1 with detector and OCR requested (dummy offline mode)
    obs1 = pipeline.process(frame_input=b64_str, run_detector=True, run_ocr=True)

    assert isinstance(obs1, VisionObservation)
    assert obs1.quality.blur > 0.0
    assert 0.0 <= obs1.corridor.edge_density <= 1.0
    assert obs1.timing_ms.fast >= 0.0
    assert obs1.timing_ms.detect is not None
    assert obs1.timing_ms.ocr is not None

    # Process frame 2 directly as NumPy array
    frame2 = np.roll(frame1, shift=5, axis=0)
    obs2 = pipeline.process(frame_input=frame2, run_detector=False, run_ocr=False)

    assert isinstance(obs2, VisionObservation)
    assert obs2.motion.ego_motion > 0.0
    assert obs2.timing_ms.detect is None
    assert obs2.timing_ms.ocr is None
