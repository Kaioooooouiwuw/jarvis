"""
═══════════════════════════════════════════════════════════════
  [30] linha_do_tempo  +  [31] aprender_com_erros
═══════════════════════════════════════════════════════════════

Timeline unificada — registra TUDO que o Jarvis faz, incluindo
erros e soluções aprendidas. Nunca repete o mesmo erro.

Funcionalidades:
  • Registrar evento genérico (ação, decisão, erro, sistema)
  • Consultar por período (hoje, ontem, semana, data, tudo)
  • Registrar erros com contexto + solução
  • Sugerir correção baseada em erros similares
  • Estatísticas de produtividade por período
"""

from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from collections import Counter
from .core import DataStore, barra_progresso, periodo_do_dia, event_bus, agora_brasil_iso, agora_brasil


# ── Stores ────────────────────────────────────────────────────
_timeline = DataStore("timeline", default=[])
_erros = DataStore("erros_aprendidos", default=[])


# ═══════════════════════════════════════════════════════════════
#  TIMELINE — Registro & Consulta
# ═══════════════════════════════════════════════════════════════

def registrar_evento(tipo: str, descricao: str, detalhes: str = "") -> str:
    """
    Registra evento na timeline global.

    tipo: sistema | acao | dev | web | foco | rotina | autonomo | erro | objetivo
    """
    dados = _timeline.load()
    evento = {
        "id": len(dados) + 1,
        "timestamp": agora_brasil_iso(),
        "tipo": tipo,
        "descricao": descricao,
        "detalhes": detalhes,
        "periodo": periodo_do_dia(),
    }
    dados.append(evento)

    # Mantém últimos 2000 eventos para não crescer infinitamente
    if len(dados) > 2000:
        dados = dados[-2000:]

    _timeline.save(dados)
    event_bus.publish("evento_registrado", evento)
    return f"[{tipo}] {descricao}"


def consultar_timeline(periodo: str = "hoje") -> str:
    """
    Consulta timeline.

    periodo: hoje | ontem | semana | mes | tudo | YYYY-MM-DD
    """
    dados = _timeline.load()
    if not dados:
        return "📅 A linha do tempo está vazia."

    agora = agora_brasil()
    fim = agora

    if periodo == "hoje":
        inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "ontem":
        inicio = (agora - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        fim = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        inicio = (agora - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "mes":
        inicio = (agora - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "tudo":
        inicio = datetime.min
    else:
        try:
            inicio = datetime.fromisoformat(periodo)
        except ValueError:
            inicio = datetime.min

    filtrados = []
    for e in dados:
        try:
            ts = datetime.fromisoformat(e["timestamp"])
            if inicio <= ts <= fim:
                filtrados.append(e)
        except (ValueError, KeyError):
            continue

    if not filtrados:
        return f"📅 Nenhum evento para '{periodo}'."

    # Header com estatísticas
    tipos = Counter(e["tipo"] for e in filtrados)
    linhas = [
        f"📅 **Linha do Tempo — {periodo.upper()}** ({len(filtrados)} eventos)\n",
        f"📊 Distribuição: {' · '.join(f'{t}({c})' for t, c in tipos.most_common(5))}\n",
    ]

    # Agrupa por hora
    for e in filtrados[-40:]:
        ts = datetime.fromisoformat(e["timestamp"]).strftime("%H:%M")
        emoji = _emoji_tipo(e["tipo"])
        linhas.append(f"  {emoji} [{ts}] {e['descricao']}")
        if e.get("detalhes"):
            linhas.append(f"        ↳ {e['detalhes']}")

    if len(filtrados) > 40:
        linhas.append(f"\n  … +{len(filtrados) - 40} eventos anteriores")

    return "\n".join(linhas)


def estatisticas_timeline() -> str:
    """Estatísticas gerais da atividade."""
    dados = _timeline.load()
    if not dados:
        return "Sem dados suficientes."

    total = len(dados)
    tipos = Counter(e["tipo"] for e in dados)
    periodos = Counter(e.get("periodo", "?") for e in dados)

    melhor_periodo = periodos.most_common(1)[0][0] if periodos else "?"

    linhas = [
        "📊 **Estatísticas Globais**\n",
        f"  📌 Total de eventos: {total}",
        f"  🏆 Período mais ativo: {melhor_periodo}",
        f"\n  🎯 Por tipo:",
    ]
    for tipo, count in tipos.most_common(10):
        linhas.append(f"    {_emoji_tipo(tipo)} {tipo}: {count}")

    return "\n".join(linhas)


def ultimos_eventos(n: int = 10) -> list:
    """Retorna últimos N eventos como lista de dicts."""
    return _timeline.load()[-n:]


# ═══════════════════════════════════════════════════════════════
#  APRENDIZADO COM ERROS — Nunca erra duas vezes
# ═══════════════════════════════════════════════════════════════

def registrar_erro(contexto: str, erro: str, solucao: str = "") -> str:
    """
    Registra erro com contexto e solução.

    Se um erro similar (>85% match) já existir, incrementa ocorrências
    e atualiza a solução se for diferente.
    """
    dados = _erros.load()

    # Busca duplicata
    for item in dados:
        if _similaridade(item["erro"], erro) > 0.85:
            item["ocorrencias"] = item.get("ocorrencias", 1) + 1
            item["ultima_ocorrencia"] = agora_brasil_iso()
            if solucao and item.get("solucao") != solucao:
                item["solucao"] = solucao
                _erros.save(dados)
                return f"⚠️ Erro já conhecido — solução ATUALIZADA. Ocorrências: {item['ocorrencias']}"
            _erros.save(dados)
            return f"⚠️ Erro já registrado. Ocorrências: {item['ocorrencias']}"

    novo = {
        "id": len(dados) + 1,
        "timestamp": agora_brasil_iso(),
        "contexto": contexto,
        "erro": erro,
        "solucao": solucao,
        "ocorrencias": 1,
        "ultima_ocorrencia": agora_brasil_iso(),
    }
    dados.append(novo)
    _erros.save(dados)

    registrar_evento("erro", f"Erro aprendido: {erro[:80]}", contexto)
    return f"🧠 Erro registrado e aprendido. Contexto: {contexto}"


def sugerir_correcao(erro: str) -> str:
    """Busca erro similar no histórico e sugere a solução."""
    dados = _erros.load()
    melhor, score = None, 0.0

    for item in dados:
        s = _similaridade(item["erro"], erro)
        if s > score:
            score, melhor = s, item

    if melhor and score > 0.5:
        return (
            f"🧠 **Erro similar encontrado** (match: {score:.0%})\n"
            f"  Contexto: {melhor['contexto']}\n"
            f"  Erro: {melhor['erro']}\n"
            f"  Solução: {melhor.get('solucao', 'Nenhuma registrada')}\n"
            f"  Ocorrências: {melhor.get('ocorrencias', 1)}"
        )
    return "🆕 Erro novo — nenhuma solução conhecida no banco."


def consultar_erros(contexto: str = "") -> str:
    """Lista erros, opcionalmente filtrados."""
    dados = _erros.load()
    if not dados:
        return "✅ Nenhum erro registrado."

    if contexto:
        dados = [
            e for e in dados
            if _similaridade(e.get("contexto", ""), contexto) > 0.4
            or contexto.lower() in e.get("erro", "").lower()
        ]

    if not dados:
        return f"Nenhum erro relacionado a '{contexto}'."

    linhas = [f"📋 **Erros Aprendidos ({len(dados)}):**\n"]
    for e in dados[-15:]:
        linhas.append(f"  #{e['id']} [{e['contexto']}]")
        linhas.append(f"     ❌ {e['erro']}")
        linhas.append(f"     ✅ {e.get('solucao', '—')}")
        linhas.append(f"     🔁 {e.get('ocorrencias', 1)}x\n")

    return "\n".join(linhas)


# ── Helpers privados ──────────────────────────────────────────

def _similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _emoji_tipo(tipo: str) -> str:
    mapa = {
        "sistema": "🔧", "acao": "⚡", "dev": "💻", "web": "🌐",
        "foco": "🎯", "rotina": "📋", "autonomo": "🤖", "erro": "❌",
        "objetivo": "🏆", "conhecimento": "🧠", "multi_etapas": "🔗",
        "gestos": "🖐️",
    }
    return mapa.get(tipo, "📌")
