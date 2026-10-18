"""SeeGuide Vision Pipeline Orchestrator
Coordinates tiered vision execution:
- Fast Tier (quality, motion, corridor edge density) on every cycle
- Object Detector & Tracker (looming growth and zone estimation) on demand
- Hazard Estimator (corridor blockage and collision risk)
- OCR Scene Text Reader on demand
Emits strict VisionObservation Pydantic models conforming to Stage 1 contracts
with comprehensive FR-16 failure handling, model timeouts, and graceful degradation.
"""

import base64
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union
import cv2
import numpy as np

from server.models import (
    CorridorMetrics,
    DetectedObject,
    MotionMetrics,
    QualityMetrics,
    TimingMetrics,
    VisionObservation,
)
from vision.detector import ObjectDetector
from vision.fast_tier import process_fast
from vision.hazard import estimate_hazard
from vision.ocr import TextRecognizer
from vision.tracker import Tracker

logger = logging.getLogger("seeguide.vision.pipeline")

# Default latency thresholds for failure/timeout detection (ms)
DEFAULT_TIMEOUT_MS = 500.0


class VisionPipeline:
    """Orchestrates OpenCV 5 vision components and emits structured VisionObservations

    with resilient failure handling and timeout containment (FR-16).
    """

    def __init__(
        self,
        detector_model_path: Optional[str] = None,
        ocr_det_path: Optional[str] = None,
        ocr_rec_path: Optional[str] = None,
        yunet_model_path: Optional[str] = None,
        vocabulary_path: Optional[str] = None,
        timeout_ms: float = DEFAULT_TIMEOUT_MS,
    ):
        self.detector = ObjectDetector(model_path=detector_model_path)
        self.tracker = Tracker()
        self.ocr = TextRecognizer(
            det_model_path=ocr_det_path,
            rec_model_path=ocr_rec_path,
            vocabulary_path=vocabulary_path,
        )
        self.yunet_model_path = yunet_model_path
        self.prev_frame: Optional[np.ndarray] = None
        self.timeout_ms = timeout_ms

    def process(
        self,
        frame_input: Union[str, bytes, np.ndarray],
        run_detector: bool = False,
        run_ocr: bool = False,
        timestamp: Optional[float] = None,
    ) -> VisionObservation:
        """Processes an incoming frame through active vision tiers.

        Guarantees safe fallback metrics, timeouts, and degradation status under any failure.

        Args:
            frame_input: Base64 JPEG string, raw JPEG bytes, or pre-decoded BGR numpy array.
            run_detector: Whether to execute object detection tier.
            run_ocr: Whether to execute scene text OCR tier.
            timestamp: Epoch timestamp for the observation (defaults to current time).

        Returns:
            VisionObservation instance conforming strictly to contract schemas.
        """
        obs_time = timestamp if timestamp is not None else time.time()
        pipeline_status = "ok"

        # 1. Decode frame into BGR numpy array
        if isinstance(frame_input, np.ndarray):
            frame = frame_input
        elif isinstance(frame_input, (str, bytes)):
            if isinstance(frame_input, str):
                if "," in frame_input:
                    frame_input = frame_input.split(",", 1)[1]
                raw_bytes = base64.b64decode(frame_input)
            else:
                raw_bytes = frame_input
            np_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("Failed to decode base64/bytes into valid image frame")
        else:
            raise TypeError(f"Unsupported frame input type: {type(frame_input)}")

        h, w = frame.shape[:2]

        # 2. Fast Tier Processing (Quality, Motion, Corridor ROI)
        t_fast_start = time.perf_counter()
        try:
            fast_metrics = process_fast(frame=frame, prev_frame=self.prev_frame)
            fast_duration_ms = round((time.perf_counter() - t_fast_start) * 1000.0, 2)
            if fast_duration_ms > self.timeout_ms:
                logger.warning(
                    "Fast tier exceeded timeout threshold (%.2f ms > %.2f ms). Flagging degraded.",
                    fast_duration_ms,
                    self.timeout_ms,
                )
                pipeline_status = "degraded"
        except Exception as fast_err:
            logger.warning("Fast tier execution error: %s. Using safe defaults.", fast_err)
            fast_duration_ms = round((time.perf_counter() - t_fast_start) * 1000.0, 2)
            fast_metrics = {
                "quality": {"blur": 0.0, "brightness": 0.0, "stable": False},
                "motion": {"corridor_divergence": 0.0, "ego_motion": 0.0},
                "corridor": {"edge_density": 0.0, "blocked_score": 0.0},
            }
            pipeline_status = "error"

        # 3. Object Detection & Tracking Tier
        detect_duration_ms: Optional[float] = None
        tracked_objects: List[Dict[str, Any]] = []

        if run_detector:
            t_det_start = time.perf_counter()
            try:
                raw_detections = self.detector.detect(frame)
                detect_duration_ms = round((time.perf_counter() - t_det_start) * 1000.0, 2)
                if detect_duration_ms > self.timeout_ms:
                    logger.warning(
                        "Detector tier exceeded timeout (%.2f ms > %.2f ms). Flagging degraded.",
                        detect_duration_ms,
                        self.timeout_ms,
                    )
                    pipeline_status = "degraded"
                    tracked_objects = []
                else:
                    tracked_objects = self.tracker.update(raw_detections, frame_width=w, frame_height=h)
            except Exception as det_err:
                logger.warning("Detector tier failed: %s. Returning safe empty detections.", det_err)
                detect_duration_ms = round((time.perf_counter() - t_det_start) * 1000.0, 2)
                tracked_objects = []
                pipeline_status = "degraded"

        # 4. Hazard Estimation
        try:
            estimate_hazard(fast_metrics=fast_metrics, tracked_objects=tracked_objects)
        except Exception as haz_err:
            logger.warning("Hazard estimation error: %s", haz_err)
            pipeline_status = "degraded"

        # 5. Text Detection & OCR Tier
        ocr_duration_ms: Optional[float] = None
        extracted_text: Optional[str] = None
        text_confidence: Optional[float] = None
        text_clipped: Optional[bool] = None

        if run_ocr:
            t_ocr_start = time.perf_counter()
            try:
                ocr_result = self.ocr.read(frame)
                ocr_duration_ms = round((time.perf_counter() - t_ocr_start) * 1000.0, 2)
                if ocr_duration_ms > self.timeout_ms:
                    logger.warning(
                        "OCR tier exceeded timeout (%.2f ms > %.2f ms). Flagging degraded.",
                        ocr_duration_ms,
                        self.timeout_ms,
                    )
                    pipeline_status = "degraded"
                    extracted_text = None
                else:
                    extracted_text = ocr_result.get("text")
                    text_confidence = ocr_result.get("confidence")
                    text_clipped = ocr_result.get("clipped")
            except Exception as ocr_err:
                logger.warning("OCR tier failed: %s. Returning null text.", ocr_err)
                ocr_duration_ms = round((time.perf_counter() - t_ocr_start) * 1000.0, 2)
                extracted_text = None
                pipeline_status = "degraded"

        # 6. Update temporal state (only if frame was valid)
        self.prev_frame = frame.copy()

        # 7. Assemble strict VisionObservation Pydantic model
        observation = VisionObservation(
            t=round(obs_time, 2),
            quality=QualityMetrics(
                blur=fast_metrics["quality"]["blur"],
                brightness=fast_metrics["quality"]["brightness"],
                stable=fast_metrics["quality"]["stable"],
            ),
            motion=MotionMetrics(
                corridor_divergence=fast_metrics["motion"]["corridor_divergence"],
                ego_motion=fast_metrics["motion"]["ego_motion"],
            ),
            corridor=CorridorMetrics(
                edge_density=fast_metrics["corridor"]["edge_density"],
                blocked_score=fast_metrics["corridor"]["blocked_score"],
            ),
            objects=[
                DetectedObject(
                    cls=obj["cls"],
                    conf=obj["conf"],
                    bbox=obj["bbox"],
                    growth=obj["growth"],
                    zone=obj["zone"],
                )
                for obj in tracked_objects
            ],
            text=extracted_text,
            text_confidence=text_confidence,
            text_clipped=text_clipped,
            timing_ms=TimingMetrics(
                fast=fast_duration_ms,
                detect=detect_duration_ms,
                ocr=ocr_duration_ms,
            ),
            status=pipeline_status,
        )

        return observation

    def reset(self) -> None:
        """Resets pipeline temporal state and tracking history."""
        self.prev_frame = None
        self.tracker.reset()
