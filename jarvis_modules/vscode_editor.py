"""
═══════════════════════════════════════════════════════════════
  JARVIS VS CODE EDITOR v1.0
  Controle avançado do VS Code no Windows — editar, navegar,
  criar arquivos, executar comandos, terminal integrado
═══════════════════════════════════════════════════════════════
"""

import os
import time
import json
import subprocess
import logging
from .core import DataStore, agora_brasil_iso

logger = logging.getLogger(__name__)

# ── Dependências ──────────────────────────────────────────────
try:
    import pyautogui
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

# ── Store ─────────────────────────────────────────────────────
_vscode_store = DataStore("vscode_actions", default=[])


# ═══════════════════════════════════════════════════════════════
#  1. ABRIR E FOCAR VS CODE
# ═══════════════════════════════════════════════════════════════

def abrir_vscode(caminho: str = "") -> str:
    """
    Abre o VS Code, opcionalmente com um arquivo ou pasta.
    
    Args:
        caminho: Arquivo ou pasta para abrir (opcional)
    """
    try:
        cmd = ["code"]
        if caminho:
            caminho = os.path.expanduser(caminho)
            cmd.append(caminho)
        
        subprocess.Popen(cmd, shell=True)
        time.sleep(1)
        
        _log_acao("abrir_vscode", f"Abriu: {caminho or 'workspace atual'}")
        return f"✅ VS Code aberto{f': {caminho}' if caminho else ''}."
    except FileNotFoundError:
        return "❌ 'code' não encontrado no PATH. Instale o VS Code ou adicione ao PATH."
    except Exception as e:
        return f"❌ Erro ao abrir VS Code: {e}"


def focar_vscode() -> str:
    """Traz o VS Code para o foco."""
    if not _PYGETWINDOW_OK:
        return "❌ pygetwindow não instalado"
    
    try:
        janelas = [w for w in gw.getAllWindows()
                  if "visual studio code" in w.title.lower() and w.visible]
        if janelas:
            janelas[0].activate()
            time.sleep(0.3)
            return f"✅ VS Code em foco: {janelas[0].title}"
        return "❌ VS Code não encontrado. Abra-o primeiro."
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  2. EDIÇÃO VIA CLI (code command)
# ═══════════════════════════════════════════════════════════════

def abrir_arquivo_vscode(caminho: str, linha: int = 0) -> str:
    """
    Abre um arquivo no VS Code, opcionalmente em uma linha específica.
    """
    try:
        caminho = os.path.expanduser(caminho)
        cmd = ["code"]
        if linha > 0:
            cmd.append("--goto")
            cmd.append(f"{caminho}:{linha}")
        else:
            cmd.append(caminho)
        
        subprocess.Popen(cmd, shell=True)
        _log_acao("abrir_arquivo", f"{caminho}:{linha}")
        return f"✅ Arquivo aberto no VS Code: {caminho}" + (f" (linha {linha})" if linha else "")
    except Exception as e:
        return f"❌ Erro: {e}"


def criar_arquivo_vscode(caminho: str, conteudo: str = "") -> str:
    """
    Cria um novo arquivo e abre no VS Code.
    """
    try:
        caminho = os.path.expanduser(caminho)
        
        # Criar diretório se não existir
        diretorio = os.path.dirname(caminho)
        if diretorio:
            os.makedirs(diretorio, exist_ok=True)
        
        # Escrever conteúdo
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
        
        # Abrir no VS Code
        subprocess.Popen(["code", caminho], shell=True)
        
        _log_acao("criar_arquivo", f"{caminho} ({len(conteudo)} chars)")
        return f"✅ Arquivo criado e aberto: {caminho}"
    except Exception as e:
        return f"❌ Erro: {e}"


def abrir_pasta_vscode(caminho: str) -> str:
    """Abre uma pasta no VS Code como workspace."""
    try:
        caminho = os.path.expanduser(caminho)
        if not os.path.isdir(caminho):
            return f"❌ Pasta não encontrada: {caminho}"
        
        subprocess.Popen(["code", caminho], shell=True)
        _log_acao("abrir_pasta", caminho)
        return f"✅ Pasta aberta no VS Code: {caminho}"
    except Exception as e:
        return f"❌ Erro: {e}"


def diff_vscode(arquivo1: str, arquivo2: str) -> str:
    """Abre comparação de dois arquivos no VS Code."""
    try:
        subprocess.Popen(["code", "--diff", arquivo1, arquivo2], shell=True)
        return f"✅ Comparação aberta: {arquivo1} vs {arquivo2}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  3. EDIÇÃO VIA ATALHOS (GUI Automation)
# ═══════════════════════════════════════════════════════════════

def _focar_vscode_e_esperar() -> bool:
    """Foca no VS Code e espera ficar pronto."""
    if not _PYGETWINDOW_OK:
        return False
    try:
        janelas = [w for w in gw.getAllWindows()
                  if "visual studio code" in w.title.lower() and w.visible]
        if janelas:
            janelas[0].activate()
            time.sleep(0.5)
            return True
        return False
    except Exception:
        return False


def _digitar_seguro(texto: str):
    """Digita via clipboard para suportar caracteres especiais."""
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
        pyautogui.write(texto, interval=0.02)


def editar_codigo_vscode(operacao: str, texto: str = "", busca: str = "") -> str:
    """
    Operações de edição no VS Code:
    
    Operações: inserir, substituir, deletar_linha, comentar,
               ir_para_linha, buscar, buscar_substituir,
               formatar, indentar, desindentar, duplicar_linha,
               mover_linha_cima, mover_linha_baixo,
               selecionar_palavra, selecionar_linha, selecionar_tudo
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    if not _focar_vscode_e_esperar():
        return "❌ VS Code não encontrado. Abra-o primeiro."
    
    operacoes = {
        "inserir": lambda: _digitar_seguro(texto),
        "substituir": lambda: _vscode_substituir(busca, texto),
        "deletar_linha": lambda: pyautogui.hotkey("ctrl", "shift", "k"),
        "comentar": lambda: pyautogui.hotkey("ctrl", "/"),
        "comentar_bloco": lambda: pyautogui.hotkey("ctrl", "shift", "/"),
        "ir_para_linha": lambda: _vscode_ir_para_linha(texto),
        "buscar": lambda: _vscode_buscar(busca or texto),
        "buscar_substituir": lambda: _vscode_substituir(busca, texto),
        "formatar": lambda: pyautogui.hotkey("shift", "alt", "f"),
        "indentar": lambda: pyautogui.press("tab"),
        "desindentar": lambda: pyautogui.hotkey("shift", "tab"),
        "duplicar_linha": lambda: pyautogui.hotkey("shift", "alt", "down"),
        "mover_linha_cima": lambda: pyautogui.hotkey("alt", "up"),
        "mover_linha_baixo": lambda: pyautogui.hotkey("alt", "down"),
        "selecionar_palavra": lambda: pyautogui.hotkey("ctrl", "d"),
        "selecionar_linha": lambda: pyautogui.hotkey("ctrl", "l"),
        "selecionar_tudo": lambda: pyautogui.hotkey("ctrl", "a"),
        "copiar": lambda: pyautogui.hotkey("ctrl", "c"),
        "colar": lambda: pyautogui.hotkey("ctrl", "v"),
        "desfazer": lambda: pyautogui.hotkey("ctrl", "z"),
        "refazer": lambda: pyautogui.hotkey("ctrl", "y"),
        "salvar": lambda: pyautogui.hotkey("ctrl", "s"),
        "salvar_tudo": lambda: pyautogui.hotkey("ctrl", "k", "s"),
        "fechar_arquivo": lambda: pyautogui.hotkey("ctrl", "w"),
        "fechar_todos": lambda: pyautogui.hotkey("ctrl", "k", "ctrl", "w"),
    }
    
    try:
        op = operacao.lower().strip()
        if op in operacoes:
            operacoes[op]()
            _log_acao("editar_vscode", f"{op}: {texto[:50] if texto else busca[:50] if busca else ''}")
            return f"✅ VS Code: '{op}' executado."
        return f"❌ Operação '{op}' não reconhecida. Disponíveis: {', '.join(operacoes.keys())}"
    except Exception as e:
        return f"❌ Erro: {e}"


def _vscode_ir_para_linha(linha_str: str):
    """Vai para uma linha específica no VS Code."""
    pyautogui.hotkey("ctrl", "g")
    time.sleep(0.3)
    pyautogui.write(str(linha_str), interval=0.02)
    time.sleep(0.1)
    pyautogui.press("enter")


def _vscode_buscar(termo: str):
    """Busca texto no VS Code."""
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.3)
    _digitar_seguro(termo)


def _vscode_substituir(busca: str, substituicao: str):
    """Busca e substitui texto no VS Code."""
    pyautogui.hotkey("ctrl", "h")
    time.sleep(0.3)
    _digitar_seguro(busca)
    time.sleep(0.1)
    pyautogui.press("tab")
    time.sleep(0.1)
    _digitar_seguro(substituicao)


# ═══════════════════════════════════════════════════════════════
#  4. PAINEL DE COMANDOS E TERMINAL
# ═══════════════════════════════════════════════════════════════

def comando_vscode(comando: str) -> str:
    """
    Executa um comando do VS Code via Command Palette.
    
    Exemplos: 'Git: Commit', 'Format Document', 'Toggle Terminal'
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    if not _focar_vscode_e_esperar():
        return "❌ VS Code não encontrado."
    
    try:
        pyautogui.hotkey("ctrl", "shift", "p")
        time.sleep(0.5)
        _digitar_seguro(comando)
        time.sleep(0.3)
        pyautogui.press("enter")
        
        _log_acao("comando_vscode", comando)
        return f"✅ Comando VS Code executado: {comando}"
    except Exception as e:
        return f"❌ Erro: {e}"


def terminal_vscode(comando: str = "") -> str:
    """
    Abre ou usa o terminal integrado do VS Code.
    Se comando fornecido, digita e executa no terminal.
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    if not _focar_vscode_e_esperar():
        return "❌ VS Code não encontrado."
    
    try:
        # Toggle terminal
        pyautogui.hotkey("ctrl", "`")
        time.sleep(0.5)
        
        if comando:
            _digitar_seguro(comando)
            time.sleep(0.1)
            pyautogui.press("enter")
            _log_acao("terminal_vscode", comando)
            return f"✅ Comando executado no terminal: {comando}"
        
        return "✅ Terminal do VS Code aberto."
    except Exception as e:
        return f"❌ Erro: {e}"


def novo_terminal_vscode() -> str:
    """Cria um novo terminal no VS Code."""
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    if not _focar_vscode_e_esperar():
        return "❌ VS Code não encontrado."
    
    try:
        pyautogui.hotkey("ctrl", "shift", "`")
        return "✅ Novo terminal criado."
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  5. EXTENSÕES E CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════

def instalar_extensao_vscode(extensao: str) -> str:
    """Instala extensão no VS Code via CLI."""
    try:
        result = subprocess.run(
            ["code", "--install-extension", extensao],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return f"✅ Extensão instalada: {extensao}"
        return f"❌ Erro ao instalar: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "❌ Timeout ao instalar extensão"
    except Exception as e:
        return f"❌ Erro: {e}"


def listar_extensoes_vscode() -> str:
    """Lista extensões instaladas no VS Code."""
    try:
        result = subprocess.run(
            ["code", "--list-extensions"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            extensoes = result.stdout.strip().split("\n")
            linhas = [f"📦 **{len(extensoes)} extensões instaladas:**\n"]
            for ext in extensoes:
                linhas.append(f"  • {ext}")
            return "\n".join(linhas)
        return f"❌ Erro: {result.stderr}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  6. ATALHOS RÁPIDOS DO VS CODE
# ═══════════════════════════════════════════════════════════════

def atalho_vscode(acao: str) -> str:
    """
    Atalhos comuns do VS Code:
    
    Ações: explorador, busca_global, controle_fonte, debug,
           extensoes, problemas, output, painel_lateral,
           minimap, word_wrap, zen_mode, split_editor,
           preview_markdown, emmet_wrap, multi_cursor
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    if not _focar_vscode_e_esperar():
        return "❌ VS Code não encontrado."
    
    atalhos = {
        "explorador":       ("ctrl", "shift", "e"),
        "busca_global":     ("ctrl", "shift", "f"),
        "controle_fonte":   ("ctrl", "shift", "g"),
        "debug":            ("ctrl", "shift", "d"),
        "extensoes":        ("ctrl", "shift", "x"),
        "problemas":        ("ctrl", "shift", "m"),
        "output":           ("ctrl", "shift", "u"),
        "painel_lateral":   ("ctrl", "b"),
        "minimap":          None,  # via command palette
        "word_wrap":        ("alt", "z"),
        "zen_mode":         ("ctrl", "k", "z"),
        "split_editor":     ("ctrl", "\\"),
        "preview_markdown": ("ctrl", "shift", "v"),
        "multi_cursor_up":  ("ctrl", "alt", "up"),
        "multi_cursor_down":("ctrl", "alt", "down"),
        "ir_definicao":     ("f12",),
        "peek_definicao":   ("alt", "f12"),
        "renomear_simbolo": ("f2",),
        "abrir_rapido":     ("ctrl", "p"),
        "ir_simbolo":       ("ctrl", "shift", "o"),
    }
    
    try:
        acao_lower = acao.lower().strip()
        if acao_lower in atalhos:
            teclas = atalhos[acao_lower]
            if teclas is None:
                return comando_vscode(f"Toggle {acao_lower}")
            pyautogui.hotkey(*teclas)
            return f"✅ VS Code atalho: '{acao_lower}'"
        return f"❌ Atalho '{acao}' não reconhecido. Disponíveis: {', '.join(atalhos.keys())}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  7. INSERÇÃO DE CÓDIGO INTELIGENTE
# ═══════════════════════════════════════════════════════════════

def inserir_codigo_vscode(codigo: str, tipo: str = "python") -> str:
    """
    Insere bloco de código no VS Code na posição do cursor.
    """
    if not _PYAUTOGUI_OK:
        return "❌ pyautogui não instalado"
    
    if not _focar_vscode_e_esperar():
        return "❌ VS Code não encontrado."
    
    try:
        _digitar_seguro(codigo)
        time.sleep(0.2)
        
        # Formatar automaticamente
        pyautogui.hotkey("shift", "alt", "f")
        
        _log_acao("inserir_codigo", f"{tipo}: {len(codigo)} chars")
        return f"✅ Código {tipo} inserido ({len(codigo)} chars)."
    except Exception as e:
        return f"❌ Erro: {e}"


def criar_snippet_vscode(nome: str, prefixo: str, corpo: str, descricao: str = "") -> str:
    """
    Cria um snippet personalizado para uso no VS Code.
    Salva localmente e sugere adicionar nas settings.
    """
    try:
        from .core import DATA_DIR
        snippets_dir = os.path.join(DATA_DIR, "vscode_snippets")
        os.makedirs(snippets_dir, exist_ok=True)
        
        snippet = {
            nome: {
                "prefix": prefixo,
                "body": corpo.split("\n"),
                "description": descricao or nome,
            }
        }
        
        filepath = os.path.join(snippets_dir, f"{nome.replace(' ', '_')}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snippet, f, ensure_ascii=False, indent=2)
        
        _log_acao("criar_snippet", nome)
        return f"✅ Snippet '{nome}' salvo em: {filepath}\n   Prefixo: {prefixo}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════

def _log_acao(tipo: str, descricao: str):
    """Salva log de ação."""
    try:
        dados = _vscode_store.load()
        dados.append({
            "tipo": tipo,
            "descricao": descricao,
            "timestamp": agora_brasil_iso(),
        })
        if len(dados) > 200:
            dados = dados[-200:]
        _vscode_store.save(dados)
    except Exception:
        pass
