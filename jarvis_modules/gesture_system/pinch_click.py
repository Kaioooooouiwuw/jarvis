"""
═══════════════════════════════════════════════════════════════
  Módulo de Clique por Pinça (Pinch Click) v2.0
═══════════════════════════════════════════════════════════════

Substitui TODOS os cliques antigos por pinça (polegar + indicador):
  • 🤏 Pinça rápida (abrir e fechar < 300ms) → Clique simples
  • 🤏 Pinça segurando (fechada > 300ms)      → Drag and Drop (segurar clique)

Técnicas:
  • Distância thumb tip (lm[4]) ↔ index tip (lm[8])
  • Hysteresis: threshold_enter < threshold_exit (evita flickering)
  • Timer de confirmação para distinguir clique vs drag
  • On release: se segurou → soltar drag; se rápido → clique
  • Cooldown entre cliques para evitar spam

Integrado via hand landmarks — sem microfone necessário.
"""

import time
import threading
import logging

logger = logging.getLogger(__name__)


class PinchClickDetector:
    """Detector de cliques e drag baseado em gesto de pinça (polegar + indicador)."""

    def __init__(
        self,
        pinch_threshold: float = 0.045,
        release_threshold: float = 0.065,
        drag_time: float = 0.30,
        cooldown: float = 0.25,
    ):
        """
        Args:
            pinch_threshold: Distância máxima thumb↔index para entrar em pinça.
            release_threshold: Distância mínima para sair do estado de pinça
                               (hysteresis para evitar flickering).
            drag_time: Tempo (seg) que a pinça deve ser mantida fechada para
                       ativar drag mode. Se soltar antes → clique simples.
            cooldown: Tempo mínimo (seg) entre cliques executados.
        """
        self.pinch_threshold = pinch_threshold
        self.release_threshold = release_threshold
        self.drag_time = drag_time
        self.cooldown = cooldown

        # ── Estado da pinça ──────────────────────────────────
        self._is_pinching = False
        self._pinch_start_time = 0.0
        self._is_dragging = False       # True se a pinça virou drag

        # ── Cooldown de cliques ──────────────────────────────
        self._last_click_time = 0.0

        # ── Callbacks ────────────────────────────────────────
        self.on_click = None           # Chamado para clique simples (pinça rápida)
        self.on_drag_start = None      # Chamado quando entra em drag (pinça segurando)
        self.on_drag_end = None        # Chamado quando solta drag

        # ── Status para HUD ──────────────────────────────────
        self.last_event = ""           # "🤏" ou "🤏✊"
        self.last_event_time = 0.0
        self.is_currently_pinching = False  # Para feedback visual em tempo real
        self.is_currently_dragging = False  # Para feedback visual de drag
        self._lock = threading.Lock()

    def update(self, thumb_tip, index_tip):
        """
        Atualiza a cada frame com as posições do polegar e indicador.
        Deve ser chamado a cada frame do loop de gestos.

        Args:
            thumb_tip: MediaPipe landmark do polegar (lm[4]).
            index_tip: MediaPipe landmark do indicador (lm[8]).
        """
        dist = self._dist_2d(thumb_tip, index_tip)
        now = time.time()

        with self._lock:
            if not self._is_pinching:
                # ── Verificar se entrou em pinça ─────────────
                if dist < self.pinch_threshold:
                    self._is_pinching = True
                    self._pinch_start_time = now
                    self._is_dragging = False
                    self.is_currently_pinching = True
                    logger.debug(f"[PinchClick] Pinça INICIADA (dist={dist:.3f})")
            else:
                # ── Já está em pinça ─────────────────────────
                held_duration = now - self._pinch_start_time

                if dist > self.release_threshold:
                    # ── SOLTOU a pinça ────────────────────────
                    self._is_pinching = False
                    self.is_currently_pinching = False

                    if self._is_dragging:
                        # Estava em drag → soltar drag
                        self._is_dragging = False
                        self.is_currently_dragging = False
                        self.last_event = "🤏↑"
                        self.last_event_time = now
                        logger.info("[PinchClick] 🤏↑ DRAG FINALIZADO (pinça solta)")
                        if self.on_drag_end:
                            threading.Thread(target=self.on_drag_end, daemon=True).start()
                    elif held_duration < self.drag_time:
                        # Pinça rápida → CLIQUE SIMPLES
                        if now - self._last_click_time >= self.cooldown:
                            self._last_click_time = now
                            self.last_event = "🤏"
                            self.last_event_time = now
                            logger.info("[PinchClick] 🤏 CLIQUE SIMPLES (pinça rápida)")
                            if self.on_click:
                                threading.Thread(target=self.on_click, daemon=True).start()
                        else:
                            logger.debug("[PinchClick] Cooldown ativo — ignorando clique")
                    # Se held_duration >= drag_time mas já despachou drag_start, não faz nada

                else:
                    # ── Ainda segurando pinça ─────────────────
                    if not self._is_dragging and held_duration >= self.drag_time:
                        # Segurou por tempo suficiente → ativar DRAG
                        self._is_dragging = True
                        self.is_currently_dragging = True
                        self.last_event = "🤏✊"
                        self.last_event_time = now
                        logger.info("[PinchClick] 🤏✊ DRAG INICIADO (pinça segurando)")
                        if self.on_drag_start:
                            threading.Thread(target=self.on_drag_start, daemon=True).start()

    def reset(self):
        """Reseta estado (chamado ao encerrar gestos)."""
        with self._lock:
            if self._is_dragging and self.on_drag_end:
                # Soltar drag se estiver ativo
                try:
                    self.on_drag_end()
                except Exception:
                    pass
            self._is_pinching = False
            self._is_dragging = False
            self.is_currently_pinching = False
            self.is_currently_dragging = False

    @staticmethod
    def _dist_2d(a, b) -> float:
        """Distância 2D entre dois landmarks."""
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
