"""
═══════════════════════════════════════════════════════════════
  SFX ENGINE v2 — Sistema de Efeitos Sonoros do G.U.I.D.E.O.N
═══════════════════════════════════════════════════════════════

Fornece:
  • Reprodução de SFX local com ZERO delay (pygame canal dedicado)
  • Pre-loading de sons para resposta instantânea
  • Separação total entre SFX (local) e streaming (LiveKit)
  • Controle de volume e configuração persistente
  • Multi-backend com fallback (pygame → winsound → ffplay)

Arquitetura:
  SFX → pygame.mixer com canal dedicado (Channel 0)
  Streaming → LiveKit / browser (separado, nunca no mesmo canal)
"""

import os
import threading
import logging
import time
from typing import Optional, Dict

from jarvis_modules.core import BASE_DIR, DataStore, event_bus

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────
SFX_DIR = os.path.join(BASE_DIR, "SFX")
os.makedirs(SFX_DIR, exist_ok=True)

# ── Persistência de configurações SFX ─────────────────────────
_sfx_config = DataStore("sfx_config", default={
    "habilitado": True,
    "volume": 0.7,
    "sfx_mapeamento": {
        "comando_iniciado": "sonoro.wav",
        "comando_concluido": "sonoro.wav",
        "erro_detectado": "sonoro.wav",
        "audio_corrigido": "sonoro.wav",
    },
    "reproducoes_totais": 0,
    "ultimo_sfx": None,
})


# ── Player de áudio otimizado com canal dedicado ──────────────
class SFXPlayer:
    """
    Player de SFX de baixa latência com canal dedicado.
    
    Características:
      - pygame.mixer inicializado com buffer 4096 (estabilidade)
      - Canal 0 reservado exclusivamente para SFX
      - Pré-carregamento de sons em memória (cache)
      - Reprodução síncrona (aguarda término) ou assíncrona
      - Separação total do pipeline de streaming/LiveKit
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._inicializado = False
                cls._instance._backend = None
                cls._instance._volume = 0.7
                cls._instance._cache_sons: Dict[str, object] = {}
                cls._instance._canal_sfx = None
                cls._instance._pygame_disponivel = False
            return cls._instance

    def inicializar(self):
        """Inicializa o melhor backend disponível com buffer otimizado."""
        if self._inicializado:
            return

        # ── Tentativa 1: pygame com configuração otimizada ────
        try:
            import pygame
            # Pre-init para evitar conflitos se já inicializado
            if pygame.mixer.get_init():
                pygame.mixer.quit()
                time.sleep(0.1)

            pygame.mixer.pre_init(
                frequency=44100,
                size=-16,
                channels=2,
                buffer=8192  # Buffer 8192 = máxima estabilidade, zero crackle
            )
            pygame.mixer.init(
                frequency=44100,
                size=-16,
                channels=2,
                buffer=8192
            )

            # Reservar canais: canal 0 = SFX exclusivo
            pygame.mixer.set_num_channels(8)  # 8 canais disponíveis
            self._canal_sfx = pygame.mixer.Channel(0)  # Canal dedicado SFX
            self._canal_sfx.set_volume(self._volume)

            self._backend = "pygame"
            self._pygame_disponivel = True
            self._inicializado = True

            # Pré-carregar todos os sons da pasta SFX
            self._precarregar_sons()

            logger.info(
                f"[SFX] Backend: pygame.mixer ✓ "
                f"(44100Hz, 16bit, stereo, buffer=8192, canal dedicado)"
            )
            return
        except (ImportError, Exception) as e:
            logger.debug(f"[SFX] pygame não disponível: {e}")

        # ── Tentativa 2: winsound (Windows nativo, .wav only) ──
        try:
            import winsound
            self._backend = "winsound"
            self._inicializado = True
            logger.info("[SFX] Backend: winsound ✓")
            return
        except ImportError:
            logger.debug("[SFX] winsound não disponível")

        # ── Tentativa 3: subprocess com ffplay ─────────────────
        import shutil
        if shutil.which("ffplay"):
            self._backend = "ffplay"
            self._inicializado = True
            logger.info("[SFX] Backend: ffplay ✓")
            return

        logger.warning("[SFX] ⚠ Nenhum backend de áudio disponível!")
        self._backend = None
        self._inicializado = True

    def _precarregar_sons(self):
        """Carrega todos os arquivos de áudio da pasta SFX em memória."""
        if not self._pygame_disponivel:
            return

        import pygame
        extensoes = ('.wav', '.mp3', '.ogg')

        for arquivo in os.listdir(SFX_DIR):
            if arquivo.lower().endswith(extensoes):
                caminho = os.path.join(SFX_DIR, arquivo)
                try:
                    som = pygame.mixer.Sound(caminho)
                    som.set_volume(self._volume)
                    self._cache_sons[arquivo] = som
                    logger.info(f"[SFX] ⏫ Pré-carregado: {arquivo}")
                except Exception as e:
                    logger.warning(f"[SFX] Erro ao pré-carregar {arquivo}: {e}")

        logger.info(f"[SFX] {len(self._cache_sons)} sons em cache")

    def _obter_som(self, nome_arquivo: str):
        """Obtém som do cache ou carrega sob demanda."""
        if nome_arquivo in self._cache_sons:
            return self._cache_sons[nome_arquivo]

        if not self._pygame_disponivel:
            return None

        # Carregar sob demanda
        caminho = os.path.join(SFX_DIR, nome_arquivo)
        if not os.path.exists(caminho):
            # Tentar com extensão alternativa
            nome_base = os.path.splitext(nome_arquivo)[0]
            for ext in ('.wav', '.mp3', '.ogg'):
                alt_caminho = os.path.join(SFX_DIR, nome_base + ext)
                if os.path.exists(alt_caminho):
                    caminho = alt_caminho
                    nome_arquivo = nome_base + ext
                    break
            else:
                return None

        try:
            import pygame
            som = pygame.mixer.Sound(caminho)
            som.set_volume(self._volume)
            self._cache_sons[nome_arquivo] = som
            return som
        except Exception as e:
            logger.error(f"[SFX] Erro ao carregar {nome_arquivo}: {e}")
            return None

    def set_volume(self, volume: float):
        """Define volume entre 0.0 e 1.0 para todos os sons em cache."""
        self._volume = max(0.0, min(1.0, volume))

        # Atualizar volume do canal dedicado
        if self._canal_sfx is not None:
            try:
                self._canal_sfx.set_volume(self._volume)
            except Exception:
                pass

        # Atualizar volume de todos os sons no cache
        for som in self._cache_sons.values():
            try:
                som.set_volume(self._volume)
            except Exception:
                pass

    def reproduzir_sincrono(self, nome_arquivo: str, timeout_ms: int = 5000) -> bool:
        """
        Reproduz SFX e AGUARDA conclusão (bloqueante).
        Usado para garantir que o SFX toque ANTES de executar o comando.
        
        Args:
            nome_arquivo: nome do arquivo SFX
            timeout_ms: tempo máximo de espera em ms (segurança)
        
        Returns:
            True se reproduziu com sucesso
        """
        if not self._inicializado:
            self.inicializar()

        try:
            if self._backend == "pygame" and self._pygame_disponivel:
                som = self._obter_som(nome_arquivo)
                if som is None:
                    logger.warning(f"[SFX] Som não encontrado: {nome_arquivo}")
                    return False

                # Tocar no canal dedicado (não interfere com nada)
                self._canal_sfx.play(som)

                # Aguardar término com timeout
                inicio = time.time()
                timeout_s = timeout_ms / 1000.0
                while self._canal_sfx.get_busy():
                    time.sleep(0.01)
                    if time.time() - inicio > timeout_s:
                        self._canal_sfx.stop()
                        break

                return True

            elif self._backend == "winsound":
                import winsound
                caminho = os.path.join(SFX_DIR, nome_arquivo)
                if not caminho.lower().endswith(".wav"):
                    # Tentar achar .wav
                    nome_base = os.path.splitext(nome_arquivo)[0]
                    caminho = os.path.join(SFX_DIR, nome_base + ".wav")

                if os.path.exists(caminho):
                    winsound.PlaySound(caminho, winsound.SND_FILENAME)
                    return True
                return False

            elif self._backend == "ffplay":
                import subprocess
                caminho = os.path.join(SFX_DIR, nome_arquivo)
                if os.path.exists(caminho):
                    subprocess.run(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                         "-volume", str(int(self._volume * 100)), caminho],
                        timeout=timeout_ms // 1000 + 1,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True
                return False

        except Exception as e:
            logger.error(f"[SFX] Erro na reprodução síncrona: {e}")
            return False

        return False

    def reproduzir_assincrono(self, nome_arquivo: str) -> bool:
        """
        Reproduz SFX sem bloquear (fire-and-forget).
        Para efeitos de fundo ou notificações.
        """
        if not self._inicializado:
            self.inicializar()

        try:
            if self._backend == "pygame" and self._pygame_disponivel:
                som = self._obter_som(nome_arquivo)
                if som is None:
                    return False

                # Tocar no canal dedicado
                self._canal_sfx.play(som)
                return True

            elif self._backend == "winsound":
                import winsound
                caminho = os.path.join(SFX_DIR, nome_arquivo)
                if caminho.lower().endswith(".wav") and os.path.exists(caminho):
                    winsound.PlaySound(
                        caminho,
                        winsound.SND_FILENAME | winsound.SND_ASYNC
                    )
                    return True
                return False

            elif self._backend == "ffplay":
                import subprocess
                caminho = os.path.join(SFX_DIR, nome_arquivo)
                if os.path.exists(caminho):
                    subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                         "-volume", str(int(self._volume * 100)), caminho],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True
                return False

        except Exception as e:
            logger.error(f"[SFX] Erro na reprodução assíncrona: {e}")
            return False

        return False

    def parar(self):
        """Para qualquer SFX em reprodução."""
        if self._canal_sfx is not None:
            try:
                self._canal_sfx.stop()
            except Exception:
                pass

    def esta_tocando(self) -> bool:
        """Verifica se há SFX em reprodução."""
        if self._canal_sfx is not None:
            try:
                return self._canal_sfx.get_busy()
            except Exception:
                pass
        return False

    def recarregar_cache(self):
        """Recarrega todos os sons do cache (útil após adicionar novos SFX)."""
        self._cache_sons.clear()
        if self._pygame_disponivel:
            self._precarregar_sons()


# ── Singleton global ──────────────────────────────────────────
_player = SFXPlayer()


# ═══════════════════════════════════════════════════════════════
#  API Pública — Funções exportadas
# ═══════════════════════════════════════════════════════════════

def inicializar_sfx():
    """Inicializa o sistema de SFX. Chamar no startup do agente."""
    _player.inicializar()
    config = _sfx_config.load()
    _player.set_volume(config.get("volume", 0.7))
    logger.info(
        f"[SFX] Sistema inicializado | "
        f"Volume: {config.get('volume', 0.7)*100:.0f}% | "
        f"Backend: {_player._backend} | "
        f"Sons em cache: {len(_player._cache_sons)}"
    )


def tocar_sfx(evento: str = "comando_iniciado", sincrono: bool = False) -> str:
    """
    Toca o SFX associado ao evento.
    
    Args:
        evento: comando_iniciado, comando_concluido, erro_detectado, audio_corrigido
        sincrono: se True, aguarda o SFX terminar antes de retornar
                  (usar para garantir SFX antes de ação)
    """
    config = _sfx_config.load()

    if not config.get("habilitado", True):
        return "SFX desabilitado."

    mapeamento = config.get("sfx_mapeamento", {})
    arquivo = mapeamento.get(evento, "sonoro.wav")

    if sincrono:
        sucesso = _player.reproduzir_sincrono(arquivo)
    else:
        sucesso = _player.reproduzir_assincrono(arquivo)

    if sucesso:
        # Atualizar estatísticas em thread separada (não bloquear)
        def _salvar_stats():
            try:
                cfg = _sfx_config.load()
                cfg["reproducoes_totais"] = cfg.get("reproducoes_totais", 0) + 1
                cfg["ultimo_sfx"] = arquivo
                _sfx_config.save(cfg)
            except Exception:
                pass

        threading.Thread(target=_salvar_stats, daemon=True).start()
        logger.info(f"[SFX] ▶ {arquivo} (evento: {evento}, sincrono: {sincrono})")
        return f"SFX '{arquivo}' reproduzido para evento '{evento}'."

    return f"Não foi possível reproduzir SFX para '{evento}'."


def tocar_sfx_antes_comando(evento: str = "comando_iniciado"):
    """
    Toca SFX de forma ASSÍNCRONA (fire-and-forget) via thread.
    NUNCA bloqueia a execução — o comando roda imediatamente.
    
    IMPORTANTE: Roda localmente via pygame, NÃO passa pelo LiveKit.
    """
    def _fire_and_forget():
        try:
            tocar_sfx(evento, sincrono=False)
        except Exception:
            pass
    threading.Thread(target=_fire_and_forget, daemon=True).start()


def configurar_sfx(habilitado: Optional[bool] = None,
                   volume: Optional[float] = None,
                   evento: str = "",
                   arquivo: str = "") -> str:
    """
    Configura o sistema de SFX.
    - habilitado: True/False para ligar/desligar
    - volume: 0.0 a 1.0
    - evento + arquivo: mapeia evento para arquivo SFX
    """
    config = _sfx_config.load()
    alteracoes = []

    if habilitado is not None:
        config["habilitado"] = habilitado
        estado = "habilitado" if habilitado else "desabilitado"
        alteracoes.append(f"SFX {estado}")

    if volume is not None:
        vol = max(0.0, min(1.0, volume))
        config["volume"] = vol
        _player.set_volume(vol)
        alteracoes.append(f"Volume: {vol*100:.0f}%")

    if evento and arquivo:
        caminho = os.path.join(SFX_DIR, arquivo)
        # Verificar com extensões alternativas
        if not os.path.exists(caminho):
            nome_base = os.path.splitext(arquivo)[0]
            encontrado = False
            for ext in ('.wav', '.mp3', '.ogg'):
                if os.path.exists(os.path.join(SFX_DIR, nome_base + ext)):
                    arquivo = nome_base + ext
                    encontrado = True
                    break
            if not encontrado:
                return f"Arquivo SFX '{arquivo}' não encontrado na pasta SFX/"

        config.setdefault("sfx_mapeamento", {})[evento] = arquivo
        alteracoes.append(f"Evento '{evento}' → '{arquivo}'")

    _sfx_config.save(config)

    if alteracoes:
        return "SFX configurado: " + " | ".join(alteracoes)
    return "Nenhuma alteração realizada."


def listar_sfx() -> str:
    """Lista todos os arquivos SFX disponíveis e a configuração atual."""
    config = _sfx_config.load()

    # Listar arquivos na pasta SFX
    arquivos = []
    if os.path.exists(SFX_DIR):
        arquivos = [f for f in os.listdir(SFX_DIR)
                    if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a'))]

    mapeamento = config.get("sfx_mapeamento", {})

    linhas = [
        "🔊 **Sistema SFX v2 — G.U.I.D.E.O.N**",
        f"  Estado: {'✅ Habilitado' if config.get('habilitado') else '❌ Desabilitado'}",
        f"  Volume: {config.get('volume', 0.7)*100:.0f}%",
        f"  Backend: {_player._backend or 'Nenhum'}",
        f"  Sons em cache: {len(_player._cache_sons)}",
        f"  Canal dedicado: {'✅ Ativo' if _player._canal_sfx else '❌ Não'}",
        f"  Reproduções totais: {config.get('reproducoes_totais', 0)}",
        "",
        "📁 **Arquivos disponíveis:**",
    ]

    for arq in arquivos:
        # Verificar se está no cache
        em_cache = "⚡" if arq in _player._cache_sons else "💤"
        eventos_mapeados = [ev for ev, f in mapeamento.items() if f == arq]
        if eventos_mapeados:
            linhas.append(f"  {em_cache} {arq} → {', '.join(eventos_mapeados)}")
        else:
            linhas.append(f"  {em_cache} {arq} (sem mapeamento)")

    if not arquivos:
        linhas.append("  (nenhum arquivo encontrado)")

    linhas.extend([
        "",
        "🎯 **Mapeamento de eventos:**",
    ])
    for evento, arquivo in mapeamento.items():
        linhas.append(f"  {evento} → {arquivo}")

    linhas.extend([
        "",
        "ℹ️ ⚡ = Pré-carregado (instantâneo) | 💤 = Sob demanda",
    ])

    return "\n".join(linhas)


def recarregar_sfx() -> str:
    """Recarrega todos os sons do cache. Usar após adicionar novos arquivos SFX."""
    _player.recarregar_cache()
    return f"Cache SFX recarregado. {len(_player._cache_sons)} sons em memória."


# ── Hook automático no EventBus ───────────────────────────────
_ultimo_sfx_time = {}
_ultimo_sfx_lock = threading.Lock()

def _sfx_on_evento(dados):
    """Handler automático que toca SFX quando um evento é publicado."""
    if isinstance(dados, dict):
        tipo = dados.get("tipo", "comando_iniciado")
        sincrono = dados.get("sincrono", False)
    else:
        tipo = "comando_iniciado"
        sincrono = False
    
    # ✅ DESABILITADO: audio_corrigido estava causando repetições excessivas
    if tipo == "audio_corrigido":
        return  # Ignorar completamente SFX de correção de áudio
    
    tocar_sfx(tipo, sincrono=sincrono)


# Registrar no EventBus para disparo automático
event_bus.subscribe("sfx_trigger", _sfx_on_evento)
