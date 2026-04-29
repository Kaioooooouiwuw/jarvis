"""
═══════════════════════════════════════════════════════════════
  JARVIS CORE ENGINE — Motor central de persistência & eventos
═══════════════════════════════════════════════════════════════

Fornece:
  • DataStore  — CRUD thread-safe para JSON com validação
  • EventBus   — Barramento de eventos interno (publish/subscribe)
  • Helpers    — Barra de progresso, formatação de tempo, hashing
"""

import os
import json
import hashlib
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional


# ── Paths ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  DataStore — Persistência JSON thread-safe com schema
# ═══════════════════════════════════════════════════════════════

class DataStore:
    """
    Wrapper thread-safe para arquivos JSON.
    
    Uso:
        ds = DataStore("comportamento", default={"sessoes": [], "acoes": {}})
        dados = ds.load()
        dados["sessoes"].append({...})
        ds.save(dados)
    """

    _locks: dict[str, threading.Lock] = {}

    def __init__(self, nome: str, default: Any = None, subdir: str = ""):
        pasta = os.path.join(DATA_DIR, subdir) if subdir else DATA_DIR
        os.makedirs(pasta, exist_ok=True)
        self.path = os.path.join(pasta, f"{nome}.json")
        self.default = default if default is not None else {}

        if nome not in DataStore._locks:
            DataStore._locks[nome] = threading.Lock()
        self._lock = DataStore._locks[nome]

        self._garantir()

    def _garantir(self):
        if not os.path.exists(self.path):
            self._write(self.default)

    def _write(self, dados):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2, default=str)

    def load(self) -> Any:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self._write(self.default)
                return self.default.copy() if isinstance(self.default, (dict, list)) else self.default

    def save(self, dados: Any):
        with self._lock:
            self._write(dados)

    def update(self, fn: Callable[[Any], Any]):
        """Atômico: load → fn(dados) → save."""
        with self._lock:
            dados = self.load()
            resultado = fn(dados)
            self._write(dados)
            return resultado


# ═══════════════════════════════════════════════════════════════
#  DataStoreMD — Persistência Markdown
# ═══════════════════════════════════════════════════════════════

class DataStoreMD:
    """Gerencia arquivos Markdown com seções."""

    def __init__(self, nome: str):
        self.path = os.path.join(DATA_DIR, f"{nome}.md")
        self._lock = threading.Lock()

    def garantir(self, conteudo_inicial: str = ""):
        if not os.path.exists(self.path):
            with self._lock:
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write(conteudo_inicial)

    def read(self) -> str:
        with self._lock:
            if not os.path.exists(self.path):
                return ""
            with open(self.path, "r", encoding="utf-8") as f:
                return f.read()

    def write(self, conteudo: str):
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(conteudo)

    def append_to_section(self, header: str, linha: str) -> bool:
        conteudo = self.read()
        if header in conteudo:
            conteudo = conteudo.replace(header + "\n", header + "\n" + linha + "\n", 1)
        else:
            conteudo += f"\n{header}\n{linha}\n"
        self.write(conteudo)
        return True


# ═══════════════════════════════════════════════════════════════
#  EventBus — Pub/Sub interno para comunicação entre módulos
# ═══════════════════════════════════════════════════════════════

class EventBus:
    """
    Barramento de eventos.
    
    Uso:
        bus = EventBus()
        bus.subscribe("acao_executada", meu_handler)
        bus.publish("acao_executada", {"tipo": "pesquisa", "query": "x"})
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._subscribers: dict[str, list[Callable]] = {}
            return cls._instance

    def subscribe(self, evento: str, callback: Callable):
        self._subscribers.setdefault(evento, []).append(callback)

    def unsubscribe(self, evento: str, callback: Callable):
        if evento in self._subscribers:
            self._subscribers[evento] = [
                cb for cb in self._subscribers[evento] if cb != callback
            ]

    def publish(self, evento: str, dados: Any = None):
        for cb in self._subscribers.get(evento, []):
            try:
                cb(dados)
            except Exception:
                pass  # Falhas em handlers não devem parar o sistema


# ── Singleton global ──────────────────────────────────────────
event_bus = EventBus()


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#  Fuso Horário Brasil (UTC-3)
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

def agora_brasil() -> datetime:
    """Retorna datetime atual com fuso horário do Brasil (UTC-3)."""
    return datetime.now(timezone.utc) - timedelta(hours=3)


def agora_brasil_iso() -> str:
    """Retorna timestamp ISO com fuso horário do Brasil."""
    return agora_brasil().isoformat()


def agora_brasil_fmt(fmt: str = "%H:%M") -> str:
    """Retorna hora formatada com fuso horário do Brasil."""
    return agora_brasil().strftime(fmt)


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#  Helpers — Utilitários compartilhados
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

def barra_progresso(porcentagem: float, largura: int = 20) -> str:
    """Gera barra visual: [██████████░░░░░░░░░░] 50%"""
    pct = min(100, max(0, porcentagem))
    preenchido = int(pct / (100 / largura))
    vazio = largura - preenchido
    return f"[{'█' * preenchido}{'░' * vazio}] {pct:.0f}%"


def tempo_formatado(minutos: float) -> str:
    """Formata minutos em string legível."""
    if minutos < 1:
        return f"{minutos * 60:.0f}s"
    if minutos < 60:
        return f"{minutos:.0f}min"
    h = int(minutos // 60)
    m = int(minutos % 60)
    return f"{h}h{m:02d}min"


def agora_iso() -> str:
    return agora_brasil_iso()


def agora_fmt(fmt: str = "%H:%M") -> str:
    return agora_brasil_fmt(fmt)


def hash_texto(texto: str) -> str:
    return hashlib.md5(texto.encode()).hexdigest()[:12]


def saudacao() -> str:
    h = agora_brasil().hour
    if h < 6:
        return "Boa madrugada"
    elif h < 12:
        return "Bom dia"
    elif h < 18:
        return "Boa tarde"
    return "Boa noite"


def periodo_do_dia() -> str:
    h = agora_brasil().hour
    if 6 <= h < 12:
        return "manhã"
    elif 12 <= h < 18:
        return "tarde"
    elif 18 <= h < 23:
        return "noite"
    return "madrugada"
