#!/usr/bin/env python3
"""SeeGuide Latency & Performance Profiler
Executes micro-benchmarks timing each pipeline stage across synthetic frames:
- decode: Base64 JPEG decoding to BGR numpy array
- fast_tier: Laplacian blur variance, luma, corridor ROI, optical flow
- detector: OpenCV Zoo ONNX object detection + multi-frame tracker
- ocr: OpenCV Zoo Scene Text detection + recognition
- agent_decide: Deterministic 6-rule policy arbitration
- total_cycle: Full perception-decision-action loop cycle

Outputs timing percentiles (p50, p95) to benchmarks/results/profile.csv
and verifies compliance against real-time latency budgets.
"""

import argparse
import base64
import csv
import logging
from pathlib import Path
import platform
import sys
import time
from typing import Dict, List, Tuple
import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.policy import decide
from agent.state import BeliefState
from vision.detector import ObjectDetector
from vision.fast_tier import process_fast
from vision.ocr import TextRecognizer
from vision.pipeline import VisionPipeline
from vision.tracker import Tracker

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seeguide.profile")

# Latency timing budgets specified in architecture.md (ms)
TIMING_BUDGETS_MS = {
    "decode": 15.0,
    "fast_tier": 20.0,
    "detector": 80.0,
    "ocr": 90.0,
    "agent_decide": 5.0,
    "total_cycle": 100.0,
}


def create_benchmark_frame_b64(width: int = 640, height: int = 480) -> str:
    """Creates a realistic synthetic corridor frame encoded as base64 JPEG."""
    img = np.full((height, width, 3), 125, dtype=np.uint8)
    # Perspective corridor walls and geometric textures
    cv2.line(img, (int(width * 0.15), height), (int(width * 0.35), int(height * 0.35)), (230, 230, 230), 3)
    cv2.line(img, (int(width * 0.85), height), (int(width * 0.65), int(height * 0.35)), (230, 230, 230), 3)
    cv2.circle(img, (int(width * 0.5), int(height * 0.55)), 60, (50, 50, 180), -1)
    cv2.putText(img, "Room 302", (int(width * 0.4), int(height * 0.3)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")


def run_profiler(
    num_frames: int = 200,
    output_path: Path = Path("benchmarks/results/profile.csv"),
    instance_type: str = "local",
) -> Path:
    """Executes latency micro-benchmarks across N synthetic frames and saves profile.csv."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Starting SeeGuide latency profile over %d iterations (instance=%s)...", num_frames, instance_type)

    pipeline = VisionPipeline()
    state = BeliefState(mode="walk")

    b64_frame = create_benchmark_frame_b64()

    # Pre-warm runtime
    _ = pipeline.process(b64_frame, run_detector=True, run_ocr=True)

    stage_timings: Dict[str, List[float]] = {
        "decode": [],
        "fast_tier": [],
        "detector": [],
        "ocr": [],
        "agent_decide": [],
        "total_cycle": [],
    }

    prev_frame = None

    for i in range(num_frames):
        # 1. Decode stage
        t0 = time.perf_counter()
        raw_bytes = base64.b64decode(b64_frame)
        np_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        stage_timings["decode"].append((time.perf_counter() - t0) * 1000.0)

        # 2. Fast tier stage
        t1 = time.perf_counter()
        fast_metrics = process_fast(frame=frame, prev_frame=prev_frame)
        stage_timings["fast_tier"].append((time.perf_counter() - t1) * 1000.0)

        # 3. Detector tier stage
        t2 = time.perf_counter()
        raw_det = pipeline.detector.detect(frame)
        _ = pipeline.tracker.update(raw_det, frame_width=640, frame_height=480)
        stage_timings["detector"].append((time.perf_counter() - t2) * 1000.0)

        # 4. OCR tier stage
        t3 = time.perf_counter()
        _ = pipeline.ocr.read(frame)
        stage_timings["ocr"].append((time.perf_counter() - t3) * 1000.0)

        # 5. Full cycle + agent decision
        t_cycle = time.perf_counter()
        obs = pipeline.process(frame, run_detector=(i % 5 == 0), run_ocr=False)
        t_decide = time.perf_counter()
        action = decide(obs, state)
        state.update(obs, action)
        stage_timings["agent_decide"].append((time.perf_counter() - t_decide) * 1000.0)
        stage_timings["total_cycle"].append((time.perf_counter() - t_cycle) * 1000.0)

        prev_frame = frame.copy()

    py_version = platform.python_version()
    cv_version = cv2.__version__

    results = []
    for stage, timings in stage_timings.items():
        arr = np.array(timings)
        p50 = round(float(np.percentile(arr, 50)), 2)
        p95 = round(float(np.percentile(arr, 95)), 2)
        min_v = round(float(np.min(arr)), 2)
        max_v = round(float(np.max(arr)), 2)
        budget = TIMING_BUDGETS_MS.get(stage, 100.0)
        pass_budget = p95 <= budget
        detector_backend = "yolox_nano_onnx" if Path("models/yolox_nano.onnx").exists() else "dummy"

        results.append({
            "stage": stage,
            "p50_ms": p50,
            "p95_ms": p95,
            "min_ms": min_v,
            "max_ms": max_v,
            "budget_ms": budget,
            "pass_budget": pass_budget,
            "detector_backend": detector_backend,
            "python_version": py_version,
            "opencv_version": cv_version,
            "instance_type": instance_type,
        })

    # Write profile.csv
    fieldnames = [
        "stage",
        "p50_ms",
        "p95_ms",
        "min_ms",
        "max_ms",
        "budget_ms",
        "pass_budget",
        "detector_backend",
        "python_version",
        "opencv_version",
        "instance_type",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    logger.info("Saved latency benchmark profile to %s", output_path)

    # Console Report
    print("\n" + "=" * 85)
    print(f"SeeGuide Latency Profile (N={num_frames}, Python {py_version}, OpenCV {cv_version}, Host={instance_type})")
    print("=" * 85)
    header = f"{'Stage':<16} {'p50 (ms)':<10} {'p95 (ms)':<10} {'Min':<8} {'Max':<8} {'Budget':<10} {'Status':<8}"
    print(header)
    print("-" * 85)
    for r in results:
        status_str = "PASS" if r["pass_budget"] else "WARN"
        print(
            f"{r['stage']:<16} {r['p50_ms']:<10.2f} {r['p95_ms']:<10.2f} {r['min_ms']:<8.2f} {r['max_ms']:<8.2f} "
            f"{r['budget_ms']:<10.1f} {status_str:<8}"
        )
    print("=" * 85 + "\n")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="SeeGuide Stage 8 Performance Profiler")
    parser.add_argument("--frames", type=int, default=200, help="Number of benchmark iterations")
    parser.add_argument("--output", type=str, default="benchmarks/results/profile.csv", help="Output CSV path")
    parser.add_argument("--instance-type", type=str, default="local", help="Host machine / cloud instance identifier")
    args = parser.parse_args()

    run_profiler(
        num_frames=args.frames,
        output_path=Path(args.output),
        instance_type=args.instance_type,
    )


if __name__ == "__main__":
    main()
