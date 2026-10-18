"""SeeGuide Object Detector Wrapper
Integrates OpenCV Zoo ONNX object detectors (e.g. YOLOX-nano) via cv2.dnn
with safe offline fallback for local zero-dependency testing.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

logger = logging.getLogger("seeguide.vision.detector")

# Standard COCO class subset relevant for pedestrian corridor mobility
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]


class ObjectDetector:
    """OpenCV Zoo ONNX Object Detector using cv2.dnn backend."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.45,
        nms_threshold: float = 0.45,
        input_size: tuple[int, int] = (416, 416),
    ):
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.input_size = input_size
        self.net: Optional[cv2.dnn.Net] = None
        self.is_dummy: bool = True

        model_file = Path(model_path) if model_path else Path("models/yolox_nano.onnx")
        if model_file.exists():
            try:
                self.net = cv2.dnn.readNetFromONNX(str(model_file))
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self.is_dummy = False
                logger.info("Loaded ONNX object detector from %s", model_file)
            except Exception as e:
                logger.warning("Failed to initialize cv2.dnn model from %s: %s. Using dummy fallback.", model_file, e)
                self.is_dummy = True
        else:
            logger.info("ONNX model file not found at %s. Operating in safe offline dummy mode.", model_file)
            self.is_dummy = True

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Runs object detection on input frame.

        Args:
            frame: Input BGR image.

        Returns:
            List of detected objects with keys: cls, conf, bbox [x1, y1, x2, y2].
        """
        if self.is_dummy or self.net is None:
            return []

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            frame,
            scalefactor=1.0 / 255.0,
            size=self.input_size,
            mean=(0, 0, 0),
            swapRB=True,
            crop=False,
        )
        self.net.setInput(blob)
        outputs = self.net.forward()

        # Handle YOLOX / standard detector outputs
        # Output shape is typically [1, num_proposals, 85] (5 box metrics + 80 classes)
        if len(outputs.shape) == 3:
            predictions = outputs[0]
        else:
            predictions = outputs

        boxes = []
        confidences = []
        class_ids = []

        scale_x = w / float(self.input_size[0])
        scale_y = h / float(self.input_size[1])

        for pred in predictions:
            obj_conf = pred[4]
            if obj_conf < self.conf_threshold:
                continue
            class_scores = pred[5:]
            class_id = int(np.argmax(class_scores))
            score = float(class_scores[class_id] * obj_conf)
            if score >= self.conf_threshold:
                cx, cy, bw, bh = pred[0:4]
                x1 = int((cx - bw / 2.0) * scale_x)
                y1 = int((cy - bh / 2.0) * scale_y)
                x2 = int((cx + bw / 2.0) * scale_x)
                y2 = int((cy + bh / 2.0) * scale_y)
                boxes.append([max(0, x1), max(0, y1), min(w, x2), min(h, y2)])
                confidences.append(score)
                class_ids.append(class_id)

        indices = cv2.dnn.NMSBoxes(
            bboxes=[[b[0], b[1], b[2] - b[0], b[3] - b[1]] for b in boxes],
            scores=confidences,
            score_threshold=self.conf_threshold,
            nms_threshold=self.nms_threshold,
        )

        detections = []
        if len(indices) > 0:
            for idx in indices.flatten():
                label = COCO_CLASSES[class_ids[idx]] if class_ids[idx] < len(COCO_CLASSES) else f"class_{class_ids[idx]}"
                detections.append({
                    "cls": label,
                    "conf": round(float(confidences[idx]), 3),
                    "bbox": [float(c) for c in boxes[idx]],
                })

        return detections
