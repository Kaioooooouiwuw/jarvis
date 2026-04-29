"""
═══════════════════════════════════════════════════════════════
  Detecção de Pessoas — Person Detector
═══════════════════════════════════════════════════════════════

Detecta pessoas no frame usando:
  • Primário: YOLOv8 (ultralytics) — preciso e rápido
  • Fallback: OpenCV HOG + SVM — sem dependências extras

Retorna bounding boxes de todas as pessoas detectadas.
"""

import logging

logger = logging.getLogger(__name__)

# ── Backend detection ────────────────────────────────────────
_YOLO_OK = False
_OPENCV_OK = False

try:
    from ultralytics import YOLO
    _YOLO_OK = True
except ImportError:
    pass

try:
    import cv2
    _OPENCV_OK = True
except ImportError:
    pass


class PersonDetector:
    """Detector de pessoas com backend dual (YOLO / HOG)."""

    def __init__(self, confidence: float = 0.5, use_yolo: bool = True):
        """
        Args:
            confidence: Confiança mínima para detecção.
            use_yolo: Se True, tenta usar YOLO primeiro.
        """
        self.confidence = confidence
        self._use_yolo = use_yolo and _YOLO_OK
        self._model = None
        self._hog = None
        self._backend = "none"

    def start(self) -> bool:
        """Inicializa detector. Retorna True se OK."""
        if self._use_yolo:
            try:
                self._model = YOLO("yolov8n.pt")
                self._backend = "yolov8"
                logger.info("[PersonDetector] Backend: YOLOv8n")
                return True
            except Exception as e:
                logger.warning(f"[PersonDetector] YOLO falhou: {e}")
                self._use_yolo = False

        # Fallback: HOG
        if _OPENCV_OK:
            try:
                import cv2
                self._hog = cv2.HOGDescriptor()
                self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
                self._backend = "hog"
                logger.info("[PersonDetector] Backend: OpenCV HOG+SVM")
                return True
            except Exception as e:
                logger.error(f"[PersonDetector] HOG falhou: {e}")

        logger.error("[PersonDetector] Nenhum backend disponível")
        return False

    def detectar(self, frame) -> list:
        """
        Detecta pessoas no frame.

        Args:
            frame: Frame BGR (numpy array).

        Returns:
            Lista de dicts:
            [
                {
                    "bbox": (x1, y1, x2, y2),
                    "confianca": float,
                },
                ...
            ]
        """
        if self._use_yolo and self._model:
            return self._detectar_yolo(frame)
        elif self._hog is not None:
            return self._detectar_hog(frame)
        return []

    def _detectar_yolo(self, frame) -> list:
        """Detecção via YOLOv8."""
        results = self._model(frame, verbose=False, classes=[0])  # class 0 = person
        detections = []

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].int().tolist()
                conf = float(box.conf[0])

                if conf >= self.confidence:
                    detections.append({
                        "bbox": (x1, y1, x2, y2),
                        "confianca": conf,
                    })

        return detections

    def _detectar_hog(self, frame) -> list:
        """Detecção via OpenCV HOG+SVM (fallback)."""
        boxes, weights = self._hog.detectMultiScale(
            frame, winStride=(8, 8), padding=(4, 4), scale=1.05
        )

        detections = []
        for (x, y, w, h), weight in zip(boxes, weights):
            if float(weight) >= self.confidence:
                detections.append({
                    "bbox": (int(x), int(y), int(x + w), int(y + h)),
                    "confianca": float(weight),
                })

        return detections

    @property
    def backend(self) -> str:
        return self._backend

    def stop(self):
        """Libera recursos."""
        self._model = None
        self._hog = None
        logger.info("[PersonDetector] Encerrado")
