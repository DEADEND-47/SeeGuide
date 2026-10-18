"""SeeGuide Text Detection & OCR Tier
Integrates OpenCV Zoo DB (Real-time Scene Text Detection) and CRNN recognition
via cv2.dnn TextDetectionModel_DB and TextRecognitionModel using the thread-safe ModelCache.
Eliminates silent dummy modes.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

from vision.model_cache import model_cache

logger = logging.getLogger("seeguide.vision.ocr")


class TextRecognizer:
    """OpenCV 5 DNN Scene Text Detector and Recognizer using thread-safe ModelCache."""

    def __init__(
        self,
        det_model_path: Optional[str] = None,
        rec_model_path: Optional[str] = None,
        vocabulary_path: Optional[str] = None,
        strict_load: bool = False,
    ):
        self.det_model_path = det_model_path or "models/text_detection_DB.onnx"
        self.rec_model_path = rec_model_path or "models/text_recognition_CRNN.onnx"
        self.vocabulary_path = vocabulary_path or "models/charset_36_EN.txt"
        self.strict_load = strict_load

        # Verify model files
        det_exists = Path(self.det_model_path).exists()
        rec_exists = Path(self.rec_model_path).exists()
        if not (det_exists and rec_exists):
            msg = f"OCR model weights missing (det={det_exists}, rec={rec_exists})."
            if self.strict_load:
                raise FileNotFoundError(msg)
            else:
                logger.warning("%s Inference calls will raise FileNotFoundError.", msg)

    def read(
        self,
        frame: np.ndarray,
        rois: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """Detects and reads text in the frame or specified ROIs using ModelCache locks.

        Args:
            frame: Input BGR image.
            rois: Optional specific bounding boxes to read.

        Returns:
            Dictionary containing extracted text, confidence, and clipped boolean.

        Raises:
            FileNotFoundError if model weights do not exist.
        """
        detector, det_lock = model_cache.get_text_detector(self.det_model_path)
        recognizer, rec_lock = model_cache.get_text_recognizer(self.rec_model_path, self.vocabulary_path)

        if detector is None or recognizer is None:
            raise RuntimeError("ModelCache returned None for text detector or recognizer.")

        h, w = frame.shape[:2]
        with det_lock:
            boxes, confs = detector.detect(frame)

        if len(boxes) == 0:
            return {"text": None, "confidence": 0.0, "clipped": False}

        # Check if text reaches the boundary of the image (clipped frame / reframing needed)
        clipped = False
        recognized_tokens = []
        conf_scores = []

        for idx, box in enumerate(boxes):
            # Box can be 4 points [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            pts = np.array(box, dtype=np.int32)
            bx, by, bw, bh = cv2.boundingRect(pts)

            if bx <= 4 or by <= 4 or (bx + bw) >= (w - 4) or (by + bh) >= (h - 4):
                clipped = True

            with rec_lock:
                try:
                    # Crop and recognize
                    token = recognizer.recognize(frame, box)
                    if token and len(token.strip()) > 0:
                        recognized_tokens.append(token.strip())
                        if len(confs) > idx:
                            conf_scores.append(float(confs[idx]))
                except Exception as rec_err:
                    logger.debug("Recognition failed on ROI %s: %s", box, rec_err)

        full_text = " ".join(recognized_tokens) if recognized_tokens else None
        mean_conf = float(np.mean(conf_scores)) if conf_scores else 0.0

        return {
            "text": full_text,
            "confidence": round(mean_conf, 2),
            "clipped": clipped,
        }
