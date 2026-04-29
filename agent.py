"""
═══════════════════════════════════════════════════════════════
  Agente JARVIS com LiveKit
  CORRIGIDO: latncia de udio, event loop, mem0, model=
═══════════════════════════════════════════════════════════════
"""

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, RoomOutputOptions, ChatContext, llm
try:
    from livekit.agents import RoomOptions
    HAS_ROOM_OPTIONS = True
except ImportError:
    HAS_ROOM_OPTIONS = False
from livekit.plugins import noise_cancellation, google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from mem0 import AsyncMemoryClient
import logging
import os
import asyncio
import webbrowser
import subprocess
from urllib.parse import quote_plus
import urllib.request as _urllib

try:
    import yt_dlp
    YT_DLP_DISPONIVEL = True
except ImportError:
    YT_DLP_DISPONIVEL = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_DISPONIVEL = True
except ImportError:
    PLAYWRIGHT_DISPONIVEL = False

from automacao_jarvis import JarvisControl

from jarvis_modules.conhecimento import (
    salvar_conhecimento, ler_conhecimento, ler_conhecimento_para_contexto
)
from jarvis_modules.timeline import (
    registrar_evento, consultar_timeline, estatisticas_timeline,
    registrar_erro, sugerir_correcao, consultar_erros,
)
from jarvis_modules.comportamento import (
    analisar_comportamento, prever_acao, sugestao_contextual,
    registrar_sessao, registrar_acao,
)
from jarvis_modules.autonomo import (
    ativar_modo_autonomo as _ativar_autonomo,
    desativar_modo_autonomo as _desativar_autonomo,
    status_modo_autonomo as _status_autonomo,
    executar_tarefa_complexa as _executar_multi,
    status_tarefa as _status_tarefa,
    listar_tarefas as _listar_tarefas,
)
from jarvis_modules.desenvolvimento import (
    gerar_projeto_completo as _gerar_projeto,
    debug_autonomo as _debug_auto,
    refatoracao_inteligente as _refatorar,
    explicar_codigo as _explicar,
    gerar_interface_ui as _gerar_ui,
)
from jarvis_modules.web_inteligente import (
    navegar_e_extrair_dados as _extrair_dados,
    monitorar_site as _monitorar,
    parar_monitoramento as _parar_monitor,
    listar_monitores as _listar_monitores,
)
from jarvis_modules.vida_real import (
    assistente_rotina as _rotina,
    modo_foco_total as _foco,
    coach_inteligente as _coach,
)
from jarvis_modules.plugins import (
    instalar_plugin as _instalar_plugin,
    carregar_plugin as _carregar_plugin,
    listar_plugins as _listar_plugins,
    remover_plugin as _remover_plugin,
)
from jarvis_modules.clonar_tarefa import (
    gravar_tarefa as _gravar_tarefa,
    parar_gravacao as _parar_gravacao,
    executar_tarefa_clonada as _exec_clone,
    listar_tarefas_clonadas as _listar_clones,
)
from jarvis_modules.objetivos import (
    definir_objetivo as _definir_obj,
    listar_objetivos as _listar_objs,
    atualizar_progresso as _prog_obj,
    registrar_aprendizado as _aprender_obj,
    gerar_relatorio_objetivo as _relatorio_obj,
    evoluir_estrategia as _evoluir_obj,
)
from jarvis_modules.gestos import (
    iniciar_controle_gestos as _iniciar_gestos,
    parar_controle_gestos as _parar_gestos,
    status_gestos as _status_gestos,
    iniciar_voice_listener as _iniciar_voice_gestos,
    parar_voice_listener as _parar_voice_gestos,
    iniciar_sistema_completo as _iniciar_sistema_gestos,
    parar_sistema_completo as _parar_sistema_gestos,
)
from jarvis_modules.sfx import (
    inicializar_sfx,
    tocar_sfx,
    tocar_sfx_antes_comando,
    configurar_sfx,
    listar_sfx,
    recarregar_sfx,
)
from jarvis_modules.audio_health import (
    diagnostico_audio as _diagnostico_audio,
    corrigir_audio as _corrigir_audio,
    sugerir_alternativa as _sugerir_alternativa,
    historico_problemas as _historico_problemas,
    iniciar_monitor_audio as _iniciar_monitor,
    parar_monitor_audio as _parar_monitor_audio,
    status_monitor_audio as _status_monitor_audio,
)
from jarvis_modules.whatsapp import (
    enviar_mensagem_whatsapp as _enviar_whatsapp,
)
from jarvis_modules.seguranca_etica import (
    scan_seguranca_completo as _scan_seguranca_completo,
    scan_seguranca_rapido as _scan_seguranca_rapido,
    analisar_relatorio_seguranca as _analisar_relatorio_seguranca,
    get_seguranca_instance as _get_seguranca_instance,
)
from jarvis_modules.desktop_control import (
    abrir_aplicativo_avancado as _abrir_app_avancado,
    fechar_aplicativo as _fechar_app,
    listar_janelas_abertas as _listar_janelas,
    focar_janela as _focar_janela,
    minimizar_janela as _minimizar_janela,
    maximizar_janela as _maximizar_janela,
    nova_aba as _nova_aba,
    fechar_aba as _fechar_aba,
    trocar_aba as _trocar_aba,
    ir_para_aba as _ir_aba,
    reabrir_aba as _reabrir_aba,
    digitar_texto as _digitar_texto,
    pressionar_tecla as _pressionar_tecla,
    atalho_teclado as _atalho_teclado,
    clicar_posicao as _clicar_posicao,
    clicar_imagem as _clicar_imagem,
    mover_mouse as _mover_mouse,
    scroll_mouse as _scroll_mouse,
    posicao_mouse as _posicao_mouse,
    captura_tela as _captura_tela,
    interagir_photoshop as _interagir_photoshop,
    navegar_url as _navegar_url,
    busca_automatica as _busca_automatica,
    interagir_pagina as _interagir_pagina,
    arrastar as _arrastar,
)
from jarvis_modules.site_analyzer import (
    analisar_site_completo as _analisar_site,
    analise_rapida_seguranca as _analise_rapida_seg,
    ler_e_resumir_site as _ler_resumir_site,
    historico_analises as _historico_analises,
)
from jarvis_modules.notification_monitor import (
    iniciar_monitor_notificacoes as _iniciar_notif,
    parar_monitor_notificacoes as _parar_notif,
    status_monitor_notificacoes as _status_notif,
    ver_notificacoes_recentes as _ver_notif,
    capturar_notificacoes_agora as _capturar_notif,
    configurar_monitor_notificacoes as _config_notif,
    limpar_historico_notificacoes as _limpar_notif,
    ler_todas_notificacoes as _ler_todas_notif,
    ler_notificacoes_pendentes as _ler_pendentes_notif,
    verificar_novas_notificacoes as _verificar_novas_notif,
)
from jarvis_modules.memory_persistent import (
    salvar_conversa_completa as _salvar_conversa_local,
    carregar_ultima_conversa as _carregar_ultima_conversa,
    buscar_em_conversas as _buscar_conversas,
    listar_sessoes_recentes as _listar_sessoes,
    salvar_fato as _salvar_fato,
    listar_fatos as _listar_fatos,
    salvar_preferencia as _salvar_preferencia,
    listar_preferencias as _listar_preferencias,
    gerar_contexto_memorias as _gerar_contexto_memorias,
    guardar_memoria_explicita as _guardar_memoria,
    listar_memorias_explicitas as _listar_memorias,
    buscar_memoria_explicita as _buscar_memoria,
    remover_memoria_explicita as _remover_memoria,
    gerar_saudacao_contextualizada as _saudacao_contextual,
)
from jarvis_modules.vscode_editor import (
    abrir_vscode as _abrir_vscode,
    abrir_arquivo_vscode as _abrir_arquivo_vscode,
    criar_arquivo_vscode as _criar_arquivo_vscode,
    abrir_pasta_vscode as _abrir_pasta_vscode,
    editar_codigo_vscode as _editar_codigo_vscode,
    comando_vscode as _comando_vscode,
    terminal_vscode as _terminal_vscode,
    novo_terminal_vscode as _novo_terminal_vscode,
    atalho_vscode as _atalho_vscode,
    inserir_codigo_vscode as _inserir_codigo_vscode,
    instalar_extensao_vscode as _instalar_ext_vscode,
    listar_extensoes_vscode as _listar_ext_vscode,
    diff_vscode as _diff_vscode,
    criar_snippet_vscode as _criar_snippet_vscode,
)
from tuya_service import (
    get_token as _tuya_get_token,
    ligar_dispositivo as _tuya_ligar,
    desligar_dispositivo as _tuya_desligar,
    status_dispositivo as _tuya_status,
    mudar_cor as _tuya_cor,
    ajustar_brilho as _tuya_brilho,
    listar_dispositivos as _tuya_listar,
    obter_funcionalidades as _tuya_funcionalidades,
)
from jarvis_modules.clima_deslocamento import (
    consultar_clima as _consultar_clima,
    consultar_clima_coordenadas as _consultar_clima_coords,
    calcular_deslocamento as _calcular_deslocamento,
    calcular_deslocamento_cidades as _calcular_deslocamento_cidades,
    historico_consultas_clima as _historico_clima,
)
from jarvis_modules.alarme_sistema import (
    inicializar_alarmes as _inicializar_alarmes,
    definir_alarme as _definir_alarme,
    remover_alarme as _remover_alarme,
    listar_alarmes as _listar_alarmes,
    parar_alarme as _parar_alarme,
    status_alarmes as _status_alarmes,
    iniciar_keyword as _iniciar_keyword,
    parar_keyword as _parar_keyword,
    status_keyword as _status_keyword,
)
from jarvis_modules.seguranca_camera import (
    iniciar_seguranca as _iniciar_seguranca,
    parar_seguranca as _parar_seguranca,
    status_seguranca as _status_seguranca,
    cadastrar_rosto as _cadastrar_rosto,
    listar_rostos as _listar_rostos,
    remover_rosto as _remover_rosto,
    parar_alarme as _parar_alarme_seg,
    historico_intrusoes as _historico_intrusoes,
)
from jarvis_modules.nlu_engine import (
    interpretar_comando as _nlu_interpretar,
    executar_nlu as _nlu_executar,
    contexto_atual as _nlu_contexto,
    limpar_contexto as _nlu_limpar,
    historico_comandos as _nlu_historico,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# CHROME + CDP
# CORRIGIDO: removido taskkill, usa thread separada
# ─────────────────────────────────────────

def _get_chrome_path():
    caminhos = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in caminhos:
        if os.path.exists(c):
            return c
    return None

CHROME_PATH = _get_chrome_path()
CDP_URL = "http://localhost:9222"

def _cdp_disponivel() -> bool:
    try:
        with _urllib.urlopen(f"{CDP_URL}/json/version", timeout=1) as r:
            return r.status == 200
    except:
        return False

def _chrome_aberto() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/fi", "imagename eq chrome.exe"],
            capture_output=True, text=True
        )
        return "chrome.exe" in result.stdout.lower()
    except:
        return False

def _abrir_browser_thread(url: str):
    """
    CORRIGIDO: Abre URL em thread separada — NUNCA bloqueia o event loop.
    Não mata o Chrome, só abre nova aba ou janela.
    """
    import threading
    def _abrir():
        try:
            if _cdp_disponivel() and PLAYWRIGHT_DISPONIVEL:
                try:
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as p:
                        browser = p.chromium.connect_over_cdp(CDP_URL)
                        page = browser.contexts[0].new_page()
                        page.goto(url)
                        browser.disconnect()
                    return
                except Exception:
                    pass
            # Chrome aberto sem CDP: abre nova aba diretamente
            if _chrome_aberto() and CHROME_PATH:
                subprocess.Popen([CHROME_PATH, url])
                return
            # Chrome fechado: abre com CDP
            if CHROME_PATH:
                subprocess.Popen([CHROME_PATH, "--remote-debugging-port=9222", url])
                return
            # Fallback final
            webbrowser.open(url)
        except Exception:
            try:
                webbrowser.open(url)
            except Exception:
                pass
    threading.Thread(target=_abrir, daemon=True).start()


# ─────────────────────────────────────────
# AGENTE
# ─────────────────────────────────────────

class Assistant(Agent):
    def __init__(self, chat_ctx: ChatContext = None, instructions: str = AGENT_INSTRUCTION):
        super().__init__(
            instructions=instructions,  # CORRIGIDO: instructions dinâmicas com memórias
            llm=google.beta.realtime.RealtimeModel(
                model="gemini-2.5-flash-native-audio-latest",  # CORRIGIDO: modelo correto
                voice="Charon",
                temperature=0.6,
            ),
            chat_ctx=chat_ctx,
        )
        self.jarvis_control = JarvisControl()

    def _sfx_comando(self, evento: str = "comando_iniciado"):
        """CORRIGIDO: Fire-and-forget via thread — NUNCA bloqueia o event loop."""
        import threading
        def _fire():
            try:
                tocar_sfx_antes_comando(evento)
            except Exception:
                pass
        threading.Thread(target=_fire, daemon=True).start()

    # CORRIGIDO: Helper: executa função síncrona pesada sem bloquear o event loop
    async def _run_sync(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    # ═══════════════════════════════════════════
    # TOOL 1 — PESQUISA WEB E YOUTUBE
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def pesquisar_na_web(self, consulta: str, tipo: str = "google"):
        """Busca na web, YouTube ou abre URL. tipo: google, youtube, imagens, url."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("acao", f"Pesquisa {tipo}: {consulta[:50]}")
            registrar_acao("pesquisar_na_web", consulta)
            if tipo.lower() == "youtube":
                url = f"https://www.youtube.com/results?search_query={quote_plus(consulta)}"
            elif tipo.lower() == "imagens":
                url = f"https://www.google.com/search?q={quote_plus(consulta)}&tbm=isch"
            elif tipo.lower() == "url":
                url = consulta
            else:
                url = f"https://www.google.com/search?q={quote_plus(consulta)}"
            _abrir_browser_thread(url)
            return f"Abrindo '{consulta}' no {tipo}."
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro: {e}"

    # ═══════════════════════════════════════════
    # TOOL 17 — TOCAR MÚSICA (YOUTUBE AVANÇADO)
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def tocar_musica_youtube(self, artista: str, musica: str = ""):
        """Busca e toca música direta no YouTube com autoplay real."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("musica", f"Tocando YouTube: {artista} {musica}")

            import yt_dlp
            import asyncio

            busca = f"{artista} {musica}".strip() if musica else f"{artista} música"

            with yt_dlp.YoutubeDL({
                'quiet': True,
                'no_warnings': True
            }) as ydl:
                info = ydl.extract_info(f"ytsearch1:{busca}", download=False)

                if not info or not info.get("entries"):
                    return "Nenhum vídeo encontrado."

                video = info["entries"][0]
                video_url = video.get("webpage_url")  # CORRIGIDO
                titulo = video.get("title", "Desconhecido")

            # abre navegador
            _abrir_browser_thread(video_url)

            # autoplay garantido
            if PLAYWRIGHT_DISPONIVEL and _cdp_disponivel():
                try:
                    await asyncio.sleep(1.5)

                    from playwright.async_api import async_playwright

                    async with async_playwright() as p:
                        browser = await p.chromium.connect_over_cdp(CDP_URL)

                        encontrou = False

                        for ctx in browser.contexts:
                            for page in ctx.pages:
                                if "youtube.com/watch" in page.url:
                                    await page.wait_for_selector("video", timeout=10000)

                                    await page.evaluate("""
                                        const v = document.querySelector('video');
                                        if (v) {
                                            v.muted = false;
                                            v.play().catch(()=>{});
                                        }
                                    """)

                                    encontrou = True
                                    break
                            if encontrou:
                                break

                        await browser.disconnect()

                except Exception:
                    pass

            return f"Tocando: {titulo}"

        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro ao tocar música: {e}"

    @agents.function_tool
    async def tocar_musica(self, artista: str, plataforma: str = "youtube"):
        """Toca música no navegador. plataforma: youtube, spotify, deezer."""
        # CORRIGIDO: REDIRECIONA PARA FUNÇÃO ESPECÍFICA DO YOUTUBE COM AUTOPLAY
        if plataforma.lower() == "youtube":
            return await self.tocar_musica_youtube(artista)
        
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("musica", f"Tocando música: {artista}")
            if plataforma.lower() == "spotify":
                url = f"https://open.spotify.com/search/{quote_plus(artista)}"
            elif plataforma.lower() == "deezer":
                url = f"https://www.deezer.com/search/{quote_plus(artista)}"
            else:
                # Fallback para YouTube search se não for reconhecido
                return await self.tocar_musica_youtube(artista)
            _abrir_browser_thread(url)
            return f"Música de '{artista}' aberta no {plataforma}."
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro ao abrir música: {e}"

    # ═══════════════════════════════════════════
    # TOOL 18 — CONTROLE YOUTUBE AVANÇADO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def pausar_youtube(self):
        """Pausa vídeo atual do YouTube."""
        return await self.controle_youtube("pausar")

    @agents.function_tool
    async def continuar_youtube(self):
        """Retoma reprodução do YouTube."""
        return await self.controle_youtube("pausar")  # toggle play/pause

    @agents.function_tool
    async def trocar_musica_youtube(self, artista: str, musica: str = ""):
        """Troca para nova música no YouTube."""
        return await self.tocar_musica_youtube(artista, musica)

    @agents.function_tool
    async def proxima_musica_youtube(self):
        """Avança para próximo vídeo recomendado."""
        return await self.controle_youtube("pular", 10)  # pula 10s para próximo

    @agents.function_tool
    async def musica_anterior_youtube(self):
        """Volta para vídeo anterior."""
        return await self.controle_youtube("pular", -30)  # volta 30s

    @agents.function_tool
    async def reiniciar_musica_youtube(self):
        """Reinicia música atual."""
        return await self.controle_youtube("pular", -999)  # volta ao início

    @agents.function_tool
    async def garantir_autoplay_youtube(self):
        """Garante que vídeo esteja tocando."""
        if PLAYWRIGHT_DISPONIVEL and _cdp_disponivel():
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(CDP_URL)
                    for ctx in browser.contexts:
                        for page in ctx.pages:
                            if "youtube.com/watch" in page.url:
                                await page.evaluate("const v=document.querySelector('video');if(v&&v.paused)v.play();")
                                await browser.disconnect()
                                return "Autoplay ativado "
                    await browser.disconnect()
            except:
                pass
        return "Não foi possível garantir autoplay"

    @agents.function_tool
    async def identificar_musica_youtube(self):
        """Identifica música atual do YouTube."""
        return await self.controle_youtube("titulo")

    # ═══════════════════════════════════════════
    # TOOL 19 — SPOTIFY AVANÇADO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def tocar_musica_spotify(self, artista: str, musica: str = ""):
        """Busca e toca música direta no Spotify."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("musica", f"Tocando Spotify: {artista} {musica}")
            
            busca = f"{artista} {musica}".strip() if musica else artista
            url = f"https://open.spotify.com/search/{quote_plus(busca)}"
            
            _abrir_browser_thread(url)
            self._sfx_comando("comando_concluido")
            return f"Buscando '{busca}' no Spotify"
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro ao tocar no Spotify: {e}"

    @agents.function_tool
    async def pausar_spotify(self):
        """Pausa música no Spotify."""
        try:
            import pygetwindow as gw
            import pyautogui
            janelas = [w for w in gw.getAllWindows() if "spotify" in w.title.lower() and w.visible]
            if janelas:
                janelas[0].activate()
                await asyncio.sleep(0.3)
                pyautogui.press("space")
                return "Spotify pausado "
        except:
            pass
        return "Não foi possível pausar Spotify"

    @agents.function_tool
    async def continuar_spotify(self):
        """Retoma música no Spotify."""
        return await self.pausar_spotify()  # toggle play/pause

    @agents.function_tool
    async def trocar_musica_spotify(self, artista: str, musica: str = ""):
        """Troca para nova música no Spotify."""
        return await self.tocar_musica_spotify(artista, musica)

    @agents.function_tool
    async def proxima_musica_spotify(self):
        """Próxima música no Spotify."""
        try:
            import pygetwindow as gw
            import pyautogui
            janelas = [w for w in gw.getAllWindows() if "spotify" in w.title.lower() and w.visible]
            if janelas:
                janelas[0].activate()
                await asyncio.sleep(0.3)
                pyautogui.press("nexttrack")
                return "Próxima música "
        except:
            pass
        return "Não foi possível avançar"

    @agents.function_tool
    async def musica_anterior_spotify(self):
        """Música anterior no Spotify."""
        try:
            import pygetwindow as gw
            import pyautogui
            janelas = [w for w in gw.getAllWindows() if "spotify" in w.title.lower() and w.visible]
            if janelas:
                janelas[0].activate()
                await asyncio.sleep(0.3)
                pyautogui.press("prevtrack")
                return "Música anterior "
        except:
            pass
        return "Não foi possível voltar"

    @agents.function_tool
    async def modo_aleatorio_spotify(self):
        """Ativa/desativa shuffle no Spotify."""
        try:
            import pygetwindow as gw
            import pyautogui
            janelas = [w for w in gw.getAllWindows() if "spotify" in w.title.lower() and w.visible]
            if janelas:
                janelas[0].activate()
                await asyncio.sleep(0.3)
                pyautogui.press("s")  # atalho shuffle
                return "Shuffle alternado "
        except:
            pass
        return "Não foi possível alternar shuffle"

    @agents.function_tool
    async def repetir_spotify(self):
        """Ativa repetição no Spotify."""
        try:
            import pygetwindow as gw
            import pyautogui
            janelas = [w for w in gw.getAllWindows() if "spotify" in w.title.lower() and w.visible]
            if janelas:
                janelas[0].activate()
                await asyncio.sleep(0.3)
                pyautogui.press("r")  # atalho repeat
                return "Repetição alternada "
        except:
            pass
        return "Não foi possível alternar repetição"

    @agents.function_tool
    async def volume_spotify(self, valor: int):
        """Controla volume do Spotify (0-100)."""
        try:
            import pygetwindow as gw
            import pyautogui
            janelas = [w for w in gw.getAllWindows() if "spotify" in w.title.lower() and w.visible]
            if janelas:
                janelas[0].activate()
                await asyncio.sleep(0.3)
                # Usa seta cima/baixo para volume
                if valor > 50:
                    pyautogui.press("up", presses=min(10, (valor-50)//5))
                else:
                    pyautogui.press("down", presses=min(10, (50-valor)//5))
                return f"Volume ajustado para {valor}%"
        except:
            pass
        return "Não foi possível ajustar volume"

    @agents.function_tool
    async def identificar_musica_spotify(self):
        """Identifica música atual no Spotify."""
        try:
            import pygetwindow as gw
            import pyautogui
            janelas = [w for w in gw.getAllWindows() if "spotify" in w.title.lower() and w.visible]
            if janelas:
                titulo = janelas[0].title
                return f"Tocando: {titulo}"
        except:
            pass
        return "Não foi possível identificar música"

    # ═══════════════════════════════════════════
    # TOOL 2 — CONTROLE YOUTUBE
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def controle_youtube(self, acao: str = "pausar", valor: int = 0):
        """Controla YouTube. acao: pausar, volume, pular, titulo."""
        self._sfx_comando("comando_iniciado")
        try:
            if acao == "pausar":
                try:
                    import pygetwindow as gw
                    import pyautogui
                    import time
                    janelas = [w for w in gw.getAllWindows() if "youtube" in w.title.lower() and w.visible]
                    if janelas:
                        janelas[0].activate()
                        # CORRIGIDO: usa to_thread para não bloquear
                        await asyncio.to_thread(time.sleep, 0.4)
                        pyautogui.press("k")
                        return "Play/Pause alternado "
                except ImportError:
                    pass

            if PLAYWRIGHT_DISPONIVEL and _cdp_disponivel():
                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(CDP_URL)
                    
                    encontrou = False

                    for ctx in browser.contexts:
                        for page in ctx.pages:
                            if "youtube.com/watch" in page.url:
                                encontrou = True

                                if acao == "pausar":
                                    await page.evaluate("""
                                        const v = document.querySelector('video');
                                        if (v) { v.paused ? v.play() : v.pause(); }
                                    """)

                                elif acao == "volume":
                                    vol = max(0, min(100, valor)) / 100
                                    await page.evaluate(f"""
                                        const v = document.querySelector('video');
                                        if (v) v.volume = {vol};
                                    """)

                                elif acao == "pular":
                                    await page.evaluate(f"""
                                        const v = document.querySelector('video');
                                        if (v) v.currentTime += {valor};
                                    """)

                                elif acao == "titulo":
                                    titulo = await page.evaluate("""
                                        document.querySelector('h1.ytd-watch-metadata yt-formatted-string')?.textContent || document.title
                                    """)
                                    await browser.disconnect()
                                    return f"Tocando: {titulo}"

                                break
                        if encontrou:
                            break

                    await browser.disconnect()

                    if encontrou:
                        return "Comando executado "
                    else:
                        return "Nenhum vídeo YouTube encontrado."
                return "Nenhum vídeo YouTube encontrado."

            return f"Ação '{acao}' não reconhecida."

        except Exception as e:
            return f"Erro: {e}"

    # ═══════════════════════════════════════════
    # TOOL 3 — LER PÁGINA ATUAL
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def ler_pagina_atual(self):
        """Lê o conteúdo da aba ativa no Chrome via CDP."""
        try:
            if not PLAYWRIGHT_DISPONIVEL or not _cdp_disponivel():
                return "CDP não disponível."
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(CDP_URL)
                for ctx in browser.contexts:
                    for page in ctx.pages:
                        url = page.url
                        if url.startswith(("chrome://", "brave://", "about:")):
                            continue
                        if "youtube.com/watch" in url:
                            await browser.disconnect()
                            return "Página de vídeo do YouTube — sem texto útil."
                        titulo = await page.title()
                        texto = await page.evaluate("()=>document.body.innerText")
                        await browser.disconnect()
                        registrar_evento("acao", f"Leitura: {titulo[:50]}")
                        return f" {titulo}\n\n{texto[:8000]}"
                await browser.disconnect()
            return "Nenhuma aba com conteúdo útil encontrada."
        except Exception as e:
            return f"Erro: {e}"

    # ═══════════════════════════════════════════
    # TOOL 4 — PROGRAMAS
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def gerenciar_programa(self, acao: str, nome: str):
        """Abre ou fecha programas. acao: abrir, fechar."""
        self._sfx_comando("comando_iniciado")
        registrar_acao("gerenciar_programa", nome)
        if acao == "fechar":
            exe = nome if nome.lower().endswith(".exe") else f"{nome}.exe"
            # CORRIGIDO: usa to_thread para não bloquear
            res = await asyncio.to_thread(subprocess.run, ["taskkill", "/f", "/im", exe], capture_output=True)
            return f"'{nome}' fechado." if res.returncode == 0 else f"Não encontrei '{nome}'."
        else:
            return await self._run_sync(self.jarvis_control.abrir_aplicativo, nome)

    # ═══════════════════════════════════════════
    # TOOL 5 — ARQUIVOS E PASTAS
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def gerenciar_arquivos(self, acao: str, caminho: str, destino: str = ""):
        """Gerencia arquivos. acao: criar, deletar, limpar, mover, copiar, renomear, organizar, compactar, abrir, buscar."""
        self._sfx_comando("comando_iniciado")
        registrar_acao("gerenciar_arquivos", caminho)
        jc = self.jarvis_control
        # CORRIGIDO: todas as operações de I/O rodam em thread separada
        acoes = {
            "criar":     lambda: jc.cria_pasta(caminho),
            "deletar":   lambda: jc.deletar_arquivo(caminho),
            "limpar":    lambda: jc.limpar_diretorio(caminho),
            "mover":     lambda: jc.mover_item(caminho, destino),
            "copiar":    lambda: jc.copiar_item(caminho, destino),
            "renomear":  lambda: jc.renomear_item(caminho, destino),
            "organizar": lambda: jc.organizar_pasta(caminho),
            "compactar": lambda: jc.compactar_pasta(caminho),
            "abrir":     lambda: jc.abrir_pasta(caminho),
            "buscar":    lambda: jc.buscar_e_abrir_arquivo(caminho),
        }
        if acao in acoes:
            return await asyncio.to_thread(acoes[acao])
        return f"Ação '{acao}' não reconhecida."

    # ═══════════════════════════════════════════
    # TOOL 6 — SISTEMA
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def controle_sistema(self, acao: str, valor: int = 50):
        """Controla sistema. acao: volume, aumentar_volume, diminuir_volume, brilho, desligar, reiniciar, bloquear.
        Para volume: valor = porcentagem (0-100).
        Para aumentar/diminuir: valor = passo de incremento (padrão 10)."""
        self._sfx_comando("comando_iniciado")
        if acao == "volume":
            # Definir volume exato
            return await asyncio.to_thread(self.jarvis_control.controle_volume, valor)
        elif acao == "aumentar_volume":
            # Aumentar volume em 'valor' porcentagem (padrão 10)
            passo = valor if valor != 50 else 10  # se valor padrão (50), usar passo 10
            return await asyncio.to_thread(self.jarvis_control.aumentar_volume, passo)
        elif acao == "diminuir_volume":
            # Diminuir volume em 'valor' porcentagem (padrão 10)
            passo = valor if valor != 50 else 10
            return await asyncio.to_thread(self.jarvis_control.diminuir_volume, passo)
        elif acao == "brilho":
            return await asyncio.to_thread(self.jarvis_control.controle_brilho, valor)
        elif acao in ("desligar", "reiniciar", "bloquear"):
            return await asyncio.to_thread(self.jarvis_control.energia_pc, acao)
        return f"Ação '{acao}' não reconhecida."

    # ═══════════════════════════════════════════
    # TOOL 7 — CONHECIMENTO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def conhecimento(self, acao: str = "ler", categoria: str = "geral", conteudo: str = ""):
        """Base de conhecimento permanente. acao: salvar, ler."""
        if acao == "salvar":
            registrar_evento("conhecimento", f"Salvou: {conteudo[:50]}", categoria)
            return await asyncio.to_thread(salvar_conhecimento, categoria, conteudo)
        return await asyncio.to_thread(ler_conhecimento)

    # ═══════════════════════════════════════════
    # TOOL 8 — MODO AUTÔNOMO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def modo_autonomo(self, acao: str = "status", objetivo: str = "produtividade",
                            duracao_minutos: int = 30, descricao_tarefa: str = ""):
        """Modo autônomo. acao: ativar, desativar, status, tarefa_complexa, status_tarefa, listar_tarefas."""
        registrar_evento("autonomo", f"{acao}", objetivo)
        if acao == "ativar":
            return await asyncio.to_thread(_ativar_autonomo, objetivo, duracao_minutos)
        elif acao == "desativar":
            return await asyncio.to_thread(_desativar_autonomo)
        elif acao == "tarefa_complexa":
            return await asyncio.to_thread(_executar_multi, descricao_tarefa)
        elif acao == "status_tarefa":
            return await asyncio.to_thread(_status_tarefa, 0)
        elif acao == "listar_tarefas":
            return await asyncio.to_thread(_listar_tarefas)
        return await asyncio.to_thread(_status_autonomo)

    # ═══════════════════════════════════════════
    # TOOL 9 — INTELIGÊNCIA
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def inteligencia(self, acao: str, descricao: str = "", atividade: str = ""):
        """Hub de inteligência. acao: analisar_comportamento, prever_acao, sugestao, linha_do_tempo, estatisticas, aprender_erro, consultar_erro, consultar_erros."""
        if acao == "analisar_comportamento":
            return await asyncio.to_thread(analisar_comportamento)
        elif acao == "prever_acao":
            return await asyncio.to_thread(prever_acao)
        elif acao == "sugestao":
            return await asyncio.to_thread(sugestao_contextual, atividade)
        elif acao == "linha_do_tempo":
            return await asyncio.to_thread(consultar_timeline, descricao or "hoje")
        elif acao == "estatisticas":
            return await asyncio.to_thread(estatisticas_timeline)
        elif acao == "aprender_erro":
            partes = descricao.split("|") if "|" in descricao else [descricao, descricao, ""]
            return await asyncio.to_thread(registrar_erro, partes[0], partes[1] if len(partes)>1 else "", partes[2] if len(partes)>2 else "")
        elif acao == "consultar_erro":
            return await asyncio.to_thread(sugerir_correcao, descricao)
        elif acao == "consultar_erros":
            return await asyncio.to_thread(consultar_erros, descricao)
        return f"Ação '{acao}' não reconhecida."

    # ═══════════════════════════════════════════
    # TOOL 10 — DESENVOLVIMENTO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def desenvolvimento(self, acao: str, nome: str = "", tipo: str = "web", descricao: str = ""):
        """Dev tools. acao: gerar_projeto, debug, refatorar, explicar, gerar_ui."""
        registrar_evento("dev", f"{acao}: {nome or descricao[:30]}")
        if acao == "gerar_projeto":
            return await asyncio.to_thread(_gerar_projeto, nome, tipo, descricao or "Projeto gerado pelo Jarvis")
        elif acao == "debug":
            return await asyncio.to_thread(_debug_auto, nome, descricao)
        elif acao == "refatorar":
            return await asyncio.to_thread(_refatorar, nome)
        elif acao == "explicar":
            return await asyncio.to_thread(_explicar, nome or descricao)
        elif acao == "gerar_ui":
            return await asyncio.to_thread(_gerar_ui, nome, descricao, "#6C63FF", tipo or "moderno_dark")
        return f"Ação '{acao}' não reconhecida."

    # ═══════════════════════════════════════════
    # TOOL 11 — INTERNET INTELIGENTE
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def internet_inteligente(self, acao: str, url: str, seletor: str = "",
                                    tipo: str = "texto", intervalo: int = 30, descricao: str = ""):
        """Scraping e monitoramento. acao: extrair, monitorar, parar_monitor, listar_monitores."""
        if acao == "extrair":
            return await _extrair_dados(url, seletor, tipo)
        elif acao == "monitorar":
            return await _monitorar(url, seletor, intervalo, descricao)
        elif acao == "parar_monitor":
            return await asyncio.to_thread(_parar_monitor, url)
        elif acao == "listar_monitores":
            return await asyncio.to_thread(_listar_monitores)
        return f"Ação '{acao}' não reconhecida."

    # ═══════════════════════════════════════════
    # TOOL 12 — VIDA REAL
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def vida_real(self, acao: str, detalhe: str = "", duracao: int = 25, area: str = ""):
        """Vida real. acao: organizar_dia, adicionar_tarefa, concluir_tarefa, ver_tarefas, foco_ativar, foco_desativar, foco_status, definir_meta, cobrar_meta, status_coach, relatorio_coach."""
        if acao in ("organizar_dia", "ver_tarefas"):
            return await asyncio.to_thread(_rotina, "ver", detalhe)
        elif acao == "adicionar_tarefa":
            return await asyncio.to_thread(_rotina, "adicionar", detalhe)
        elif acao == "concluir_tarefa":
            return await asyncio.to_thread(_rotina, "concluir", detalhe)
        elif acao == "foco_ativar":
            return await asyncio.to_thread(_foco, "ativar", duracao)
        elif acao == "foco_desativar":
            return await asyncio.to_thread(_foco, "desativar")
        elif acao == "foco_status":
            return await asyncio.to_thread(_foco, "status")
        elif acao == "definir_meta":
            return await asyncio.to_thread(_coach, "definir_meta", area, detalhe)
        elif acao == "cobrar_meta":
            return await asyncio.to_thread(_coach, "cobrar")
        elif acao == "status_coach":
            return await asyncio.to_thread(_coach, "status")
        elif acao == "relatorio_coach":
            return await asyncio.to_thread(_coach, "relatorio")
        return await asyncio.to_thread(_rotina, "ver")

    # ═══════════════════════════════════════════
    # TOOL 13 — PLUGINS
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def plugins(self, acao: str = "listar", nome: str = "", descricao: str = "", codigo: str = ""):
        """Plugins dinâmicos. acao: listar, instalar, carregar, remover."""
        if acao == "instalar":
            return await asyncio.to_thread(_instalar_plugin, nome, descricao, codigo)
        elif acao == "carregar":
            return await asyncio.to_thread(_carregar_plugin, nome)
        elif acao == "remover":
            return await asyncio.to_thread(_remover_plugin, nome)
        return await asyncio.to_thread(_listar_plugins)

    # ═══════════════════════════════════════════
    # TOOL 14 — TAREFAS E OBJETIVOS
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def tarefas_e_objetivos(self, acao: str, nome: str = "", objetivo: str = "",
                                   prazo_dias: int = 90, objetivo_id: int = 0,
                                   etapa_idx: int = 0, texto: str = ""):
        """Tarefas clonadas e objetivos."""
        if acao == "gravar":
            return await asyncio.to_thread(_gravar_tarefa, nome)
        elif acao == "parar_gravacao":
            return await asyncio.to_thread(_parar_gravacao)
        elif acao == "executar_clone":
            return await asyncio.to_thread(_exec_clone, nome)
        elif acao == "listar_clones":
            return await asyncio.to_thread(_listar_clones)
        elif acao == "definir_objetivo":
            return await asyncio.to_thread(_definir_obj, objetivo, prazo_dias)
        elif acao == "listar_objetivos":
            return await asyncio.to_thread(_listar_objs)
        elif acao == "progresso":
            return await asyncio.to_thread(_prog_obj, objetivo_id, etapa_idx, texto)
        elif acao == "aprendizado":
            return await asyncio.to_thread(_aprender_obj, objetivo_id, texto)
        elif acao == "evoluir":
            return await asyncio.to_thread(_evoluir_obj, objetivo_id, texto)
        elif acao == "relatorio":
            return await asyncio.to_thread(_relatorio_obj, objetivo_id)
        return f"Ação '{acao}' não reconhecida."

    # ═══════════════════════════════════════════
    # TOOL 15 — CONTROLE POR GESTOS HÍBRIDO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def controle_gestos(self, acao: str = "status"):
        """Controle por gestos + pinça + voz v4. acao: iniciar, parar, status, iniciar_voz, parar_voz, iniciar_tudo, parar_tudo."""
        self._sfx_comando("comando_iniciado")
        if acao == "iniciar":
            return await asyncio.to_thread(_iniciar_gestos)
        elif acao == "parar":
            return await asyncio.to_thread(_parar_gestos)
        elif acao == "iniciar_voz":
            return await asyncio.to_thread(_iniciar_voice_gestos)
        elif acao == "parar_voz":
            return await asyncio.to_thread(_parar_voice_gestos)
        elif acao == "iniciar_tudo":
            return await asyncio.to_thread(_iniciar_sistema_gestos)
        elif acao == "parar_tudo":
            return await asyncio.to_thread(_parar_sistema_gestos)
        return await asyncio.to_thread(_status_gestos)


    # ═══════════════════════════════════════════
    # TOOL 15B — SEGURANÇA COM CÂMERA
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def seguranca_camera(self, acao: str = "status", nome: str = "", num_amostras: int = 10):
        """Sistema de segurança inteligente com câmera e reconhecimento facial. acao: iniciar, parar, status, cadastrar_rosto, listar_rostos, remover_rosto, parar_alarme, historico."""
        self._sfx_comando("comando_iniciado")
        if acao == "iniciar":
            return await asyncio.to_thread(_iniciar_seguranca)
        elif acao == "parar":
            return await asyncio.to_thread(_parar_seguranca)
        elif acao == "cadastrar_rosto":
            return await asyncio.to_thread(_cadastrar_rosto, nome, num_amostras)
        elif acao == "listar_rostos":
            return await asyncio.to_thread(_listar_rostos)
        elif acao == "remover_rosto":
            return await asyncio.to_thread(_remover_rosto, nome)
        elif acao == "parar_alarme":
            return await asyncio.to_thread(_parar_alarme_seg)
        elif acao == "historico":
            return await asyncio.to_thread(_historico_intrusoes)
        return await asyncio.to_thread(_status_seguranca)

    # ═══════════════════════════════════════════
    # TOOL 16 — ÁUDIO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def audio_sistema(self, acao: str = "diagnostico", tipo: str = "geral",
                            habilitado: bool = True, volume: float = 0.7,
                            evento_sfx: str = "", arquivo_sfx: str = ""):
        """Sistema de áudio completo. acao: diagnostico, corrigir, alternativas, historico, sfx_tocar, sfx_config, sfx_listar, sfx_recarregar, iniciar_monitor, parar_monitor, status_monitor."""
        self._sfx_comando("comando_iniciado")
        try:
            if acao == "diagnostico":
                return await asyncio.to_thread(_diagnostico_audio)
            elif acao == "corrigir":
                return await asyncio.to_thread(_corrigir_audio, tipo)
            elif acao == "alternativas":
                return await asyncio.to_thread(_sugerir_alternativa)
            elif acao == "historico":
                return await asyncio.to_thread(_historico_problemas)
            elif acao == "sfx_tocar":
                return await asyncio.to_thread(tocar_sfx, evento_sfx or "comando_iniciado")
            elif acao == "sfx_config":
                return await asyncio.to_thread(configurar_sfx, habilitado, volume, evento_sfx, arquivo_sfx)
            elif acao == "sfx_listar":
                return await asyncio.to_thread(listar_sfx)
            elif acao == "sfx_recarregar":
                return await asyncio.to_thread(recarregar_sfx)
            elif acao == "iniciar_monitor":
                return await asyncio.to_thread(_iniciar_monitor)
            elif acao == "parar_monitor":
                return await asyncio.to_thread(_parar_monitor_audio)
            elif acao == "status_monitor":
                return await asyncio.to_thread(_status_monitor_audio)
            return f"Ação '{acao}' não reconhecida."
        except Exception as e:
            return f"Erro: {e}"

    # ═══════════════════════════════════════════
    # TOOL 18 — CASA INTELIGENTE
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def casa_inteligente(self, *args, **kwargs):
        return "Automação residencial (Home Assistant/SmartThings) foi removida deste projeto."


    # ═══════════════════════════════════════════
    # TOOL 27 — DISPOSITIVOS TUYA (IoT Cloud)
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def dispositivo_tuya(self, acao: str, device_id: str = "",
                                r: int = 0, g: int = 0, b: int = 0,
                                brilho: int = 50):
        """Controla dispositivos inteligentes via Tuya Cloud API.
        acao: ligar, desligar, status, cor, brilho, listar, funcionalidades.
        device_id: ID do dispositivo Tuya (obrigatório para ações individuais).
        r, g, b: valores RGB 0-255 (para acao=cor).
        brilho: 0-100 (para acao=brilho)."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("tuya", f"{acao}: {device_id or 'todos'}")
            registrar_acao("dispositivo_tuya", acao)

            if acao == "listar":
                resultado = await asyncio.to_thread(_tuya_listar)
                if resultado.get("sucesso"):
                    self._sfx_comando("comando_concluido")
                    dispositivos = resultado.get("dispositivos", [])
                    if not dispositivos:
                        return "Nenhum dispositivo Tuya encontrado."
                    linhas = [f" {len(dispositivos)} dispositivo(s) Tuya:"]
                    for d in dispositivos:
                        status_icon = "" if d.get("online") else ""
                        linhas.append(f"  {status_icon} {d['nome']} — ID: {d['id']} ({d.get('categoria', '?')})")
                    return "\n".join(linhas)
                return f" {resultado.get('mensagem', 'Erro desconhecido')}"

            if not device_id:
                return "Especifique o device_id. Use acao='listar' para ver dispositivos disponíveis."

            if acao == "ligar":
                resultado = await asyncio.to_thread(_tuya_ligar, device_id)
            elif acao == "desligar":
                resultado = await asyncio.to_thread(_tuya_desligar, device_id)
            elif acao == "status":
                resultado = await asyncio.to_thread(_tuya_status, device_id)
                if resultado.get("sucesso"):
                    self._sfx_comando("comando_concluido")
                    nome = resultado.get("nome", "?")
                    online = " Online" if resultado.get("online") else " Offline"
                    ligado = resultado.get("ligado")
                    estado = "Ligado" if ligado else ("Desligado" if ligado is False else "Desconhecido")
                    brilho_val = resultado.get("brilho")
                    info = f" {nome} ({online})\n  Estado: {estado}"
                    if brilho_val is not None:
                        info += f"\n  Brilho: {brilho_val}"
                    return info
                return f" Erro ao obter status"
            elif acao == "cor":
                resultado = await asyncio.to_thread(_tuya_cor, device_id, r, g, b)
            elif acao == "brilho":
                resultado = await asyncio.to_thread(_tuya_brilho, device_id, brilho)
            elif acao == "funcionalidades":
                resultado = await asyncio.to_thread(_tuya_funcionalidades, device_id)
                if resultado.get("sucesso"):
                    self._sfx_comando("comando_concluido")
                    funcs = resultado.get("funcionalidades", [])
                    if not funcs:
                        return "Nenhuma funcionalidade encontrada."
                    linhas = [f" {len(funcs)} funcionalidade(s):"]
                    for f in funcs:
                        linhas.append(f"  • {f.get('code', '?')} — {f.get('name', '')} (tipo: {f.get('type', '?')})")
                    return "\n".join(linhas)
                return f" {resultado.get('mensagem', 'Erro')}"
            else:
                return f"Ação '{acao}' não reconhecida. Use: ligar, desligar, status, cor, brilho, listar, funcionalidades."

            if resultado.get("sucesso"):
                self._sfx_comando("comando_concluido")
            else:
                self._sfx_comando("erro_detectado")
            return resultado.get("mensagem", str(resultado))

        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro no controle Tuya: {str(e)}"

    # ═══════════════════════════════════════════
    # TOOL 20 — WHATSAPP
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def enviar_whatsapp(self, contato: str, mensagem: str):
        """Envia mensagem pelo WhatsApp Desktop. contato: nome do contato. mensagem: texto a enviar."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("whatsapp", f"Mensagem para {contato}: {mensagem[:50]}")
            registrar_acao("enviar_whatsapp", contato)
            resultado = await asyncio.to_thread(_enviar_whatsapp, contato, mensagem)
            if "sucesso" in resultado.lower() or "" in resultado:
                self._sfx_comando("comando_concluido")
            else:
                self._sfx_comando("erro_detectado")
            return resultado
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro ao enviar mensagem no WhatsApp: {e}"

    # TOOL 21 - SEGURANÇA ÉTICA
    @agents.function_tool
    async def scan_seguranca(self, target_url: str, tipo_scan: str = "completo"):
        """Executa scan de segurança ética. tipo_scan: completo, rapido. target_url: URL ou IP do alvo."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("seguranca", f"Scan {tipo_scan} em: {target_url}")
            
            if tipo_scan == "completo":
                resultado = await _scan_seguranca_completo(target_url)
            elif tipo_scan == "rapido":
                resultado = await _scan_seguranca_rapido(target_url)
            else:
                return "Tipo de scan não reconhecido. Use: completo ou rapido"
            
            # Resumo inteligente
            if "scans" in resultado:
                total_vulns = 0
                risco_maximo = "Baixo"
                
                for scan_data in resultado["scans"].values():
                    if "vulnerabilidades" in scan_data:
                        total_vulns += len(scan_data["vulnerabilidades"])
                        for vuln in scan_data["vulnerabilidades"]:
                            risco = vuln.get("risco", "Baixo")
                            if risco == "Alto":
                                risco_maximo = "Alto"
                            elif risco == "Médio" and risco_maximo != "Alto":
                                risco_maximo = "Médio"
                
                resumo = f"""
 Scan {tipo_scan} concluído!
 
 Target: {target_url}
 Total de vulnerabilidades: {total_vulns}
 Risco máximo: {risco_maximo}
 
 Relatórios salvos em: Downloads/Relatorios_Seguranca/
 
 Análise detalhada disponível no relatório completo.
                """.strip()
                
                if risco_maximo == "Alto":
                    self._sfx_comando("alerta_critico")
                elif risco_maximo == "Médio":
                    self._sfx_comando("alerta_medio")
                else:
                    self._sfx_comando("comando_concluido")
                
                return resumo
            else:
                self._sfx_comando("comando_concluido")
                return "Scan concluído. Verifique relatórios em Downloads/Relatorios_Seguranca/"
                
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro no scan de segurança: {str(e)}"

    @agents.function_tool
    async def analisar_relatorio_seguranca_tool(self, caminho_relatorio: str):
        """Analisa relatório de segurança existente e gera insights inteligentes."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("seguranca", f"Analisando relatório: {caminho_relatorio}")
            
            resultado = await asyncio.to_thread(_analisar_relatorio_seguranca, caminho_relatorio)
            
            if "erro" in resultado:
                self._sfx_comando("erro_detectado")
                return f"Erro ao analisar relatório: {resultado['erro']}"
            
            # Gerar resumo inteligente
            analise = resultado.get("analise_inteligente", {})
            insights = resultado.get("insights", [])
            
            resumo = f"""
 Análise Inteligente de Relatório
 
 Resumo Geral:
 - Total de vulnerabilidades: {analise.get('resumo_geral', {}).get('total_vulnerabilidades', 0)}
 - Risco máximo: {analise.get('resumo_geral', {}).get('risco_maximo', 'Desconhecido')}
 
 Insights Adicionais:
            """.strip()
            
            for insight in insights[:3]:  # Limitar a 3 insights
                severidade = insight.get("severidade", "Baixa")
                mensagem = insight.get("mensagem", "")
                resumo += f"\n - [{severidade}] {mensagem}"
            
            if analise.get("prioridade_acoes"):
                resumo += "\n\n Ações Prioritárias:"
                for acao in analise["prioridade_acoes"][:2]:  # Limitar a 2 ações
                    prioridade = acao.get("prioridade", "Média")
                    descricao = acao.get("descricao", "")
                    resumo += f"\n - [{prioridade}] {descricao}"
            
            self._sfx_comando("comando_concluido")
            return resumo
            
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro na análise do relatório: {str(e)}"

    # ═══════════════════════════════════════════
    # TOOL 22 — CONTROLE DESKTOP AVANÇADO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def controle_desktop(self, acao: str, alvo: str = "", texto: str = "",
                                x: int = 0, y: int = 0, x2: int = 0, y2: int = 0,
                                botao: str = "left", duplo: bool = False,
                                direcao: str = "proxima", numero: int = 0,
                                quantidade: int = 3, parametro: str = ""):
        """Controle total do desktop Windows. 
        acao: abrir_app, fechar_app, listar_janelas, focar_janela, minimizar, maximizar,
              nova_aba, fechar_aba, trocar_aba, ir_aba, reabrir_aba,
              digitar, tecla, atalho, clicar, clicar_imagem, mover_mouse, scroll,
              posicao_mouse, captura_tela, photoshop, navegar_url,
              busca_automatica, interagir_pagina, arrastar."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("desktop", f"{acao}: {alvo or texto or ''}")
            registrar_acao("controle_desktop", acao)

            if acao == "abrir_app":
                return await asyncio.to_thread(_abrir_app_avancado, alvo, parametro)
            elif acao == "fechar_app":
                return await asyncio.to_thread(_fechar_app, alvo)
            elif acao == "listar_janelas":
                return await asyncio.to_thread(_listar_janelas)
            elif acao == "focar_janela":
                return await asyncio.to_thread(_focar_janela, alvo)
            elif acao == "minimizar":
                return await asyncio.to_thread(_minimizar_janela, alvo)
            elif acao == "maximizar":
                return await asyncio.to_thread(_maximizar_janela, alvo)
            elif acao == "nova_aba":
                return await asyncio.to_thread(_nova_aba, alvo)
            elif acao == "fechar_aba":
                return await asyncio.to_thread(_fechar_aba)
            elif acao == "trocar_aba":
                return await asyncio.to_thread(_trocar_aba, direcao)
            elif acao == "ir_aba":
                return await asyncio.to_thread(_ir_aba, numero)
            elif acao == "reabrir_aba":
                return await asyncio.to_thread(_reabrir_aba)
            elif acao == "digitar":
                return await asyncio.to_thread(_digitar_texto, texto, parametro, alvo)
            elif acao == "tecla":
                return await asyncio.to_thread(_pressionar_tecla, texto or alvo)
            elif acao == "atalho":
                return await asyncio.to_thread(_atalho_teclado, texto or alvo)
            elif acao == "clicar":
                return await asyncio.to_thread(_clicar_posicao, x, y, botao, duplo)
            elif acao == "clicar_imagem":
                return await asyncio.to_thread(_clicar_imagem, alvo)
            elif acao == "mover_mouse":
                return await asyncio.to_thread(_mover_mouse, x, y)
            elif acao == "scroll":
                return await asyncio.to_thread(_scroll_mouse, quantidade, direcao)
            elif acao == "posicao_mouse":
                return await asyncio.to_thread(_posicao_mouse)
            elif acao == "captura_tela":
                return await asyncio.to_thread(_captura_tela, alvo)
            elif acao == "photoshop":
                return await asyncio.to_thread(_interagir_photoshop, alvo, parametro)
            elif acao == "navegar_url":
                return await asyncio.to_thread(_navegar_url, alvo)
            elif acao == "busca_automatica":
                return await asyncio.to_thread(_busca_automatica, texto or alvo, parametro or "google")
            elif acao == "interagir_pagina":
                return await asyncio.to_thread(_interagir_pagina, alvo, parametro, texto)
            elif acao == "arrastar":
                return await asyncio.to_thread(_arrastar, x, y, x2, y2)
            
            self._sfx_comando("comando_concluido")
            return f"Ação '{acao}' não reconhecida."
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro no controle desktop: {e}"

    # ═══════════════════════════════════════════
    # TOOL 23 — ANÁLISE DE SITES
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def analisar_site(self, url: str, tipo: str = "completa"):
        """Analisa site: conteúdo, título, resumo, segurança, phishing, SSL.
        tipo: completa, rapida, ler_resumir, historico."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("site_analysis", f"Analisando: {url}")

            if tipo == "completa":
                resultado = await _analisar_site(url)
            elif tipo == "rapida":
                resultado = await _analise_rapida_seg(url)
            elif tipo == "ler_resumir":
                resultado = await _ler_resumir_site(url)
            elif tipo == "historico":
                resultado = await asyncio.to_thread(_historico_analises)
            else:
                resultado = await _analisar_site(url)

            self._sfx_comando("comando_concluido")
            return resultado
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro na análise de site: {e}"

    # ═══════════════════════════════════════════
    # TOOL 24 — NOTIFICAÇÕES DO WINDOWS (v2.0)
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def notificacoes(self, acao: str = "ver", quantidade: int = 10,
                           categoria: str = "", intervalo: int = 5,
                           app_ignorar: str = ""):
        """Monitor avançado de notificações do Windows. Lê notificações em voz alta.
        acao: iniciar_monitor, parar_monitor, status, ver (histórico),
              capturar_agora, ler_tudo (lê TODAS formatadas para fala natural),
              ler_pendentes (lê só as novas em voz alta),
              verificar_novas (check rápido), configurar, limpar_historico.
        USE ler_tudo quando o usuário pedir para ler ou falar as notificações.
        USE ler_pendentes quando perguntar se chegou algo novo."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("notificacao", f"{acao}")

            if acao == "iniciar_monitor":
                return await asyncio.to_thread(_iniciar_notif, intervalo)
            elif acao == "parar_monitor":
                return await asyncio.to_thread(_parar_notif)
            elif acao == "status":
                return await asyncio.to_thread(_status_notif)
            elif acao == "ver":
                return await asyncio.to_thread(_ver_notif, quantidade, categoria)
            elif acao == "capturar_agora":
                return await asyncio.to_thread(_capturar_notif)
            elif acao == "ler_tudo":
                return await asyncio.to_thread(_ler_todas_notif, quantidade)
            elif acao == "ler_pendentes":
                return await asyncio.to_thread(_ler_pendentes_notif)
            elif acao == "verificar_novas":
                return await asyncio.to_thread(_verificar_novas_notif)
            elif acao == "configurar":
                return await asyncio.to_thread(_config_notif, intervalo, app_ignorar, "")
            elif acao == "limpar_historico":
                return await asyncio.to_thread(_limpar_notif)

            return f"Ação '{acao}' não reconhecida."
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro nas notificações: {e}"

    # ═══════════════════════════════════════════
    # TOOL 25 — MEMÓRIA LOCAL PERSISTENTE (v2.0)
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def memoria_local(self, acao: str = "ver", termo: str = "",
                             categoria: str = "", chave: str = "", valor: str = "",
                             quantidade: int = 10):
        """Memória avançada persistente. Guarda informações e lembra entre sessões.
        acao: ultima_conversa, buscar, listar_sessoes, salvar_fato,
              listar_fatos, salvar_preferencia, listar_preferencias,
              guardar_memoria (GUARDA informação que o usuário pediu para lembrar),
              listar_memorias (lista memórias guardadas),
              buscar_memoria (busca em memórias guardadas),
              remover_memoria (remove memória),
              saudacao_contextual (gera saudação baseada na memória).
        QUANDO o usuário disser 'guarde isso', 'lembre-se', 'memorize', 'anote':
        → Use acao='guardar_memoria' com termo=informação a guardar."""
        try:
            registrar_evento("memoria", f"{acao}: {termo or chave or ''}")

            if acao == "ultima_conversa":
                return await asyncio.to_thread(_carregar_ultima_conversa)
            elif acao == "buscar":
                return await asyncio.to_thread(_buscar_conversas, termo, quantidade)
            elif acao == "listar_sessoes":
                return await asyncio.to_thread(_listar_sessoes, quantidade)
            elif acao == "salvar_fato":
                return await asyncio.to_thread(_salvar_fato, categoria or "geral", termo or valor)
            elif acao == "listar_fatos":
                return await asyncio.to_thread(_listar_fatos, categoria)
            elif acao == "salvar_preferencia":
                return await asyncio.to_thread(_salvar_preferencia, chave, valor)
            elif acao == "listar_preferencias":
                return await asyncio.to_thread(_listar_preferencias)
            elif acao == "guardar_memoria":
                return await asyncio.to_thread(_guardar_memoria, termo or valor, categoria or "geral")
            elif acao == "listar_memorias":
                return await asyncio.to_thread(_listar_memorias, categoria, quantidade)
            elif acao == "buscar_memoria":
                resultados = await asyncio.to_thread(_buscar_memoria, termo)
                if not resultados:
                    return f"Nenhuma memória encontrada para '{termo}'."
                linhas = [f" Memórias encontradas para '{termo}':"]
                for r in resultados:
                    linhas.append(f"  {r.get('informacao', '')}")
                return "\n".join(linhas)
            elif acao == "remover_memoria":
                return await asyncio.to_thread(_remover_memoria, termo)
            elif acao == "saudacao_contextual":
                return await asyncio.to_thread(_saudacao_contextual)

            return f"Ação '{acao}' não reconhecida."
        except Exception as e:
            return f"Erro na memória local: {e}"

    # ═══════════════════════════════════════════
    # TOOL 26 — EDITOR VS CODE
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def editor_vscode(self, acao: str, caminho: str = "", texto: str = "",
                             busca: str = "", comando: str = "", extensao: str = "",
                             linha: int = 0, tipo: str = "python",
                             nome: str = "", prefixo: str = "", descricao: str = ""):
        """Editor VS Code completo.
        acao: abrir, abrir_arquivo, criar_arquivo, abrir_pasta,
              editar (operação em 'texto': inserir/deletar_linha/comentar/formatar/etc),
              comando_palette, terminal, novo_terminal, atalho,
              inserir_codigo, instalar_extensao, listar_extensoes,
              diff, criar_snippet."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("vscode", f"{acao}: {caminho or comando or ''}")
            registrar_acao("editor_vscode", acao)

            if acao == "abrir":
                return await asyncio.to_thread(_abrir_vscode, caminho)
            elif acao == "abrir_arquivo":
                return await asyncio.to_thread(_abrir_arquivo_vscode, caminho, linha)
            elif acao == "criar_arquivo":
                return await asyncio.to_thread(_criar_arquivo_vscode, caminho, texto)
            elif acao == "abrir_pasta":
                return await asyncio.to_thread(_abrir_pasta_vscode, caminho)
            elif acao == "editar":
                return await asyncio.to_thread(_editar_codigo_vscode, texto, busca, caminho)
            elif acao == "comando_palette":
                return await asyncio.to_thread(_comando_vscode, comando or texto)
            elif acao == "terminal":
                return await asyncio.to_thread(_terminal_vscode, comando or texto)
            elif acao == "novo_terminal":
                return await asyncio.to_thread(_novo_terminal_vscode)
            elif acao == "atalho":
                return await asyncio.to_thread(_atalho_vscode, texto or comando)
            elif acao == "inserir_codigo":
                return await asyncio.to_thread(_inserir_codigo_vscode, texto, tipo)
            elif acao == "instalar_extensao":
                return await asyncio.to_thread(_instalar_ext_vscode, extensao or texto)
            elif acao == "listar_extensoes":
                return await asyncio.to_thread(_listar_ext_vscode)
            elif acao == "diff":
                return await asyncio.to_thread(_diff_vscode, caminho, busca)
            elif acao == "criar_snippet":
                return await asyncio.to_thread(_criar_snippet_vscode, nome, prefixo, texto, descricao)

            self._sfx_comando("comando_concluido")
            return f"Ação '{acao}' não reconhecida."
        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro no VS Code: {e}"

    # ═══════════════════════════════════════════
    # TOOL 28 — CLIMA E DESLOCAMENTO
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def clima_e_deslocamento(self, acao: str, cidade: str = "",
                                    cidade_origem: str = "", cidade_destino: str = "",
                                    origem_lat: float = 0.0, origem_lon: float = 0.0,
                                    destino_lat: float = 0.0, destino_lon: float = 0.0,
                                    perfil: str = "driving-car"):
        """Consulta clima e calcula rotas de deslocamento.
        acao: clima (consulta clima de uma cidade),
              clima_coordenadas (clima por lat/lon),
              deslocamento (calcula rota entre coordenadas),
              deslocamento_cidades (calcula rota entre cidades por nome),
              historico (histórico de consultas).
        cidade: nome da cidade para clima (ex: Itambé, Pedras de Fogo, Recife).
        cidade_origem, cidade_destino: nomes para rota (ex: Itambé, Pedras de Fogo).
        origem_lat, origem_lon, destino_lat, destino_lon: coordenadas para rota.
        perfil: carro, bicicleta, a pé (padrão: carro)."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("clima_deslocamento", f"{acao}: {cidade or cidade_origem or ''}")
            registrar_acao("clima_e_deslocamento", acao)

            if acao == "clima":
                if not cidade:
                    return "Senhor, preciso do nome da cidade para consultar o clima."
                resultado = await asyncio.to_thread(_consultar_clima, cidade)
                self._sfx_comando("comando_concluido")
                return resultado

            elif acao == "clima_coordenadas":
                resultado = await asyncio.to_thread(_consultar_clima_coords, origem_lat, origem_lon)
                self._sfx_comando("comando_concluido")
                return resultado

            elif acao == "deslocamento":
                if origem_lat == 0.0 and origem_lon == 0.0:
                    return "Senhor, preciso das coordenadas de origem."
                resultado = await asyncio.to_thread(
                    _calcular_deslocamento,
                    origem_lat, origem_lon,
                    destino_lat, destino_lon,
                    perfil
                )
                self._sfx_comando("comando_concluido")
                return resultado

            elif acao == "deslocamento_cidades":
                if not cidade_origem or not cidade_destino:
                    return "Senhor, preciso dos nomes da cidade de origem e destino."
                resultado = await asyncio.to_thread(
                    _calcular_deslocamento_cidades,
                    cidade_origem, cidade_destino, perfil
                )
                self._sfx_comando("comando_concluido")
                return resultado

            elif acao == "historico":
                resultado = await asyncio.to_thread(_historico_clima)
                return resultado

            return f"Ação '{acao}' não reconhecida. Use: clima, deslocamento, deslocamento_cidades, historico."

        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro na consulta de clima/deslocamento: {e}"

    # ═══════════════════════════════════════════
    # TOOL 29 — SISTEMA DE ALARMES
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def sistema_alarme(self, acao: str, horario: str = "",
                              descricao: str = "Alarme", indice: int = -1):
        """Sistema de alarmes avançado com ativação por palavra-chave.
        acao: definir (cria alarme — horario pode ser '07:30', 'amanhã 8h', 'daqui 30 min', '6 da manhã'),
              remover (remove alarme pelo índice),
              listar (lista alarmes ativos),
              parar (interrompe alarme tocando),
              status (informações do sistema),
              iniciar_keyword (ativa detecção da palavra 'Jarvis'),
              parar_keyword (desativa detecção),
              status_keyword (status da detecção por voz).
        horario: para acao=definir — aceita linguagem natural.
        descricao: descrição do alarme.
        indice: para acao=remover (0-based, -1 = último)."""
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("alarme", f"{acao}: {horario or descricao}")
            registrar_acao("sistema_alarme", acao)

            if acao == "definir":
                if not horario:
                    return "Senhor, preciso do horário para definir o alarme."
                resultado = await asyncio.to_thread(_definir_alarme, horario, descricao)
                self._sfx_comando("comando_concluido")
                return resultado

            elif acao == "remover":
                resultado = await asyncio.to_thread(_remover_alarme, indice)
                self._sfx_comando("comando_concluido")
                return resultado

            elif acao == "listar":
                return await asyncio.to_thread(_listar_alarmes)

            elif acao == "parar":
                resultado = await asyncio.to_thread(_parar_alarme)
                return resultado

            elif acao == "status":
                return await asyncio.to_thread(_status_alarmes)

            elif acao == "iniciar_keyword":
                return await asyncio.to_thread(_iniciar_keyword, "jarvis")

            elif acao == "parar_keyword":
                return await asyncio.to_thread(_parar_keyword)

            elif acao == "status_keyword":
                return await asyncio.to_thread(_status_keyword)

            return f"Ação '{acao}' não reconhecida. Use: definir, remover, listar, parar, status, iniciar_keyword."

        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro no sistema de alarmes: {e}"

    # ═══════════════════════════════════════════
    # TOOL 30 — NLU ENGINE (Compreensão de Linguagem Natural)
    # ═══════════════════════════════════════════

    @agents.function_tool
    async def nlu_comando(self, texto: str, acao_nlu: str = "interpretar"):
        """Motor de compreensão de linguagem natural ultra-avançado.
        Interpreta comandos com sinônimos, slots, compostos e contexto conversacional.
        acao_nlu: interpretar (analisa comando), contexto (mostra contexto atual),
                  limpar_contexto (reseta contexto), historico (últimos comandos).
        texto: o comando em linguagem natural para interpretar.
        
        QUANDO USAR: Use esta ferramenta ANTES de executar qualquer comando ambíguo.
        Ela decompõe comandos compostos como "apaga a luz do quarto e coloca música baixa"
        em sub-ações ordenadas. Também resolve contexto: se o usuário disse "no quarto"
        antes, o próximo "deixa mais fraca" entende automaticamente "luz do quarto".
        
        Exemplos de comandos que esta ferramenta entende:
        - "acende a luz da cozinha" → intenção=controlar_luz, acao=ligar, comodo=cozinha
        - "põe o volume em 70%" → intenção=controlar_volume, acao=ajustar, intensidade=70
        - "mais forte" → usa contexto anterior para resolver dispositivo/cômodo
        - "apaga tudo e coloca música baixa" → comando composto com 2 sub-ações
        """
        self._sfx_comando("comando_iniciado")
        try:
            registrar_evento("nlu", f"{acao_nlu}: {texto[:80]}")

            if acao_nlu == "interpretar":
                resultado = await asyncio.to_thread(_nlu_executar, texto)
                self._sfx_comando("comando_concluido")
                return resultado

            elif acao_nlu == "contexto":
                return await asyncio.to_thread(_nlu_contexto)

            elif acao_nlu == "limpar_contexto":
                return await asyncio.to_thread(_nlu_limpar)

            elif acao_nlu == "historico":
                return await asyncio.to_thread(_nlu_historico, 15)

            return f"Ação NLU '{acao_nlu}' não reconhecida. Use: interpretar, contexto, limpar_contexto, historico."

        except Exception as e:
            self._sfx_comando("erro_detectado")
            return f"Erro no NLU Engine: {e}"

# ENTRYPOINT
# ─────────────────────────────────────────

async def entrypoint(ctx: agents.JobContext):

    user_id = "Senhor"
    mem0_client = None

    await ctx.connect()

    # Inicializar SFX
    try:
        await asyncio.to_thread(inicializar_sfx)
        logger.info("[SFX] Sistema de efeitos sonoros inicializado.")
    except Exception as e:
        logger.warning(f"[SFX] Falha ao inicializar: {e}")

    # Inicializar Sistema de Alarmes
    try:
        await asyncio.to_thread(_inicializar_alarmes)
        logger.info("[Alarme] Sistema de alarmes inicializado.")
    except Exception as e:
        logger.warning(f"[Alarme] Falha ao inicializar: {e}")

    # CORRIGIDO: CARREGA MEMÓRIAS E INJETA PERSONALIDADE DINÂMICA (NÍVEL STARK)
    instructions_finais = AGENT_INSTRUCTION + f"""

# ═══════════════════════════════════════════
# CONTEXTO DINÂMICO DO USUÁRIO (TEMPO REAL)
# ═══════════════════════════════════════════

Usuário atual: {user_id}

Você foi criado por este usuário.

Regras:
- Você conhece profundamente esse usuário
- Você deve agir como sistema pessoal dele
- Priorize decisões que beneficiem a vida dele
- Use contexto pessoal SEMPRE que relevante
"""
    
    # CORRIGIDO: MEM0 COM FALLBACK ROBUSTO
    mem0_disponivel = False
    mem0_erro_msg = None
    try:
        logger.info(f"[Mem0] Carregando memórias inteligentes para '{user_id}'...")
        
        # Verificação de conectividade inicial
        import socket
        try:
            socket.gethostbyname('api.mem0.ai')
            logger.info("[Mem0] Conectividade com api.mem0.ai verificada")
        except socket.gaierror as e:
            raise ConnectionError(f"DNS resolution failed for api.mem0.ai: {e}")
        
        mem0_client = AsyncMemoryClient()
        
        # Testa conexão primeiro
        query_mem0 = (
            f"Informações importantes, personalidade, rotina, gostos, relações pessoais e objetivos de {user_id}"
        )
        response = await mem0_client.search(
            query=query_mem0,
            filters={"user_id": user_id},
            limit=30,
        )
        results = response.get("results", []) if isinstance(response, dict) else response if isinstance(response, list) else []
        logger.info(f"[Mem0] {len(results)} memórias encontradas.")
        mem0_disponivel = True

        # ORGANIZAÇÃO INTELIGENTE DAS MEMÓRIAS (GAME CHANGER)
        memorias_pessoais = []
        memorias_rotina = []
        memorias_gostos = []
        memorias_objetivos = []

        for r in results:
            if isinstance(r, dict):
                texto = (r.get("memory") or r.get("text") or r.get("content") or "").lower()

                if not texto:
                    continue

                if any(p in texto for p in ["mãe", "pai", "irmão", "namorada", "esposa", "filho", "família"]):
                    memorias_pessoais.append(texto)

                elif any(p in texto for p in ["escola", "rotina", "horário", "trabalho", "aula", "estuda"]):
                    memorias_rotina.append(texto)

                elif any(p in texto for p in ["gosta", "música", "prefere", "estilo", "cor", "comida"]):
                    memorias_gostos.append(texto)

                elif any(p in texto for p in ["sonho", "objetivo", "empresa", "elytron", "meta", "futuro"]):
                    memorias_objetivos.append(texto)

        # INJEÇÃO ORGANIZADA (MUITO MAIS INTELIGENTE)
        bloco_memoria = ""

        if memorias_pessoais:
            bloco_memoria += "\n[Relações pessoais]\n" + "\n".join(f"- {m}" for m in memorias_pessoais)

        if memorias_rotina:
            bloco_memoria += "\n[Rotina]\n" + "\n".join(f"- {m}" for m in memorias_rotina)

        if memorias_gostos:
            bloco_memoria += "\n[Preferências]\n" + "\n".join(f"- {m}" for m in memorias_gostos)

        if memorias_objetivos:
            bloco_memoria += "\n[Objetivos]\n" + "\n".join(f"- {m}" for m in memorias_objetivos)

        if bloco_memoria:
            instructions_finais += f"\n\nMemória estruturada do usuário:\n{bloco_memoria}"
            logger.info(f"[Mem0] {len(results)} memórias organizadas e injetadas nas instructions.")
            
    except Exception as e:
        mem0_erro_msg = str(e)
        logger.error(f"[Mem0] Erro ao carregar memória: {e}")
        logger.warning("[Mem0] Operando sem memória persistente - usando conhecimento estático")
        
        # FALLBACK: CONHECIMENTO ESTÁTICO DO USUÁRIO
        instructions_finais += f"""

[Memória estática do usuário - Fallback]

[Relações pessoais]
- Pai: [PREENCHER]
- Mãe: [PREENCHER]
- Irmãos: [PREENCHER]
- Parceira(o): [PREENCHER]
- Sogra/Sogro: [PREENCHER]

[Rotina]
- Rotina principal: [PREENCHER]
- Compromissos recorrentes: [PREENCHER]

[Preferências]
- Preferências gerais: [PREENCHER]
- Estilo musical: [PREENCHER]

[Objetivos]
- Objetivos: [PREENCHER]
"""
        logger.info("[Fallback] Memória estática injetada com sucesso")

    # Carrega conhecimento permanente também nas instructions
    try:
        conhecimento = await asyncio.to_thread(ler_conhecimento_para_contexto)
        if conhecimento:
            instructions_finais += f"\n\n[Conhecimento permanente do usuário]\n{conhecimento}"
            logger.info("[Conhecimento] Base injetada nas instructions.")
    except Exception as e:
        logger.error(f"[Conhecimento] Erro: {e}")

    # MEMÓRIA LOCAL PERSISTENTE v2.0 — contexto completo com memórias explícitas
    try:
        contexto_local = await asyncio.to_thread(_gerar_contexto_memorias, 4000)
        if contexto_local:
            instructions_finais += f"\n\n# MEMÓRIA LOCAL PERSISTENTE (MENTE AVANÇADA)\n{contexto_local}"
            logger.info("[MemLocal] Contexto de memória avançada injetado.")
    except Exception as e:
        logger.warning(f"[MemLocal] Erro ao carregar memória local: {e}")

    # SAUDAÇÃO CONTEXTUALIZADA — lembra o que foi discutido na última sessão
    saudacao_ctx = ""
    try:
        saudacao_ctx = await asyncio.to_thread(_saudacao_contextual)
        if saudacao_ctx:
            instructions_finais += f"\n\n# SAUDAÇÃO SUGERIDA (use como base, adapte naturalmente)\n{saudacao_ctx}"
            logger.info("[MemLocal] Saudação contextualizada gerada.")
    except Exception as e:
        logger.warning(f"[MemLocal] Erro ao gerar saudação: {e}")

    session = AgentSession()
    agent = Assistant(chat_ctx=ChatContext(), instructions=instructions_finais)

    # Inicia sessão
    try:
        if HAS_ROOM_OPTIONS:
            await session.start(
                room=ctx.room, agent=agent,
                room_options=RoomOptions(video_enabled=True, noise_cancellation=noise_cancellation.BVC()),
            )
        else:
            await session.start(
                room=ctx.room, agent=agent,
                room_input_options=RoomInputOptions(video_enabled=True, noise_cancellation=noise_cancellation.BVC()),
            )
    except Exception as e:
        logger.error(f"[Session] Erro ao iniciar sessão: {e}")
        await session.start(room=ctx.room, agent=agent)

    # Monitor de áudio DESABILITADO (causando repetições de SFX)
    # try:
    #     resultado_monitor = await asyncio.to_thread(_iniciar_monitor)
    #     logger.info(f"[AudioHealth] {resultado_monitor}")
    # except Exception as e:
    #     logger.warning(f"[AudioHealth] Falha: {e}")

    await asyncio.to_thread(registrar_sessao)
    registrar_evento("sistema", "Sessão do Jarvis iniciada")

    # Iniciar monitor de notificações em background
    try:
        resultado_notif = await asyncio.to_thread(_iniciar_notif, 10)
        logger.info(f"[NotifMonitor] {resultado_notif}")
    except Exception as e:
        logger.warning(f"[NotifMonitor] Falha ao iniciar: {e}")

    # shutdown COM DUAL SAVE: Mem0 (cloud) + Memória Local (disco)
    async def shutdown_hook():
        try:
            registrar_evento("sistema", "Sessão encerrada")
            msgs = []
            chat_items = []
            try:
                chat_items = session._agent.chat_ctx.items if session._agent else []
            except Exception:
                pass
            for item in chat_items:
                if not hasattr(item, "content") or not item.content:
                    continue
                if item.role not in ("user", "assistant"):
                    continue
                conteudo = "".join(item.content) if isinstance(item.content, list) else str(item.content)
                conteudo = conteudo.strip()
                if conteudo:
                    msgs.append({"role": item.role, "content": conteudo})

            # SAVE 1: Mem0 Cloud
            if msgs and mem0_disponivel and mem0_client is not None:
                try:
                    await mem0_client.add(msgs, user_id=user_id)
                    logger.info(f"[Mem0] {len(msgs)} mensagens salvas na nuvem.")
                except Exception as e:
                    logger.warning(f"[Mem0] Erro ao salvar mensagens: {e}")
            elif mem0_erro_msg:
                logger.warning(f"[Mem0] Erro ao salvar mensagens: {mem0_erro_msg}")

            # SAVE 2: Memória Local Persistente (SEMPRE salva)
            if msgs:
                try:
                    resultado_local = await asyncio.to_thread(_salvar_conversa_local, msgs, user_id)
                    logger.info(f"[MemLocal] {resultado_local}")
                except Exception as e:
                    logger.warning(f"[MemLocal] Erro ao salvar localmente: {e}")

            # Parar monitor de notificações
            try:
                await asyncio.to_thread(_parar_notif)
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"[Shutdown] Erro: {e}")

    ctx.add_shutdown_callback(shutdown_hook)

    await asyncio.sleep(0.5)
    try:
        saudacao_instrucao = SESSION_INSTRUCTION
        if saudacao_ctx:
            saudacao_instrucao += f"\n\nSaudação sugerida baseada na memória: {saudacao_ctx}\nAdapte naturalmente — lembre de coisas que o Senhor pediu para guardar."
        else:
            saudacao_instrucao += "\nCumprimente o usuário de forma natural, confiante e personalizada."
        if session is not None:
            await session.generate_reply(
                instructions=saudacao_instrucao
            )
    except RuntimeError as e:
        if "AgentSession isn't running" in str(e):
            logger.info("Session closed before reply — skipping")
        else:
            logger.error(f"[Session] Erro: {e}")
    except Exception as e:
        logger.error(f"[Session] Erro inesperado: {e}")


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))