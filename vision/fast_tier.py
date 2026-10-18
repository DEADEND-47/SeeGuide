"""SeeGuide Fast-Tier Vision Perception
Executes ultra-lightweight frame analysis on every incoming video frame:
- Laplacian variance blur metric
- Grayscale luma/brightness intensity
- Dynamic walking corridor edge density
- Dense optical flow ego-motion and divergence
"""

from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np

# Standard processing width for CPU efficiency
FAST_WIDTH = 320


def process_fast(
    frame: np.ndarray,
    prev_frame: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Processes a video frame through fast-tier OpenCV 5 algorithms.

    Args:
        frame: BGR image array (uint8)
        prev_frame: Previous frame for optical flow calculation (optional)

    Returns:
        Dictionary containing quality, motion, and corridor metrics.
    """
    if frame is None or frame.size == 0:
        raise ValueError("Invalid or empty frame provided to process_fast")

    # 1. Resize to standardized resolution preserving aspect ratio
    h, w = frame.shape[:2]
    scale = FAST_WIDTH / float(w)
    fast_h = max(int(h * scale), 1)
    resized = cv2.resize(frame, (FAST_WIDTH, fast_h), interpolation=cv2.INTER_LINEAR)

    # 2. Convert to grayscale
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if len(resized.shape) == 3 else resized

    # 3. Quality Metrics
    # Blur score using Laplacian variance
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    blur_score = float(laplacian.var())

    # Brightness (mean pixel intensity)
    brightness = float(np.mean(gray))

    # Stability heuristic: reasonable blur and illumination
    stable = bool(blur_score >= 25.0 and 30.0 <= brightness <= 225.0)

    # 4. Corridor ROI & Edge Density
    # Corridor defined as central 50% horizontal swath, lower 70% vertical
    x_start = int(FAST_WIDTH * 0.25)
    x_end = int(FAST_WIDTH * 0.75)
    y_start = int(fast_h * 0.30)
    y_end = fast_h

    corridor_roi = gray[y_start:y_end, x_start:x_end]
    if corridor_roi.size > 0:
        edges = cv2.Canny(corridor_roi, 50, 150)
        edge_density = float(np.count_nonzero(edges) / edges.size)
    else:
        edge_density = 0.0

    # 5. Motion Metrics (Dense Optical Flow)
    ego_motion = 0.0
    corridor_divergence = 0.0

    if prev_frame is not None and prev_frame.size > 0:
        prev_resized = cv2.resize(prev_frame, (FAST_WIDTH, fast_h), interpolation=cv2.INTER_LINEAR)
        prev_gray = cv2.cvtColor(prev_resized, cv2.COLOR_BGR2GRAY) if len(prev_resized.shape) == 3 else prev_resized

        # Farneback dense optical flow
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray,
            gray,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )

        # Flow magnitude inside corridor
        corridor_flow = flow[y_start:y_end, x_start:x_end]
        if corridor_flow.size > 0:
            mag, _ = cv2.cartToPolar(corridor_flow[..., 0], corridor_flow[..., 1])
            ego_motion = float(np.mean(mag))

            # Divergence: partial derivative sum (du/dx + dv/dy)
            du_dx = np.gradient(corridor_flow[..., 0], axis=1)
            dv_dy = np.gradient(corridor_flow[..., 1], axis=0)
            corridor_divergence = float(np.mean(du_dx + dv_dy))

    return {
        "quality": {
            "blur": round(blur_score, 2),
            "brightness": round(brightness, 2),
            "stable": stable,
        },
        "motion": {
            "corridor_divergence": round(corridor_divergence, 3),
            "ego_motion": round(ego_motion, 3),
        },
        "corridor": {
            "edge_density": round(edge_density, 3),
            "blocked_score": 0.0,
        },
    }
