"""
═══════════════════════════════════════════════════════════════
  JARVIS NOTIFICATION MONITOR v2.0
  Monitoramento de notificações do Windows em tempo real
  ✅ Captura, resume e armazena todas as notificações do sistema
  ✅ Alerta proativo para mensagens de WhatsApp e outros apps
  ✅ Fila de notificações pendentes para leitura por voz
  ✅ Extração inteligente de contato e conteúdo
  ✅ Formatação humanizada para fala natural do JARVIS
═══════════════════════════════════════════════════════════════
"""

import os
import json
import time
import threading
import logging
import subprocess
from datetime import datetime
from collections import deque
from .core import DataStore, agora_brasil_iso, agora_brasil

logger = logging.getLogger(__name__)


def _decode_subprocess_output(data: object) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, (bytes, bytearray)):
        try:
            return bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            return bytes(data).decode("cp1252", errors="replace")
    return str(data)

# ── Store ─────────────────────────────────────────────────────
_notif_store = DataStore("notifications_history", default=[])
_notif_config = DataStore("notifications_config", default={
    "monitorando": False,
    "intervalo_segundos": 5,
    "resumir_automaticamente": True,
    "alertar_mensagens": True,
    "ignorar_apps": ["Windows Security"],
    "ultimo_check": "",
    "apps_prioritarios": ["WhatsApp", "Telegram", "Discord", "Messenger", "Instagram"],
})

# Estado do monitor
_monitor_thread = None
_monitor_ativo = False
_lock = threading.Lock()

# ── Fila de notificações pendentes (para o agente ler em voz alta) ──
_notificacoes_pendentes = deque(maxlen=100)
_pendentes_lock = threading.Lock()

# ── Callback de alerta (será conectado ao agente) ──
_alerta_callback = None


def registrar_callback_alerta(callback):
    """Registra callback para alertas em tempo real."""
    global _alerta_callback
    _alerta_callback = callback


# ═══════════════════════════════════════════════════════════════
#  1. CAPTURA DE NOTIFICAÇÕES (PowerShell)
# ═══════════════════════════════════════════════════════════════

def _capturar_notificacoes_ps() -> list:
    """
    Captura notificações ativas no Action Center do Windows
    usando PowerShell e Windows Runtime API.
    """
    try:
        ps_script = '''
        [Windows.UI.Notifications.Management.UserNotificationListener, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.UI.Notifications.Management.UserNotificationListenerAccessStatus, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null

        $listener = [Windows.UI.Notifications.Management.UserNotificationListener]::Current
        $accessStatus = $listener.RequestAccessAsync().GetAwaiter().GetResult()

        if ($accessStatus -ne [Windows.UI.Notifications.Management.UserNotificationListenerAccessStatus]::Allowed) {
            Write-Output '{"error": "Acesso negado às notificações"}'
            return
        }

        $notifications = $listener.GetNotificationsAsync(
            [Windows.UI.Notifications.NotificationKinds]::Toast
        ).GetAwaiter().GetResult()

        $results = @()
        foreach ($notif in $notifications) {
            try {
                $binding = $notif.Notification.Visual.GetBinding(
                    [Windows.UI.Notifications.KnownNotificationBindings]::ToastGeneric
                )
                $texts = $binding.GetTextElements()
                $title = ""
                $body = ""
                $idx = 0
                foreach ($t in $texts) {
                    if ($idx -eq 0) { $title = $t.Text }
                    else { $body += $t.Text + " " }
                    $idx++
                }
                $results += @{
                    id = $notif.Id.ToString()
                    app = $notif.AppInfo.DisplayInfo.DisplayName
                    title = $title
                    body = $body.Trim()
                    timestamp = $notif.CreationTime.ToString("yyyy-MM-ddTHH:mm:ss")
                }
            } catch {
                continue
            }
        }
        $results | ConvertTo-Json -Depth 3
        '''
        
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=False, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode != 0:
            stderr_txt = _decode_subprocess_output(result.stderr)
            logger.warning(f"PowerShell WinRT falhou: {stderr_txt[:200]}")
            return _capturar_notificacoes_fallback()
        
        output = _decode_subprocess_output(result.stdout).strip()
        if not output or output.startswith('{"error"'):
            return _capturar_notificacoes_fallback()
        
        dados = json.loads(output)
        if isinstance(dados, dict):
            dados = [dados]
        return dados
        
    except subprocess.TimeoutExpired:
        logger.warning("Timeout ao capturar notificações via WinRT")
        return _capturar_notificacoes_fallback()
    except json.JSONDecodeError:
        return _capturar_notificacoes_fallback()
    except Exception as e:
        logger.warning(f"Erro ao capturar notificações: {e}")
        return _capturar_notificacoes_fallback()


def _capturar_notificacoes_fallback() -> list:
    """
    Fallback: captura notificações via Event Log do Windows.
    """
    try:
        ps_script = '''
        try {
            $events = Get-WinEvent -LogName "Microsoft-Windows-PushNotification-Platform/Operational" -MaxEvents 20 -ErrorAction SilentlyContinue |
                Select-Object TimeCreated, Id, Message, ProviderName |
                ForEach-Object {
                    @{
                        id = $_.Id.ToString() + "_" + $_.TimeCreated.ToString("yyyyMMddHHmmss")
                        app = $_.ProviderName
                        title = "Notificação do Sistema"
                        body = if ($_.Message) { $_.Message.Substring(0, [Math]::Min(200, $_.Message.Length)) } else { "" }
                        timestamp = $_.TimeCreated.ToString("yyyy-MM-ddTHH:mm:ss")
                    }
                }
            $events | ConvertTo-Json -Depth 3
        } catch {
            # Fallback to toast history
            $toasts = Get-WinEvent -LogName "Microsoft-Windows-Shell-Notification/Operational" -MaxEvents 15 -ErrorAction SilentlyContinue |
                Select-Object TimeCreated, Message |
                ForEach-Object {
                    @{
                        id = $_.TimeCreated.ToString("yyyyMMddHHmmss")
                        app = "Windows"
                        title = "Notificação"
                        body = if ($_.Message) { $_.Message.Substring(0, [Math]::Min(200, $_.Message.Length)) } else { "Notificação recebida" }
                        timestamp = $_.TimeCreated.ToString("yyyy-MM-ddTHH:mm:ss")
                    }
                }
            if ($toasts) { $toasts | ConvertTo-Json -Depth 3 }
            else { "[]" }
        }
        '''
        
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=False, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        output = _decode_subprocess_output(result.stdout).strip()
        if not output:
            return []
        
        dados = json.loads(output)
        if isinstance(dados, dict):
            dados = [dados]
        return dados
        
    except Exception as e:
        logger.warning(f"Fallback de notificações falhou: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
#  2. PROCESSAMENTO E RESUMO AVANÇADO
# ═══════════════════════════════════════════════════════════════

def _processar_notificacao(notif: dict) -> dict:
    """Processa e enriquece uma notificação capturada."""
    app = notif.get("app", "Desconhecido")
    titulo = notif.get("title", "")
    corpo = notif.get("body", "")
    
    # Categorizar
    categoria = _categorizar_notificacao(app, titulo, corpo)
    
    # Extrair contato (para apps de mensagem)
    contato = _extrair_contato(app, titulo, corpo)
    
    # Gerar resumo
    resumo = _resumir_notificacao(app, titulo, corpo, contato)
    
    # Prioridade
    prioridade = _calcular_prioridade(app, titulo, corpo, categoria)
    
    # Gerar texto para fala natural
    texto_fala = _gerar_texto_fala(app, titulo, corpo, contato, categoria)
    
    return {
        "id": notif.get("id", ""),
        "app": app,
        "titulo": titulo,
        "corpo": corpo,
        "contato": contato,
        "timestamp": notif.get("timestamp", agora_brasil_iso()),
        "categoria": categoria,
        "resumo": resumo,
        "prioridade": prioridade,
        "texto_fala": texto_fala,
        "lida": False,
        "processado_em": agora_brasil_iso(),
    }


def _extrair_contato(app: str, titulo: str, corpo: str) -> str:
    """Extrai nome do contato de notificações de mensageiros."""
    app_lower = app.lower()
    
    # WhatsApp: título geralmente é o nome do contato
    if "whatsapp" in app_lower:
        if titulo and titulo not in ("WhatsApp", "Nova Mensagem", "New Message"):
            # Remove indicadores de grupo (ex: "Grupo: Nome")
            if ":" in titulo and any(g in titulo.lower() for g in ["grupo", "group"]):
                parts = titulo.split(":", 1)
                return parts[1].strip() if len(parts) > 1 else titulo
            return titulo
    
    # Telegram
    elif "telegram" in app_lower:
        if titulo and titulo not in ("Telegram", "Nova Mensagem"):
            return titulo
    
    # Discord
    elif "discord" in app_lower:
        if titulo and titulo not in ("Discord",):
            return titulo
    
    # Instagram
    elif "instagram" in app_lower:
        if titulo and titulo not in ("Instagram",):
            return titulo
    
    # Messenger
    elif "messenger" in app_lower:
        if titulo and titulo not in ("Messenger",):
            return titulo
    
    # Teams
    elif "teams" in app_lower:
        if titulo and titulo not in ("Microsoft Teams",):
            return titulo
    
    return ""


def _categorizar_notificacao(app: str, titulo: str, corpo: str) -> str:
    """Categoriza uma notificação automaticamente."""
    texto = f"{app} {titulo} {corpo}".lower()
    
    if any(w in texto for w in ["whatsapp", "telegram", "discord", "messenger", "teams", "slack", "instagram direct"]):
        return "mensagem"
    elif any(w in texto for w in ["email", "outlook", "gmail", "mail"]):
        return "email"
    elif any(w in texto for w in ["update", "atualização", "download", "install"]):
        return "atualização"
    elif any(w in texto for w in ["alarme", "lembrete", "reminder", "agenda", "calendar"]):
        return "lembrete"
    elif any(w in texto for w in ["segurança", "security", "virus", "ameaça", "threat"]):
        return "segurança"
    elif any(w in texto for w in ["bateria", "battery", "energia", "power"]):
        return "sistema"
    elif any(w in texto for w in ["news", "notícia", "breaking"]):
        return "notícia"
    elif any(w in texto for w in ["spotify", "music", "player", "tocando"]):
        return "mídia"
    elif any(w in texto for w in ["instagram", "facebook", "twitter", "tiktok", "curtiu", "seguiu"]):
        return "rede_social"
    else:
        return "geral"


def _resumir_notificacao(app: str, titulo: str, corpo: str, contato: str = "") -> str:
    """Gera resumo curto da notificação."""
    if contato:
        if corpo:
            return f"[{app}] {contato}: {corpo[:100]}"
        return f"[{app}] Mensagem de {contato}"
    elif titulo and corpo:
        return f"[{app}] {titulo}: {corpo[:100]}"
    elif titulo:
        return f"[{app}] {titulo}"
    elif corpo:
        return f"[{app}] {corpo[:120]}"
    else:
        return f"[{app}] Notificação recebida"


def _calcular_prioridade(app: str, titulo: str, corpo: str, categoria: str) -> str:
    """Calcula prioridade: alta, média, baixa."""
    texto = f"{titulo} {corpo}".lower()
    
    if categoria == "segurança":
        return "alta"
    elif any(w in texto for w in ["urgente", "urgent", "important", "crítico", "critical"]):
        return "alta"
    elif categoria in ("mensagem",):
        return "alta"  # Mensagens são sempre prioridade alta
    elif categoria in ("email",):
        return "média"
    elif categoria == "atualização":
        return "baixa"
    elif categoria == "rede_social":
        return "baixa"
    else:
        return "média"


def _gerar_texto_fala(app: str, titulo: str, corpo: str, contato: str, categoria: str) -> str:
    """
    Gera texto formatado para o JARVIS falar naturalmente.
    Estilo humanizado como um verdadeiro assistente pessoal.
    """
    app_lower = app.lower()
    
    # ── Mensagens de WhatsApp ──
    if "whatsapp" in app_lower:
        if contato and corpo:
            return f"Senhor, chegou uma mensagem do contato {contato} no WhatsApp. A mensagem diz: {corpo[:200]}"
        elif contato:
            return f"Senhor, {contato} enviou uma mensagem no WhatsApp."
        elif corpo:
            return f"Senhor, nova mensagem no WhatsApp: {corpo[:200]}"
        return "Senhor, você recebeu uma nova mensagem no WhatsApp."
    
    # ── Telegram ──
    elif "telegram" in app_lower:
        if contato and corpo:
            return f"Senhor, {contato} lhe enviou uma mensagem no Telegram: {corpo[:200]}"
        elif contato:
            return f"Senhor, {contato} enviou algo no Telegram."
        return "Senhor, nova mensagem no Telegram."
    
    # ── Discord ──
    elif "discord" in app_lower:
        if contato and corpo:
            return f"Senhor, {contato} enviou no Discord: {corpo[:150]}"
        return "Senhor, nova notificação no Discord."
    
    # ── Instagram ──
    elif "instagram" in app_lower:
        if corpo:
            return f"Senhor, notificação do Instagram: {corpo[:150]}"
        return "Senhor, nova notificação do Instagram."
    
    # ── Email ──
    elif categoria == "email":
        if titulo and corpo:
            return f"Senhor, novo email recebido. Assunto: {titulo}. Prévia: {corpo[:100]}"
        elif titulo:
            return f"Senhor, novo email com assunto: {titulo}"
        return "Senhor, você recebeu um novo email."
    
    # ── Lembrete ──
    elif categoria == "lembrete":
        return f"Senhor, lembrete: {titulo or corpo[:150]}"
    
    # ── Segurança ──
    elif categoria == "segurança":
        return f"Senhor, alerta de segurança do {app}: {titulo or corpo[:150]}"
    
    # ── Genérico ──
    else:
        if titulo and corpo:
            return f"Senhor, notificação do {app}: {titulo}. {corpo[:100]}"
        elif titulo:
            return f"Senhor, notificação do {app}: {titulo}"
        elif corpo:
            return f"Senhor, notificação do {app}: {corpo[:150]}"
        return f"Senhor, nova notificação do {app}."


# ═══════════════════════════════════════════════════════════════
#  3. FILA DE NOTIFICAÇÕES PENDENTES
# ═══════════════════════════════════════════════════════════════

def adicionar_pendente(notif_processada: dict):
    """Adiciona notificação à fila de pendentes para leitura."""
    with _pendentes_lock:
        _notificacoes_pendentes.append(notif_processada)


def obter_pendentes() -> list:
    """Retorna e limpa todas as notificações pendentes."""
    with _pendentes_lock:
        pendentes = list(_notificacoes_pendentes)
        _notificacoes_pendentes.clear()
        return pendentes


def tem_pendentes() -> bool:
    """Verifica se há notificações pendentes."""
    with _pendentes_lock:
        return len(_notificacoes_pendentes) > 0


def contar_pendentes() -> int:
    """Conta notificações pendentes."""
    with _pendentes_lock:
        return len(_notificacoes_pendentes)


# ═══════════════════════════════════════════════════════════════
#  4. MONITOR EM BACKGROUND
# ═══════════════════════════════════════════════════════════════

def _monitor_loop():
    """Loop principal do monitor de notificações."""
    global _monitor_ativo
    
    config = _notif_config.load()
    intervalo = config.get("intervalo_segundos", 5)
    ignorar = set(config.get("ignorar_apps", []))
    
    ids_vistos = set()
    
    # Carregar IDs já conhecidos
    historico = _notif_store.load()
    for n in historico[-100:]:
        if n.get("id"):
            ids_vistos.add(n["id"])
    
    logger.info("[NotifMonitor] Monitor de notificações v2.0 iniciado")
    
    while _monitor_ativo:
        try:
            notificacoes = _capturar_notificacoes_ps()
            novas = []
            
            for notif in notificacoes:
                nid = notif.get("id", "")
                app = notif.get("app", "")
                
                if nid in ids_vistos:
                    continue
                if app in ignorar:
                    continue
                
                ids_vistos.add(nid)
                processada = _processar_notificacao(notif)
                novas.append(processada)
                
                # Adicionar à fila de pendentes para leitura por voz
                adicionar_pendente(processada)
            
            if novas:
                historico = _notif_store.load()
                historico.extend(novas)
                
                # Manter últimas 500
                if len(historico) > 500:
                    historico = historico[-500:]
                
                _notif_store.save(historico)
                
                for n in novas:
                    logger.info(f"[NotifMonitor] Nova: {n['resumo']}")
                    
                    # Chamar callback se registrado (para alerta em tempo real)
                    if _alerta_callback and n.get("prioridade") in ("alta", "média"):
                        try:
                            _alerta_callback(n)
                        except Exception as e:
                            logger.warning(f"[NotifMonitor] Callback erro: {e}")
            
            # Atualizar timestamp
            config = _notif_config.load()
            config["ultimo_check"] = agora_brasil_iso()
            _notif_config.save(config)
            
        except Exception as e:
            logger.warning(f"[NotifMonitor] Erro no loop: {e}")
        
        time.sleep(intervalo)
    
    logger.info("[NotifMonitor] Monitor parado")


# ═══════════════════════════════════════════════════════════════
#  5. API PÚBLICA
# ═══════════════════════════════════════════════════════════════

def iniciar_monitor_notificacoes(intervalo: int = 5) -> str:
    """Inicia o monitor de notificações em background."""
    global _monitor_thread, _monitor_ativo
    
    with _lock:
        if _monitor_ativo and _monitor_thread and _monitor_thread.is_alive():
            return "⚠️ Monitor de notificações já está ativo."
        
        config = _notif_config.load()
        config["monitorando"] = True
        config["intervalo_segundos"] = intervalo
        _notif_config.save(config)
        
        _monitor_ativo = True
        _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
        _monitor_thread.start()
        
        return f"✅ Monitor de notificações v2.0 iniciado (intervalo: {intervalo}s)."


def parar_monitor_notificacoes() -> str:
    """Para o monitor de notificações."""
    global _monitor_ativo
    
    with _lock:
        if not _monitor_ativo:
            return "⚠️ Monitor já está parado."
        
        _monitor_ativo = False
        
        config = _notif_config.load()
        config["monitorando"] = False
        _notif_config.save(config)
        
        return "⏹️ Monitor de notificações parado."


def status_monitor_notificacoes() -> str:
    """Retorna status do monitor de notificações."""
    config = _notif_config.load()
    historico = _notif_store.load()
    
    ativo = _monitor_ativo and _monitor_thread and _monitor_thread.is_alive()
    pendentes = contar_pendentes()
    
    # Contar por categoria
    categorias = {}
    for n in historico[-100:]:
        cat = n.get("categoria", "geral")
        categorias[cat] = categorias.get(cat, 0) + 1
    
    # Contar não lidas
    nao_lidas = sum(1 for n in historico[-100:] if not n.get("lida", True))
    
    linhas = [
        f"🔔 **Monitor de Notificações v2.0**\n",
        f"  Status: {'🟢 Ativo' if ativo else '🔴 Parado'}",
        f"  Intervalo: {config.get('intervalo_segundos', 5)}s",
        f"  Último check: {config.get('ultimo_check', 'N/A')}",
        f"  Total capturado: {len(historico)} notificações",
        f"  Pendentes para leitura: {pendentes}",
        f"  Não lidas: {nao_lidas}",
    ]
    
    if categorias:
        linhas.append(f"\n  📊 **Por categoria:**")
        for cat, count in sorted(categorias.items(), key=lambda x: -x[1]):
            linhas.append(f"    • {cat}: {count}")
    
    return "\n".join(linhas)


def ver_notificacoes_recentes(quantidade: int = 10, categoria: str = "") -> str:
    """Mostra notificações recentes com resumos."""
    historico = _notif_store.load()
    
    if categoria:
        historico = [n for n in historico if n.get("categoria") == categoria.lower()]
    
    if not historico:
        return "Nenhuma notificação encontrada."
    
    recentes = historico[-quantidade:]
    recentes.reverse()
    
    linhas = [f"🔔 **Últimas {len(recentes)} notificações:**\n"]
    
    for n in recentes:
        prio = n.get("prioridade", "média")
        prio_emoji = {"alta": "🔴", "média": "🟡", "baixa": "🟢"}.get(prio, "⚪")
        cat = n.get("categoria", "geral")
        contato = n.get("contato", "")
        
        if contato:
            linhas.append(f"  {prio_emoji} [{cat}] **{n.get('app', 'N/A')}** — {contato} — {n.get('timestamp', '')}")
        else:
            linhas.append(f"  {prio_emoji} [{cat}] **{n.get('app', 'N/A')}** — {n.get('timestamp', '')}")
        linhas.append(f"     {n.get('resumo', '')}")
        linhas.append("")
    
    return "\n".join(linhas)


def ler_todas_notificacoes(quantidade: int = 20) -> str:
    """
    Retorna TODAS as notificações formatadas para fala natural.
    Projetado para quando o usuário pede: 'Jarvis, leia todas as notificações'.
    """
    historico = _notif_store.load()
    
    if not historico:
        return "Senhor, não há notificações registradas no momento."
    
    # Pegar pendentes primeiro, depois recentes
    pendentes = obter_pendentes()
    
    if pendentes:
        # Há notificações não lidas na fila
        linhas = []
        
        # Agrupar por app
        por_app = {}
        for n in pendentes:
            app = n.get("app", "Outro")
            por_app.setdefault(app, []).append(n)
        
        total = len(pendentes)
        linhas.append(f"Senhor, você tem {total} notificação{'ões' if total > 1 else ''} pendente{'s' if total > 1 else ''}.")
        
        for app, notifs in por_app.items():
            if len(notifs) > 1:
                linhas.append(f" {len(notifs)} notificações do {app}:")
            for n in notifs:
                linhas.append(f" {n.get('texto_fala', n.get('resumo', ''))}")
        
        # Marcar como lidas no histórico
        _marcar_como_lidas([n.get("id") for n in pendentes])
        
        return " ".join(linhas)
    else:
        # Sem pendentes, ler as mais recentes
        recentes = historico[-quantidade:]
        recentes.reverse()
        
        if not recentes:
            return "Senhor, sem notificações recentes."
        
        linhas = [f"Senhor, aqui estão as últimas {len(recentes)} notificações:"]
        
        for n in recentes:
            texto = n.get("texto_fala", n.get("resumo", ""))
            if texto:
                linhas.append(texto)
        
        return " ".join(linhas)


def ler_notificacoes_pendentes() -> str:
    """
    Lê apenas notificações pendentes (não lidas).
    Retorna texto formatado para fala natural.
    """
    pendentes = obter_pendentes()
    
    if not pendentes:
        return "Senhor, não há notificações pendentes no momento. Tudo tranquilo."
    
    linhas = []
    total = len(pendentes)
    
    # Contagem por tipo
    mensagens = [n for n in pendentes if n.get("categoria") == "mensagem"]
    outras = [n for n in pendentes if n.get("categoria") != "mensagem"]
    
    if mensagens and outras:
        linhas.append(f"Senhor, você tem {len(mensagens)} mensagem{'ns' if len(mensagens) > 1 else ''} e {len(outras)} outra{'s' if len(outras) > 1 else ''} notificação{'ões' if len(outras) > 1 else ''}.")
    elif mensagens:
        linhas.append(f"Senhor, você tem {len(mensagens)} mensagem{'ns' if len(mensagens) > 1 else ''} nova{'s' if len(mensagens) > 1 else ''}.")
    else:
        linhas.append(f"Senhor, você tem {total} notificação{'ões' if total > 1 else ''} pendente{'s' if total > 1 else ''}.")
    
    # Mensagens primeiro (prioridade)
    for n in mensagens:
        linhas.append(n.get("texto_fala", n.get("resumo", "")))
    
    # Depois as outras
    for n in outras:
        linhas.append(n.get("texto_fala", n.get("resumo", "")))
    
    # Marcar como lidas
    _marcar_como_lidas([n.get("id") for n in pendentes])
    
    return " ".join(linhas)


def verificar_novas_notificacoes() -> str:
    """
    Verifica se há novas notificações e retorna resumo rápido.
    Usado pelo agente para check proativo periódico.
    """
    n_pendentes = contar_pendentes()
    
    if n_pendentes == 0:
        return ""  # Retorna vazio = sem novidades
    
    # Peek sem remover
    with _pendentes_lock:
        pendentes = list(_notificacoes_pendentes)
    
    mensagens = [n for n in pendentes if n.get("categoria") == "mensagem"]
    
    if mensagens:
        contatos = list(set(n.get("contato", "alguém") for n in mensagens if n.get("contato")))
        if contatos:
            return f"Senhor, {len(mensagens)} mensagem{'ns' if len(mensagens) > 1 else ''} nova{'s' if len(mensagens) > 1 else ''} de {', '.join(contatos[:3])}."
        return f"Senhor, {len(mensagens)} mensagem{'ns' if len(mensagens) > 1 else ''} nova{'s' if len(mensagens) > 1 else ''}."
    
    return f"Senhor, {n_pendentes} notificação{'ões' if n_pendentes > 1 else ''} nova{'s' if n_pendentes > 1 else ''}."


def _marcar_como_lidas(ids: list):
    """Marca notificações como lidas no histórico."""
    try:
        historico = _notif_store.load()
        ids_set = set(ids)
        for n in historico:
            if n.get("id") in ids_set:
                n["lida"] = True
        _notif_store.save(historico)
    except Exception as e:
        logger.warning(f"[NotifMonitor] Erro ao marcar como lidas: {e}")


def capturar_notificacoes_agora() -> str:
    """Captura notificações instantaneamente (sem monitor ativo)."""
    notificacoes = _capturar_notificacoes_ps()
    
    if not notificacoes:
        return "📭 Nenhuma notificação ativa no momento."
    
    processadas = [_processar_notificacao(n) for n in notificacoes]
    
    # Salvar
    historico = _notif_store.load()
    ids_existentes = {n.get("id") for n in historico}
    novas = [p for p in processadas if p.get("id") not in ids_existentes]
    
    if novas:
        historico.extend(novas)
        if len(historico) > 500:
            historico = historico[-500:]
        _notif_store.save(historico)
        
        # Adicionar à fila de pendentes
        for n in novas:
            adicionar_pendente(n)
    
    linhas = [f"🔔 **{len(processadas)} notificação(ões) capturada(s):**\n"]
    
    for n in processadas:
        prio_emoji = {"alta": "🔴", "média": "🟡", "baixa": "🟢"}.get(
            n.get("prioridade", "média"), "⚪"
        )
        contato = n.get("contato", "")
        info_contato = f" de {contato}" if contato else ""
        linhas.append(f"  {prio_emoji} [{n['categoria']}] **{n['app']}**{info_contato}")
        linhas.append(f"     {n['resumo']}")
        linhas.append("")
    
    return "\n".join(linhas)


def limpar_historico_notificacoes() -> str:
    """Limpa o histórico de notificações."""
    _notif_store.save([])
    with _pendentes_lock:
        _notificacoes_pendentes.clear()
    return "✅ Histórico de notificações limpo."


def configurar_monitor_notificacoes(
    intervalo: int = None,
    ignorar_app: str = None,
    remover_ignorar: str = None,
) -> str:
    """Configura o monitor de notificações."""
    config = _notif_config.load()
    
    alteracoes = []
    
    if intervalo is not None:
        config["intervalo_segundos"] = max(2, min(300, intervalo))
        alteracoes.append(f"Intervalo: {config['intervalo_segundos']}s")
    
    if ignorar_app:
        if ignorar_app not in config.get("ignorar_apps", []):
            config.setdefault("ignorar_apps", []).append(ignorar_app)
            alteracoes.append(f"Ignorando: {ignorar_app}")
    
    if remover_ignorar:
        apps = config.get("ignorar_apps", [])
        if remover_ignorar in apps:
            apps.remove(remover_ignorar)
            alteracoes.append(f"Removido do ignore: {remover_ignorar}")
    
    _notif_config.save(config)
    
    if alteracoes:
        return f"✅ Configuração atualizada: {', '.join(alteracoes)}"
    return "Nenhuma alteração feita."
