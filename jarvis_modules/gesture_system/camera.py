"""
═══════════════════════════════════════════════════════════════
  Módulo de Captura de Vídeo — Webcam
═══════════════════════════════════════════════════════════════

Gerencia ciclo de vida da webcam com:
  • Inicialização sob demanda (ativada por voz)
  • 30 FPS mínimo
  • Conversão BGR → RGB automática
  • Mirror (flip horizontal)
  • Thread-safe
"""

import logging
import threading

logger = logging.getLogger(__name__)


class Camera:
    """Wrapper thread-safe para cv2.VideoCapture."""

    def __init__(self, device_id: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        self._cap = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Inicializa webcam. Retorna True se abriu com sucesso."""
        try:
            import cv2
        except ImportError:
            logger.error("[Camera] OpenCV não instalado. Execute: pip install opencv-python")
            return False

        with self._lock:
            if self._cap is not None and self._cap.isOpened():
                return True  # Já aberta

            # Auto-detectar webcam real (ignora virtual como Animaze)
            try:
                from jarvis_modules.security_system.camera_utils import encontrar_webcam_real
                real_idx = encontrar_webcam_real()
            except ImportError:
                real_idx = self.device_id

            self._cap = cv2.VideoCapture(real_idx, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                logger.error("[Camera] Não foi possível abrir a webcam")
                self._cap = None
                return False

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)

            # Log resolução real obtida
            real_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            real_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            real_fps = int(self._cap.get(cv2.CAP_PROP_FPS))
            logger.info(f"[Camera] Webcam iniciada: {real_w}x{real_h} @ {real_fps}fps")
            return True

    def read(self):
        """
        Lê um frame da webcam.

        Returns:
            (success, frame_bgr, frame_rgb) — frame_bgr para exibição,
            frame_rgb para processamento MediaPipe.
        """
        import cv2

        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                return False, None, None

            ret, frame = self._cap.read()
            if not ret:
                return False, None, None

            # Mirror horizontal para feedback natural
            frame = cv2.flip(frame, 1)
            # Conversão para RGB (MediaPipe exige RGB)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return True, frame, rgb

    def stop(self):
        """Libera webcam."""
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                logger.info("[Camera] Webcam encerrada")

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()
