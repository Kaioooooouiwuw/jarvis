"""
═══════════════════════════════════════════════════════════════
  Ações do Sistema v4.1 — Automação Avançada por Gestos
═══════════════════════════════════════════════════════════════

Mapeamento completo:
  🖐 Mão aberta        → Cursor (média móvel + aceleração)
  👌 OK                → Trocar abas (mov. lateral)
  ☝️ Apontar           → Cursor preciso (sem aceleração)
  ✌️ Paz (V)           → Screenshot
  🤙 Scroll            → Scroll vertical (mov. vertical)
  🤏 Pinça rápida      → Clique simples (via PinchClickDetector)
  🤏 Pinça segurando   → Drag and Drop (via PinchClickDetector)
  ✊ Punho              → Drag and Drop (alternativa à pinça)

RESTAURADO na v4.1:
  ✊ Punho              → De volta como alternativa para Drag

Multi-monitor: usa ctypes (Windows) para cobrir toda a área
virtual da tela (todos os monitores).
"""

import logging
import time
import os
import ctypes
from collections import deque

logger = logging.getLogger(__name__)


class GestureActions:
    """Motor de automação: converte gestos em ações do sistema."""

    def __init__(self, smoothing_window: int = 5):
        self.smoothing_window = smoothing_window

        # ── Resolução da tela (MULTI-MONITOR via ctypes) ─────
        self.virtual_left = 0
        self.virtual_top = 0
        self.screen_width = 1920
        self.screen_height = 1080
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
        except ImportError:
            logger.warning("[Actions] pyautogui não disponível")

        try:
            user32 = ctypes.windll.user32
            # SM_XVIRTUALSCREEN (76) = left edge of virtual screen
            # SM_YVIRTUALSCREEN (77) = top edge of virtual screen
            # SM_CXVIRTUALSCREEN (78) = total width across all monitors
            # SM_CYVIRTUALSCREEN (79) = total height across all monitors
            self.virtual_left = user32.GetSystemMetrics(76)
            self.virtual_top = user32.GetSystemMetrics(77)
            self.screen_width = user32.GetSystemMetrics(78)
            self.screen_height = user32.GetSystemMetrics(79)
            logger.info(
                f"[Actions] Virtual Screen: "
                f"origin=({self.virtual_left},{self.virtual_top}) "
                f"size={self.screen_width}x{self.screen_height}"
            )
        except Exception as e:
            logger.warning(f"[Actions] Fallback para 1920x1080: {e}")
            self.screen_width = 1920
            self.screen_height = 1080

        # ── Buffers de suavização do cursor ──────────────────
        self._x_buffer = deque(maxlen=smoothing_window)
        self._y_buffer = deque(maxlen=smoothing_window)

        # ── Estado de Drag (agora controlado pela pinça) ─────
        self._dragging = False

        # ── Estado do Modo OK ────────────────────────────────
        self._ok_mode = False
        self._ok_start_x = 0.0
        self._ok_threshold = 0.12
        self._ok_last_action = 0.0
        self._ok_cooldown = 0.8

        # ── Estado de Scroll ─────────────────────────────────
        self._scroll_start_y = 0.0
        self._scroll_active = False
        self._scroll_last_action = 0.0
        self._scroll_cooldown = 0.15      # Mais responsivo que tab switch
        self._scroll_threshold = 0.03     # Movimento mínimo para scroll

        # ── Screenshot cooldown ──────────────────────────────
        self._screenshot_last = 0.0
        self._screenshot_cooldown = 2.0   # 2s entre screenshots

        # ── Debounce de cliques ──────────────────────────────
        self._last_click_time = 0.0
        self._click_cooldown = 0.25

        # ── Contadores ───────────────────────────────────────
        self.total_moves = 0
        self.total_clicks = 0
        self.total_drags = 0
        self.total_tab_switches = 0
        self.total_scrolls = 0
        self.total_screenshots = 0

    # ═══════════════════════════════════════════════════════════
    #  CURSOR — Mão aberta + Apontar (🖐 / ☝️)
    # ═══════════════════════════════════════════════════════════

    def move_cursor(self, hand_x: float, hand_y: float, speed: float = 0.0):
        """
        Move cursor com suavização e aceleração baseada na velocidade.
        Usa ctypes SetCursorPos para suporte multi-monitor.

        Args:
            hand_x/y: Coordenadas normalizadas (0-1).
            speed: Velocidade do movimento da mão (para aceleração).
        """
        try:
            # Zona ativa da câmera (margem de 10% nas bordas)
            mapped_x = (hand_x - 0.1) / 0.8
            mapped_y = (hand_y - 0.15) / 0.7
            mapped_x = max(0.0, min(1.0, mapped_x))
            mapped_y = max(0.0, min(1.0, mapped_y))

            # Coordenadas de tela VIRTUAL (multi-monitor)
            sx = self.virtual_left + int(mapped_x * self.screen_width)
            sy = self.virtual_top + int(mapped_y * self.screen_height)

            # Aceleração: movimentos rápidos cobrem mais tela
            if speed > 2.0:
                accel = min(1.5, 1.0 + (speed - 2.0) * 0.1)
                center_x = self.virtual_left + self.screen_width // 2
                center_y = self.virtual_top + self.screen_height // 2
                sx = int(center_x + (sx - center_x) * accel)
                sy = int(center_y + (sy - center_y) * accel)

            # Clamp dentro da área virtual
            sx = max(self.virtual_left, min(self.virtual_left + self.screen_width - 1, sx))
            sy = max(self.virtual_top, min(self.virtual_top + self.screen_height - 1, sy))

            # Filtro de média móvel
            self._x_buffer.append(sx)
            self._y_buffer.append(sy)
            smooth_x = int(sum(self._x_buffer) / len(self._x_buffer))
            smooth_y = int(sum(self._y_buffer) / len(self._y_buffer))

            # SetCursorPos funciona em coordenadas virtuais (multi-monitor)
            ctypes.windll.user32.SetCursorPos(smooth_x, smooth_y)
            self.total_moves += 1

        except Exception as e:
            logger.debug(f"[Actions] Erro cursor: {e}")

    # ═══════════════════════════════════════════════════════════
    #  DRAG — Pinça segurando (🤏 mantida)
    # ═══════════════════════════════════════════════════════════

    def start_drag(self):
        """Inicia drag — chamado pelo PinchClickDetector quando pinça é mantida."""
        if self._dragging:
            return
        try:
            import pyautogui
            pyautogui.mouseDown(_pause=False)
            self._dragging = True
            self.total_drags += 1
            logger.info("[Actions] 🤏 Drag INICIADO (pinça segurando)")
        except Exception as e:
            logger.debug(f"[Actions] Erro drag: {e}")

    def stop_drag(self):
        """Para drag — chamado quando pinça é solta ou mão desaparece."""
        if not self._dragging:
            return
        try:
            import pyautogui
            pyautogui.mouseUp(_pause=False)
            self._dragging = False
            logger.info("[Actions] 🤏 Drag FINALIZADO (pinça solta)")
        except Exception as e:
            logger.debug(f"[Actions] Erro drag: {e}")

    # ═══════════════════════════════════════════════════════════
    #  TAB SWITCH — OK (👌)
    # ═══════════════════════════════════════════════════════════

    def enter_ok_mode(self, hand_x: float):
        if not self._ok_mode:
            self._ok_mode = True
            self._ok_start_x = hand_x
            logger.info("[Actions] 👌 Modo OK ATIVADO")

    def process_ok_mode(self, hand_x: float):
        if not self._ok_mode:
            return
        now = time.time()
        if now - self._ok_last_action < self._ok_cooldown:
            return
        delta_x = hand_x - self._ok_start_x
        try:
            import pyautogui
            if delta_x > self._ok_threshold:
                pyautogui.hotkey("ctrl", "tab", _pause=False)
                self._ok_start_x = hand_x
                self._ok_last_action = now
                self.total_tab_switches += 1
                logger.info("[Actions] 👌→ Próxima aba")
            elif delta_x < -self._ok_threshold:
                pyautogui.hotkey("ctrl", "shift", "tab", _pause=False)
                self._ok_start_x = hand_x
                self._ok_last_action = now
                self.total_tab_switches += 1
                logger.info("[Actions] ←👌 Aba anterior")
        except Exception as e:
            logger.debug(f"[Actions] Erro OK: {e}")

    def exit_ok_mode(self):
        if self._ok_mode:
            self._ok_mode = False

    # ═══════════════════════════════════════════════════════════
    #  SCROLL — 2 dedos (🤙)
    # ═══════════════════════════════════════════════════════════

    def enter_scroll_mode(self, hand_y: float):
        """Entra no modo scroll — rastreia posição Y inicial."""
        if not self._scroll_active:
            self._scroll_active = True
            self._scroll_start_y = hand_y
            logger.info("[Actions] 🤙 Modo SCROLL ativado")

    def process_scroll(self, hand_y: float):
        """Processa scroll baseado no movimento vertical."""
        if not self._scroll_active:
            return
        now = time.time()
        if now - self._scroll_last_action < self._scroll_cooldown:
            return

        delta_y = hand_y - self._scroll_start_y

        try:
            import pyautogui
            if delta_y > self._scroll_threshold:
                # Mão desceu → scroll DOWN
                amount = int(max(1, abs(delta_y) * 10))
                pyautogui.scroll(-amount, _pause=False)
                self._scroll_start_y = hand_y
                self._scroll_last_action = now
                self.total_scrolls += 1
            elif delta_y < -self._scroll_threshold:
                # Mão subiu → scroll UP
                amount = int(max(1, abs(delta_y) * 10))
                pyautogui.scroll(amount, _pause=False)
                self._scroll_start_y = hand_y
                self._scroll_last_action = now
                self.total_scrolls += 1
        except Exception as e:
            logger.debug(f"[Actions] Erro scroll: {e}")

    def exit_scroll_mode(self):
        if self._scroll_active:
            self._scroll_active = False

    # ═══════════════════════════════════════════════════════════
    #  SCREENSHOT — Paz / V (✌️)
    # ═══════════════════════════════════════════════════════════

    def take_screenshot(self):
        """Tira screenshot e salva no Desktop."""
        now = time.time()
        if now - self._screenshot_last < self._screenshot_cooldown:
            return

        self._screenshot_last = now

        try:
            import pyautogui
            from datetime import datetime

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(desktop, filename)

            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            self.total_screenshots += 1
            logger.info(f"[Actions] ✌️ Screenshot salvo: {filepath}")

        except Exception as e:
            logger.debug(f"[Actions] Erro screenshot: {e}")

    # ═══════════════════════════════════════════════════════════
    #  CLIQUE VIA PINÇA (🤏)
    # ═══════════════════════════════════════════════════════════

    def left_click(self):
        """Clique esquerdo — chamado pelo PinchClickDetector (pinça rápida)."""
        now = time.time()
        if now - self._last_click_time < self._click_cooldown:
            return
        self._last_click_time = now
        try:
            import pyautogui
            pyautogui.click(_pause=False)
            self.total_clicks += 1
            logger.info("[Actions] 🤏 Clique SIMPLES (pinça rápida)")
        except Exception as e:
            logger.debug(f"[Actions] Erro clique: {e}")

    # ═══════════════════════════════════════════════════════════
    #  ESTADO
    # ═══════════════════════════════════════════════════════════

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    @property
    def is_ok_mode(self) -> bool:
        return self._ok_mode

    @property
    def is_scroll_mode(self) -> bool:
        return self._scroll_active

    def reset(self):
        self.stop_drag()
        self.exit_ok_mode()
        self.exit_scroll_mode()
        self._x_buffer.clear()
        self._y_buffer.clear()

    def stats(self) -> str:
        return (
            f"Moves: {self.total_moves} | Clicks: {self.total_clicks} | "
            f"Drags: {self.total_drags} | Tabs: {self.total_tab_switches} | "
            f"Scrolls: {self.total_scrolls} | Screenshots: {self.total_screenshots}"
        )
