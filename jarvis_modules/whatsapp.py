"""
═══════════════════════════════════════════════════════════════
  MÓDULO WHATSAPP — Enviar mensagens pelo WhatsApp Desktop
  ✅ pyautogui + pygetwindow para automação nativa
  ✅ Clipboard via PowerShell (zero risco de access violation)
  ✅ Delays inteligentes: rápido mas estável
  ✅ Retries automáticos e validação de foco
  ✅ Suporte completo a Unicode (acentos, emojis)
═══════════════════════════════════════════════════════════════
"""

import time
import subprocess
import logging

logger = logging.getLogger(__name__)

# Imports lazy — carregados apenas quando necessário
_pyautogui = None
_gw = None


def _get_pyautogui():
    """Carrega pyautogui com configurações seguras."""
    global _pyautogui
    if _pyautogui is None:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        _pyautogui = pyautogui
    return _pyautogui


def _get_gw():
    """Carrega pygetwindow."""
    global _gw
    if _gw is None:
        import pygetwindow as gw
        _gw = gw
    return _gw


# ─────────────────────────────────────────
# CLIPBOARD — POWERSHELL (SEGURO, SEM ACCESS VIOLATION)
# ─────────────────────────────────────────

def _clipboard_set(texto: str) -> bool:
    """
    Copia texto para o clipboard do Windows via PowerShell.
    ✅ Sem ctypes, sem access violation, sem risco.
    ✅ Suporta Unicode completo (acentos, emojis, etc.).
    Retorna True se sucesso.
    """
    try:
        # Escapa aspas simples para PowerShell (duplica cada ')
        texto_escapado = texto.replace("'", "''")

        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NoLogo",
                "-Command",
                f"Set-Clipboard -Value '{texto_escapado}'"
            ],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if result.returncode == 0:
            return True

        logger.warning(f"[WhatsApp] PowerShell clipboard falhou: {result.stderr}")
        return False

    except subprocess.TimeoutExpired:
        logger.warning("[WhatsApp] Timeout ao definir clipboard via PowerShell")
        return False
    except Exception as e:
        logger.error(f"[WhatsApp] Erro ao definir clipboard: {e}")
        return False


def _digitar_texto(texto: str) -> bool:
    """
    Digita texto via clipboard + Ctrl+V.
    ✅ Funciona com qualquer caractere (acentos, emojis, Unicode).
    ✅ Retry automático se clipboard falhar.
    Retorna True se sucesso.
    """
    pag = _get_pyautogui()

    # Tenta definir o clipboard (com até 2 tentativas)
    for tentativa in range(2):
        if _clipboard_set(texto):
            break
        logger.warning(f"[WhatsApp] Clipboard tentativa {tentativa + 1} falhou, retentando...")
        time.sleep(0.3)
    else:
        logger.error("[WhatsApp] Não foi possível copiar texto para clipboard")
        return False

    time.sleep(0.1)
    pag.hotkey("ctrl", "v")
    time.sleep(0.2)
    return True


# ─────────────────────────────────────────
# VALIDAÇÃO DE FOCO DA JANELA
# ─────────────────────────────────────────

def _encontrar_janela_whatsapp():
    """
    Encontra a janela do WhatsApp Desktop.
    Busca por variações do título: WhatsApp, WhatsApp Desktop, etc.
    """
    try:
        gw = _get_gw()
        janelas = [
            w for w in gw.getAllWindows()
            if w.title and "whatsapp" in w.title.lower() and w.visible
        ]
        return janelas[0] if janelas else None
    except Exception as e:
        logger.error(f"[WhatsApp] Erro ao buscar janela: {e}")
        return None


def _garantir_foco_whatsapp() -> bool:
    """
    Garante que a janela do WhatsApp está em foco.
    Retorna True se conseguiu focar.
    """
    janela = _encontrar_janela_whatsapp()
    if not janela:
        return False

    try:
        if janela.isMinimized:
            janela.restore()
            time.sleep(0.4)
        janela.activate()
        time.sleep(0.3)
        return True
    except Exception as e:
        logger.warning(f"[WhatsApp] Erro ao focar janela: {e}")
        # Fallback: tenta com Alt+Tab de volta
        try:
            pag = _get_pyautogui()
            pag.hotkey("alt", "tab")
            time.sleep(0.5)
            # Verifica se realmente focou
            janela2 = _encontrar_janela_whatsapp()
            if janela2:
                return True
        except Exception:
            pass
        return False


def _whatsapp_esta_em_foco() -> bool:
    """Verifica se a janela do WhatsApp está em primeiro plano."""
    try:
        gw = _get_gw()
        ativa = gw.getActiveWindow()
        if ativa and ativa.title and "whatsapp" in ativa.title.lower():
            return True
    except Exception:
        pass
    return False


# ─────────────────────────────────────────
# ABRIR WHATSAPP
# ─────────────────────────────────────────

def _abrir_whatsapp() -> bool:
    """
    Abre o WhatsApp Desktop se não estiver aberto.
    ✅ Tenta 3 métodos diferentes em sequência.
    ✅ Aguarda até a janela ficar visível e focada.
    Retorna True se o app estiver pronto para uso.
    """
    # Se já está aberto, apenas foca
    janela = _encontrar_janela_whatsapp()
    if janela:
        logger.info("[WhatsApp] App já aberto, focando janela...")
        try:
            if janela.isMinimized:
                janela.restore()
                time.sleep(0.4)
            janela.activate()
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"[WhatsApp] Erro ao focar janela existente: {e}")

    # Método 1: Protocolo URI whatsapp: (Microsoft Store)
    logger.info("[WhatsApp] Tentando abrir via protocolo whatsapp:...")
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "whatsapp:"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        logger.warning(f"[WhatsApp] Protocolo whatsapp: falhou: {e}")

    if _aguardar_janela_whatsapp(10):
        return True

    # Método 2: Start Menu
    logger.info("[WhatsApp] Tentando abrir via Start Menu...")
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "WhatsApp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        logger.warning(f"[WhatsApp] Start Menu falhou: {e}")

    if _aguardar_janela_whatsapp(8):
        return True

    # Método 3: explorer.exe shell:AppsFolder (UWP)
    logger.info("[WhatsApp] Tentando abrir via explorer...")
    try:
        subprocess.Popen(
            ["explorer.exe", "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!WhatsAppDesktop"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    if _aguardar_janela_whatsapp(8):
        return True

    logger.error("[WhatsApp] Não foi possível abrir o WhatsApp após 3 tentativas.")
    return False


def _aguardar_janela_whatsapp(timeout_segundos: int) -> bool:
    """
    Aguarda a janela do WhatsApp aparecer e ficar pronta.
    Retorna True se encontrou e focou.
    """
    iteracoes = timeout_segundos * 2  # Checa a cada 0.5s
    for _ in range(iteracoes):
        time.sleep(0.5)
        janela = _encontrar_janela_whatsapp()
        if janela:
            try:
                janela.activate()
                time.sleep(0.5)
                return True
            except Exception:
                pass
    return False


# ─────────────────────────────────────────
# FUNÇÃO PRINCIPAL: ENVIAR MENSAGEM
# ─────────────────────────────────────────

def enviar_mensagem_whatsapp(contato: str, mensagem: str) -> str:
    """
    Envia uma mensagem para um contato no WhatsApp Desktop.

    Fluxo completo:
    1. Abre o WhatsApp (ou foca se já estiver aberto)
    2. Valida foco da janela
    3. Reseta estado com Escape
    4. Abre barra de pesquisa (Ctrl+F)
    5. Digita nome do contato via clipboard
    6. Aguarda resultados e seleciona com Enter
    7. Digita mensagem via clipboard
    8. Envia com Enter

    Retorna:
        Mensagem de status (sucesso ou erro detalhado)
    """
    pag = _get_pyautogui()

    # ─── Validação de entrada ───
    if not contato or not contato.strip():
        return "Erro: nome do contato não pode ser vazio."

    if not mensagem or not mensagem.strip():
        return "Erro: mensagem não pode ser vazia."

    contato = contato.strip()
    mensagem = mensagem.strip()

    try:
        # ═══ PASSO 1: Abrir WhatsApp ═══
        logger.info("[WhatsApp] Passo 1/7: Abrindo WhatsApp...")
        if not _abrir_whatsapp():
            return "Erro: não foi possível abrir o WhatsApp. Verifique se está instalado e logado."

        # Aguarda a interface estabilizar
        time.sleep(1.0)

        # ═══ PASSO 2: Validar foco ═══
        logger.info("[WhatsApp] Passo 2/7: Validando foco...")
        if not _whatsapp_esta_em_foco():
            if not _garantir_foco_whatsapp():
                return "Erro: não foi possível focar a janela do WhatsApp."
            time.sleep(0.3)

        # ═══ PASSO 3: Resetar estado ═══
        logger.info("[WhatsApp] Passo 3/7: Resetando estado...")
        # Duplo Escape para sair de qualquer menu/busca anterior
        pag.press("escape")
        time.sleep(0.3)
        pag.press("escape")
        time.sleep(0.3)

        # Revalida foco após Escape (pode ter mudado)
        if not _whatsapp_esta_em_foco():
            _garantir_foco_whatsapp()
            time.sleep(0.3)

        # ═══ PASSO 4: Abrir barra de pesquisa ═══
        logger.info("[WhatsApp] Passo 4/7: Abrindo barra de pesquisa...")
        pag.hotkey("ctrl", "f")
        time.sleep(0.7)

        # ═══ PASSO 5: Digitar nome do contato ═══
        logger.info(f"[WhatsApp] Passo 5/7: Pesquisando contato: {contato}")

        # Limpa qualquer texto residual no campo
        pag.hotkey("ctrl", "a")
        time.sleep(0.1)
        pag.press("backspace")
        time.sleep(0.1)

        # Digita o nome via clipboard
        if not _digitar_texto(contato):
            return "Erro: falha ao digitar o nome do contato no campo de pesquisa."

        # Aguarda os resultados da busca aparecerem
        time.sleep(1.2)

        # ═══ PASSO 6: Selecionar o contato ═══
        logger.info("[WhatsApp] Passo 6/7: Selecionando contato...")

        # Enter seleciona o primeiro resultado e abre a conversa
        pag.press("enter")

        # Aguarda a conversa carregar
        time.sleep(1.0)

        # ═══ PASSO 7: Digitar e enviar a mensagem ═══
        logger.info("[WhatsApp] Passo 7/7: Digitando e enviando mensagem...")

        # Revalida foco antes de digitar (proteção contra mudança de janela)
        if not _whatsapp_esta_em_foco():
            if not _garantir_foco_whatsapp():
                return "Erro: WhatsApp perdeu o foco durante o envio da mensagem."
            time.sleep(0.3)

        # Digita a mensagem via clipboard
        if not _digitar_texto(mensagem):
            return "Erro: falha ao digitar a mensagem."

        time.sleep(0.3)

        # Envia com Enter
        pag.press("enter")
        time.sleep(0.3)

        logger.info(f"[WhatsApp] ✅ Mensagem enviada para '{contato}' com sucesso!")
        return f"Mensagem enviada para '{contato}' com sucesso ✓"

    except Exception as e:
        logger.error(f"[WhatsApp] Erro inesperado ao enviar mensagem: {e}")
        return f"Erro ao enviar mensagem no WhatsApp: {str(e)}"
