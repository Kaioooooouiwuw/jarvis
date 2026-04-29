"""
═══════════════════════════════════════════════════════════════
  Reconhecimento de Gestos v4.1 — Pinça + Punho Restaurado
═══════════════════════════════════════════════════════════════

Gestos detectados:
  🖐 Mão aberta     → Mover cursor
  👌 OK             → Modo abas
  ☝️ Apontar        → Cursor preciso
  ✌️ Paz (V)        → Screenshot
  🤙 Scroll         → 2 dedos juntos + mov. vertical
  🤏 Pinça          → Clique / Drag (via PinchClickDetector)
  ✊ Punho           → Drag and Drop (alternativa à pinça segurando)

Técnicas:
  • Debounce configurável (frames consecutivos)
  • Detecção de curvatura por distância tip → pip
  • Suporte a mão esquerda/direita
  • Detecção de velocidade do gesto
"""

import time
import logging

logger = logging.getLogger(__name__)


class GestureRecognizer:
    """Classificador de gestos avançado com debounce e velocidade."""

    # ── Constantes de gestos ─────────────────────────────────
    OPEN_HAND = "mao_aberta"
    OK = "ok"
    POINT = "apontar"
    PEACE = "paz"
    SCROLL = "scroll"
    FIST = "punho"
    UNKNOWN = "desconhecido"

    def __init__(self, debounce_frames: int = 3):
        """
        Args:
            debounce_frames: Frames consecutivos necessários para confirmar gesto.
        """
        self.debounce_frames = debounce_frames
        self._current_gesture = self.UNKNOWN
        self._gesture_counter = 0
        self._confirmed_gesture = self.UNKNOWN

        # ── Tracking de velocidade ───────────────────────────
        self._prev_wrist_y = 0.0
        self._prev_wrist_x = 0.0
        self._velocity_y = 0.0
        self._velocity_x = 0.0
        self._prev_time = time.time()

    def recognize(self, hand_landmarks) -> tuple:
        """
        Classifica o gesto da mão.

        Args:
            hand_landmarks: MediaPipe hand landmarks.

        Returns:
            (gesture_name, fingers_state, is_confirmed, extra_data)
            extra_data: dict com informações extras (velocidade, etc.)
        """
        lm = hand_landmarks.landmark

        # ── Detectar estado dos dedos ────────────────────────
        fingers = self._detect_fingers(lm)

        # ── Calcular velocidade ──────────────────────────────
        now = time.time()
        dt = now - self._prev_time
        if dt > 0:
            self._velocity_y = (lm[0].y - self._prev_wrist_y) / dt
            self._velocity_x = (lm[0].x - self._prev_wrist_x) / dt
        self._prev_wrist_y = lm[0].y
        self._prev_wrist_x = lm[0].x
        self._prev_time = now

        # ── Classificar gesto ────────────────────────────────
        gesture = self._classify(fingers, lm)

        # ── Debounce ─────────────────────────────────────────
        if gesture == self._current_gesture:
            self._gesture_counter += 1
        else:
            self._current_gesture = gesture
            self._gesture_counter = 1

        confirmed = self._gesture_counter >= self.debounce_frames
        if confirmed:
            self._confirmed_gesture = gesture

        # ── Extra data ───────────────────────────────────────
        extra = {
            "velocity_x": self._velocity_x,
            "velocity_y": self._velocity_y,
            "speed": abs(self._velocity_x) + abs(self._velocity_y),
        }

        return gesture, fingers, confirmed, extra

    def _detect_fingers(self, lm) -> list:
        """
        Detecta quais dedos estão estendidos.

        Returns:
            [thumb, index, middle, ring, pinky] — True se estendido.
        """
        fingers = []

        # Polegar — comparar x do tip vs pip (funciona para mão direita)
        # Usar distância do tip ao wrist vs pip ao wrist para robustez
        thumb_tip = lm[4]
        thumb_pip = lm[3]
        thumb_mcp = lm[2]

        # Polegar: tip mais longe do palm center que pip
        palm_x = lm[0].x
        thumb_extended = abs(thumb_tip.x - palm_x) > abs(thumb_pip.x - palm_x)
        fingers.append(thumb_extended)

        # Dedos 2-5: tip acima do pip (y menor = mais acima)
        finger_tips = [8, 12, 16, 20]   # Index, Middle, Ring, Pinky
        finger_pips = [6, 10, 14, 18]

        for tip_id, pip_id in zip(finger_tips, finger_pips):
            fingers.append(lm[tip_id].y < lm[pip_id].y)

        return fingers

    def _classify(self, fingers: list, lm) -> str:
        """Classifica gesto baseado nos dedos e posições."""
        thumb, index, middle, ring, pinky = fingers
        extended_count = sum(fingers)

        # ── Mão aberta (4-5 dedos) ───────────────────────────
        if extended_count >= 4:
            return self.OPEN_HAND

        # ── Apontar (só indicador) ───────────────────────────
        if index and not middle and not ring and not pinky:
            return self.POINT

        # ── Paz / V (indicador + médio) ──────────────────────
        if index and middle and not ring and not pinky:
            # Verificar se dedos estão separados (V) vs juntos
            index_tip = lm[8]
            middle_tip = lm[12]
            separation = abs(index_tip.x - middle_tip.x)
            if separation > 0.04:  # Dedos em V
                return self.PEACE
            else:
                return self.SCROLL  # Dedos juntos = modo scroll

        # ── OK (polegar + indicador formando círculo) ────────
        if thumb and not pinky:
            thumb_tip = lm[4]
            index_tip = lm[8]
            dist = self._dist_2d(thumb_tip, index_tip)
            if dist < 0.06:
                return self.OK

        # ── Scroll (2 dedos estendidos) ──────────────────────
        if extended_count == 2 and index and middle:
            return self.SCROLL

        # ── Punho / Fist (✊) — todos os dedos fechados ─────
        # RESTAURADO na v4.1: funciona como Drag and Drop
        # alternativo à pinça segurando.
        if extended_count == 0:
            return self.FIST

        # NOTA: A Pinça (🤏) é detectada diretamente pelo PinchClickDetector
        # no loop principal (gestos.py), independente do gesto classificado.
        # Isso permite que a pinça funcione SOBRE qualquer outro gesto,
        # ou seja, onde quer que você faça a pinça, o clique é executado.

        return self.UNKNOWN

    @staticmethod
    def _dist_2d(a, b) -> float:
        """Distância 2D entre dois landmarks."""
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    @property
    def confirmed_gesture(self) -> str:
        return self._confirmed_gesture
