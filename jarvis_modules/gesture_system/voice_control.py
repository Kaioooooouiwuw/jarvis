"""
═══════════════════════════════════════════════════════════════
  Módulo de Controle por Voz — Ativação/Desativação do Sistema
═══════════════════════════════════════════════════════════════

Listener contínuo de voz usando SpeechRecognition + Google API:
  • "Jarvis, ative o controle de gesto"   → Ativa webcam + gestos
  • "Jarvis, desative o controle de gesto" → Encerra webcam

Funcionalidades:
  • Wake word detection ("Jarvis" / "Gideon")
  • Reconhecimento de voz em português (pt-BR)
  • Calibração automática de ruído ambiente
  • Thread daemon — não bloqueia o programa principal
  • Tolerância a erros de rede (Google API)
"""

import time
import threading
import logging

logger = logging.getLogger(__name__)


class VoiceController:
    """Listener de voz para ativação/desativação do sistema de gestos."""

    def __init__(self, language: str = "pt-BR"):
        """
        Args:
            language: Idioma para reconhecimento de voz (padrão: pt-BR).
        """
        self.language = language
        self._running = False
        self._thread = None

        # ── Callbacks ────────────────────────────────────────
        self.on_activate = None     # Chamado ao detectar comando de ativar
        self.on_deactivate = None   # Chamado ao detectar comando de desativar

        # ── Wake words ───────────────────────────────────────
        self._wake_words = ["jarvis", "gideon", "jarvi", "jarbis"]

        # ── Keywords de ativação ─────────────────────────────
        self._activate_keywords = [
            "ative o controle",
            "ativar controle",
            "ative controle",
            "ative gestos",
            "ativar gestos",
            "ative o gesto",
            "ativa o controle",
            "ativa controle",
            "ativa gestos",
            "ligar controle",
            "ligar gestos",
            "iniciar controle",
            "iniciar gestos",
            "activate gesture",
            "activate control",
        ]

        # ── Keywords de desativação ──────────────────────────
        self._deactivate_keywords = [
            "desative o controle",
            "desativar controle",
            "desative controle",
            "desative gestos",
            "desativar gestos",
            "desative o gesto",
            "desativa o controle",
            "desativa controle",
            "desativa gestos",
            "desligar controle",
            "desligar gestos",
            "parar controle",
            "parar gestos",
            "pare controle",
            "pare gestos",
            "deactivate gesture",
            "deactivate control",
        ]

        # ── Status ───────────────────────────────────────────
        self.last_heard = ""
        self.last_heard_time = 0.0

    def start(self):
        """Inicia listener de voz em thread daemon."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("[VoiceControl] Listener de voz iniciado")

    def stop(self):
        """Para listener de voz."""
        self._running = False
        logger.info("[VoiceControl] Listener de voz parado")

    @property
    def is_running(self) -> bool:
        return self._running

    def _listen_loop(self):
        """Loop principal de reconhecimento de voz."""
        try:
            import speech_recognition as sr
        except ImportError:
            logger.error(
                "[VoiceControl] SpeechRecognition não instalado. "
                "Execute: pip install SpeechRecognition"
            )
            self._running = False
            return

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        try:
            mic = sr.Microphone()
        except Exception as e:
            logger.error(f"[VoiceControl] Erro ao abrir microfone: {e}")
            self._running = False
            return

        # Calibrar ruído ambiente
        with mic as source:
            logger.info("[VoiceControl] Calibrando ruído ambiente (2s)...")
            recognizer.adjust_for_ambient_noise(source, duration=2)

        logger.info(
            "[VoiceControl] 🎤 Pronto! "
            "Diga 'Jarvis, ative o controle de gesto'"
        )

        while self._running:
            try:
                with mic as source:
                    audio = recognizer.listen(
                        source, timeout=5, phrase_time_limit=5
                    )

                try:
                    text = recognizer.recognize_google(
                        audio, language=self.language
                    ).lower()

                    logger.debug(f"[VoiceControl] Ouviu: '{text}'")
                    self.last_heard = text
                    self.last_heard_time = time.time()

                    # Verificar wake word
                    has_wake = any(w in text for w in self._wake_words)

                    if has_wake:
                        # Verificar comandos de ativação
                        if any(kw in text for kw in self._activate_keywords):
                            logger.info(
                                "[VoiceControl] 🎤 Comando detectado: "
                                "ATIVAR controle de gestos"
                            )
                            if self.on_activate:
                                self.on_activate()

                        # Verificar comandos de desativação
                        elif any(kw in text for kw in self._deactivate_keywords):
                            logger.info(
                                "[VoiceControl] 🎤 Comando detectado: "
                                "DESATIVAR controle de gestos"
                            )
                            if self.on_deactivate:
                                self.on_deactivate()

                except sr.UnknownValueError:
                    pass  # Não entendeu — silêncio ou ruído
                except sr.RequestError as e:
                    logger.warning(
                        f"[VoiceControl] Erro na API Google: {e}. "
                        "Tentando novamente em 3s..."
                    )
                    time.sleep(3)

            except sr.WaitTimeoutError:
                pass  # Nenhuma fala detectada no timeout
            except Exception as e:
                if self._running:
                    logger.debug(f"[VoiceControl] Erro no loop: {e}")
                time.sleep(0.5)
