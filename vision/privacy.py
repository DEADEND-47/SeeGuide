"""SeeGuide Privacy Tier
Face detection and irreversible Gaussian blur anonymization using OpenCV YuNet (cv2.FaceDetectorYN).
Guarantees bystander privacy before any frame or trace snapshot is persisted.
"""

import logging
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np

logger = logging.getLogger("seeguide.vision.privacy")


class FaceAnonymizer:
    """Detects faces using OpenCV Zoo YuNet and applies irreversible Gaussian blur."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        input_size: tuple[int, int] = (320, 320),
    ):
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.input_size = input_size
        self.detector = None
        self.is_dummy = True

        model_file = Path(model_path) if model_path else Path("models/face_detection_yunet.onnx")
        if model_file.exists():
            try:
                self.detector = cv2.FaceDetectorYN.create(
                    model=str(model_file),
                    config="",
                    input_size=self.input_size,
                    score_threshold=self.conf_threshold,
                    nms_threshold=self.nms_threshold,
                    top_k=50,
                    backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
                    target_id=cv2.dnn.DNN_TARGET_CPU,
                )
                self.is_dummy = False
                logger.info("Loaded YuNet face detector from %s", model_file)
            except Exception as e:
                logger.warning("Failed to initialize FaceDetectorYN from %s: %s. Using dummy fallback.", model_file, e)
                self.is_dummy = True
        else:
            logger.info("YuNet model file not found at %s. Operating in safe offline dummy mode.", model_file)
            self.is_dummy = True

    def blur_faces(self, frame: np.ndarray) -> np.ndarray:
        """Detects faces in frame and applies heavy Gaussian blur to face regions.

        Args:
            frame: Input BGR image.

        Returns:
            Anonymized copy of the image.
        """
        if frame is None or frame.size == 0:
            return frame

        out = frame.copy()
        if self.is_dummy or self.detector is None:
            return out

        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))

        try:
            _, faces = self.detector.detect(frame)
        except Exception as e:
            logger.warning("Face detection failed: %s", e)
            return out

        if faces is not None and len(faces) > 0:
            for face in faces:
                fx = max(0, int(face[0]))
                fy = max(0, int(face[1]))
                fw = min(w - fx, int(face[2]))
                fh = min(h - fy, int(face[3]))

                if fw > 4 and fh > 4:
                    face_roi = out[fy : fy + fh, fx : fx + fw]
                    # Ensure kernel size is odd
                    k_w = max(15, (fw // 3) | 1)
                    k_h = max(15, (fh // 3) | 1)
                    blurred = cv2.GaussianBlur(face_roi, (k_w, k_h), 30)
                    out[fy : fy + fh, fx : fx + fw] = blurred

        return out


# Global singleton instance for convenient functional invocation
_default_anonymizer = FaceAnonymizer()


def blur_faces(frame: np.ndarray, model_path: Optional[str] = None) -> np.ndarray:
    """Functional interface for face blurring."""
    if model_path:
        anonymizer = FaceAnonymizer(model_path=model_path)
        return anonymizer.blur_faces(frame)
    return _default_anonymizer.blur_faces(frame)
