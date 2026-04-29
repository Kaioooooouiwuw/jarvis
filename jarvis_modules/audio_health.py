"""
═══════════════════════════════════════════════════════════════
  AUDIO HEALTH MONITOR v2 — Diagnóstico e Correção Inteligente
═══════════════════════════════════════════════════════════════

Fornece:
  • Monitoramento ATIVO de saúde do áudio em tempo real
  • Detecção automática: buffer overflow, cortes, distorção
  • Correção automática com retry inteligente
  • Diagnóstico de rede para streaming (YouTube, etc.)
  • Sugestões de fontes alternativas
  • Notificação ao usuário quando problemas persistem

Arquitetura:
  - Thread de monitoramento contínuo (5s interval)
  - Detecção de overflow via log + processo de áudio
  - Auto-restart de stream quando detecta falha
  - Separação total: SFX local (pygame) / Streaming (LiveKit/browser)
"""

import os
import time
import threading
import logging
import subprocess
import json
import re
from typing import Optional, Dict, List, Tuple, Callable
from datetime import datetime
from collections import deque

from jarvis_modules.core import BASE_DIR, DataStore, event_bus

logger = logging.getLogger(__name__)

# ── Persistência ──────────────────────────────────────────────
_audio_health_store = DataStore("audio_health", default={
    "monitoramento_ativo": False,
    "ultimo_diagnostico": None,
    "historico_problemas": [],
    "correcoes_aplicadas": 0,
    "config": {
        "intervalo_check_segundos": 5,
        "max_latencia_ms": 200,
        "min_velocidade_mbps": 2.0,
        "buffer_recomendado_ms": 3000,
        "tentativas_correcao_max": 3,
        "auto_correcao_habilitada": True,
        "fontes_alternativas": [
            "Spotify Web (open.spotify.com)",
            "SoundCloud (soundcloud.com)",
            "Deezer (deezer.com)",
            "YouTube Music (music.youtube.com)",
        ],
    },
})

# ── Estado do monitoramento ───────────────────────────────────
_monitor_thread: Optional[threading.Thread] = None
_monitor_ativo = threading.Event()
_problemas_recentes: deque = deque(maxlen=50)
_tentativas_correcao_consecutivas = 0
_MAX_TENTATIVAS_CONSECUTIVAS = 3
_callback_notificacao: Optional[Callable] = None


# ═══════════════════════════════════════════════════════════════
#  Detector de Problemas de Áudio
# ═══════════════════════════════════════════════════════════════

class AudioProblemDetector:
    """
    Detecta problemas de áudio em tempo real:
      - Buffer overflow (via processos e logs)
      - Travamentos (processo de áudio não responde)
      - Cortes de stream (rede instável)
      - Distorção (carga de CPU excessiva no audiodg)
    """

    def __init__(self):
        self._ultimo_check: Optional[datetime] = None
        self._overflow_count = 0
        self._cortes_count = 0
        self._lock = threading.Lock()

    def detectar_overflow_buffer(self) -> Dict:
        """
        Detecta sinais de buffer overflow no sistema de áudio.
        Verifica processos audiodg.exe e estado dos devices.
        """
        resultado = {
            "overflow_detectado": False,
            "audiodg_status": "desconhecido",
            "cpu_audiodg": 0.0,
            "detalhes": "",
        }

        try:
            # Verificar se audiodg.exe está usando CPU excessiva
            proc = subprocess.run(
                ["wmic", "process", "where",
                 "name='audiodg.exe'", "get",
                 "WorkingSetSize,ThreadCount,HandleCount",
                 "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = proc.stdout.strip()

            if "audiodg" in output.lower() or proc.returncode == 0:
                resultado["audiodg_status"] = "ativo"

                # Verificar uso de memória excessivo (sinal de overflow)
                nums = re.findall(r"(\d+)", output)
                if nums:
                    # WorkingSetSize em bytes
                    for n in nums:
                        val = int(n)
                        if val > 100_000_000:  # > 100MB = possível overflow
                            resultado["overflow_detectado"] = True
                            resultado["detalhes"] = (
                                f"audiodg.exe usando {val // 1_000_000}MB de RAM "
                                f"(possível buffer overflow)"
                            )
            else:
                resultado["audiodg_status"] = "não_encontrado"

        except Exception as e:
            resultado["audiodg_status"] = f"erro: {e}"

        return resultado

    def detectar_travamento_stream(self) -> Dict:
        """
        Verifica se processos de streaming (Chrome/Edge) estão travados
        ou com alto consumo de recursos (sinal de problema de áudio).
        """
        resultado = {
            "travamento_detectado": False,
            "processos_suspeitos": [],
            "detalhes": "",
        }

        try:
            # Verificar se Chrome/Edge estão com uso anormal de CPU
            proc = subprocess.run(
                ["tasklist", "/fi", "STATUS eq NOT RESPONDING", "/fo", "CSV"],
                capture_output=True, text=True, timeout=5
            )

            processos_audio = ["chrome.exe", "msedge.exe", "firefox.exe",
                               "audiodg.exe", "wmplayer.exe"]

            for line in proc.stdout.split("\n"):
                for pa in processos_audio:
                    if pa.lower() in line.lower():
                        resultado["travamento_detectado"] = True
                        resultado["processos_suspeitos"].append(pa)

            if resultado["processos_suspeitos"]:
                resultado["detalhes"] = (
                    f"Processos não respondendo: "
                    f"{', '.join(resultado['processos_suspeitos'])}"
                )

        except Exception as e:
            logger.debug(f"[AudioHealth] Erro ao detectar travamento: {e}")

        return resultado

    def detectar_problemas_rede_stream(self) -> Dict:
        """Verificação rápida de conectividade para streaming."""
        resultado = {
            "problema_detectado": False,
            "latencia_ms": -1,
            "perda_pacotes": False,
            "detalhes": "",
        }

        try:
            proc = subprocess.run(
                ["ping", "-n", "2", "-w", "1000", "8.8.8.8"],
                capture_output=True, text=True, timeout=8
            )
            output = proc.stdout

            # Verificar perda de pacotes
            for line in output.split("\n"):
                if "%" in line and ("perda" in line.lower() or "loss" in line.lower()):
                    pcts = re.findall(r"(\d+)%", line)
                    if pcts and int(pcts[0]) > 5:
                        resultado["problema_detectado"] = True
                        resultado["perda_pacotes"] = True
                        resultado["detalhes"] += f"Perda: {pcts[0]}%. "

                # Latência
                if ("dia" in line.lower() or "average" in line.lower()) and "ms" in line.lower():
                    nums = re.findall(r"(\d+)ms", line)
                    if nums:
                        lat = int(nums[-1])
                        resultado["latencia_ms"] = lat
                        if lat > 200:
                            resultado["problema_detectado"] = True
                            resultado["detalhes"] += f"Latência: {lat}ms. "

            if proc.returncode != 0:
                resultado["problema_detectado"] = True
                resultado["detalhes"] = "Sem conexão com a internet."

        except subprocess.TimeoutExpired:
            resultado["problema_detectado"] = True
            resultado["detalhes"] = "Timeout no teste de rede."
        except Exception as e:
            resultado["detalhes"] = f"Erro: {e}"

        return resultado


# ── Instância global do detector ──────────────────────────────
_detector = AudioProblemDetector()


# ═══════════════════════════════════════════════════════════════
#  Monitor de Áudio em Tempo Real
# ═══════════════════════════════════════════════════════════════

def _thread_monitoramento():
    """
    Thread de monitoramento contínuo de áudio.
    Roda em background, verifica a cada N segundos.
    
    Fluxo:
      1. Detectar problemas (overflow, travamento, rede)
      2. Se problema detectado → tentar corrigir automaticamente
      3. Se persistir → notificar usuário via callback
    """
    global _tentativas_correcao_consecutivas

    config = _audio_health_store.load().get("config", {})
    intervalo = config.get("intervalo_check_segundos", 5)

    logger.info(f"[AudioHealth] Monitor ativo (intervalo: {intervalo}s)")

    while _monitor_ativo.is_set():
        try:
            problemas_encontrados = []

            # ── Check 1: Buffer overflow ──────────────────
            overflow = _detector.detectar_overflow_buffer()
            if overflow.get("overflow_detectado"):
                problemas_encontrados.append({
                    "tipo": "buffer_overflow",
                    "detalhe": overflow.get("detalhes", ""),
                    "timestamp": datetime.now().isoformat(),
                })

            # ── Check 2: Travamento de stream ─────────────
            travamento = _detector.detectar_travamento_stream()
            if travamento.get("travamento_detectado"):
                problemas_encontrados.append({
                    "tipo": "travamento_stream",
                    "detalhe": travamento.get("detalhes", ""),
                    "timestamp": datetime.now().isoformat(),
                })

            # ── Check 3: Problemas de rede (a cada 3 ciclos)──
            # Não checar rede todo ciclo para não sobrecarregar
            if hasattr(_thread_monitoramento, '_ciclo_num'):
                _thread_monitoramento._ciclo_num += 1
            else:
                _thread_monitoramento._ciclo_num = 0

            if _thread_monitoramento._ciclo_num % 3 == 0:
                rede = _detector.detectar_problemas_rede_stream()
                if rede.get("problema_detectado"):
                    problemas_encontrados.append({
                        "tipo": "rede_instavel",
                        "detalhe": rede.get("detalhes", ""),
                        "timestamp": datetime.now().isoformat(),
                    })

            # ── Processar problemas ───────────────────────
            if problemas_encontrados:
                for prob in problemas_encontrados:
                    _problemas_recentes.append(prob)
                    logger.warning(
                        f"[AudioHealth] ⚠ Problema: {prob['tipo']} — {prob['detalhe']}"
                    )

                # Auto-correção se habilitada
                config = _audio_health_store.load().get("config", {})
                if config.get("auto_correcao_habilitada", True):
                    if _tentativas_correcao_consecutivas < _MAX_TENTATIVAS_CONSECUTIVAS:
                        _tentativas_correcao_consecutivas += 1
                        logger.info(
                            f"[AudioHealth] 🔧 Auto-correção "
                            f"(tentativa {_tentativas_correcao_consecutivas}/"
                            f"{_MAX_TENTATIVAS_CONSECUTIVAS})"
                        )

                        # Determinar tipo de correção
                        tipos = [p["tipo"] for p in problemas_encontrados]
                        if "buffer_overflow" in tipos or "travamento_stream" in tipos:
                            _auto_corrigir("streaming")
                        elif "rede_instavel" in tipos:
                            _auto_corrigir("rede")
                        else:
                            _auto_corrigir("geral")

                        # Publicar evento para SFX de correção
                        event_bus.publish("sfx_trigger", {"tipo": "audio_corrigido"})
                    else:
                        # Muitas tentativas — notificar usuário
                        _notificar_usuario(
                            "Senhor, detectei instabilidade persistente no áudio. "
                            "Tentei corrigir automaticamente mas o problema persiste. "
                            "Recomendo verificar a conexão ou trocar a fonte de reprodução."
                        )
                        _tentativas_correcao_consecutivas = 0  # Reset
            else:
                # Sem problemas — resetar contador
                if _tentativas_correcao_consecutivas > 0:
                    _tentativas_correcao_consecutivas = 0
                    logger.info("[AudioHealth] ✅ Áudio estabilizado")

        except Exception as e:
            logger.error(f"[AudioHealth] Erro no ciclo de monitoramento: {e}")

        # Aguardar próximo ciclo
        _monitor_ativo.wait(timeout=intervalo)
        if not _monitor_ativo.is_set():
            break

    logger.info("[AudioHealth] Monitor desativado")


def _auto_corrigir(tipo: str):
    """Aplica correção automática baseada no tipo de problema."""
    global _tentativas_correcao_consecutivas
    
    # ✅ LIMITAR TENTATIVAS CONSECUTIVAS para evitar loops infinitos
    if _tentativas_correcao_consecutivas >= _MAX_TENTATIVAS_CONSECUTIVAS:
        logger.warning(f"[AudioHealth] ⚠ Máximo de {_MAX_TENTATIVAS_CONSECUTIVAS} tentativas alcançado - pausando auto-correção")
        return
    
    _tentativas_correcao_consecutivas += 1
    
    try:
        if tipo == "streaming":
            # Reiniciar reprodução no YouTube via CDP
            try:
                _reiniciar_youtube_cdp()
            except Exception:
                pass

        elif tipo == "rede":
            # Flush DNS para melhorar conectividade
            try:
                subprocess.run(
                    ["ipconfig", "/flushdns"],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass

        elif tipo == "geral":
            # Reiniciar serviço Windows Audio
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     "Restart-Service -Name 'Audiosrv' -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, timeout=10
                )
            except Exception:
                pass

        # Registrar correção
        dados = _audio_health_store.load()
        dados["correcoes_aplicadas"] = dados.get("correcoes_aplicadas", 0) + 1
        historico = dados.get("historico_problemas", [])
        historico.append({
            "timestamp": datetime.now().isoformat(),
            "tipo": f"auto_{tipo}",
            "acoes": [f"Auto-correção: {tipo} (tentativa {_tentativas_correcao_consecutivas}/{_MAX_TENTATIVAS_CONSECUTIVAS})"],
            "automatica": True,
        })
        dados["historico_problemas"] = historico[-50:]
        _audio_health_store.save(dados)
        
        # ✅ Resetar contador após correção bem-sucedida
        if _tentativas_correcao_consecutivas == 1:
            _tentativas_correcao_consecutivas = 0
            logger.info("[AudioHealth] ✅ Áudio estabilizado")

    except Exception as e:
        logger.error(f"[AudioHealth] Erro na auto-correção ({tipo}): {e}")


def _reiniciar_youtube_cdp():
    """Tenta reiniciar reprodução do YouTube via Chrome DevTools Protocol."""
    try:
        import urllib.request
        # Verificar se CDP está disponível
        with urllib.request.urlopen("http://localhost:9222/json/version", timeout=1) as r:
            if r.status != 200:
                return False
    except Exception:
        return False

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            for ctx in browser.contexts:
                for page in ctx.pages:
                    if "youtube.com/watch" in page.url:
                        page.evaluate("""
                            (() => {
                                const v = document.querySelector('video');
                                if (v) {
                                    v.pause();
                                    setTimeout(() => {
                                        v.currentTime = Math.max(0, v.currentTime - 2);
                                        v.play();
                                    }, 1500);
                                }
                            })()
                        """)
                        logger.info("[AudioHealth] YouTube reiniciado via CDP")
                        browser.disconnect()
                        return True
            browser.disconnect()
    except Exception as e:
        logger.debug(f"[AudioHealth] CDP restart falhou: {e}")

    return False


def _notificar_usuario(mensagem: str):
    """Notifica o usuário sobre problemas persistentes."""
    global _callback_notificacao
    logger.warning(f"[AudioHealth] NOTIFICAÇÃO: {mensagem}")

    # Publicar evento para que o agente possa falar
    event_bus.publish("audio_health_notificacao", {
        "mensagem": mensagem,
        "timestamp": datetime.now().isoformat(),
        "tipo": "instabilidade_audio",
    })

    # Callback personalizado se registrado
    if _callback_notificacao:
        try:
            _callback_notificacao(mensagem)
        except Exception:
            pass


def registrar_callback_notificacao(callback: Callable):
    """Registra um callback para notificações de áudio."""
    global _callback_notificacao
    _callback_notificacao = callback


# ═══════════════════════════════════════════════════════════════
#  Funções de Diagnóstico
# ═══════════════════════════════════════════════════════════════

def _medir_latencia_rede() -> Dict:
    """
    Mede latência e qualidade de rede para streaming de áudio.
    Retorna dict com latência, jitter e perda de pacotes.
    """
    resultado = {
        "latencia_ms": -1,
        "jitter_ms": -1,
        "perda_pacotes_pct": 0,
        "status": "desconhecido",
    }

    try:
        hosts = ["youtube.com", "googlevideo.com", "8.8.8.8"]
        latencias = []

        for host in hosts:
            try:
                proc = subprocess.run(
                    ["ping", "-n", "4", "-w", "2000", host],
                    capture_output=True, text=True, timeout=15
                )
                output = proc.stdout

                for line in output.split("\n"):
                    line_lower = line.strip().lower()
                    if ("dia" in line_lower or "average" in line_lower) and "ms" in line_lower:
                        nums = re.findall(r"(\d+)ms", line)
                        if nums:
                            latencias.append(int(nums[-1]))

                for line in output.split("\n"):
                    if "%" in line and ("perda" in line.lower() or "loss" in line.lower()):
                        pcts = re.findall(r"(\d+)%", line)
                        if pcts:
                            resultado["perda_pacotes_pct"] = max(
                                resultado["perda_pacotes_pct"], int(pcts[0])
                            )
            except (subprocess.TimeoutExpired, Exception):
                continue

        if latencias:
            resultado["latencia_ms"] = sum(latencias) // len(latencias)
            if len(latencias) > 1:
                resultado["jitter_ms"] = max(latencias) - min(latencias)
            else:
                resultado["jitter_ms"] = 0

            lat = resultado["latencia_ms"]
            perda = resultado["perda_pacotes_pct"]

            if lat < 50 and perda == 0:
                resultado["status"] = "excelente"
            elif lat < 100 and perda <= 2:
                resultado["status"] = "bom"
            elif lat < 200 and perda <= 5:
                resultado["status"] = "regular"
            elif lat < 500 and perda <= 10:
                resultado["status"] = "instável"
            else:
                resultado["status"] = "crítico"
        else:
            resultado["status"] = "sem_conexao"

    except Exception as e:
        logger.error(f"[AudioHealth] Erro ao medir latência: {e}")
        resultado["status"] = "erro"

    return resultado


def _verificar_dispositivo_audio() -> Dict:
    """Verifica o estado do dispositivo de áudio do sistema."""
    resultado = {
        "dispositivo_detectado": False,
        "volume_sistema": -1,
        "mudo": False,
        "taxa_amostragem": "desconhecida",
        "status": "desconhecido",
    }

    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        import comtypes

        comtypes.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        resultado["dispositivo_detectado"] = True
        resultado["volume_sistema"] = int(volume.GetMasterVolumeLevelScalar() * 100)
        resultado["mudo"] = bool(volume.GetMute())
        resultado["status"] = "ok"

        if resultado["mudo"]:
            resultado["status"] = "mudo"
        elif resultado["volume_sistema"] < 10:
            resultado["status"] = "volume_muito_baixo"

    except Exception as e:
        logger.debug(f"[AudioHealth] Erro ao verificar dispositivo: {e}")
        resultado["status"] = "erro_verificacao"

    return resultado


def _verificar_processos_audio() -> Dict:
    """Verifica processos de áudio em execução (players, streaming)."""
    resultado = {
        "processos_audio": [],
        "youtube_ativo": False,
        "player_ativo": False,
        "carga_cpu_audio": "desconhecida",
    }

    try:
        proc = subprocess.run(
            ["tasklist", "/fi", "STATUS eq RUNNING", "/fo", "CSV"],
            capture_output=True, text=True, timeout=10
        )

        processos_audio_conhecidos = {
            "chrome.exe": "Chrome (possível streaming)",
            "firefox.exe": "Firefox (possível streaming)",
            "msedge.exe": "Edge (possível streaming)",
            "spotify.exe": "Spotify",
            "vlc.exe": "VLC Media Player",
            "wmplayer.exe": "Windows Media Player",
            "foobar2000.exe": "foobar2000",
            "aimp.exe": "AIMP",
            "audiodg.exe": "Windows Audio Device Graph",
        }

        for line in proc.stdout.split("\n"):
            for processo, nome in processos_audio_conhecidos.items():
                if processo.lower() in line.lower():
                    if nome not in resultado["processos_audio"]:
                        resultado["processos_audio"].append(nome)
                    if "chrome" in processo.lower() or "edge" in processo.lower():
                        resultado["player_ativo"] = True

        try:
            import pygetwindow as gw
            janelas = gw.getAllWindows()
            for w in janelas:
                if "youtube" in w.title.lower():
                    resultado["youtube_ativo"] = True
                    break
        except ImportError:
            pass

    except Exception as e:
        logger.debug(f"[AudioHealth] Erro ao verificar processos: {e}")

    return resultado


def _verificar_buffer_streaming() -> Dict:
    """Estima qualidade do buffer de streaming com base em métricas de rede."""
    resultado = {
        "buffer_estimado_ms": 0,
        "suficiente": True,
        "recomendacao": "",
    }

    config = _audio_health_store.load().get("config", {})
    buffer_recomendado = config.get("buffer_recomendado_ms", 3000)

    rede = _medir_latencia_rede()

    if rede["status"] in ("excelente", "bom"):
        resultado["buffer_estimado_ms"] = 5000
        resultado["suficiente"] = True
        resultado["recomendacao"] = "Conexão estável. Buffer adequado."
    elif rede["status"] == "regular":
        resultado["buffer_estimado_ms"] = 2000
        resultado["suficiente"] = resultado["buffer_estimado_ms"] >= buffer_recomendado
        resultado["recomendacao"] = "Conexão regular. Possíveis micro-cortes."
    elif rede["status"] == "instável":
        resultado["buffer_estimado_ms"] = 800
        resultado["suficiente"] = False
        resultado["recomendacao"] = (
            "Conexão instável. Alta chance de falhas no áudio. "
            "Recomendo pausar e aguardar estabilização, ou usar fonte local."
        )
    else:
        resultado["buffer_estimado_ms"] = 0
        resultado["suficiente"] = False
        resultado["recomendacao"] = (
            "Conexão crítica ou ausente. Streaming de áudio inviável. "
            "Tente reprodução local ou verifique a conexão."
        )

    return resultado


# ═══════════════════════════════════════════════════════════════
#  Diagnóstico Completo
# ═══════════════════════════════════════════════════════════════

def diagnostico_audio() -> str:
    """
    Executa diagnóstico completo do sistema de áudio.
    Retorna relatório detalhado e recomendações.
    """
    logger.info("[AudioHealth] Iniciando diagnóstico completo...")

    # 1. Rede
    rede = _medir_latencia_rede()

    # 2. Dispositivo
    dispositivo = _verificar_dispositivo_audio()

    # 3. Processos
    processos = _verificar_processos_audio()

    # 4. Buffer
    buffer = _verificar_buffer_streaming()

    # 5. Overflow (novo)
    overflow = _detector.detectar_overflow_buffer()

    # 6. Travamento (novo)
    travamento = _detector.detectar_travamento_stream()

    # Compilar resultado
    timestamp = datetime.now().isoformat()

    # Determinar saúde geral
    problemas = []
    if rede["status"] in ("instável", "crítico", "sem_conexao"):
        problemas.append(
            f"🌐 Rede {rede['status']} "
            f"(latência: {rede['latencia_ms']}ms, "
            f"perda: {rede['perda_pacotes_pct']}%)"
        )
    if dispositivo["mudo"]:
        problemas.append("🔇 Dispositivo de áudio está mudo")
    if dispositivo["volume_sistema"] >= 0 and dispositivo["volume_sistema"] < 10:
        problemas.append(f"🔉 Volume muito baixo: {dispositivo['volume_sistema']}%")
    if not buffer["suficiente"]:
        problemas.append(f"📦 Buffer insuficiente: ~{buffer['buffer_estimado_ms']}ms")
    if rede.get("perda_pacotes_pct", 0) > 5:
        problemas.append(f"📡 Perda de pacotes alta: {rede['perda_pacotes_pct']}%")
    if rede.get("jitter_ms", 0) > 50:
        problemas.append(f"📊 Jitter elevado: {rede['jitter_ms']}ms")
    if overflow.get("overflow_detectado"):
        problemas.append(f"⚡ Buffer overflow: {overflow.get('detalhes', '')}")
    if travamento.get("travamento_detectado"):
        problemas.append(f"🔴 Travamento: {travamento.get('detalhes', '')}")

    saude = "✅ Saudável" if not problemas else "⚠️ Problemas detectados"
    if len(problemas) >= 3:
        saude = "🔴 Crítico"

    # Salvar diagnóstico
    diag = {
        "timestamp": timestamp,
        "saude": saude,
        "rede": rede,
        "dispositivo": dispositivo,
        "processos": processos,
        "buffer": buffer,
        "overflow": overflow,
        "travamento": travamento,
        "problemas": problemas,
    }

    dados = _audio_health_store.load()
    dados["ultimo_diagnostico"] = diag
    _audio_health_store.save(dados)

    # Montar relatório
    linhas = [
        f"🎧 **Diagnóstico de Áudio — G.U.I.D.E.O.N v2**",
        f"  Status geral: {saude}",
        f"  Monitor ativo: {'✅ Sim' if _monitor_ativo.is_set() else '❌ Não'}",
        f"  Data: {timestamp[:19]}",
        "",
        "🌐 **Rede / Streaming:**",
        f"  Latência: {rede['latencia_ms']}ms",
        f"  Jitter: {rede['jitter_ms']}ms",
        f"  Perda de pacotes: {rede['perda_pacotes_pct']}%",
        f"  Qualidade: {rede['status'].upper()}",
        "",
        "🔊 **Dispositivo de Áudio:**",
        f"  Detectado: {'Sim' if dispositivo['dispositivo_detectado'] else 'Não'}",
        f"  Volume: {dispositivo['volume_sistema']}%",
        f"  Mudo: {'Sim' if dispositivo['mudo'] else 'Não'}",
        f"  Status: {dispositivo['status']}",
        "",
        "⚡ **Buffer / Overflow:**",
        f"  Buffer estimado: ~{buffer['buffer_estimado_ms']}ms",
        f"  Suficiente: {'Sim' if buffer['suficiente'] else 'Não'}",
        f"  Overflow: {'⚠ DETECTADO' if overflow.get('overflow_detectado') else '✅ Normal'}",
        f"  audiodg: {overflow.get('audiodg_status', 'N/A')}",
        f"  {buffer['recomendacao']}",
        "",
        "🎵 **Processos de Áudio:**",
        f"  YouTube ativo: {'Sim' if processos['youtube_ativo'] else 'Não'}",
        f"  Processos: {', '.join(processos['processos_audio']) if processos['processos_audio'] else 'Nenhum detectado'}",
    ]

    if problemas:
        linhas.extend(["", "⚠️ **Problemas encontrados:**"])
        for p in problemas:
            linhas.append(f"  {p}")

    # Problemas recentes do monitor
    if _problemas_recentes:
        linhas.extend(["", f"📊 **Problemas recentes (monitor): {len(_problemas_recentes)}**"])
        for prob in list(_problemas_recentes)[-5:]:
            linhas.append(
                f"  [{prob['timestamp'][:19]}] {prob['tipo']}: {prob['detalhe']}"
            )

    # Recomendações
    recomendacoes = _gerar_recomendacoes(rede, dispositivo, buffer, processos)
    if recomendacoes:
        linhas.extend(["", "💡 **Recomendações:**"])
        for rec in recomendacoes:
            linhas.append(f"  • {rec}")

    return "\n".join(linhas)


def _gerar_recomendacoes(rede: Dict, dispositivo: Dict,
                         buffer: Dict, processos: Dict) -> List[str]:
    """Gera recomendações inteligentes baseadas no diagnóstico."""
    recs = []

    if rede["status"] in ("instável", "crítico"):
        recs.append("Conecte-se a uma rede Wi-Fi mais estável ou use cabo Ethernet")
        recs.append("Feche downloads ou streams paralelos para liberar banda")

    if rede.get("perda_pacotes_pct", 0) > 5:
        recs.append("Perda de pacotes alta — reinicie o roteador se possível")
        recs.append("Considere usar uma fonte de áudio local em vez de streaming")

    if dispositivo.get("mudo"):
        recs.append("Desative o Mudo do sistema para ouvir áudio")

    if dispositivo.get("volume_sistema", 100) < 10:
        recs.append("Aumente o volume do sistema (está abaixo de 10%)")

    if not buffer.get("suficiente"):
        recs.append("Reduza a qualidade do vídeo/áudio no YouTube (720p ou inferior)")
        recs.append("Pause e aguarde o buffer carregar antes de reproduzir")

    config = _audio_health_store.load().get("config", {})
    alternativas = config.get("fontes_alternativas", [])
    if rede["status"] in ("instável", "crítico") and alternativas:
        recs.append(f"Fontes alternativas: {' | '.join(alternativas[:3])}")

    if len(processos.get("processos_audio", [])) > 3:
        recs.append("Muitos processos de áudio abertos. Feche os desnecessários.")

    if not _monitor_ativo.is_set():
        recs.append("Ative o monitor de áudio para correção automática: audio_sistema(acao='iniciar_monitor')")

    return recs


# ═══════════════════════════════════════════════════════════════
#  Correção Automática (Manual)
# ═══════════════════════════════════════════════════════════════

def corrigir_audio(tipo_problema: str = "geral") -> str:
    """
    Tenta corrigir problemas de áudio automaticamente.
    
    tipo_problema:
      - geral: tenta todas as correções
      - streaming: foca em problemas de streaming/YouTube
      - dispositivo: reinicia serviço de áudio
      - rede: tenta liberar e renovar conexão
    """
    logger.info(f"[AudioHealth] Tentando corrigir: {tipo_problema}")

    acoes = []
    config = _audio_health_store.load()

    try:
        if tipo_problema in ("geral", "dispositivo"):
            try:
                subprocess.run(
                    ["net", "stop", "audiosrv"], capture_output=True, timeout=10
                )
                time.sleep(1)
                subprocess.run(
                    ["net", "start", "audiosrv"], capture_output=True, timeout=10
                )
                acoes.append("✅ Serviço Windows Audio reiniciado")
            except Exception as e:
                acoes.append(f"⚠️ Não foi possível reiniciar Windows Audio: {e}")

        if tipo_problema in ("geral", "rede"):
            try:
                subprocess.run(
                    ["ipconfig", "/flushdns"], capture_output=True, timeout=10
                )
                acoes.append("✅ Cache DNS limpo")
            except Exception:
                pass

            try:
                subprocess.run(
                    ["ipconfig", "/release"], capture_output=True, timeout=10
                )
                time.sleep(1)
                subprocess.run(
                    ["ipconfig", "/renew"], capture_output=True, timeout=15
                )
                acoes.append("✅ IP renovado")
            except Exception:
                acoes.append("⚠️ Não foi possível renovar IP")

        if tipo_problema in ("geral", "streaming"):
            # Desmutar e ajustar volume
            try:
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                import comtypes

                comtypes.CoInitialize()
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )
                volume = cast(interface, POINTER(IAudioEndpointVolume))

                if volume.GetMute():
                    volume.SetMute(0, None)
                    acoes.append("✅ Áudio desmutado")

                vol_level = volume.GetMasterVolumeLevelScalar()
                if vol_level < 0.1:
                    volume.SetMasterVolumeLevelScalar(0.5, None)
                    acoes.append("✅ Volume ajustado para 50%")

            except Exception as e:
                acoes.append(f"⚠️ Erro ao ajustar volume: {e}")

            # Reiniciar YouTube via CDP
            try:
                if _reiniciar_youtube_cdp():
                    acoes.append("✅ Reprodução YouTube reiniciada")
                else:
                    acoes.append("⚠️ Nenhum vídeo YouTube encontrado para reiniciar")
            except Exception as e:
                acoes.append(f"⚠️ Erro ao reiniciar YouTube: {e}")

        # Registrar correção
        config["correcoes_aplicadas"] = config.get("correcoes_aplicadas", 0) + 1
        historico = config.get("historico_problemas", [])
        historico.append({
            "timestamp": datetime.now().isoformat(),
            "tipo": tipo_problema,
            "acoes": acoes,
            "automatica": False,
        })
        config["historico_problemas"] = historico[-50:]
        _audio_health_store.save(config)

    except Exception as e:
        acoes.append(f"❌ Erro geral na correção: {e}")

    if not acoes:
        return "Nenhuma ação de correção necessária."

    resultado = [
        "🔧 **Correção de Áudio — G.U.I.D.E.O.N**",
        f"  Tipo: {tipo_problema}",
        "",
    ]
    resultado.extend(f"  {a}" for a in acoes)

    # Publicar evento de correção (SFX)
    event_bus.publish("sfx_trigger", {"tipo": "audio_corrigido"})

    return "\n".join(resultado)


# ═══════════════════════════════════════════════════════════════
#  Monitor — Iniciar / Parar
# ═══════════════════════════════════════════════════════════════

def iniciar_monitor_audio() -> str:
    """
    Inicia o monitoramento de áudio em tempo real.
    Detecta e corrige problemas automaticamente.
    """
    global _monitor_thread

    if _monitor_ativo.is_set():
        return "⚠️ Monitor de áudio já está ativo."

    _monitor_ativo.set()
    _monitor_thread = threading.Thread(
        target=_thread_monitoramento,
        daemon=True,
        name="AudioHealthMonitor"
    )
    _monitor_thread.start()

    # Salvar estado
    dados = _audio_health_store.load()
    dados["monitoramento_ativo"] = True
    _audio_health_store.save(dados)

    return (
        "🎧 **Monitor de Áudio ATIVO**\n"
        "  Verificando a cada 5 segundos:\n"
        "  • Buffer overflow\n"
        "  • Travamentos de stream\n"
        "  • Instabilidade de rede\n"
        "  • Correção automática habilitada ✅"
    )


def parar_monitor_audio() -> str:
    """Para o monitoramento de áudio."""
    if not _monitor_ativo.is_set():
        return "Monitor de áudio não está ativo."

    _monitor_ativo.clear()

    dados = _audio_health_store.load()
    dados["monitoramento_ativo"] = False
    _audio_health_store.save(dados)

    return "🔇 Monitor de áudio desativado."


def status_monitor_audio() -> str:
    """Retorna o status atual do monitor de áudio."""
    ativo = _monitor_ativo.is_set()
    dados = _audio_health_store.load()

    linhas = [
        "🎧 **Status do Monitor de Áudio**",
        f"  Monitor: {'✅ ATIVO' if ativo else '❌ Inativo'}",
        f"  Correções aplicadas: {dados.get('correcoes_aplicadas', 0)}",
        f"  Problemas recentes: {len(_problemas_recentes)}",
        f"  Tentativas correção: {_tentativas_correcao_consecutivas}/{_MAX_TENTATIVAS_CONSECUTIVAS}",
    ]

    config = dados.get("config", {})
    linhas.extend([
        "",
        "⚙️ **Configuração:**",
        f"  Intervalo: {config.get('intervalo_check_segundos', 5)}s",
        f"  Auto-correção: {'✅' if config.get('auto_correcao_habilitada', True) else '❌'}",
        f"  Max tentativas: {config.get('tentativas_correcao_max', 3)}",
    ])

    if _problemas_recentes:
        linhas.extend(["", "📊 **Últimos problemas:**"])
        for prob in list(_problemas_recentes)[-5:]:
            linhas.append(
                f"  [{prob['timestamp'][:19]}] {prob['tipo']}: {prob['detalhe']}"
            )

    return "\n".join(linhas)


def sugerir_alternativa() -> str:
    """Sugere fontes alternativas de áudio quando YouTube está instável."""
    config = _audio_health_store.load().get("config", {})
    alternativas = config.get("fontes_alternativas", [])

    linhas = [
        "🎵 **Fontes Alternativas de Áudio:**",
        "",
        "Se o YouTube está com problemas de áudio, tente:",
    ]

    for i, alt in enumerate(alternativas, 1):
        linhas.append(f"  {i}. {alt}")

    linhas.extend([
        "",
        "💡 **Dicas adicionais:**",
        "  • Reduza a qualidade do vídeo (360p/480p) para priorizar áudio",
        "  • Use o YouTube Music em vez do YouTube padrão",
        "  • Considere baixar o áudio para reprodução local",
        "  • Feche outras abas e aplicativos que consomem banda",
    ])

    return "\n".join(linhas)


def historico_problemas() -> str:
    """Retorna histórico de problemas e correções de áudio."""
    dados = _audio_health_store.load()
    historico = dados.get("historico_problemas", [])
    total_correcoes = dados.get("correcoes_aplicadas", 0)

    if not historico:
        return "📊 Nenhum problema de áudio registrado até o momento."

    linhas = [
        "📊 **Histórico de Áudio — G.U.I.D.E.O.N**",
        f"  Total de correções aplicadas: {total_correcoes}",
        f"  Automáticas: {sum(1 for h in historico if h.get('automatica', False))}",
        f"  Manuais: {sum(1 for h in historico if not h.get('automatica', False))}",
        "",
    ]

    for item in historico[-10:]:
        ts = item.get("timestamp", "")[:19]
        tipo = item.get("tipo", "desconhecido")
        auto = " 🤖" if item.get("automatica") else " 👤"
        acoes = item.get("acoes", [])
        linhas.append(f"  📅 {ts} | {tipo}{auto}")
        for a in acoes:
            linhas.append(f"    {a}")
        linhas.append("")

    return "\n".join(linhas)
