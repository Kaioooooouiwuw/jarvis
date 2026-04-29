"""
═══════════════════════════════════════════════════════════════
  [42] assistente_rotina
  [43] modo_foco_total
  [44] coach_inteligente
═══════════════════════════════════════════════════════════════

Motor de vida real nível Iron Man — rotina, foco Pomodoro e
coaching com cobrança baseada em comportamento real.
"""

from datetime import datetime, timedelta, timezone
from .core import agora_brasil, agora_brasil_iso
from .core import DataStore, barra_progresso, saudacao, tempo_formatado


# ── Stores ────────────────────────────────────────────────────
_rotina = DataStore("rotina", default={"tarefas_dia": [], "rotina_padrao": {}, "historico": []})
_foco = DataStore("foco", default={"sessoes": [], "bloqueados": [], "ativo": False, "estatisticas": {"total_sessoes": 0, "tempo_total": 0}})
_metas = DataStore("metas_coach", default={"metas": [], "lembretes": []})


# ═══════════════════════════════════════════════════════════════
#  [42] ASSISTENTE DE ROTINA
# ═══════════════════════════════════════════════════════════════

def assistente_rotina(comando: str, detalhe: str = "") -> str:
    """
    Gerencia rotina diária.

    comando: organizar | ver | adicionar | concluir | limpar
    """
    dados = _rotina.load()
    agora = agora_brasil()
    hoje = agora.strftime("%Y-%m-%d")

    if comando in ("organizar", "ver"):
        tarefas_hoje = [t for t in dados.get("tarefas_dia", []) if t.get("data", "").startswith(hoje)]
        pendentes = [t for t in tarefas_hoje if not t.get("concluida")]
        concluidas = [t for t in tarefas_hoje if t.get("concluida")]

        result = [f"📅 **{saudacao()}! Seu dia ({agora.strftime('%d/%m/%Y')}):**\n"]

        if tarefas_hoje:
            if pendentes:
                result.append("📋 **Pendentes:**")
                for t in sorted(pendentes, key=lambda x: _prioridade_rank(x.get("prioridade", "media"))):
                    emoji = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}.get(t.get("prioridade", "media"), "🟡")
                    hora = f" [{t['hora']}]" if t.get("hora") else ""
                    result.append(f"  {emoji}{hora} {t['titulo']}")

            if concluidas:
                result.append(f"\n✅ **Concluídas ({len(concluidas)}):**")
                for t in concluidas:
                    result.append(f"  ☑️ {t['titulo']}")

            pct = len(concluidas) / len(tarefas_hoje) * 100 if tarefas_hoje else 0
            result.append(f"\n📊 **Progresso:** {barra_progresso(pct)} ({len(concluidas)}/{len(tarefas_hoje)})")
        else:
            result.append("📭 Nenhuma tarefa para hoje.")
            result.append("💡 Diga: 'Jarvis, adiciona tarefa: ...'")

        # Dica por horário
        h = agora.hour
        dicas = {
            range(6, 9): "💡 Bom momento para planejar! Foque nas prioridades.",
            range(9, 12): "💡 Pico de produtividade! Ataque as tarefas difíceis.",
            range(12, 14): "💡 Pausa para recarregar. Coma bem!",
            range(14, 16): "💡 Após almoço — tarefas que exigem menos concentração.",
            range(18, 22): "💡 Fim do dia. Revise o que fez e planeje amanhã.",
            range(22, 24): "💡 Hora de descansar! Durma bem para render amanhã.",
        }
        for faixa, dica in dicas.items():
            if h in faixa:
                result.append(f"\n{dica}")
                break

        return "\n".join(result)

    elif comando == "adicionar":
        if not detalhe:
            return "Especifique a tarefa. Ex: 'reunião 14:00 alta'"

        partes = detalhe.split()
        titulo = detalhe
        hora_tarefa = ""
        prioridade = "media"

        for p in partes:
            if ":" in p and len(p) <= 5:
                try:
                    int(p.replace(":", ""))
                    hora_tarefa = p
                    titulo = titulo.replace(p, "").strip()
                except ValueError:
                    pass

        for p in partes:
            pl = p.lower()
            if pl in ("alta", "urgente", "importante"):
                prioridade = "alta"
                titulo = titulo.replace(p, "").strip()
            elif pl in ("baixa", "tranquilo"):
                prioridade = "baixa"
                titulo = titulo.replace(p, "").strip()

        tarefa = {
            "id": len(dados.get("tarefas_dia", [])) + 1,
            "titulo": titulo.strip(),
            "hora": hora_tarefa,
            "prioridade": prioridade,
            "data": hoje,
            "concluida": False,
            "criada_em": agora.isoformat(),
        }

        dados.setdefault("tarefas_dia", []).append(tarefa)
        _rotina.save(dados)

        emoji = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}[prioridade]
        hora_msg = f" às {hora_tarefa}" if hora_tarefa else ""
        return f"✅ Tarefa adicionada: {emoji} **{titulo}**{hora_msg}"

    elif comando == "concluir":
        for t in dados.get("tarefas_dia", []):
            if (t.get("data", "").startswith(hoje) and not t.get("concluida")
                    and detalhe.lower() in t.get("titulo", "").lower()):
                t["concluida"] = True
                t["concluida_em"] = agora.isoformat()
                dados.setdefault("historico", []).append({
                    "tarefa": t["titulo"], "data": hoje, "hora": agora.strftime("%H:%M"),
                })
                _rotina.save(dados)
                return f"☑️ **'{t['titulo']}'** concluída!"
        return f"Tarefa '{detalhe}' não encontrada ou já concluída."

    elif comando == "limpar":
        dados["tarefas_dia"] = [t for t in dados.get("tarefas_dia", []) if not t.get("data", "").startswith(hoje)]
        _rotina.save(dados)
        return "🗑️ Tarefas do dia limpas."

    return f"Comando '{comando}' inválido. Use: organizar, adicionar, concluir, ver, limpar."


def _prioridade_rank(p: str) -> int:
    return {"alta": 0, "media": 1, "baixa": 2}.get(p, 1)


# ═══════════════════════════════════════════════════════════════
#  [43] MODO FOCO TOTAL (Pomodoro Avançado)
# ═══════════════════════════════════════════════════════════════

def modo_foco_total(acao: str = "ativar", duracao_minutos: int = 25) -> str:
    """
    Foco com Pomodoro + bloqueio de distrações.

    acao: ativar | desativar | status
    """
    dados = _foco.load()
    agora = agora_brasil()

    if acao == "ativar":
        sites_distracao = [
            "instagram.com", "twitter.com", "x.com", "tiktok.com",
            "facebook.com", "reddit.com", "9gag.com",
        ]

        sessao = {
            "id": dados.get("estatisticas", {}).get("total_sessoes", 0) + 1,
            "inicio": agora.isoformat(),
            "duracao_minutos": duracao_minutos,
            "fim_previsto": (agora + timedelta(minutes=duracao_minutos)).isoformat(),
            "concluida": False,
        }

        dados["ativo"] = True
        dados["sessao_atual"] = sessao
        dados.setdefault("sessoes", []).append(sessao)
        dados["bloqueados"] = sites_distracao
        dados.setdefault("estatisticas", {})["total_sessoes"] = sessao["id"]
        _foco.save(dados)

        fim = (agora + timedelta(minutes=duracao_minutos)).strftime("%H:%M")

        return (
            f"🎯 **Modo Foco — ATIVADO!**\n\n"
            f"⏱️ Duração: **{duracao_minutos} min** (até {fim})\n"
            f"🚫 {len(sites_distracao)} sites de distração bloqueados\n\n"
            f"💡 **Dicas:**\n"
            f"  → Foque em UMA tarefa\n"
            f"  → Celular longe\n"
            f"  → Beba água\n"
            f"  → {duracao_minutos} min de foco → 5 min de pausa"
        )

    elif acao == "desativar":
        tempo_focado = 0
        sessao = dados.get("sessao_atual")
        if sessao:
            try:
                inicio = datetime.fromisoformat(sessao["inicio"])
                tempo_focado = (agora - inicio).total_seconds() / 60
                sessao["concluida"] = True
                sessao["tempo_real"] = round(tempo_focado, 1)
            except (ValueError, KeyError):
                pass

        dados["ativo"] = False
        dados["bloqueados"] = []
        dados.setdefault("estatisticas", {})["tempo_total"] = (
            dados.get("estatisticas", {}).get("tempo_total", 0) + round(tempo_focado, 1)
        )
        _foco.save(dados)

        return (
            f"⏸️ **Modo Foco — DESATIVADO**\n\n"
            f"⏱️ Tempo focado: **{tempo_formatado(tempo_focado)}**\n"
            f"🔓 Sites desbloqueados\n"
            f"☕ Hora de uma pausa!"
        )

    elif acao == "status":
        if not dados.get("ativo"):
            stats = dados.get("estatisticas", {})
            return (
                f"💤 Modo foco **inativo**.\n"
                f"📊 Sessões: {stats.get('total_sessoes', 0)} | "
                f"Tempo total: {tempo_formatado(stats.get('tempo_total', 0))}"
            )

        sessao = dados.get("sessao_atual", {})
        try:
            inicio = datetime.fromisoformat(sessao["inicio"])
            tempo = (agora - inicio).total_seconds() / 60
            duracao = sessao.get("duracao_minutos", 25)
            restante = max(0, duracao - tempo)
            pct = min(100, tempo / duracao * 100)
        except (ValueError, KeyError):
            tempo, restante, pct = 0, 0, 0

        return (
            f"🎯 **Modo Foco — ATIVO**\n\n"
            f"⏱️ {tempo_formatado(tempo)} / {int(duracao)} min\n"
            f"⏳ Restante: {tempo_formatado(restante)}\n"
            f"📊 {barra_progresso(pct)}"
        )

    return f"Ação '{acao}' inválida. Use: ativar, desativar, status."


# ═══════════════════════════════════════════════════════════════
#  [44] COACH INTELIGENTE
# ═══════════════════════════════════════════════════════════════

def coach_inteligente(comando: str = "status", area: str = "", meta: str = "") -> str:
    """
    Coach que cobra metas baseado em comportamento real.

    comando: definir_meta | status | cobrar | relatorio
    """
    dados = _metas.load()
    agora = agora_brasil()

    if comando == "definir_meta":
        if not meta:
            return "Defina a meta. Ex: 'estudar 2 horas por dia'"

        nova = {
            "id": len(dados.get("metas", [])) + 1,
            "area": area or "geral",
            "descricao": meta,
            "criada_em": agora.isoformat(),
            "prazo": (agora + timedelta(days=30)).isoformat(),
            "progresso": 0,
            "check_ins": [],
            "ativa": True,
        }

        dados.setdefault("metas", []).append(nova)
        _metas.save(dados)

        return (
            f"🎯 **Meta definida!**\n\n"
            f"📌 **{meta}**\n"
            f"📁 Área: {area or 'geral'}\n"
            f"📅 Prazo: 30 dias ({(agora + timedelta(days=30)).strftime('%d/%m/%Y')})\n\n"
            f"Vou te cobrar periodicamente. Não me decepcione! 💪"
        )

    elif comando == "cobrar":
        ativas = [m for m in dados.get("metas", []) if m.get("ativa")]
        if not ativas:
            return "Nenhuma meta ativa. Defina uma primeiro!"

        linhas = ["🔥 **Hora da Cobrança!**\n"]
        for m in ativas:
            dias = (agora - datetime.fromisoformat(m["criada_em"])).days
            prog = m.get("progresso", 0)

            if prog < 25:
                emoji, msg = "😤", "Você mal começou. FOCO!"
            elif prog < 50:
                emoji, msg = "🤔", "Progresso razoável, mas pode melhorar."
            elif prog < 75:
                emoji, msg = "💪", "Bom progresso! Continue!"
            else:
                emoji, msg = "🏆", "Quase lá! Finalize com chave de ouro!"

            linhas.append(f"  {emoji} **{m['descricao']}** ({m.get('area', 'geral')})")
            linhas.append(f"     {barra_progresso(prog)}")
            linhas.append(f"     📅 {dias} dias | → {msg}\n")

        return "\n".join(linhas)

    elif comando == "status":
        metas = dados.get("metas", [])
        ativas = [m for m in metas if m.get("ativa")]
        concluidas = [m for m in metas if not m.get("ativa")]

        result = [
            "📊 **Status do Coach:**\n",
            f"🎯 Ativas: {len(ativas)} | ✅ Concluídas: {len(concluidas)}\n",
        ]
        for m in ativas:
            result.append(f"  📌 {m['descricao']}")
            result.append(f"     {barra_progresso(m.get('progresso', 0))}")

        if not ativas:
            result.append("Nenhuma meta ativa. Vamos definir uma?")

        return "\n".join(result)

    elif comando == "relatorio":
        metas = dados.get("metas", [])
        total = len(metas)
        n_ativas = len([m for m in metas if m.get("ativa")])
        n_concluidas = total - n_ativas

        foco_dados = _foco.load()
        stats_foco = foco_dados.get("estatisticas", {})

        result = [
            "📈 **Relatório do Coach**\n",
            f"📊 Metas: {total} total | {n_ativas} ativas | {n_concluidas} concluídas",
            f"📈 Taxa: {(n_concluidas / total * 100) if total else 0:.0f}%",
            f"\n⏱️ Foco: {stats_foco.get('total_sessoes', 0)} sessões | "
            f"{tempo_formatado(stats_foco.get('tempo_total', 0))} total",
        ]
        return "\n".join(result)

    return f"Comando '{comando}' inválido. Use: definir_meta, status, cobrar, relatorio."


def atualizar_progresso_meta(meta_id: int, progresso: int) -> str:
    """Atualiza progresso de uma meta."""
    dados = _metas.load()
    for m in dados.get("metas", []):
        if m.get("id") == meta_id:
            m["progresso"] = min(100, max(0, progresso))
            if progresso >= 100:
                m["ativa"] = False
                m["concluida_em"] = agora_brasil_iso()
            m.setdefault("check_ins", []).append({"data": agora_brasil_iso(), "progresso": progresso})
            _metas.save(dados)
            if progresso >= 100:
                return f"🏆 **Meta concluída!** '{m['descricao']}' — Parabéns!"
            return f"📊 Meta '{m['descricao']}': {barra_progresso(progresso)}"
    return f"Meta #{meta_id} não encontrada."
