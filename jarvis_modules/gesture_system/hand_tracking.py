"""
═══════════════════════════════════════════════════════════════
  Módulo de Rastreamento de Mãos — MediaPipe Hands
═══════════════════════════════════════════════════════════════

Detecta e rastreia 21 landmarks por mão em tempo real.
Suporta desenho de landmarks com estilos customizados.
"""

import logging

logger = logging.getLogger(__name__)


class HandTracker:
    """Wrapper para MediaPipe Hands com detecção de landmarks."""

    def __init__(
        self,
        max_hands: int = 1,
        detection_confidence: float = 0.7,
        tracking_confidence: float = 0.5,
    ):
        self.max_hands = max_hands
        self.detection_confidence = detection_confidence
        self.tracking_confidence = tracking_confidence
        self._hands = None
        self._mp_hands = None
        self._mp_draw = None
        self._mp_styles = None

    def start(self) -> bool:
        """Inicializa MediaPipe Hands. Retorna True se OK."""
        try:
            import mediapipe as mp

            self._mp_hands = mp.solutions.hands
            self._mp_draw = mp.solutions.drawing_utils

            # drawing_styles pode não existir em versões antigas
            try:
                self._mp_styles = mp.solutions.drawing_styles
            except AttributeError:
                self._mp_styles = None

            self._hands = self._mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_hands,
                min_detection_confidence=self.detection_confidence,
                min_tracking_confidence=self.tracking_confidence,
            )

            logger.info(
                f"[HandTracker] MediaPipe Hands iniciado "
                f"(max_hands={self.max_hands}, "
                f"det={self.detection_confidence}, "
                f"track={self.tracking_confidence})"
            )
            return True

        except ImportError:
            logger.error("[HandTracker] MediaPipe não instalado. Execute: pip install mediapipe")
            return False
        except Exception as e:
            logger.error(f"[HandTracker] Erro ao iniciar: {e}")
            return False

    def process(self, rgb_frame):
        """
        Processa frame RGB e retorna resultados do MediaPipe.

        Args:
            rgb_frame: Frame em formato RGB (numpy array).

        Returns:
            MediaPipe results com multi_hand_landmarks ou None.
        """
        if self._hands is None:
            return None
        return self._hands.process(rgb_frame)

    def draw_landmarks(self, frame_bgr, hand_landmarks):
        """
        Desenha landmarks e conexões sobre frame BGR.

        Args:
            frame_bgr: Frame em formato BGR para desenho.
            hand_landmarks: Landmarks de uma mão detectada.
        """
        if self._mp_draw is None or self._mp_hands is None:
            return

        if self._mp_styles is not None:
            self._mp_draw.draw_landmarks(
                frame_bgr,
                hand_landmarks,
                self._mp_hands.HAND_CONNECTIONS,
                self._mp_styles.get_default_hand_landmarks_style(),
                self._mp_styles.get_default_hand_connections_style(),
            )
        else:
            self._mp_draw.draw_landmarks(
                frame_bgr,
                hand_landmarks,
                self._mp_hands.HAND_CONNECTIONS,
            )

    def stop(self):
        """Libera recursos do MediaPipe."""
        if self._hands is not None:
            self._hands.close()
            self._hands = None
            logger.info("[HandTracker] MediaPipe encerrado")
