"""SeeGuide Text Detection & OCR Tier
Integrates OpenCV Zoo DB (Real-time Scene Text Detection) and CRNN recognition
via cv2.dnn TextDetectionModel_DB and TextRecognitionModel with safe offline dummy fallbacks.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

logger = logging.getLogger("seeguide.vision.ocr")


class TextRecognizer:
    """OpenCV 5 DNN Scene Text Detector and Recognizer."""

    def __init__(
        self,
        det_model_path: Optional[str] = None,
        rec_model_path: Optional[str] = None,
        vocabulary_path: Optional[str] = None,
    ):
        self.is_dummy: bool = True
        self.detector = None
        self.recognizer = None

        det_file = Path(det_model_path) if det_model_path else Path("models/text_detection_DB.onnx")
        rec_file = Path(rec_model_path) if rec_model_path else Path("models/text_recognition_CRNN.onnx")

        if det_file.exists() and rec_file.exists():
            try:
                # Initialize DB text detector
                det_net = cv2.dnn.readNet(str(det_file))
                self.detector = cv2.dnn.TextDetectionModel_DB(det_net)
                self.detector.setBinaryThreshold(0.3)
                self.detector.setPolygonThreshold(0.5)
                self.detector.setUnclipRatio(2.0)
                self.detector.setMaxCandidate(200)
                self.detector.setInputParams(
                    1.0 / 255.0,
                    (736, 736),
                    (123.68, 116.78, 103.94),
                    True,
                    False,
                )

                # Initialize CRNN text recognizer
                rec_net = cv2.dnn.readNet(str(rec_file))
                self.recognizer = cv2.dnn.TextRecognitionModel(rec_net)
                self.recognizer.setDecodeType("CTC-greedy")
                if vocabulary_path and Path(vocabulary_path).exists():
                    with open(vocabulary_path, "r", encoding="utf-8") as f:
                        vocab = [line.strip("\r\n") for line in f]
                    self.recognizer.setVocabulary(vocab)
                self.recognizer.setInputParams(
                    1.0 / 127.5,
                    (100, 32),
                    (127.5, 127.5, 127.5),
                    True,
                )

                self.is_dummy = False
                logger.info("Loaded OpenCV OCR models successfully.")
            except Exception as e:
                logger.warning("Failed to initialize cv2.dnn OCR models: %s. Using dummy fallback.", e)
                self.is_dummy = True
        else:
            logger.info("OCR model files not found (%s, %s). Operating in safe offline dummy mode.", det_file, rec_file)
            self.is_dummy = True

    def read(
        self,
        frame: np.ndarray,
        rois: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """Detects and reads text in the frame or specified ROIs.

        Args:
            frame: Input BGR image.
            rois: Optional specific bounding boxes to read.

        Returns:
            Dictionary containing extracted text, confidence, and clipped boolean.
        """
        if self.is_dummy or self.detector is None:
            return {
                "text": None,
                "confidence": 0.0,
                "clipped": False,
            }

        h, w = frame.shape[:2]
        try:
            boxes, confs = self.detector.detect(frame)
        except Exception as e:
            logger.warning("Error during text detection: %s", e)
            return {"text": None, "confidence": 0.0, "clipped": False}

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

            if self.recognizer is not None:
                try:
                    # Crop and recognize
                    token = self.recognizer.recognize(frame, box)
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
