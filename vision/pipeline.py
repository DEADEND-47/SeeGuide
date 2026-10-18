"""SeeGuide Vision Pipeline Orchestrator
Coordinates tiered vision execution:
- Fast Tier (quality, motion, corridor edge density) on every cycle
- Object Detector & Tracker (looming growth and zone estimation) on demand
- Hazard Estimator (corridor blockage and collision risk)
- OCR Scene Text Reader on demand
Emits strict VisionObservation Pydantic models conforming to Stage 1 contracts.
"""

import base64
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


class VisionPipeline:
    """Orchestrates OpenCV 5 vision components and emits structured VisionObservations."""

    def __init__(
        self,
        detector_model_path: Optional[str] = None,
        ocr_det_path: Optional[str] = None,
        ocr_rec_path: Optional[str] = None,
    ):
        self.detector = ObjectDetector(model_path=detector_model_path)
        self.tracker = Tracker()
        self.ocr = TextRecognizer(det_model_path=ocr_det_path, rec_model_path=ocr_rec_path)
        self.prev_frame: Optional[np.ndarray] = None

    def process(
        self,
        frame_input: Union[str, bytes, np.ndarray],
        run_detector: bool = False,
        run_ocr: bool = False,
        timestamp: Optional[float] = None,
    ) -> VisionObservation:
        """Processes an incoming frame through active vision tiers.

        Args:
            frame_input: Base64 JPEG string, raw JPEG bytes, or pre-decoded BGR numpy array.
            run_detector: Whether to execute object detection tier.
            run_ocr: Whether to execute scene text OCR tier.
            timestamp: Epoch timestamp for the observation (defaults to current time).

        Returns:
            VisionObservation instance conforming strictly to contract schemas.
        """
        obs_time = timestamp if timestamp is not None else time.time()

        # 1. Decode frame into BGR numpy array
        if isinstance(frame_input, np.ndarray):
            frame = frame_input
        elif isinstance(frame_input, (str, bytes)):
            if isinstance(frame_input, str):
                # Handle potential data URI prefix
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

        # 2. Fast Tier Processing
        t_fast_start = time.perf_counter()
        fast_metrics = process_fast(frame=frame, prev_frame=self.prev_frame)
        fast_duration_ms = round((time.perf_counter() - t_fast_start) * 1000.0, 2)

        # 3. Object Detection & Tracking Tier
        detect_duration_ms: Optional[float] = None
        tracked_objects: List[Dict[str, Any]] = []

        if run_detector:
            t_det_start = time.perf_counter()
            raw_detections = self.detector.detect(frame)
            tracked_objects = self.tracker.update(raw_detections, frame_width=w, frame_height=h)
            detect_duration_ms = round((time.perf_counter() - t_det_start) * 1000.0, 2)

        # 4. Hazard Estimation
        estimate_hazard(fast_metrics=fast_metrics, tracked_objects=tracked_objects)

        # 5. Text Detection & OCR Tier
        ocr_duration_ms: Optional[float] = None
        extracted_text: Optional[str] = None

        if run_ocr:
            t_ocr_start = time.perf_counter()
            ocr_result = self.ocr.read(frame)
            extracted_text = ocr_result.get("text")
            ocr_duration_ms = round((time.perf_counter() - t_ocr_start) * 1000.0, 2)

        # 6. Update temporal state
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
            timing_ms=TimingMetrics(
                fast=fast_duration_ms,
                detect=detect_duration_ms,
                ocr=ocr_duration_ms,
            ),
        )

        return observation

    def reset(self) -> None:
        """Resets pipeline temporal state and tracking history."""
        self.prev_frame = None
        self.tracker.reset()
