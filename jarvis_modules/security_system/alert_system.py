"""
═══════════════════════════════════════════════════════════════
  Sistema de Alerta — Alert System
═══════════════════════════════════════════════════════════════

Gerencia alertas de segurança:
  • Toca alarme2.mp3 em loop (volume alto)
  • Captura foto do intruso com timestamp
  • Salva em data/security/intrusions/
  • Cooldown entre alertas para evitar spam
  • (Opcional) Envio via WhatsApp
"""

import os
import time
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTRUSION_DIR = os.path.join(BASE_DIR, "data", "security", "intrusions")
ALARM_FILE = os.path.join(BASE_DIR, "alarme2.mp3")

os.makedirs(INTRUSION_DIR, exist_ok=True)


class AlertSystem:
    """Sistema de alerta com alarme sonoro e captura de evidências."""

    def __init__(self, cooldown: float = 15.0, alarm_volume: float = 1.0):
        """
        Args:
            cooldown: Tempo mínimo (seg) entre alertas consecutivos.
            alarm_volume: Volume do alarme (0.0 a 1.0).
        """
        self.cooldown = cooldown
        self.alarm_volume = alarm_volume

        # ── Estado ───────────────────────────────────────────
        self._alarm_playing = False
        self._alarm_thread = None
        self._last_alert_time = 0.0
        self._lock = threading.Lock()

        # ── Estatísticas ─────────────────────────────────────
        self.total_alerts = 0
        self.total_photos = 0
        self._intrusion_log = []  # [{timestamp, photo_path, ...}]

    def disparar_alerta(self, frame=None, nome_intruso: str = "INTRUSO") -> bool:
        """
        Dispara alerta de segurança.

        Args:
            frame: Frame BGR para capturar foto (opcional).
            nome_intruso: Identificação do intruso.

        Returns:
            True se o alerta foi disparado (não em cooldown).
        """
        now = time.time()
        with self._lock:
            if now - self._last_alert_time < self.cooldown:
                return False
            self._last_alert_time = now

        self.total_alerts += 1
        logger.warning(
            f"[SEGURANÇA] 🚨 ALERTA #{self.total_alerts}: "
            f"{nome_intruso} detectado!"
        )

        # Capturar foto
        photo_path = None
        if frame is not None:
            photo_path = self._salvar_foto(frame, nome_intruso)

        # Registrar intrusão
        self._intrusion_log.append({
            "timestamp": datetime.now().isoformat(),
            "intruso": nome_intruso,
            "foto": photo_path,
        })

        # Tocar alarme
        self._iniciar_alarme()

        return True

    def _salvar_foto(self, frame, nome: str) -> str:
        """Salva foto do intruso com timestamp."""
        try:
            import cv2

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"intruso_{nome}_{timestamp}.jpg"
            path = os.path.join(INTRUSION_DIR, filename)

            # Adicionar marca d'água com horário
            frame_copy = frame.copy()
            cv2.putText(
                frame_copy,
                f"INTRUSO DETECTADO - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                (10, frame_copy.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2,
            )

            cv2.imwrite(path, frame_copy)
            self.total_photos += 1
            logger.info(f"[SEGURANÇA] 📸 Foto salva: {path}")
            return path

        except Exception as e:
            logger.error(f"[SEGURANÇA] Erro ao salvar foto: {e}")
            return None

    def _iniciar_alarme(self):
        """Inicia alarme em loop (thread separada)."""
        if self._alarm_playing:
            return

        if not os.path.exists(ALARM_FILE):
            logger.error(f"[SEGURANÇA] Arquivo de alarme não encontrado: {ALARM_FILE}")
            return

        self._alarm_playing = True
        self._alarm_thread = threading.Thread(target=self._alarme_loop, daemon=True)
        self._alarm_thread.start()
        logger.info("[SEGURANÇA] 🔊 ALARME ATIVADO!")

    def _alarme_loop(self):
        """Loop de reprodução do alarme."""
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.load(ALARM_FILE)
            pygame.mixer.music.set_volume(self.alarm_volume)
            pygame.mixer.music.play(-1)  # -1 = loop infinito

            while self._alarm_playing:
                time.sleep(0.5)

            pygame.mixer.music.stop()
            logger.info("[SEGURANÇA] 🔇 Alarme parado")

        except Exception as e:
            logger.error(f"[SEGURANÇA] Erro no alarme: {e}")
            self._alarm_playing = False

    def parar_alarme(self) -> str:
        """Para o alarme."""
        if not self._alarm_playing:
            return "🔇 Alarme já está parado."

        self._alarm_playing = False
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

        return "🔇 Alarme **DESATIVADO**."

    def historico_intrusoes(self) -> str:
        """Retorna histórico de intrusões."""
        if not self._intrusion_log:
            return "📋 Nenhuma intrusão registrada."

        linhas = [f"🚨 **Histórico de Intrusões ({len(self._intrusion_log)} eventos):**\n"]
        for i, ev in enumerate(self._intrusion_log[-20:], 1):  # Últimas 20
            foto = f" 📸" if ev.get("foto") else ""
            linhas.append(
                f"  {i}. [{ev['timestamp'][:19]}] "
                f"{ev['intruso']}{foto}"
            )
        return "\n".join(linhas)

    @property
    def is_alarm_playing(self) -> bool:
        return self._alarm_playing

    def reset(self):
        """Reseta estado do sistema de alerta."""
        self.parar_alarme()
        self._intrusion_log = []
        self.total_alerts = 0
        self.total_photos = 0
