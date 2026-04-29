"""
═══════════════════════════════════════════════════════════════
  [54] sistema_de_objetivos
═══════════════════════════════════════════════════════════════

Objetivos de longo prazo com plano evolutivo.
Define → planeja → executa → aprende → evolui estratégia.
"""

from datetime import datetime, timedelta, timezone
from .core import agora_brasil, agora_brasil_iso
from .core import DataStore, barra_progresso, agora_iso


# ── Store ─────────────────────────────────────────────────────
_store = DataStore("objetivos", default={"objetivos": []})


# ═══════════════════════════════════════════════════════════════
#  API Pública
# ═══════════════════════════════════════════════════════════════

def definir_objetivo(objetivo: str, prazo_dias: int = 90) -> str:
    """Define objetivo de longo prazo com plano auto-gerado."""
    dados = _store.load()
    plano = _gerar_plano(objetivo)

    novo = {
        "id": len(dados["objetivos"]) + 1,
        "objetivo": objetivo,
        "criado_em": agora_iso(),
        "prazo": (agora_brasil() + timedelta(days=prazo_dias)).isoformat(),
        "prazo_dias": prazo_dias,
        "plano": plano,
        "progresso": 0,
        "aprendizados": [],
        "evolucoes": [],
        "ativo": True,
    }
    dados["objetivos"].append(novo)
    _store.save(dados)

    linhas = [
        "🎯 **Objetivo Definido!**\n",
        f"📌 **{objetivo}**",
        f"📅 Prazo: {prazo_dias} dias ({(agora_brasil() + timedelta(days=prazo_dias)).strftime('%d/%m/%Y')})",
        f"\n📋 **Plano ({len(plano)} etapas):**\n",
    ]
    for i, e in enumerate(plano, 1):
        linhas.append(f"  {i}. {e['etapa']} (prazo: {e['prazo']})")
    linhas.append("\n💪 Vamos nessa! Vou te cobrar periodicamente.")

    return "\n".join(linhas)


def listar_objetivos() -> str:
    """Lista todos os objetivos."""
    dados = _store.load()
    objs = dados.get("objetivos", [])
    if not objs:
        return "🎯 Nenhum objetivo definido. Diga: 'Jarvis, meu objetivo é…'"

    linhas = [f"🎯 **Seus Objetivos ({len(objs)}):**\n"]
    for o in objs:
        status = "🟢" if o.get("ativo") else "✅"
        pct = o.get("progresso", 0)
        linhas.append(f"  {status} #{o['id']} — {o['objetivo']}")
        linhas.append(f"     {barra_progresso(pct)}")

        # Dias restantes
        if o.get("ativo"):
            try:
                prazo = datetime.fromisoformat(o["prazo"])
                dias_rest = max(0, (prazo - agora_brasil()).days)
                linhas.append(f"     📅 {dias_rest} dias restantes")
            except (ValueError, KeyError):
                pass
        linhas.append("")

    return "\n".join(linhas)


def atualizar_progresso(objetivo_id: int, etapa_idx: int, resultado: str = "") -> str:
    """Marca etapa como concluída."""
    dados = _store.load()
    for o in dados["objetivos"]:
        if o["id"] == objetivo_id:
            if 0 <= etapa_idx < len(o["plano"]):
                o["plano"][etapa_idx]["status"] = "concluido"
                o["plano"][etapa_idx]["resultado"] = resultado
                o["plano"][etapa_idx]["concluida_em"] = agora_iso()

                concluidas = sum(1 for e in o["plano"] if e["status"] == "concluido")
                o["progresso"] = int(concluidas / len(o["plano"]) * 100)

                if o["progresso"] >= 100:
                    o["ativo"] = False
                    o["concluido_em"] = agora_iso()
                    _store.save(dados)
                    return f"🏆 **Objetivo CONCLUÍDO!** '{o['objetivo']}' — Parabéns!"

                _store.save(dados)
                return f"✅ Etapa concluída! Progresso: {barra_progresso(o['progresso'])}"
    return "Objetivo ou etapa não encontrado."


def registrar_aprendizado(objetivo_id: int, aprendizado: str) -> str:
    """Registra algo aprendido durante a busca do objetivo."""
    dados = _store.load()
    for o in dados["objetivos"]:
        if o["id"] == objetivo_id:
            o.setdefault("aprendizados", []).append({
                "texto": aprendizado,
                "data": agora_iso(),
            })
            _store.save(dados)
            return f"📝 Aprendizado registrado no objetivo #{objetivo_id}."
    return "Objetivo não encontrado."


def evoluir_estrategia(objetivo_id: int, nova_abordagem: str) -> str:
    """Registra evolução de estratégia para um objetivo."""
    dados = _store.load()
    for o in dados["objetivos"]:
        if o["id"] == objetivo_id:
            o.setdefault("evolucoes", []).append({
                "abordagem": nova_abordagem,
                "data": agora_iso(),
            })
            _store.save(dados)
            return f"🔄 Estratégia evoluída para objetivo #{objetivo_id}: {nova_abordagem}"
    return "Objetivo não encontrado."


def gerar_relatorio_objetivo(objetivo_id: int) -> str:
    """Relatório completo de um objetivo."""
    dados = _store.load()
    o = next((x for x in dados["objetivos"] if x["id"] == objetivo_id), None)
    if not o:
        return "Objetivo não encontrado."

    dias = (agora_brasil() - datetime.fromisoformat(o["criado_em"])).days
    etapas = o.get("plano", [])
    concluidas = sum(1 for e in etapas if e["status"] == "concluido")

    linhas = [
        f"📈 **Relatório:** {o['objetivo']}\n",
        f"📅 Dias: {dias}/{o.get('prazo_dias', 90)}",
        f"📊 Progresso: {barra_progresso(o.get('progresso', 0))}",
        f"✅ Etapas: {concluidas}/{len(etapas)}\n",
        "📋 **Etapas:**",
    ]
    for i, e in enumerate(etapas):
        ck = "✅" if e["status"] == "concluido" else "⬜"
        linhas.append(f"  {ck} {i + 1}. {e['etapa']}")
        if e.get("resultado"):
            linhas.append(f"       ↳ {e['resultado']}")

    aprendizados = o.get("aprendizados", [])
    if aprendizados:
        linhas.append(f"\n🧠 **Aprendizados ({len(aprendizados)}):**")
        for a in aprendizados[-5:]:
            linhas.append(f"  ↳ {a['texto']}")

    evolucoes = o.get("evolucoes", [])
    if evolucoes:
        linhas.append(f"\n🔄 **Evoluções de estratégia ({len(evolucoes)}):**")
        for ev in evolucoes[-3:]:
            linhas.append(f"  ↳ {ev['abordagem']}")

    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════
#  Gerador de planos
# ═══════════════════════════════════════════════════════════════

def _gerar_plano(objetivo: str) -> list:
    obj = objetivo.lower()

    templates = {
        ("dinheiro", "renda", "ganhar", "financeiro", "freelance", "negócio"): [
            {"etapa": "Definir nicho e habilidades", "prazo": "3 dias", "status": "pendente"},
            {"etapa": "Criar portfólio profissional", "prazo": "7 dias", "status": "pendente"},
            {"etapa": "Cadastrar em plataformas", "prazo": "3 dias", "status": "pendente"},
            {"etapa": "Prospectar primeiros clientes", "prazo": "14 dias", "status": "pendente"},
            {"etapa": "Entregar primeiro projeto", "prazo": "7 dias", "status": "pendente"},
            {"etapa": "Escalar e automatizar", "prazo": "30 dias", "status": "pendente"},
        ],
        ("design", "ui", "interface", "figma", "canva"): [
            {"etapa": "Estudar fundamentos de design", "prazo": "7 dias", "status": "pendente"},
            {"etapa": "Dominar ferramenta (Figma/Canva)", "prazo": "14 dias", "status": "pendente"},
            {"etapa": "Criar 5 projetos práticos", "prazo": "21 dias", "status": "pendente"},
            {"etapa": "Montar portfólio online", "prazo": "7 dias", "status": "pendente"},
            {"etapa": "Buscar clientes/vagas", "prazo": "14 dias", "status": "pendente"},
        ],
        ("programar", "programação", "dev", "código", "python", "javascript"): [
            {"etapa": "Definir linguagem/stack", "prazo": "1 dia", "status": "pendente"},
            {"etapa": "Completar tutorial base", "prazo": "14 dias", "status": "pendente"},
            {"etapa": "Construir 3 projetos", "prazo": "30 dias", "status": "pendente"},
            {"etapa": "Contribuir em open source", "prazo": "14 dias", "status": "pendente"},
            {"etapa": "Criar perfil profissional", "prazo": "7 dias", "status": "pendente"},
        ],
        ("saúde", "saude", "exercício", "exercicio", "emagrecer", "fitness"): [
            {"etapa": "Definir rotina de exercícios", "prazo": "3 dias", "status": "pendente"},
            {"etapa": "Ajustar alimentação", "prazo": "7 dias", "status": "pendente"},
            {"etapa": "Treinar 21 dias seguidos", "prazo": "21 dias", "status": "pendente"},
            {"etapa": "Reavaliar e ajustar", "prazo": "7 dias", "status": "pendente"},
        ],
    }

    for keywords, plano in templates.items():
        if any(k in obj for k in keywords):
            return plano

    return [
        {"etapa": f"Pesquisar: {objetivo}", "prazo": "3 dias", "status": "pendente"},
        {"etapa": "Criar plano detalhado", "prazo": "3 dias", "status": "pendente"},
        {"etapa": "Executar primeira fase", "prazo": "14 dias", "status": "pendente"},
        {"etapa": "Avaliar resultados", "prazo": "3 dias", "status": "pendente"},
        {"etapa": "Ajustar estratégia", "prazo": "7 dias", "status": "pendente"},
        {"etapa": "Escalar", "prazo": "30 dias", "status": "pendente"},
    ]
