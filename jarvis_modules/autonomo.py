"""
═══════════════════════════════════════════════════════════════
  [24] modo_autonomo  +  [25] agente_multi_etapas
═══════════════════════════════════════════════════════════════

Motor autônomo unificado — combina:
  • Modo Autônomo: define objetivo, gera plano, executa, se adapta
  • Agente Multi-Etapas: decompõe tarefas complexas em pipeline
    (Análise → Planejamento → Execução → Verificação → Correção)

Funciona como um AutoGPT interno — planeja, executa e itera.
"""

from datetime import datetime, timedelta, timezone
from .core import agora_brasil
from .core import DataStore, barra_progresso, agora_iso, tempo_formatado


# ── Stores ────────────────────────────────────────────────────
_autonomo = DataStore("modo_autonomo", default={
    "ativo": False,
    "sessoes": [],
    "acoes_executadas": [],
    "objetivo_atual": None,
    "estatisticas": {"total_sessoes": 0, "tempo_total_min": 0},
})

_tarefas = DataStore("tarefas_multi_etapas", default={"tarefas": []})

# Estado em memória
_autonomo_ativo = False


# ═══════════════════════════════════════════════════════════════
#  [24] MODO AUTÔNOMO
# ═══════════════════════════════════════════════════════════════

def ativar_modo_autonomo(objetivo: str, duracao_minutos: int = 30) -> str:
    """
    Ativa modo autônomo com objetivo e duração.

    O Jarvis gera um plano contextual e executa etapa por etapa.
    Observa comportamento do usuário e se adapta.

    Args:
        objetivo: 'produtividade', 'estudar', 'organizar', 'projeto', 'descansar', etc.
        duracao_minutos: duração da sessão (default: 30)
    """
    global _autonomo_ativo
    dados = _autonomo.load()
    agora = agora_brasil()

    plano = _gerar_plano(objetivo)

    sessao = {
        "id": dados["estatisticas"]["total_sessoes"] + 1,
        "objetivo": objetivo,
        "inicio": agora.isoformat(),
        "duracao_minutos": duracao_minutos,
        "fim_previsto": (agora + timedelta(minutes=duracao_minutos)).isoformat(),
        "plano": plano,
        "acoes_executadas": [],
        "status": "ativo",
        "adaptacoes": [],
    }

    dados["ativo"] = True
    dados["objetivo_atual"] = objetivo
    dados["sessoes"].append(sessao)
    dados["estatisticas"]["total_sessoes"] += 1
    _autonomo.save(dados)
    _autonomo_ativo = True

    fim = (agora + timedelta(minutes=duracao_minutos)).strftime("%H:%M")

    linhas = [
        "🤖 **Modo Autônomo — ATIVADO**\n",
        f"🎯 Objetivo: **{objetivo}**",
        f"⏱️ Duração: {duracao_minutos} min (até {fim})",
        f"\n📋 **Plano de Ação ({len(plano)} etapas):**\n",
    ]
    for i, etapa in enumerate(plano, 1):
        linhas.append(f"  {i}. {etapa['titulo']} — {etapa['descricao']}")

    linhas.append(f"\n⚡ Executando automaticamente.")
    linhas.append(f"🔇 Diga 'Jarvis, desativa autônomo' para parar.")

    return "\n".join(linhas)


def desativar_modo_autonomo() -> str:
    """Desativa o modo autônomo e registra estatísticas."""
    global _autonomo_ativo
    dados = _autonomo.load()
    agora = agora_brasil()

    if not dados.get("ativo"):
        return "💤 O modo autônomo já está desativado."

    # Finaliza sessão
    if dados["sessoes"]:
        ultima = dados["sessoes"][-1]
        if ultima.get("status") == "ativo":
            inicio = datetime.fromisoformat(ultima["inicio"])
            tempo = (agora - inicio).total_seconds() / 60
            ultima["status"] = "finalizado"
            ultima["fim_real"] = agora.isoformat()
            ultima["tempo_real_minutos"] = round(tempo, 1)
            dados["estatisticas"]["tempo_total_min"] = (
                dados["estatisticas"].get("tempo_total_min", 0) + round(tempo, 1)
            )

    dados["ativo"] = False
    dados["objetivo_atual"] = None
    _autonomo.save(dados)
    _autonomo_ativo = False

    tempo = dados["sessoes"][-1].get("tempo_real_minutos", 0) if dados["sessoes"] else 0
    acoes = len(dados["sessoes"][-1].get("acoes_executadas", [])) if dados["sessoes"] else 0

    return (
        f"⏹️ **Modo Autônomo — DESATIVADO**\n\n"
        f"⏱️ Tempo ativo: {tempo_formatado(tempo)}\n"
        f"⚡ Ações executadas: {acoes}\n"
        f"📊 Total histórico: {dados['estatisticas']['total_sessoes']} sessões / "
        f"{tempo_formatado(dados['estatisticas']['tempo_total_min'])}"
    )


def status_modo_autonomo() -> str:
    """Status detalhado com progresso visual."""
    dados = _autonomo.load()

    if not dados.get("ativo"):
        stats = dados.get("estatisticas", {})
        return (
            f"💤 Modo autônomo **inativo**.\n"
            f"📊 Sessões anteriores: {stats.get('total_sessoes', 0)}\n"
            f"⏱️ Tempo total: {tempo_formatado(stats.get('tempo_total_min', 0))}"
        )

    ultima = dados["sessoes"][-1]
    agora = agora_brasil()

    try:
        inicio = datetime.fromisoformat(ultima["inicio"])
        tempo = (agora - inicio).total_seconds() / 60
        duracao = ultima.get("duracao_minutos", 30)
        restante = max(0, duracao - tempo)
        progresso = min(100, tempo / duracao * 100)
    except (ValueError, KeyError):
        tempo, restante, progresso = 0, 0, 0

    plano = ultima.get("plano", [])
    acoes = ultima.get("acoes_executadas", [])

    linhas = [
        "🤖 **Modo Autônomo — ATIVO**\n",
        f"🎯 Objetivo: **{ultima.get('objetivo', '?')}**",
        f"⏱️ {tempo_formatado(tempo)} / {duracao} min",
        f"⏳ Restante: {tempo_formatado(restante)}",
        f"📊 {barra_progresso(progresso)}",
        f"\n📋 **Plano** ({len(acoes)}/{len(plano)} concluídas):\n",
    ]

    for i, etapa in enumerate(plano):
        check = "✅" if i < len(acoes) else "🔄" if i == len(acoes) else "⬜"
        linhas.append(f"  {check} {i + 1}. {etapa['titulo']}")

    # Adaptações
    if ultima.get("adaptacoes"):
        linhas.append("\n🔄 **Adaptações feitas:**")
        for a in ultima["adaptacoes"][-3:]:
            linhas.append(f"  ↳ {a}")

    return "\n".join(linhas)


def registrar_acao_autonoma(acao: str, resultado: str = ""):
    """Registra ação executada durante modo autônomo."""
    dados = _autonomo.load()
    if dados.get("sessoes"):
        ultima = dados["sessoes"][-1]
        if ultima.get("status") == "ativo":
            ultima.setdefault("acoes_executadas", []).append({
                "timestamp": agora_iso(),
                "acao": acao,
                "resultado": resultado,
            })
            _autonomo.save(dados)


def esta_autonomo() -> bool:
    return _autonomo.load().get("ativo", False)


# ═══════════════════════════════════════════════════════════════
#  [25] AGENTE MULTI-ETAPAS (AutoGPT interno)
# ═══════════════════════════════════════════════════════════════

def executar_tarefa_complexa(descricao: str) -> str:
    """
    Decompõe tarefa complexa em pipeline e registra para execução.

    Pipeline: Análise → Planejamento → Execução → Verificação → Correção → Entrega

    Args:
        descricao: "cria um site completo", "monta uma API", etc.
    """
    dados = _tarefas.load()
    etapas = _decompor_tarefa(descricao)

    tarefa = {
        "id": len(dados["tarefas"]) + 1,
        "descricao": descricao,
        "criada_em": agora_iso(),
        "etapas": etapas,
        "status": "em_andamento",
        "etapa_atual": 0,
        "log": [],
    }

    dados["tarefas"].append(tarefa)
    _tarefas.save(dados)

    linhas = [
        f"🧠 **Agente Multi-Etapas — Tarefa #{tarefa['id']}**\n",
        f"📝 {descricao}\n",
        f"📋 **Pipeline ({len(etapas)} etapas):**\n",
    ]
    for i, e in enumerate(etapas, 1):
        linhas.append(f"  {i}. **{e['titulo']}** — {e['descricao']} [{e['tipo']}]")

    linhas.append("\n🚀 Iniciando execução sequencial…")

    return "\n".join(linhas)


def atualizar_etapa(tarefa_id: int, etapa_idx: int, status: str, resultado: str = "") -> str:
    """Atualiza status de uma etapa."""
    dados = _tarefas.load()
    for t in dados["tarefas"]:
        if t["id"] == tarefa_id:
            if 0 <= etapa_idx < len(t["etapas"]):
                t["etapas"][etapa_idx]["status"] = status
                t["etapas"][etapa_idx]["resultado"] = resultado
                t["etapas"][etapa_idx]["concluida_em"] = agora_iso()

                if status == "concluido":
                    t["etapa_atual"] = etapa_idx + 1
                    if t["etapa_atual"] >= len(t["etapas"]):
                        t["status"] = "concluido"
                        t["concluida_em"] = agora_iso()
                        _tarefas.save(dados)
                        return f"🏆 **Tarefa #{tarefa_id} CONCLUÍDA!** Todas as etapas finalizadas."

                t["log"].append({"etapa": etapa_idx, "status": status, "ts": agora_iso()})
                _tarefas.save(dados)
                return f"✅ Etapa {etapa_idx + 1} → {status}"
    return "Tarefa ou etapa não encontrada."


def status_tarefa(tarefa_id: int = 0) -> str:
    """Status visual com progresso."""
    dados = _tarefas.load()
    tarefas = dados.get("tarefas", [])
    if not tarefas:
        return "Nenhuma tarefa criada."

    t = tarefas[-1] if tarefa_id == 0 else next((x for x in tarefas if x["id"] == tarefa_id), None)
    if not t:
        return f"Tarefa #{tarefa_id} não encontrada."

    etapas = t.get("etapas", [])
    ea = t.get("etapa_atual", 0)
    pct = (ea / len(etapas) * 100) if etapas else 0

    linhas = [
        f"📊 **Tarefa #{t['id']}:** {t['descricao']}\n",
        f"📊 {barra_progresso(pct)}\n",
    ]
    for i, e in enumerate(etapas):
        ck = "✅" if i < ea else "🔄" if i == ea else "⬜"
        linhas.append(f"  {ck} {i + 1}. {e['titulo']}")
        if e.get("resultado") and i < ea:
            linhas.append(f"       ↳ {e['resultado'][:100]}")

    return "\n".join(linhas)


def listar_tarefas() -> str:
    """Lista todas as tarefas do agente."""
    dados = _tarefas.load()
    tarefas = dados.get("tarefas", [])
    if not tarefas:
        return "Nenhuma tarefa registrada."

    linhas = [f"📋 **Tarefas ({len(tarefas)}):**\n"]
    for t in tarefas[-10:]:
        s = "✅" if t.get("status") == "concluido" else "🔄"
        ea = t.get("etapa_atual", 0)
        total = len(t.get("etapas", []))
        linhas.append(f"  {s} #{t['id']} — {t['descricao']} [{ea}/{total}]")
    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════
#  Geração de planos internos
# ═══════════════════════════════════════════════════════════════

def _gerar_plano(objetivo: str) -> list:
    """Gera plano autônomo baseado no objetivo."""
    obj = objetivo.lower()

    planos = {
        ("produtividade", "trabalhar", "trabalho", "produtivo"): [
            {"titulo": "Diagnóstico", "descricao": "Verificar tarefas pendentes e prioridades"},
            {"titulo": "Ambiente", "descricao": "Abrir ferramentas e projeto mais recente"},
            {"titulo": "Foco", "descricao": "Ativar modo foco Pomodoro (25 min)"},
            {"titulo": "Monitoramento", "descricao": "Verificar progresso a cada 10 min"},
            {"titulo": "Pausa Estratégica", "descricao": "Intervalo de 5 min ao fim do ciclo"},
            {"titulo": "Retrospectiva", "descricao": "Registrar produtividade na timeline"},
        ],
        ("estudar", "estudo", "aprender", "curso"): [
            {"titulo": "Material", "descricao": "Verificar / abrir material de estudo"},
            {"titulo": "Ambiente", "descricao": "Ativar modo foco + silêncio"},
            {"titulo": "Absorção", "descricao": "Estudo concentrado do conteúdo"},
            {"titulo": "Notas", "descricao": "Organizar anotações e resumos"},
            {"titulo": "Revisão", "descricao": "Revisão espaçada dos pontos-chave"},
            {"titulo": "Registro", "descricao": "Salvar progresso no conhecimento"},
        ],
        ("organizar", "organização", "limpar", "arrumar"): [
            {"titulo": "Scan", "descricao": "Verificar pastas bagunçadas"},
            {"titulo": "Downloads", "descricao": "Limpar e organizar downloads"},
            {"titulo": "Temporários", "descricao": "Remover lixo e caches"},
            {"titulo": "Notas", "descricao": "Revisar e organizar anotações"},
            {"titulo": "Projetos", "descricao": "Verificar projetos abandonados"},
            {"titulo": "Relatório", "descricao": "Gerar relatório de organização"},
        ],
        ("projeto", "código", "codigo", "dev", "programar"): [
            {"titulo": "Abertura", "descricao": "Abrir projeto no VS Code + terminal"},
            {"titulo": "Análise", "descricao": "Analisar código existente e TODOs"},
            {"titulo": "Debug", "descricao": "Executar debug autônomo"},
            {"titulo": "Implementação", "descricao": "Trabalhar na funcionalidade principal"},
            {"titulo": "Refatoração", "descricao": "Otimizar código escrito"},
            {"titulo": "Documentação", "descricao": "Atualizar README e docs"},
        ],
        ("descansar", "relaxar", "pausa", "break"): [
            {"titulo": "Ambiente", "descricao": "Colocar música relaxante"},
            {"titulo": "Silêncio", "descricao": "Desativar notificações"},
            {"titulo": "Sugestões", "descricao": "Sugerir atividades leves"},
            {"titulo": "Hidratação", "descricao": "Lembrar de beber água"},
            {"titulo": "Recuperação", "descricao": "Monitorar tempo de descanso"},
            {"titulo": "Retorno", "descricao": "Planejar retomada de atividades"},
        ],
    }

    for keywords, plano in planos.items():
        if any(k in obj for k in keywords):
            return plano

    return [
        {"titulo": "Análise", "descricao": f"Entender contexto de '{objetivo}'"},
        {"titulo": "Planejamento", "descricao": "Criar plano detalhado"},
        {"titulo": "Execução", "descricao": "Executar primeira fase"},
        {"titulo": "Verificação", "descricao": "Conferir resultados"},
        {"titulo": "Ajuste", "descricao": "Corrigir e adaptar"},
        {"titulo": "Conclusão", "descricao": "Finalizar e registrar"},
    ]


def _decompor_tarefa(desc: str) -> list:
    """Decompõe descrição em etapas executáveis (AutoGPT)."""
    d = desc.lower()

    templates = {
        ("site", "portfólio", "portfolio", "landing", "página", "pagina"): [
            {"titulo": "Análise de Requisitos", "descricao": "Definir escopo, público e funcionalidades", "tipo": "planejamento", "status": "pendente"},
            {"titulo": "Arquitetura", "descricao": "Definir estrutura de pastas e componentes", "tipo": "planejamento", "status": "pendente"},
            {"titulo": "HTML Base", "descricao": "Criar estrutura semântica completa", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Design System", "descricao": "CSS com variáveis, tipografia e cores", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Interatividade", "descricao": "JavaScript — animações e lógica", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Responsividade", "descricao": "Adaptar para mobile e tablet", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Validação", "descricao": "Testar e corrigir problemas", "tipo": "debug", "status": "pendente"},
            {"titulo": "Entrega", "descricao": "README + deploy", "tipo": "manual", "status": "pendente"},
        ],
        ("api", "backend", "servidor", "rest"): [
            {"titulo": "Setup", "descricao": "Criar projeto e dependências", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Modelos", "descricao": "Schemas e modelos de dados", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Rotas", "descricao": "Endpoints CRUD completos", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Auth", "descricao": "Autenticação e autorização", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Validação", "descricao": "Error handling e testes", "tipo": "debug", "status": "pendente"},
            {"titulo": "Docs", "descricao": "Documentação Swagger/OpenAPI", "tipo": "manual", "status": "pendente"},
        ],
        ("saas", "app", "sistema", "plataforma"): [
            {"titulo": "Requisitos", "descricao": "Definir escopo e features", "tipo": "planejamento", "status": "pendente"},
            {"titulo": "Backend", "descricao": "API completa", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Frontend", "descricao": "Interface de usuário", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Integração", "descricao": "Conectar front + back", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Auth & Pagamento", "descricao": "Login + billing", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Testes", "descricao": "E2E + unitários", "tipo": "debug", "status": "pendente"},
            {"titulo": "Deploy", "descricao": "Produção + CI/CD", "tipo": "manual", "status": "pendente"},
        ],
        ("bot", "automação", "whatsapp", "telegram", "discord"): [
            {"titulo": "Setup", "descricao": "Configurar bot + credenciais", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Comandos", "descricao": "Implementar comandos base", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "IA/Lógica", "descricao": "Adicionar inteligência", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Persistência", "descricao": "Banco de dados / estado", "tipo": "gerar_projeto", "status": "pendente"},
            {"titulo": "Teste", "descricao": "Testar todos os fluxos", "tipo": "debug", "status": "pendente"},
        ],
    }

    for keywords, etapas in templates.items():
        if any(k in d for k in keywords):
            return etapas

    return [
        {"titulo": "Análise", "descricao": f"Entender: {desc}", "tipo": "planejamento", "status": "pendente"},
        {"titulo": "Planejamento", "descricao": "Criar plano detalhado", "tipo": "planejamento", "status": "pendente"},
        {"titulo": "Execução", "descricao": "Implementar solução", "tipo": "automatico", "status": "pendente"},
        {"titulo": "Verificação", "descricao": "Conferir resultado", "tipo": "debug", "status": "pendente"},
        {"titulo": "Correção", "descricao": "Ajustar problemas", "tipo": "debug", "status": "pendente"},
        {"titulo": "Entrega", "descricao": "Finalizar e documentar", "tipo": "manual", "status": "pendente"},
    ]
