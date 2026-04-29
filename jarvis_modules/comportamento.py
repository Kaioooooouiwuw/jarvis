"""
═══════════════════════════════════════════════════════════════
  [26] analisar_comportamento_usuario
  [27] prever_acao_usuario
  [28] sugestao_inteligente_contextual
═══════════════════════════════════════════════════════════════

Motor de inteligência comportamental — analisa padrões reais,
prevê próximas ações e sugere contextualmente com base em
dados acumulados + timeline + horário + dia da semana.

Algoritmos:
  • Frequency-weighted action ranking
  • Time-of-day pattern detection
  • Day-of-week affinity scoring
  • Context-aware suggestion engine
  • Streak detection (consistência)
"""

from datetime import datetime, timezone
from .core import agora_brasil, timedelta
from collections import Counter, defaultdict
from .core import DataStore, barra_progresso, periodo_do_dia, saudacao, event_bus


# ── Store ─────────────────────────────────────────────────────
_store = DataStore("comportamento", default={
    "sessoes": [],
    "acoes": {},
    "horarios": {},
    "dias_semana": {},
    "projetos_recentes": [],
    "padroes": [],
    "streaks": {},
})

_timeline_store = DataStore("timeline", default=[])


# ═══════════════════════════════════════════════════════════════
#  Registro de dados (chamado internamente)
# ═══════════════════════════════════════════════════════════════

def registrar_sessao(hora_inicio: str = None):
    """Registra início de sessão."""
    dados = _store.load()
    agora = agora_brasil()
    hora = agora.hour
    dia = agora.strftime("%A")

    # Garantir que todas as chaves existam (dados legados podem não ter)
    dados.setdefault("sessoes", [])
    dados.setdefault("acoes", {})
    dados.setdefault("horarios", {})
    dados.setdefault("dias_semana", {})
    dados.setdefault("projetos_recentes", [])
    dados.setdefault("padroes", [])
    dados.setdefault("streaks", {})

    dados["sessoes"].append({
        "inicio": hora_inicio or agora.isoformat(),
        "hora": hora,
        "dia_semana": dia,
        "data": agora.strftime("%Y-%m-%d"),
    })

    # Contadores
    h_str = str(hora)
    dados["horarios"][h_str] = dados["horarios"].get(h_str, 0) + 1
    dados["dias_semana"][dia] = dados["dias_semana"].get(dia, 0) + 1

    # Streak de dias consecutivos
    hoje_str = agora.strftime("%Y-%m-%d")
    streaks = dados.get("streaks", {})
    ultimo_dia = streaks.get("ultimo_dia", "")
    if ultimo_dia == hoje_str:
        pass  # Já registrado hoje
    elif ultimo_dia == (agora - timedelta(days=1)).strftime("%Y-%m-%d"):
        streaks["atual"] = streaks.get("atual", 1) + 1
        streaks["recorde"] = max(streaks.get("recorde", 0), streaks["atual"])
    else:
        streaks["atual"] = 1
    streaks["ultimo_dia"] = hoje_str
    dados["streaks"] = streaks

    # Limita sessões
    if len(dados["sessoes"]) > 200:
        dados["sessoes"] = dados["sessoes"][-200:]

    _store.save(dados)


def registrar_acao(acao: str, contexto: str = ""):
    """Registra uma ação para análise estatística."""
    dados = _store.load()

    # Incrementa contagem
    dados["acoes"][acao] = dados["acoes"].get(acao, 0) + 1

    # Projetos recentes
    acoes_dev = {"abrir_projeto", "gerar_projeto", "debug", "refatorar"}
    if any(a in acao.lower() for a in acoes_dev) and contexto:
        projs = dados.get("projetos_recentes", [])
        if contexto in projs:
            projs.remove(contexto)
        projs.insert(0, contexto)
        dados["projetos_recentes"] = projs[:15]

    _store.save(dados)


# ═══════════════════════════════════════════════════════════════
#  [26] Análise de Comportamento
# ═══════════════════════════════════════════════════════════════

def analisar_comportamento() -> str:
    """
    Análise profunda: horários produtivos, hábitos, rotinas reais,
    consistência (streaks), distribuição por tipo.
    """
    dados = _store.load()
    timeline = _timeline_store.load()

    if not dados["sessoes"] and not timeline:
        return (
            "📊 Ainda não tenho dados suficientes para analisar seu comportamento.\n"
            "Continue usando e eu aprendo seus padrões automaticamente!"
        )

    analise = ["🧠 **Análise Comportamental Avançada**\n"]

    # ── 1. Streak de consistência ─────────────────────────────
    streaks = dados.get("streaks", {})
    if streaks.get("atual", 0) > 0:
        analise.append(f"🔥 **Streak atual:** {streaks['atual']} dia(s) consecutivos")
        if streaks.get("recorde", 0) > 1:
            analise.append(f"🏆 **Recorde:** {streaks['recorde']} dias")
        analise.append("")

    # ── 2. Horários mais ativos ───────────────────────────────
    if dados["horarios"]:
        top_horas = sorted(dados["horarios"].items(), key=lambda x: x[1], reverse=True)[:5]
        analise.append("⏰ **Horários mais ativos:**")
        for hora, count in top_horas:
            h = int(hora)
            per = "manhã" if 6 <= h < 12 else "tarde" if 12 <= h < 18 else "noite" if 18 <= h < 23 else "madrugada"
            analise.append(f"  ↳ {h:02d}:00 ({per}) — {count} sessões")
        analise.append("")

    # ── 3. Dias da semana ─────────────────────────────────────
    if dados.get("dias_semana"):
        top_dias = sorted(dados["dias_semana"].items(), key=lambda x: x[1], reverse=True)[:3]
        analise.append("📆 **Dias mais ativos:**")
        for dia, count in top_dias:
            analise.append(f"  ↳ {dia}: {count} sessões")
        analise.append("")

    # ── 4. Ações mais frequentes ──────────────────────────────
    if dados["acoes"]:
        top_acoes = sorted(dados["acoes"].items(), key=lambda x: x[1], reverse=True)[:8]
        analise.append("🎯 **Ações mais frequentes:**")
        for acao, count in top_acoes:
            analise.append(f"  ↳ {acao}: {count}×")
        analise.append("")

    # ── 5. Projetos recentes ──────────────────────────────────
    if dados.get("projetos_recentes"):
        analise.append("💻 **Projetos recentes:**")
        for p in dados["projetos_recentes"][:5]:
            analise.append(f"  ↳ {p}")
        analise.append("")

    # ── 6. Produtividade da timeline ──────────────────────────
    if timeline:
        periodos = {"manhã": 0, "tarde": 0, "noite": 0, "madrugada": 0}
        for e in timeline:
            per = e.get("periodo")
            if per in periodos:
                periodos[per] += 1

        if any(v > 0 for v in periodos.values()):
            melhor = max(periodos, key=periodos.get)
            total = sum(periodos.values())
            analise.append("📊 **Produtividade por período:**")
            for per, count in sorted(periodos.items(), key=lambda x: x[1], reverse=True):
                pct = count / total * 100 if total > 0 else 0
                analise.append(f"  ↳ {per}: {barra_progresso(pct, 10)} ({count} ações)")
            analise.append(f"\n🏆 **Período mais produtivo:** {melhor}")

    # ── 7. Padrões detectados ─────────────────────────────────
    padroes = _detectar_padroes(dados, timeline)
    if padroes:
        analise.append("\n🔮 **Padrões detectados:**")
        for p in padroes:
            analise.append(f"  → {p}")

    return "\n".join(analise)


# ═══════════════════════════════════════════════════════════════
#  [27] Previsão de Ação
# ═══════════════════════════════════════════════════════════════

def prever_acao() -> str:
    """Prevê o que o usuário provavelmente vai fazer com base em padrões."""
    dados = _store.load()
    agora = agora_brasil()
    hora = agora.hour
    dia = agora.strftime("%A")

    previsoes = []

    # Baseado na hora atual + histórico
    if dados["acoes"]:
        top_acao = max(dados["acoes"], key=dados["acoes"].get)
        count = dados["acoes"][top_acao]
        previsoes.append(f"📊 Sua ação mais frequente é **{top_acao}** ({count}×). Quer que eu execute?")

    if dados.get("projetos_recentes"):
        projeto = dados["projetos_recentes"][0]
        previsoes.append(f"💻 Quer continuar no projeto **{projeto}**?")

    # Contexto horário
    sugestoes_hora = {
        range(6, 9): "☀️ Início do dia! Quer que eu organize suas tarefas?",
        range(9, 12): "🚀 Pico de produtividade! Quer ativar modo foco?",
        range(12, 14): "🍽️ Horário de pausa. Quer algo relaxante no YouTube?",
        range(14, 18): "💪 Tarde produtiva! Quer revisar pendências?",
        range(18, 22): "🌆 Fim do dia. Quer um resumo do que fez hoje?",
        range(22, 24): "🌙 Hora de descansar. Quer que eu finalize tudo?",
        range(0, 6): "🦉 Madrugada? Cuide-se! Quer que eu monitore seu tempo?",
    }
    for faixa, msg in sugestoes_hora.items():
        if hora in faixa:
            previsoes.append(msg)
            break

    # Streak motivacional
    streaks = dados.get("streaks", {})
    if streaks.get("atual", 0) >= 3:
        previsoes.append(f"🔥 {streaks['atual']} dias consecutivos! Mantenha o ritmo!")

    if not previsoes:
        return "🔮 Ainda aprendendo seus padrões. Continue usando normalmente!"

    return "🔮 **Previsões Inteligentes:**\n\n" + "\n".join(f"  → {p}" for p in previsoes)


# ═══════════════════════════════════════════════════════════════
#  [28] Sugestão Contextual
# ═══════════════════════════════════════════════════════════════

def sugestao_contextual(atividade_atual: str = "") -> str:
    """Sugere ações baseadas na atividade atual + dados históricos."""
    ativ = atividade_atual.lower()
    sugestoes = []

    # Mapa de contexto → sugestões
    contextos = {
        ("youtube", "video", "vídeo", "música", "musica"): [
            "🎥 Quer que eu resuma esse vídeo?",
            "📝 Quer salvar como anotação?",
            "🔍 Quer conteúdo relacionado?",
            "⏲️ Quer que eu cronometre seu tempo?",
        ],
        ("vscode", "código", "codigo", "programando", "dev"): [
            "🔍 Quer que eu analise o código?",
            "📈 Quer sugestões de melhoria?",
            "🧪 Quer que eu crie testes?",
            "📄 Quer que eu documente?",
            "🐛 Quer rodar debug autônomo?",
        ],
        ("chrome", "browser", "navegando", "site"): [
            "📖 Quer que eu resuma essa página?",
            "📊 Quer extrair dados?",
            "💾 Quer salvar como nota?",
            "👁️ Quer monitorar mudanças?",
        ],
        ("projeto", "repositorio", "github"): [
            "📁 Quer analisar a estrutura?",
            "📝 Quer um README automático?",
            "🐛 Quer debug geral?",
            "♻️ Quer refatorar?",
        ],
        ("estudando", "estudo", "aprendendo", "curso"): [
            "📋 Quer flashcards do conteúdo?",
            "📝 Quer um resumo?",
            "🎯 Quer ativar modo foco?",
            "🧠 Quer salvar no conhecimento?",
        ],
        ("reunião", "reuniao", "call", "meeting"): [
            "📋 Quer que eu inicie uma ata?",
            "⏱️ Quer controlar o tempo?",
            "📝 Quer resumir depois?",
        ],
    }

    for keywords, sug in contextos.items():
        if any(k in ativ for k in keywords):
            sugestoes = sug
            break

    if not sugestoes:
        dados = _store.load()
        hora = agora_brasil().hour
        if dados.get("projetos_recentes"):
            sugestoes.append(f"💻 Quer abrir **{dados['projetos_recentes'][0]}**?")
        if 9 <= hora < 18:
            sugestoes.append("🎯 Quer ativar modo foco?")
        sugestoes.append("📅 Quer organizar seu dia?")
        sugestoes.append("🧠 Quer ver sua análise de comportamento?")

    return "💡 **Sugestões Contextuais:**\n\n" + "\n".join(f"  → {s}" for s in sugestoes)


# ═══════════════════════════════════════════════════════════════
#  Detecção automática de padrões
# ═══════════════════════════════════════════════════════════════

def _detectar_padroes(dados: dict, timeline: list) -> list:
    """Detecta padrões reais a partir dos dados acumulados."""
    padroes = []

    # Padrão de horário
    horarios = dados.get("horarios", {})
    if horarios:
        horas_ativas = [int(h) for h, c in horarios.items() if c >= 3]
        noturno = sum(1 for h in horas_ativas if h >= 22 or h < 6)
        diurno = sum(1 for h in horas_ativas if 8 <= h < 18)
        if noturno > diurno:
            padroes.append("🦉 Você é notoriamente noturno — mais ativo após as 22h")
        elif diurno > noturno:
            padroes.append("☀️ Perfil diurno — pico de atividade entre 8h-18h")

    # Padrão de consistência
    streaks = dados.get("streaks", {})
    if streaks.get("recorde", 0) >= 7:
        padroes.append(f"📈 Alta consistência — recorde de {streaks['recorde']} dias seguidos")

    # Padrão de foco em projetos
    projs = dados.get("projetos_recentes", [])
    if len(projs) == 1:
        padroes.append(f"🎯 Foco intenso em um único projeto: {projs[0]}")
    elif len(projs) > 5:
        padroes.append("🔀 Multitarefas — trabalhando em vários projetos simultaneamente")

    # Padrão de ações
    acoes = dados.get("acoes", {})
    if acoes:
        total = sum(acoes.values())
        for acao, count in acoes.items():
            if count / total > 0.4:
                padroes.append(f"⚡ Uso intenso de '{acao}' ({count / total:.0%} das ações)")

    return padroes
