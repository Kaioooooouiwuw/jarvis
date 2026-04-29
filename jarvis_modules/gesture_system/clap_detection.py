"""
═══════════════════════════════════════════════════════════════
  Módulo de Detecção de Palmas (Claps) via Microfone
═══════════════════════════════════════════════════════════════

Detecta picos sonoros (palmas) no áudio do microfone:
  • 1 palma (👏)           → Callback on_single_clap
  • 2 palmas rápidas (👏👏) → Callback on_double_clap
    (intervalo < 500ms)

Técnicas:
  • Threshold adaptativo baseado no ruído ambiente
  • Janela de tempo para diferenciar 1 vs 2 palmas
  • Filtro de eco (ignora reflexões < 100ms)
  • Calibração automática inicial
  • Roda em thread daemon independente
"""

import math
import struct
import time
import threading
import logging

logger = logging.getLogger(__name__)


class ClapDetector:
    """Detector de palmas via análise de amplitude do microfone."""

    def __init__(
        self,
        threshold: float = 2000.0,
        double_window: float = 0.5,
        cooldown: float = 0.8,
        calibration_seconds: float = 1.0,
        ambient_multiplier: float = 3.0,
    ):
        """
        Args:
            threshold: Amplitude RMS mínima para detectar um clap.
            double_window: Janela de tempo (seg) para 2ª palma contar
                           como dupla.
            cooldown: Tempo mínimo (seg) entre conjuntos de palmas.
            calibration_seconds: Duração da calibração de ruído ambiente.
            ambient_multiplier: Multiplicador do nível ambiente para
                                definir threshold adaptativo.
        """
        self.threshold = threshold
        self.double_window = double_window
        self.cooldown = cooldown
        self.calibration_seconds = calibration_seconds
        self.ambient_multiplier = ambient_multiplier

        # ── Estado interno ───────────────────────────────────
        self._running = False
        self._thread = None
        self._last_clap_time = 0.0
        self._pending_single = False
        self._lock = threading.Lock()
        self._ambient_level = 500.0

        # ── Callbacks ────────────────────────────────────────
        self.on_single_clap = None   # Chamado para 1 palma
        self.on_double_clap = None   # Chamado para 2 palmas rápidas

        # ── Status para UI ───────────────────────────────────
        self.last_event = ""         # "👏" ou "👏👏"
        self.last_event_time = 0.0

    def start(self):
        """Inicia detector em thread daemon."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("[ClapDetector] Iniciado")

    def stop(self):
        """Para detector."""
        self._running = False
        logger.info("[ClapDetector] Parado")

    @property
    def is_running(self) -> bool:
        return self._running

    def _listen_loop(self):
        """Loop principal de captura e análise de áudio."""
        try:
            import pyaudio
        except ImportError:
            logger.error(
                "[ClapDetector] PyAudio não instalado. "
                "Execute: pip install pyaudio"
            )
            self._running = False
            return

        # Parâmetros de captura
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100

        pa = pyaudio.PyAudio()

        try:
            stream = pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
        except Exception as e:
            logger.error(f"[ClapDetector] Erro ao abrir microfone: {e}")
            pa.terminate()
            self._running = False
            return

        # ── Calibração de ruído ambiente ─────────────────────
        logger.info("[ClapDetector] Calibrando ruído ambiente...")
        ambient_samples = []
        cal_frames = int(RATE / CHUNK * self.calibration_seconds)
        for _ in range(cal_frames):
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                rms = self._rms(data)
                ambient_samples.append(rms)
            except Exception:
                pass

        if ambient_samples:
            self._ambient_level = sum(ambient_samples) / len(ambient_samples)
            adaptive_threshold = self._ambient_level * self.ambient_multiplier
            self.threshold = max(self.threshold, adaptive_threshold)
            logger.info(
                f"[ClapDetector] Ambiente: {self._ambient_level:.0f} RMS | "
                f"Threshold: {self.threshold:.0f} RMS"
            )

        logger.info("[ClapDetector] 🎤 Escutando palmas...")

        # ── Loop de detecção ─────────────────────────────────
        while self._running:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                rms = self._rms(data)

                # Atualizar nível ambiente (lentamente)
                self._ambient_level = self._ambient_level * 0.995 + rms * 0.005

                now = time.time()

                # Detectar pico acima do threshold
                if rms > self.threshold and rms > self._ambient_level * 2.0:
                    with self._lock:
                        time_since_last = now - self._last_clap_time

                        # Filtro de eco (< 100ms é reflexão, não palma nova)
                        if time_since_last < 0.1:
                            continue

                        if self._pending_single and time_since_last < self.double_window:
                            # Segunda palma dentro da janela → DUPLA
                            self._pending_single = False
                            self._last_clap_time = now
                            self.last_event = "👏👏"
                            self.last_event_time = now
                            logger.info("[ClapDetector] 👏👏 DUPLA palma detectada!")
                            if self.on_double_clap:
                                threading.Thread(
                                    target=self.on_double_clap, daemon=True
                                ).start()
                        else:
                            # Primeira palma — agendar verificação de single
                            self._pending_single = True
                            self._last_clap_time = now
                            threading.Timer(
                                self.double_window,
                                self._check_single_clap,
                                args=[now],
                            ).start()

            except Exception as e:
                if self._running:
                    logger.debug(f"[ClapDetector] Erro no frame: {e}")
                time.sleep(0.01)

        # ── Cleanup ──────────────────────────────────────────
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        pa.terminate()

    def _check_single_clap(self, clap_time: float):
        """
        Chamado após double_window expirar.
        Se nenhuma segunda palma veio, confirma palma única.
        """
        with self._lock:
            if self._pending_single and self._last_clap_time == clap_time:
                self._pending_single = False
                self.last_event = "👏"
                self.last_event_time = time.time()
                logger.info("[ClapDetector] 👏 Palma ÚNICA detectada!")
                if self.on_single_clap:
                    threading.Thread(
                        target=self.on_single_clap, daemon=True
                    ).start()

    @staticmethod
    def _rms(data: bytes) -> float:
        """Calcula RMS (Root Mean Square) de dados PCM 16-bit."""
        count = len(data) // 2
        if count == 0:
            return 0.0
        shorts = struct.unpack(f"<{count}h", data)
        sum_squares = sum(s * s for s in shorts)
        return math.sqrt(sum_squares / count)
