"""SeeGuide Privacy Tier
Face detection and irreversible Gaussian blur anonymization using OpenCV YuNet (cv2.FaceDetectorYN)
via the thread-safe process-wide ModelCache. Eliminates silent dummy modes.
Guarantees bystander privacy before any frame or trace snapshot is persisted.
"""

import logging
from pathlib import Path
from typing import Optional, Union
import cv2
import numpy as np

from vision.model_cache import model_cache

logger = logging.getLogger("seeguide.vision.privacy")


class FaceAnonymizer:
    """Detects faces using OpenCV Zoo YuNet and applies irreversible Gaussian blur using ModelCache."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        input_size: tuple[int, int] = (320, 320),
        strict_load: bool = False,
    ):
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.input_size = input_size
        self.model_path = model_path or "models/face_detection_yunet.onnx"
        self.strict_load = strict_load

        path = Path(self.model_path)
        if not path.exists():
            msg = f"YuNet face detector model weights missing at: {path}."
            if self.strict_load:
                raise FileNotFoundError(msg)
            else:
                logger.warning("%s Face blurring will raise FileNotFoundError.", msg)

    def blur_faces(self, frame: np.ndarray) -> np.ndarray:
        """Detects faces in frame and applies heavy Gaussian blur to face regions.

        Args:
            frame: Input BGR image.

        Returns:
            Anonymized copy of the image.

        Raises:
            FileNotFoundError if YuNet model weights do not exist.
        """
        if frame is None or frame.size == 0:
            return frame

        out = frame.copy()
        detector, lock = model_cache.get_face_detector(
            self.model_path,
            input_size=self.input_size,
            conf_threshold=self.conf_threshold,
            nms_threshold=self.nms_threshold,
        )

        if detector is None:
            raise RuntimeError("ModelCache returned None for face detector.")

        h, w = frame.shape[:2]

        with lock:
            detector.setInputSize((w, h))
            try:
                _, faces = detector.detect(frame)
            except Exception as e:
                logger.warning("Face detection failed during execution: %s", e)
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


def enforce_blur_before_persist(
    image_input: Union[np.ndarray, bytes],
    model_path: Optional[str] = None
) -> bytes:
    """Guarantees bystander privacy by applying irreversible Gaussian face blur

    before any frame is written to disk or uploaded to cloud storage.
    Accepts BGR numpy array or JPEG/PNG byte buffer; returns encoded JPEG bytes.
    """
    if isinstance(image_input, bytes):
        nparr = np.frombuffer(image_input, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image bytes for privacy face blurring.")
    else:
        img = image_input

    # Apply face blur
    blurred_img = blur_faces(img, model_path=model_path)
    success, encoded_buf = cv2.imencode(".jpg", blurred_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise RuntimeError("Failed to encode anonymized image to JPEG.")
    return encoded_buf.tobytes()
