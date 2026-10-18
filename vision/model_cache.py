"""SeeGuide Process-Wide Thread-Safe Model Cache
Maintains a thread-safe Singleton ModelCache for OpenCV 5 DNN networks and detectors.
Loads heavy ONNX weights exactly ONCE per process to prevent memory exhaustion (OOM)
on AWS Free Tier instances (e.g. EC2 t4g.micro with 1GB RAM).

Each model accessor returns a tuple of:
    (model_instance, threading.Lock)
ensuring thread-safe inference when FastAPI executes concurrent worker threads via asyncio.to_thread.
"""

import logging
from pathlib import Path
import threading
from typing import Any, Dict, Optional, Tuple
import cv2

logger = logging.getLogger("seeguide.vision.model_cache")


class ModelCache:
    """Thread-safe process-wide singleton cache for OpenCV Zoo models."""

    _instance: Optional["ModelCache"] = None
    _init_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ModelCache":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        with self._init_lock:
            if getattr(self, "_initialized", False):
                return
            self._models: Dict[str, Any] = {}
            self._locks: Dict[str, threading.Lock] = {}
            self._cache_lock = threading.Lock()
            self._initialized = True
            logger.info("Initialized process-wide ModelCache singleton.")

    def get_detector(self, model_path: str) -> Tuple[Optional[cv2.dnn.Net], threading.Lock]:
        """Loads and returns the cached YOLOX object detection cv2.dnn.Net and its inference lock.
        
        Raises FileNotFoundError if model_path does not exist on disk (no silent dummy modes).
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Object detector model not found at: {path}")

        key = f"detector:{path.resolve()}"
        with self._cache_lock:
            if key not in self._models:
                logger.info("Loading object detector into process cache from %s...", path)
                net = cv2.dnn.readNetFromONNX(str(path))
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self._models[key] = net
                self._locks[key] = threading.Lock()
                logger.info("Object detector successfully cached under key: %s", key)
            return self._models[key], self._locks[key]

    def get_text_detector(self, model_path: str) -> Tuple[Optional[cv2.dnn.TextDetectionModel_DB], threading.Lock]:
        """Loads and returns the cached DB text detection model and its inference lock.
        
        Raises FileNotFoundError if model_path does not exist on disk.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Text detector model not found at: {path}")

        key = f"text_det:{path.resolve()}"
        with self._cache_lock:
            if key not in self._models:
                logger.info("Loading text detector into process cache from %s...", path)
                det_net = cv2.dnn.readNet(str(path))
                detector = cv2.dnn.TextDetectionModel_DB(det_net)
                detector.setBinaryThreshold(0.3)
                detector.setPolygonThreshold(0.5)
                detector.setUnclipRatio(2.0)
                detector.setMaxCandidates(200)
                detector.setInputParams(
                    1.0 / 255.0,
                    (736, 736),
                    (123.68, 116.78, 103.94),
                    True,
                    False,
                )
                self._models[key] = detector
                self._locks[key] = threading.Lock()
                logger.info("Text detector successfully cached under key: %s", key)
            return self._models[key], self._locks[key]

    def get_text_recognizer(
        self,
        model_path: str,
        vocabulary_path: Optional[str] = None
    ) -> Tuple[Optional[cv2.dnn.TextRecognitionModel], threading.Lock]:
        """Loads and returns the cached CRNN text recognition model and its inference lock.
        
        Raises FileNotFoundError if model_path does not exist on disk.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Text recognizer model not found at: {path}")

        key = f"text_rec:{path.resolve()}:{vocabulary_path}"
        with self._cache_lock:
            if key not in self._models:
                logger.info("Loading text recognizer into process cache from %s...", path)
                rec_net = cv2.dnn.readNet(str(path))
                recognizer = cv2.dnn.TextRecognitionModel(rec_net)
                recognizer.setDecodeType("CTC-greedy")
                
                # Check vocabulary
                vocab_file = Path(vocabulary_path) if vocabulary_path else Path("models/charset_36_EN.txt")
                if vocab_file.exists():
                    with open(vocab_file, "r", encoding="utf-8") as f:
                        vocab = [line.strip("\r\n") for line in f if line.strip("\r\n")]
                    recognizer.setVocabulary(vocab)
                    logger.info("Loaded OCR vocabulary with %d characters from %s", len(vocab), vocab_file)

                recognizer.setInputParams(
                    1.0 / 127.5,
                    (100, 32),
                    (127.5, 127.5, 127.5),
                    True,
                )
                self._models[key] = recognizer
                self._locks[key] = threading.Lock()
                logger.info("Text recognizer successfully cached under key: %s", key)
            return self._models[key], self._locks[key]

    def get_face_detector(
        self,
        model_path: str,
        input_size: Tuple[int, int] = (320, 320),
        conf_threshold: float = 0.6,
        nms_threshold: float = 0.3,
    ) -> Tuple[Optional[cv2.FaceDetectorYN], threading.Lock]:
        """Loads and returns the cached YuNet face detector and its inference lock.
        
        Raises FileNotFoundError if model_path does not exist on disk.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Face detector model not found at: {path}")

        key = f"face_det:{path.resolve()}"
        with self._cache_lock:
            if key not in self._models:
                logger.info("Loading YuNet face detector into process cache from %s...", path)
                detector = cv2.FaceDetectorYN.create(
                    model=str(path),
                    config="",
                    input_size=input_size,
                    score_threshold=conf_threshold,
                    nms_threshold=nms_threshold,
                    top_k=50,
                    backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
                    target_id=cv2.dnn.DNN_TARGET_CPU,
                )
                self._models[key] = detector
                self._locks[key] = threading.Lock()
                logger.info("Face detector successfully cached under key: %s", key)
            return self._models[key], self._locks[key]

    def clear(self) -> None:
        """Clears all cached models and locks."""
        with self._cache_lock:
            self._models.clear()
            self._locks.clear()
            logger.info("Cleared ModelCache.")


# Global singleton instance
model_cache = ModelCache()
