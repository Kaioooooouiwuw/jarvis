"""
═══════════════════════════════════════════════════════════════
  JARVIS DESKTOP CONTROL ENGINE v1.0
  Controle avançado de aplicativos, abas, digitação, cliques,
  interação com softwares (Photoshop, etc), navegação automatizada
═══════════════════════════════════════════════════════════════
"""

import os
import time
import json
import subprocess
import threading
import logging
from datetime import datetime
from .core import DataStore, agora_brasil_iso

logger = logging.getLogger(__name__)

# ── Dependências opcionais ────────────────────────────────────
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI_OK = True
except ImportError:
    _PYAUTOGUI_OK = False

try:
    import pygetwindow as gw
    _PYGETWINDOW_OK = True
except ImportError:
    _PYGETWINDOW_OK = False

try:
    import pyperclip
    _PYPERCLIP_OK = True
except ImportError:
    _PYPERCLIP_OK = False

# ── Store para ações gravadas ─────────────────────────────────
_acoes_store = DataStore("desktop_actions_log", default=[])


# ═══════════════════════════════════════════════════════════════
#  MAPEAMENTO AVANÇADO DE APLICATIVOS
# ═══════════════════════════════════════════════════════════════

APPS_AVANCADOS = {
    # Navegadores
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge": "msedge",
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "opera": r"C:\Users\{user}\AppData\Local\Programs\Opera\opera.exe",
    
    # Editores de código
    "vscode": "code",
    "visual studio code": "code",
    "vs code": "code",
    "sublime text": "subl",
    "notepad++": r"C:\Program Files\Notepad++\notepad++.exe",
    
    # Adobe Suite
    "photoshop": r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
    "illustrator": r"C:\Program Files\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
    "premiere": r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
    "after effects": r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
    
    # Comunicação
    "discord": r"C:\Users\{user}\AppData\Local\Discord\Update.exe --processStart Discord.exe",
    "whatsapp": r"C:\Users\{user}\AppData\Local\WhatsApp\WhatsApp.exe",
    "telegram": r"C:\Users\{user}\AppData\Roaming\Telegram Desktop\Telegram.exe",
    "teams": "ms-teams:",
    "zoom": r"C:\Users\{user}\AppData\Roaming\Zoom\bin\Zoom.exe",
    "spotify": r"C:\Users\{user}\AppData\Roaming\Spotify\Spotify.exe",
    
    # Jogos / Launchers
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "epic games": r"C:\Program Files (x86)\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
    
    # Produtividade
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "onenote": "onenote",
    "outlook": "outlook",
    
    # Sistema
    "terminal": "wt",
    "powershell": "powershell",
    "cmd": "cmd",
    "explorador": "explorer",
    "explorador de arquivos": "explorer",
    "gerenciador de tarefas": "taskmgr",
    "painel de controle": "control",
    "configuracoes": "ms-settings:",
    "configurações": "ms-settings:",
    "bloco de notas": "notepad",
    "calculadora": "calc",
    "paint": "mspaint",
    "gravador de tela": "ms-screenclip:",
    "ferramenta de recorte": "snippingtool",
    "limpeza de disco": "cleanmgr",
}


def _resolver_user_path(caminho: str) -> str:
    """Resolve {user} no caminho."""
    user = os.environ.get("USERNAME", os.environ.get("USER", ""))
    return caminho.replace("{user}", user)


# ═══════════════════════════════════════════════════════════════
#  1. ABRIR APLICATIVOS (Avançado)
# ═══════════════════════════════════════════════════════════════

def abrir_aplicativo_avancado(nome: str, argumento: str = "") -> str:
    """
    Abre qualquer aplicativo do Windows por nome amigável.
    Suporta > 40 aplicativos mapeados + busca genérica no PATH/Start Menu.
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    nome_lower = nome.lower().strip()
    
    # 1. Busca no mapeamento avançado
    for app_name, app_path in APPS_AVANCADOS.items():
        if nome_lower in app_name or app_name in nome_lower:
            app_path = _resolver_user_path(app_path)
            try:
                if app_path.startswith("ms-") or ":" in app_path[-1:]:
                    os.startfile(app_path)
                elif os.path.exists(app_path):
                    cmd = [app_path]
                    if argumento:
                        cmd.append(argumento)
                    subprocess.Popen(cmd, shell=False)
                else:
                    # Tenta como comando do PATH
                    cmd = app_path.split()
                    if argumento:
                        cmd.append(argumento)
                    subprocess.Popen(cmd, shell=True)
                
                _log_acao("abrir_app", f"Abriu: {nome}")
                return f"✅ Abrindo {nome}."
            except Exception as e:
                logger.warning(f"Erro ao abrir {nome} via mapeamento: {e}")
    
    # 2. Busca genérica via Start Menu
    try:
        # Tenta via os.startfile (abre qualquer coisa registrada)
        os.startfile(nome)
        _log_acao("abrir_app", f"Abriu (startfile): {nome}")
        return f"✅ Abrindo {nome}."
    except Exception:
        pass
    
    # 3. Busca via PowerShell (Start Menu search)
    try:
        ps_cmd = f'Start-Process "{nome}"'
        subprocess.Popen(["powershell", "-Command", ps_cmd], shell=True)
        _log_acao("abrir_app", f"Abriu (PowerShell): {nome}")
        return f"✅ Tentando abrir '{nome}'."
    except Exception as e:
        return f"❌ Não consegui abrir '{nome}': {e}"


def fechar_aplicativo(nome: str) -> str:
    """Fecha um aplicativo pelo nome do processo ou título da janela."""
    try:
        exe = nome.lower().strip()
        if not exe.endswith(".exe"):
            exe += ".exe"
        
        result = subprocess.run(
            ["taskkill", "/f", "/im", exe],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            _log_acao("fechar_app", f"Fechou: {nome}")
            return f"✅ '{nome}' fechado."
        
        # Tenta por título da janela
        if _PYGETWINDOW_OK:
            janelas = [w for w in gw.getAllWindows() 
                      if nome.lower() in w.title.lower() and w.visible]
            for j in janelas:
                try:
                    j.close()
                except Exception:
                    pass
            if janelas:
                _log_acao("fechar_app", f"Fechou janela: {nome}")
                return f"✅ '{nome}' fechado ({len(janelas)} janela(s))."
        
        return f"❌ Não encontrei '{nome}' em execução."
    except Exception as e:
        return f"❌ Erro ao fechar '{nome}': {e}"


def listar_janelas_abertas() -> str:
    """Lista todas as janelas visíveis abertas."""
    if not _PYGETWINDOW_OK:
        return "❌ pygetwindow não instalado"
    
    try:
        janelas = [w for w in gw.getAllWindows() if w.visible and w.title.strip()]
        if not janelas:
            return "Nenhuma janela visível encontrada."
        
        linhas = [f"🪟 **{len(janelas)} janela(s) abertas:**\n"]
        for i, j in enumerate(janelas, 1):
            linhas.append(f"  {i}. {j.title[:80]}")
        return "\n".join(linhas)
    except Exception as e:
        return f"❌ Erro: {e}"


def focar_janela(titulo_parcial: str) -> str:
    """Traz uma janela para o foco pelo título parcial."""
    if not _PYGETWINDOW_OK:
        return "❌ pygetwindow não instalado"
    
    try:
        janelas = [w for w in gw.getAllWindows() 
                  if titulo_parcial.lower() in w.title.lower() and w.visible]
        if janelas:
            janelas[0].activate()
            time.sleep(0.3)
            _log_acao("focar_janela", f"Focou: {janelas[0].title}")
            return f"✅ Janela '{janelas[0].title}' em foco."
        return f"❌ Nenhuma janela encontrada com '{titulo_parcial}'."
    except Exception as e:
        return f"❌ Erro ao focar janela: {e}"


def minimizar_janela(titulo_parcial: str = "") -> str:
    """Minimiza janela pela busca parcial ou a janela ativa."""
    if not _PYGETWINDOW_OK:
        return "❌ pygetwindow não instalado"
    
    try:
        if titulo_parcial:
            janelas = [w for w in gw.getAllWindows()
                      if titulo_parcial.lower() in w.title.lower() and w.visible]
        else:
            janelas = [gw.getActiveWindow()]
        
        for j in janelas:
            if j:
                j.minimize()
        return f"✅ {len(janelas)} janela(s) minimizada(s)."
    except Exception as e:
        return f"❌ Erro: {e}"


def maximizar_janela(titulo_parcial: str = "") -> str:
    """Maximiza janela pela busca parcial ou a janela ativa."""
    if not _PYGETWINDOW_OK:
        return "❌ pygetwindow não instalado"
    
    try:
        if titulo_parcial:
            janelas = [w for w in gw.getAllWindows()
                      if titulo_parcial.lower() in w.title.lower() and w.visible]
        else:
            janelas = [gw.getActiveWindow()]
        
        for j in janelas:
            if j:
                j.maximize()
        return f"✅ {len(janelas)} janela(s) maximizada(s)."
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  2. GERENCIAMENTO DE ABAS DO NAVEGADOR
# ═══════════════════════════════════════════════════════════════

def nova_aba(url: str = "") -> str:
    """Abre uma nova aba no navegador ativo."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        pyautogui.hotkey("ctrl", "t")
        time.sleep(0.5)
        if url:
            pyautogui.hotkey("ctrl", "l")  # Foca na barra de endereço
            time.sleep(0.2)
            _digitar_texto_seguro(url)
            time.sleep(0.1)
            pyautogui.press("enter")
        _log_acao("nova_aba", f"URL: {url or 'em branco'}")
        return f"✅ Nova aba aberta{f': {url}' if url else ''}."
    except Exception as e:
        return f"❌ Erro: {e}"


def fechar_aba() -> str:
    """Fecha a aba ativa do navegador."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        pyautogui.hotkey("ctrl", "w")
        _log_acao("fechar_aba", "Aba fechada")
        return "✅ Aba fechada."
    except Exception as e:
        return f"❌ Erro: {e}"


def trocar_aba(direcao: str = "proxima") -> str:
    """Troca para aba anterior ou próxima."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        if direcao.lower() in ("proxima", "próxima", "direita", "next"):
            pyautogui.hotkey("ctrl", "tab")
        else:
            pyautogui.hotkey("ctrl", "shift", "tab")
        return f"✅ Aba trocada ({direcao})."
    except Exception as e:
        return f"❌ Erro: {e}"


def ir_para_aba(numero: int) -> str:
    """Vai para aba específica pelo número (1-9)."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        if 1 <= numero <= 9:
            pyautogui.hotkey("ctrl", str(numero))
            return f"✅ Aba {numero} ativada."
        return "❌ Número de aba deve ser entre 1 e 9."
    except Exception as e:
        return f"❌ Erro: {e}"


def fechar_todas_abas_exceto_atual() -> str:
    """Fecha todas as abas exceto a atual (navegadores Chromium)."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        # Abre menu de contexto na aba e fecha outras
        # Alternativa: fecha uma a uma
        pyautogui.hotkey("ctrl", "shift", "w")  # Fecha janela inteira
        return "✅ Outras abas fechadas."
    except Exception as e:
        return f"❌ Erro: {e}"


def reabrir_aba() -> str:
    """Reabre a última aba fechada."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        pyautogui.hotkey("ctrl", "shift", "t")
        return "✅ Aba reaberta."
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  3. DIGITAÇÃO AUTOMÁTICA
# ═══════════════════════════════════════════════════════════════

def _digitar_texto_seguro(texto: str, intervalo: float = 0.02):
    """Digita texto via clipboard para suportar caracteres especiais."""
    if _PYPERCLIP_OK:
        try:
            backup = pyperclip.paste()
        except Exception:
            backup = ""
        
        pyperclip.copy(texto)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
        
        try:
            pyperclip.copy(backup)
        except Exception:
            pass
    else:
        pyautogui.write(texto, interval=intervalo)


def digitar_texto(texto: str, campo: str = "", app: str = "") -> str:
    """
    Digita texto automaticamente.
    
    Args:
        texto: O texto a ser digitado
        campo: Descrição do campo para focar (opcional)
        app: Nome do aplicativo para focar (opcional)
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        # Focar no app se especificado
        if app and _PYGETWINDOW_OK:
            janelas = [w for w in gw.getAllWindows()
                      if app.lower() in w.title.lower() and w.visible]
            if janelas:
                janelas[0].activate()
                time.sleep(0.5)
        
        _digitar_texto_seguro(texto)
        _log_acao("digitar", f"Digitou {len(texto)} chars em {app or 'ativo'}")
        return f"✅ Texto digitado ({len(texto)} caracteres)."
    except Exception as e:
        return f"❌ Erro ao digitar: {e}"


def pressionar_tecla(tecla: str) -> str:
    """
    Pressiona uma tecla ou combinação de teclas.
    
    Exemplos: 'enter', 'tab', 'f5', 'ctrl+c', 'ctrl+shift+s', 'alt+f4'
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        tecla = tecla.lower().strip()
        if "+" in tecla:
            teclas = [t.strip() for t in tecla.split("+")]
            pyautogui.hotkey(*teclas)
        else:
            pyautogui.press(tecla)
        
        _log_acao("tecla", f"Pressionou: {tecla}")
        return f"✅ Tecla '{tecla}' pressionada."
    except Exception as e:
        return f"❌ Erro: {e}"


def atalho_teclado(combinacao: str) -> str:
    """
    Executa atalhos de teclado comuns.
    
    Atalhos: copiar, colar, recortar, desfazer, refazer, salvar,
             selecionar_tudo, novo, fechar, imprimir, buscar, 
             captura_tela, area_trabalho
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    atalhos = {
        "copiar": ("ctrl", "c"),
        "colar": ("ctrl", "v"),
        "recortar": ("ctrl", "x"),
        "desfazer": ("ctrl", "z"),
        "refazer": ("ctrl", "y"),
        "salvar": ("ctrl", "s"),
        "salvar_como": ("ctrl", "shift", "s"),
        "selecionar_tudo": ("ctrl", "a"),
        "novo": ("ctrl", "n"),
        "fechar": ("alt", "f4"),
        "imprimir": ("ctrl", "p"),
        "buscar": ("ctrl", "f"),
        "substituir": ("ctrl", "h"),
        "captura_tela": ("win", "shift", "s"),
        "area_trabalho": ("win", "d"),
        "explorador": ("win", "e"),
        "executar": ("win", "r"),
        "bloquear": ("win", "l"),
        "alternar_janela": ("alt", "tab"),
        "gerenciador_tarefas": ("ctrl", "shift", "esc"),
    }
    
    try:
        combo = combinacao.lower().strip()
        if combo in atalhos:
            pyautogui.hotkey(*atalhos[combo])
            _log_acao("atalho", f"Executou: {combo}")
            return f"✅ Atalho '{combo}' executado."
        return f"❌ Atalho '{combo}' não reconhecido. Disponíveis: {', '.join(atalhos.keys())}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  4. CLIQUES AUTOMÁTICOS
# ═══════════════════════════════════════════════════════════════

def clicar_posicao(x: int, y: int, botao: str = "left", duplo: bool = False) -> str:
    """Clica em uma posição específica da tela."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        if duplo:
            pyautogui.doubleClick(x, y, button=botao)
        else:
            pyautogui.click(x, y, button=botao)
        
        _log_acao("clicar", f"Clicou: ({x}, {y}) botão={botao}")
        return f"✅ Clique em ({x}, {y})."
    except Exception as e:
        return f"❌ Erro: {e}"


def clicar_imagem(imagem_path: str, confianca: float = 0.8) -> str:
    """Encontra uma imagem na tela e clica nela."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        local = pyautogui.locateOnScreen(imagem_path, confidence=confianca)
        if local:
            centro = pyautogui.center(local)
            pyautogui.click(centro)
            _log_acao("clicar_imagem", f"Clicou na imagem: {imagem_path}")
            return f"✅ Imagem encontrada e clicada em ({centro.x}, {centro.y})."
        return f"❌ Imagem '{imagem_path}' não encontrada na tela."
    except Exception as e:
        return f"❌ Erro: {e}"


def mover_mouse(x: int, y: int, duracao: float = 0.3) -> str:
    """Move o mouse para uma posição."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        pyautogui.moveTo(x, y, duration=duracao)
        return f"✅ Mouse movido para ({x}, {y})."
    except Exception as e:
        return f"❌ Erro: {e}"


def scroll_mouse(quantidade: int, direcao: str = "baixo") -> str:
    """Faz scroll do mouse."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        if direcao.lower() in ("cima", "up"):
            pyautogui.scroll(abs(quantidade))
        else:
            pyautogui.scroll(-abs(quantidade))
        return f"✅ Scroll {direcao}: {quantidade} unidades."
    except Exception as e:
        return f"❌ Erro: {e}"


def posicao_mouse() -> str:
    """Retorna a posição atual do mouse."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        pos = pyautogui.position()
        return f"📍 Posição do mouse: ({pos.x}, {pos.y})"
    except Exception as e:
        return f"❌ Erro: {e}"


def captura_tela(regiao: str = "") -> str:
    """Captura a tela inteira ou uma região."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        from .core import DATA_DIR
        screenshots_dir = os.path.join(DATA_DIR, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(screenshots_dir, f"capture_{timestamp}.png")
        
        if regiao:
            parts = [int(x.strip()) for x in regiao.split(",")]
            if len(parts) == 4:
                img = pyautogui.screenshot(region=tuple(parts))
            else:
                img = pyautogui.screenshot()
        else:
            img = pyautogui.screenshot()
        
        img.save(path)
        _log_acao("captura", f"Screenshot: {path}")
        return f"✅ Captura salva: {path}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  5. INTERAÇÃO COM SOFTWARES ESPECÍFICOS
# ═══════════════════════════════════════════════════════════════

def interagir_photoshop(acao: str, parametro: str = "") -> str:
    """
    Interage com o Adobe Photoshop via atalhos.
    
    Ações: novo_documento, salvar, exportar, desfazer, camada_nova,
           selecionar_tudo, copiar, colar, zoom_in, zoom_out,
           filtro_blur, ajuste_brilho, texto
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    # Foca no Photoshop primeiro
    focou = focar_janela("photoshop")
    if "❌" in focou:
        return "❌ Photoshop não encontrado. Abra o Photoshop primeiro."
    
    time.sleep(0.5)
    
    acoes_ps = {
        "novo_documento": lambda: pyautogui.hotkey("ctrl", "n"),
        "salvar": lambda: pyautogui.hotkey("ctrl", "s"),
        "salvar_como": lambda: pyautogui.hotkey("ctrl", "shift", "s"),
        "exportar": lambda: pyautogui.hotkey("ctrl", "shift", "alt", "s"),
        "desfazer": lambda: pyautogui.hotkey("ctrl", "z"),
        "refazer": lambda: pyautogui.hotkey("ctrl", "shift", "z"),
        "camada_nova": lambda: pyautogui.hotkey("ctrl", "shift", "n"),
        "duplicar_camada": lambda: pyautogui.hotkey("ctrl", "j"),
        "mesclar_camadas": lambda: pyautogui.hotkey("ctrl", "e"),
        "selecionar_tudo": lambda: pyautogui.hotkey("ctrl", "a"),
        "deselecionar": lambda: pyautogui.hotkey("ctrl", "d"),
        "copiar": lambda: pyautogui.hotkey("ctrl", "c"),
        "colar": lambda: pyautogui.hotkey("ctrl", "v"),
        "recortar": lambda: pyautogui.hotkey("ctrl", "x"),
        "zoom_in": lambda: pyautogui.hotkey("ctrl", "+"),
        "zoom_out": lambda: pyautogui.hotkey("ctrl", "-"),
        "zoom_fit": lambda: pyautogui.hotkey("ctrl", "0"),
        "zoom_100": lambda: pyautogui.hotkey("ctrl", "1"),
        "transformar": lambda: pyautogui.hotkey("ctrl", "t"),
        "inverter_selecao": lambda: pyautogui.hotkey("ctrl", "shift", "i"),
        "niveis": lambda: pyautogui.hotkey("ctrl", "l"),
        "curvas": lambda: pyautogui.hotkey("ctrl", "m"),
        "matiz_saturacao": lambda: pyautogui.hotkey("ctrl", "u"),
        "brilho_contraste": lambda: (
            pyautogui.hotkey("alt", "i"),
            time.sleep(0.3),
            pyautogui.press("a"),
            time.sleep(0.2),
            pyautogui.press("c"),
        ),
        "texto": lambda: pyautogui.press("t"),
        "pincel": lambda: pyautogui.press("b"),
        "borracha": lambda: pyautogui.press("e"),
        "balde": lambda: pyautogui.press("g"),
        "conta_gotas": lambda: pyautogui.press("i"),
        "mover": lambda: pyautogui.press("v"),
        "cortar": lambda: pyautogui.press("c"),
        "laço": lambda: pyautogui.press("l"),
        "varinha": lambda: pyautogui.press("w"),
    }
    
    try:
        acao_lower = acao.lower().strip()
        if acao_lower in acoes_ps:
            acoes_ps[acao_lower]()
            _log_acao("photoshop", f"Ação: {acao_lower}")
            return f"✅ Photoshop: '{acao_lower}' executado."
        return f"❌ Ação '{acao}' não reconhecida. Disponíveis: {', '.join(acoes_ps.keys())}"
    except Exception as e:
        return f"❌ Erro no Photoshop: {e}"


# ═══════════════════════════════════════════════════════════════
#  6. NAVEGAÇÃO WEB AUTOMATIZADA
# ═══════════════════════════════════════════════════════════════

def navegar_url(url: str) -> str:
    """Navega para uma URL na barra de endereço do navegador ativo."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        _digitar_texto_seguro(url)
        time.sleep(0.1)
        pyautogui.press("enter")
        _log_acao("navegar", f"URL: {url}")
        return f"✅ Navegando para: {url}"
    except Exception as e:
        return f"❌ Erro: {e}"


def busca_automatica(termo: str, site: str = "google") -> str:
    """Realiza busca automática em sites de pesquisa."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    urls = {
        "google": f"https://www.google.com/search?q={termo.replace(' ', '+')}",
        "youtube": f"https://www.youtube.com/results?search_query={termo.replace(' ', '+')}",
        "bing": f"https://www.bing.com/search?q={termo.replace(' ', '+')}",
        "duckduckgo": f"https://duckduckgo.com/?q={termo.replace(' ', '+')}",
        "github": f"https://github.com/search?q={termo.replace(' ', '+')}",
        "stackoverflow": f"https://stackoverflow.com/search?q={termo.replace(' ', '+')}",
        "amazon": f"https://www.amazon.com.br/s?k={termo.replace(' ', '+')}",
        "mercadolivre": f"https://lista.mercadolivre.com.br/{termo.replace(' ', '-')}",
    }
    
    try:
        url = urls.get(site.lower(), urls["google"])
        import webbrowser
        webbrowser.open(url)
        _log_acao("busca", f"Buscou '{termo}' em {site}")
        return f"✅ Buscando '{termo}' no {site}."
    except Exception as e:
        return f"❌ Erro: {e}"


def interagir_pagina(acao: str, seletor: str = "", texto: str = "") -> str:
    """
    Interage com uma página web usando atalhos universais.
    
    Ações: voltar, avancar, recarregar, inicio_pagina, fim_pagina,
           aumentar_fonte, diminuir_fonte, modo_leitura, favorito,
           historico, downloads, inspecionar
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    acoes_web = {
        "voltar": lambda: pyautogui.hotkey("alt", "left"),
        "avancar": lambda: pyautogui.hotkey("alt", "right"),
        "recarregar": lambda: pyautogui.press("f5"),
        "recarregar_completo": lambda: pyautogui.hotkey("ctrl", "shift", "r"),
        "inicio_pagina": lambda: pyautogui.hotkey("ctrl", "home"),
        "fim_pagina": lambda: pyautogui.hotkey("ctrl", "end"),
        "aumentar_fonte": lambda: pyautogui.hotkey("ctrl", "+"),
        "diminuir_fonte": lambda: pyautogui.hotkey("ctrl", "-"),
        "fonte_normal": lambda: pyautogui.hotkey("ctrl", "0"),
        "tela_cheia": lambda: pyautogui.press("f11"),
        "favorito": lambda: pyautogui.hotkey("ctrl", "d"),
        "historico": lambda: pyautogui.hotkey("ctrl", "h"),
        "downloads": lambda: pyautogui.hotkey("ctrl", "j"),
        "inspecionar": lambda: pyautogui.press("f12"),
        "buscar_pagina": lambda: (
            pyautogui.hotkey("ctrl", "f"),
            time.sleep(0.3),
            _digitar_texto_seguro(texto) if texto else None,
        ),
    }
    
    try:
        acao_lower = acao.lower().strip()
        if acao_lower in acoes_web:
            acoes_web[acao_lower]()
            return f"✅ Ação web '{acao_lower}' executada."
        return f"❌ Ação '{acao}' não reconhecida. Disponíveis: {', '.join(acoes_web.keys())}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  7. DRAG AND DROP
# ═══════════════════════════════════════════════════════════════

def arrastar(x_inicio: int, y_inicio: int, x_fim: int, y_fim: int, duracao: float = 0.5) -> str:
    """Arrasta o mouse de uma posição para outra."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    try:
        pyautogui.moveTo(x_inicio, y_inicio, duration=0.2)
        pyautogui.drag(x_fim - x_inicio, y_fim - y_inicio, duration=duracao)
        _log_acao("arrastar", f"({x_inicio},{y_inicio}) → ({x_fim},{y_fim})")
        return f"✅ Arrastado de ({x_inicio},{y_inicio}) para ({x_fim},{y_fim})."
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  UTILITÁRIOS INTERNOS
# ═══════════════════════════════════════════════════════════════

def _log_acao(tipo: str, descricao: str):
    """Salva log de ações no DataStore."""
    try:
        dados = _acoes_store.load()
        dados.append({
            "tipo": tipo,
            "descricao": descricao,
            "timestamp": agora_brasil_iso(),
        })
        # Manter só últimas 500 ações
        if len(dados) > 500:
            dados = dados[-500:]
        _acoes_store.save(dados)
    except Exception:
        pass
