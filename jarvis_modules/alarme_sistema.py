"""
═══════════════════════════════════════════════════════════════
  JARVIS — Sistema de Alarmes & Ativação por Palavra-Chave v1.0
═══════════════════════════════════════════════════════════════

Fornece:
  • Alarmes personalizados com parsing de linguagem natural
  • Suporte a "amanhã", "daqui X minutos", períodos do dia
  • Reprodução contínua de alarme.mp3 até interrupção
  • Múltiplos alarmes simultâneos sem duplicações
  • Ativação por palavra-chave "Jarvis"
  • Verificação contínua com precisão de 1 segundo
"""

import os
import re
import threading
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any

from jarvis_modules.core import BASE_DIR, DataStore, agora_brasil

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────
ALARME_MP3 = os.path.join(BASE_DIR, "alarme2.mp3")

# ── Persistência de alarmes ───────────────────────────────────
_alarme_store = DataStore("alarmes_config", default={
    "alarmes": [],
    "historico": [],
    "total_disparados": 0,
    "ativacao_keyword": True,
    "keyword": "jarvis",
})


# ═══════════════════════════════════════════════════════════════
#  PARSER DE HORÁRIO — Interpreta linguagem natural
# ═══════════════════════════════════════════════════════════════

def _parse_horario(horario_str: str) -> Optional[datetime]:
    """
    Interpreta strings de horário em linguagem natural e retorna datetime.
    
    Formatos aceitos:
      - "07:30", "7:30", "07h30", "7h30"
      - "amanhã 07:30", "amanhã às 8h"
      - "daqui 30 minutos", "daqui 1 hora"
      - "meio-dia", "meia-noite"
      - "6 da manhã", "8 da noite", "3 da tarde"
    """
    horario_str = horario_str.strip().lower()
    agora = agora_brasil()
    
    # ── "daqui X minutos/horas" ───────────────────────────
    match = re.match(r"daqui\s+(\d+)\s*(minuto|minutos|min|hora|horas|h|segundo|segundos|seg)", horario_str)
    if match:
        valor = int(match.group(1))
        unidade = match.group(2)
        if unidade in ("hora", "horas", "h"):
            return agora + timedelta(hours=valor)
        elif unidade in ("minuto", "minutos", "min"):
            return agora + timedelta(minutes=valor)
        elif unidade in ("segundo", "segundos", "seg"):
            return agora + timedelta(seconds=valor)
    
    # ── "em X minutos/horas" ──────────────────────────────
    match = re.match(r"em\s+(\d+)\s*(minuto|minutos|min|hora|horas|h)", horario_str)
    if match:
        valor = int(match.group(1))
        unidade = match.group(2)
        if unidade in ("hora", "horas", "h"):
            return agora + timedelta(hours=valor)
        return agora + timedelta(minutes=valor)
    
    # ── "meio-dia" / "meia-noite" ─────────────────────────
    if "meio" in horario_str and "dia" in horario_str:
        alvo = agora.replace(hour=12, minute=0, second=0, microsecond=0)
        if alvo <= agora:
            alvo += timedelta(days=1)
        return alvo
    
    if "meia" in horario_str and "noite" in horario_str:
        alvo = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        if alvo <= agora:
            alvo += timedelta(days=1)
        return alvo
    
    # ── Detectar "amanhã" ─────────────────────────────────
    amanha = False
    horario_limpo = horario_str
    if "amanhã" in horario_str or "amanha" in horario_str:
        amanha = True
        horario_limpo = re.sub(r"amanhã|amanha", "", horario_limpo).strip()
        horario_limpo = re.sub(r"^(às|as|a)\s+", "", horario_limpo).strip()
    
    # ── "X da manhã/tarde/noite/madrugada" ────────────────
    match = re.match(r"(\d{1,2})\s*(da\s+)?(manhã|manha|tarde|noite|madrugada)", horario_limpo)
    if match:
        hora = int(match.group(1))
        periodo = match.group(3)
        
        if periodo in ("tarde",) and hora < 12:
            hora += 12
        elif periodo in ("noite",):
            if hora < 6:
                hora += 12
            elif hora < 12:
                hora += 12
        elif periodo in ("madrugada",) and hora >= 12:
            hora -= 12
        elif periodo in ("manhã", "manha") and hora == 12:
            hora = 0
        
        alvo = agora.replace(hour=hora, minute=0, second=0, microsecond=0)
        if amanha:
            alvo = alvo + timedelta(days=1)
        elif alvo <= agora:
            alvo += timedelta(days=1)
        return alvo
    
    # ── "HH:MM" ou "HHhMM" ou "HH h MM" ─────────────────
    match = re.match(r"(\d{1,2})\s*[h:]\s*(\d{0,2})", horario_limpo)
    if match:
        hora = int(match.group(1))
        minuto = int(match.group(2)) if match.group(2) else 0
        
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            alvo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if amanha:
                alvo = alvo + timedelta(days=1)
            elif alvo <= agora:
                alvo += timedelta(days=1)
            return alvo
    
    # ── Apenas número (assume horas) ──────────────────────
    match = re.match(r"^(\d{1,2})$", horario_limpo)
    if match:
        hora = int(match.group(1))
        if 0 <= hora <= 23:
            alvo = agora.replace(hour=hora, minute=0, second=0, microsecond=0)
            if amanha:
                alvo = alvo + timedelta(days=1)
            elif alvo <= agora:
                alvo += timedelta(days=1)
            return alvo
    
    return None


# ═══════════════════════════════════════════════════════════════
#  SISTEMA DE ALARMES — Motor principal
# ═══════════════════════════════════════════════════════════════

class AlarmeEngine:
    """
    Motor de alarmes com verificação contínua e reprodução de áudio.
    
    Características:
      - Thread de verificação rodando a cada 1s
      - Reprodução de alarme.mp3 em loop até interrupção
      - Suporte a múltiplos alarmes simultâneos
      - Prevenção de duplicatas (tolerância de 60s)
      - Persistência entre sessões
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._inicializado = False
                cls._instance._alarmes: List[Dict] = []
                cls._instance._thread_monitor: Optional[threading.Thread] = None
                cls._instance._ativo = False
                cls._instance._alarme_tocando = False
                cls._instance._alarme_channel = None
                cls._instance._stop_alarme = threading.Event()
                cls._instance._pygame_disponivel = False
            return cls._instance
    
    def inicializar(self):
        """Inicializa o motor de alarmes e carrega alarmes salvos."""
        if self._inicializado:
            return
        
        # Verificar pygame
        try:
            import pygame
            self._pygame_disponivel = True
        except ImportError:
            logger.warning("[Alarme] pygame não disponível — alarme sonoro desabilitado")
            self._pygame_disponivel = False
        
        # Verificar arquivo de alarme
        if not os.path.exists(ALARME_MP3):
            logger.warning(f"[Alarme] Arquivo alarme.mp3 não encontrado: {ALARME_MP3}")
        
        # Carregar alarmes salvos
        config = _alarme_store.load()
        alarmes_salvos = config.get("alarmes", [])
        
        agora = agora_brasil()
        for a in alarmes_salvos:
            try:
                horario = datetime.fromisoformat(a["horario"])
                if horario > agora:
                    self._alarmes.append(a)
            except (ValueError, KeyError):
                pass
        
        self._inicializado = True
        self._iniciar_monitor()
        
        logger.info(f"[Alarme] Motor inicializado — {len(self._alarmes)} alarme(s) ativo(s)")
    
    def _iniciar_monitor(self):
        """Inicia thread de monitoramento contínuo."""
        if self._ativo:
            return
        
        self._ativo = True
        self._thread_monitor = threading.Thread(
            target=self._loop_verificacao,
            daemon=True,
            name="AlarmeMonitor"
        )
        self._thread_monitor.start()
        logger.info("[Alarme] Monitor de alarmes iniciado")
    
    def _loop_verificacao(self):
        """Loop principal que verifica alarmes a cada segundo."""
        while self._ativo:
            try:
                self._verificar_alarmes()
            except Exception as e:
                logger.error(f"[Alarme] Erro no loop de verificação: {e}")
            time.sleep(1)
    
    def _verificar_alarmes(self):
        """Verifica se algum alarme atingiu o horário."""
        agora = agora_brasil()
        alarmes_disparados = []
        
        for alarme in self._alarmes[:]:
            try:
                horario = datetime.fromisoformat(alarme["horario"])
                
                # Tolerância de 2 segundos (para garantir disparo preciso)
                diff = abs((agora - horario).total_seconds())
                
                if diff <= 2 and not alarme.get("disparado", False):
                    alarme["disparado"] = True
                    alarmes_disparados.append(alarme)
                    logger.info(f"[Alarme] DISPARADO: {alarme.get('descricao', 'Alarme')}")
                    
            except (ValueError, KeyError) as e:
                logger.warning(f"[Alarme] Alarme inválido removido: {e}")
                self._alarmes.remove(alarme)
        
        # Disparar alarmes
        for alarme in alarmes_disparados:
            self._tocar_alarme(alarme)
            # Remover alarme disparado
            if alarme in self._alarmes:
                self._alarmes.remove(alarme)
            
            # Registrar no histórico
            try:
                config = _alarme_store.load()
                config["historico"].append({
                    "descricao": alarme.get("descricao", "Alarme"),
                    "horario": alarme["horario"],
                    "disparado_em": agora.isoformat(),
                })
                config["historico"] = config["historico"][-100:]
                config["total_disparados"] = config.get("total_disparados", 0) + 1
                config["alarmes"] = [
                    a for a in self._alarmes if not a.get("disparado", False)
                ]
                _alarme_store.save(config)
            except Exception:
                pass
        
        # Limpar alarmes expirados (mais de 1 minuto no passado)
        for alarme in self._alarmes[:]:
            try:
                horario = datetime.fromisoformat(alarme["horario"])
                if (agora - horario).total_seconds() > 60:
                    self._alarmes.remove(alarme)
            except (ValueError, KeyError):
                self._alarmes.remove(alarme)
    
    def _tocar_alarme(self, alarme: Dict):
        """Toca o alarme.mp3 em loop contínuo em thread separada."""
        if not os.path.exists(ALARME_MP3):
            logger.error("[Alarme] alarme.mp3 não encontrado!")
            return
        
        self._stop_alarme.clear()
        self._alarme_tocando = True
        
        def _reproduzir():
            try:
                if self._pygame_disponivel:
                    import pygame
                    
                    # Inicializar mixer se necessário
                    if not pygame.mixer.get_init():
                        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
                    
                    # Usar canal separado para alarme (canal 7)
                    if pygame.mixer.get_num_channels() < 8:
                        pygame.mixer.set_num_channels(8)
                    
                    canal_alarme = pygame.mixer.Channel(7)
                    som = pygame.mixer.Sound(ALARME_MP3)
                    som.set_volume(1.0)  # Volume máximo
                    
                    # Tocar em loop (-1 = infinito)
                    canal_alarme.play(som, loops=-1)
                    self._alarme_channel = canal_alarme
                    
                    logger.info(f"[Alarme] Tocando: {alarme.get('descricao', 'Alarme')}")
                    
                    # Aguardar até ser interrompido
                    while not self._stop_alarme.is_set() and canal_alarme.get_busy():
                        time.sleep(0.1)
                    
                    canal_alarme.stop()
                    self._alarme_tocando = False
                    
                else:
                    # Fallback: subprocess com ffplay
                    import subprocess
                    
                    while not self._stop_alarme.is_set():
                        proc = subprocess.Popen(
                            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", ALARME_MP3],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        
                        while proc.poll() is None and not self._stop_alarme.is_set():
                            time.sleep(0.1)
                        
                        if self._stop_alarme.is_set():
                            proc.terminate()
                            break
                    
                    self._alarme_tocando = False
                    
            except Exception as e:
                logger.error(f"[Alarme] Erro ao tocar alarme: {e}")
                self._alarme_tocando = False
        
        threading.Thread(target=_reproduzir, daemon=True, name="AlarmePlayer").start()
    
    def adicionar_alarme(self, horario_str: str, descricao: str = "Alarme") -> str:
        """
        Adiciona um novo alarme.
        
        Args:
            horario_str: Horário em linguagem natural
            descricao: Descrição do alarme
        
        Returns:
            Mensagem de confirmação ou erro
        """
        if not self._inicializado:
            self.inicializar()
        
        # Parser de horário
        horario = _parse_horario(horario_str)
        
        if horario is None:
            return (
                f"Senhor, não consegui interpretar o horário '{horario_str}'. "
                f"Tente formatos como '07:30', 'amanhã 8h', 'daqui 30 minutos' ou '6 da manhã'."
            )
        
        agora = agora_brasil()
        
        # Validar se é futuro
        if horario <= agora:
            return "Senhor, o horário informado já passou. Defina um horário futuro."
        
        # Verificar duplicatas (tolerância de 60 segundos)
        for a in self._alarmes:
            try:
                h_existente = datetime.fromisoformat(a["horario"])
                diff = abs((horario - h_existente).total_seconds())
                if diff < 60:
                    return (
                        f"Senhor, já existe um alarme muito próximo desse horário: "
                        f"{h_existente.strftime('%H:%M')} — {a.get('descricao', 'Alarme')}."
                    )
            except (ValueError, KeyError):
                pass
        
        # Criar alarme
        alarme = {
            "horario": horario.isoformat(),
            "descricao": descricao,
            "criado_em": agora.isoformat(),
            "disparado": False,
        }
        
        self._alarmes.append(alarme)
        
        # Salvar
        try:
            config = _alarme_store.load()
            config["alarmes"] = [
                {"horario": a["horario"], "descricao": a.get("descricao", "Alarme")}
                for a in self._alarmes if not a.get("disparado", False)
            ]
            _alarme_store.save(config)
        except Exception:
            pass
        
        # Calcular tempo até disparo
        delta = horario - agora
        total_seg = int(delta.total_seconds())
        horas = total_seg // 3600
        minutos = (total_seg % 3600) // 60
        
        if horas > 0 and minutos > 0:
            tempo_str = f"{horas}h{minutos:02d}min"
        elif horas > 0:
            tempo_str = f"{horas}h"
        elif minutos > 0:
            tempo_str = f"{minutos} minuto{'s' if minutos > 1 else ''}"
        else:
            tempo_str = f"{total_seg} segundo{'s' if total_seg > 1 else ''}"
        
        return (
            f"Alarme definido para {horario.strftime('%H:%M')} "
            f"({horario.strftime('%d/%m/%Y')}). "
            f"Faltam {tempo_str}. Descrição: {descricao}."
        )
    
    def remover_alarme(self, indice: int = -1) -> str:
        """Remove um alarme pelo índice (0-based) ou o último."""
        if not self._alarmes:
            return "Senhor, não há alarmes ativos para remover."
        
        if indice < 0:
            indice = len(self._alarmes) + indice
        
        if 0 <= indice < len(self._alarmes):
            removido = self._alarmes.pop(indice)
            
            # Salvar
            try:
                config = _alarme_store.load()
                config["alarmes"] = [
                    {"horario": a["horario"], "descricao": a.get("descricao", "Alarme")}
                    for a in self._alarmes
                ]
                _alarme_store.save(config)
            except Exception:
                pass
            
            h = datetime.fromisoformat(removido["horario"])
            return f"Alarme removido: {h.strftime('%H:%M')} — {removido.get('descricao', 'Alarme')}."
        
        return f"Senhor, índice {indice} inválido. Use listar_alarmes para ver os alarmes ativos."
    
    def listar_alarmes(self) -> str:
        """Lista todos os alarmes ativos."""
        if not self._alarmes:
            return "Senhor, não há alarmes ativos no momento."
        
        agora = agora_brasil()
        linhas = [f"Alarmes ativos ({len(self._alarmes)}):"]
        
        for i, alarme in enumerate(self._alarmes):
            try:
                h = datetime.fromisoformat(alarme["horario"])
                delta = h - agora
                total_min = int(delta.total_seconds() / 60)
                
                if total_min > 60:
                    falta = f"{total_min // 60}h{total_min % 60:02d}min"
                elif total_min > 0:
                    falta = f"{total_min}min"
                else:
                    falta = "iminente"
                
                linhas.append(
                    f"  [{i}] {h.strftime('%H:%M (%d/%m)')} — {alarme.get('descricao', 'Alarme')} "
                    f"(faltam {falta})"
                )
            except (ValueError, KeyError):
                linhas.append(f"  [{i}] (alarme inválido)")
        
        return "\n".join(linhas)
    
    def parar_alarme(self) -> str:
        """Para o alarme que está tocando."""
        if self._alarme_tocando:
            self._stop_alarme.set()
            
            # Forçar parada do canal pygame
            if self._alarme_channel is not None:
                try:
                    self._alarme_channel.stop()
                except Exception:
                    pass
            
            self._alarme_tocando = False
            return "Alarme interrompido, Senhor."
        
        return "Senhor, nenhum alarme está tocando no momento."
    
    def status(self) -> str:
        """Retorna status do sistema de alarmes."""
        config = _alarme_store.load()
        
        return (
            f"Sistema de Alarmes JARVIS:\n"
            f"  Motor: {'Ativo' if self._ativo else 'Inativo'}\n"
            f"  Alarmes pendentes: {len(self._alarmes)}\n"
            f"  Alarme tocando: {'Sim' if self._alarme_tocando else 'Não'}\n"
            f"  Total disparados: {config.get('total_disparados', 0)}\n"
            f"  Ativação por palavra-chave: {'Ativa' if config.get('ativacao_keyword', True) else 'Inativa'}\n"
            f"  Keyword: {config.get('keyword', 'jarvis')}"
        )
    
    def parar(self):
        """Para o monitor de alarmes."""
        self._ativo = False
        self.parar_alarme()
        logger.info("[Alarme] Monitor parado")


# ── Singleton global ──────────────────────────────────────────
_engine = AlarmeEngine()


# ═══════════════════════════════════════════════════════════════
#  ATIVAÇÃO POR PALAVRA-CHAVE — Detecção "Jarvis"
# ═══════════════════════════════════════════════════════════════

class KeywordActivation:
    """
    Sistema de ativação por palavra-chave.
    Detecta "Jarvis" no áudio e ativa o microfone para interação.
    
    Utiliza o speech_recognition para escuta passiva em background.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._ativo = False
                cls._instance._thread: Optional[threading.Thread] = None
                cls._instance._keyword = "jarvis"
                cls._instance._callback = None
                cls._instance._sr_disponivel = False
            return cls._instance
    
    def inicializar(self, keyword: str = "jarvis", callback=None):
        """
        Inicializa o detector de palavra-chave.
        
        Args:
            keyword: Palavra de ativação (padrão: "jarvis")
            callback: Função a chamar quando a keyword é detectada
        """
        self._keyword = keyword.lower()
        self._callback = callback
        
        try:
            import speech_recognition
            self._sr_disponivel = True
        except ImportError:
            logger.warning("[Keyword] speech_recognition não disponível — ativação por keyword desabilitada")
            self._sr_disponivel = False
    
    def iniciar(self) -> str:
        """Inicia a escuta por palavra-chave em background."""
        if self._ativo:
            return "Detecção de palavra-chave já está ativa."
        
        if not self._sr_disponivel:
            return "Senhor, a biblioteca speech_recognition não está instalada. Instale com: pip install SpeechRecognition"
        
        self._ativo = True
        self._thread = threading.Thread(
            target=self._loop_escuta,
            daemon=True,
            name="KeywordListener"
        )
        self._thread.start()
        
        logger.info(f"[Keyword] Escuta ativa para: '{self._keyword}'")
        return f"Detecção de palavra-chave '{self._keyword}' ativada. Diga '{self._keyword}' para interagir."
    
    def _loop_escuta(self):
        """Loop de escuta contínua para a palavra-chave."""
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8
            
            mic = sr.Microphone()
            
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
            
            def _escuta_callback(recognizer_inst, audio):
                """Callback chamado quando áudio é detectado."""
                if not self._ativo:
                    return
                
                try:
                    texto = recognizer_inst.recognize_google(audio, language="pt-BR").lower()
                    
                    if self._keyword in texto:
                        logger.info(f"[Keyword] Palavra-chave detectada: '{texto}'")
                        
                        if self._callback:
                            try:
                                self._callback()
                            except Exception as e:
                                logger.error(f"[Keyword] Erro no callback: {e}")
                        
                except sr.UnknownValueError:
                    pass  # Áudio não reconhecido — ignorar
                except sr.RequestError as e:
                    logger.warning(f"[Keyword] Erro no reconhecimento: {e}")
                except Exception as e:
                    logger.error(f"[Keyword] Erro inesperado: {e}")
            
            stop_listening = recognizer.listen_in_background(mic, _escuta_callback, phrase_time_limit=5)
            
            # Manter thread viva
            while self._ativo:
                time.sleep(0.5)
            
            # Parar escuta
            stop_listening(wait_for_stop=False)
            
        except Exception as e:
            logger.error(f"[Keyword] Erro na escuta: {e}")
            self._ativo = False
    
    def parar(self) -> str:
        """Para a escuta por palavra-chave."""
        if not self._ativo:
            return "Detecção de palavra-chave já está inativa."
        
        self._ativo = False
        return "Detecção de palavra-chave desativada."
    
    def status(self) -> str:
        """Status da detecção de palavra-chave."""
        return (
            f"Ativação por Palavra-Chave:\n"
            f"  Estado: {'Ativa' if self._ativo else 'Inativa'}\n"
            f"  Keyword: '{self._keyword}'\n"
            f"  Biblioteca: {'Disponível' if self._sr_disponivel else 'Não disponível'}"
        )


# ── Singleton global ──────────────────────────────────────────
_keyword_engine = KeywordActivation()


# ═══════════════════════════════════════════════════════════════
#  API PÚBLICA — Funções exportadas para o agent.py
# ═══════════════════════════════════════════════════════════════

def inicializar_alarmes():
    """Inicializa o sistema de alarmes. Chamar no startup."""
    _engine.inicializar()
    logger.info("[Alarme] Sistema de alarmes inicializado")


def definir_alarme(horario: str, descricao: str = "Alarme") -> str:
    """Define um novo alarme."""
    if not _engine._inicializado:
        _engine.inicializar()
    return _engine.adicionar_alarme(horario, descricao)


def remover_alarme(indice: int = -1) -> str:
    """Remove um alarme."""
    return _engine.remover_alarme(indice)


def listar_alarmes() -> str:
    """Lista alarmes ativos."""
    return _engine.listar_alarmes()


def parar_alarme() -> str:
    """Para o alarme que está tocando."""
    return _engine.parar_alarme()


def status_alarmes() -> str:
    """Status do sistema de alarmes."""
    return _engine.status()


def iniciar_keyword(keyword: str = "jarvis", callback=None) -> str:
    """Inicia detecção de palavra-chave."""
    _keyword_engine.inicializar(keyword, callback)
    return _keyword_engine.iniciar()


def parar_keyword() -> str:
    """Para detecção de palavra-chave."""
    return _keyword_engine.parar()


def status_keyword() -> str:
    """Status da detecção de palavra-chave."""
    return _keyword_engine.status()
