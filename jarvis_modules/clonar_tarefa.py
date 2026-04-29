"""
═══════════════════════════════════════════════════════════════
  [50] clonar_tarefa
═══════════════════════════════════════════════════════════════

Você faz uma vez → Jarvis aprende → repete sozinho.
Grava sequência de ações e replay sob demanda.
"""

from datetime import datetime
from .core import DataStore, agora_iso


# ── Store ─────────────────────────────────────────────────────
_store = DataStore("tarefas_clonadas", default={"tarefas": []})

# Estado em memória
_gravando = False
_nome_gravacao = ""
_acoes_gravadas = []


# ═══════════════════════════════════════════════════════════════
#  API Pública
# ═══════════════════════════════════════════════════════════════

def gravar_tarefa(nome: str) -> str:
    """Inicia gravação de ações."""
    global _gravando, _nome_gravacao, _acoes_gravadas
    _gravando = True
    _nome_gravacao = nome
    _acoes_gravadas = []
    return (
        f"🔴 **Gravação iniciada:** '{nome}'\n"
        f"Todas as ações serão registradas.\n"
        f"Diga 'Jarvis, para de gravar' quando terminar."
    )


def registrar_acao_gravacao(funcao: str, args: str, resultado: str = ""):
    """Registra ação durante gravação (uso interno)."""
    global _acoes_gravadas
    if _gravando:
        _acoes_gravadas.append({
            "funcao": funcao,
            "args": args,
            "resultado": resultado,
            "timestamp": agora_iso(),
        })


def parar_gravacao() -> str:
    """Para gravação e salva tarefa clonável."""
    global _gravando, _nome_gravacao, _acoes_gravadas

    if not _gravando:
        return "Nenhuma gravação em andamento."

    dados = _store.load()
    tarefa = {
        "id": len(dados["tarefas"]) + 1,
        "nome": _nome_gravacao,
        "acoes": _acoes_gravadas.copy(),
        "criada_em": agora_iso(),
        "execucoes": 0,
    }
    dados["tarefas"].append(tarefa)
    _store.save(dados)

    n = len(_acoes_gravadas)
    _gravando = False
    _nome_gravacao = ""
    _acoes_gravadas = []

    return (
        f"⏹️ **Gravação finalizada:** '{tarefa['nome']}'\n"
        f"📊 {n} ações registradas.\n"
        f"Diga 'Jarvis, executa tarefa {tarefa['nome']}' para repetir."
    )


def executar_tarefa_clonada(nome: str) -> str:
    """Retorna ações gravadas para o Jarvis executar."""
    dados = _store.load()
    tarefa = next((t for t in dados["tarefas"] if nome.lower() in t["nome"].lower()), None)

    if not tarefa:
        return f"Tarefa clonada '{nome}' não encontrada."

    acoes = tarefa.get("acoes", [])
    if not acoes:
        return f"Tarefa '{nome}' não tem ações gravadas."

    tarefa["execucoes"] = tarefa.get("execucoes", 0) + 1
    tarefa["ultima_execucao"] = agora_iso()
    _store.save(dados)

    linhas = [
        f"🔄 **Executando:** '{tarefa['nome']}'\n",
        f"📊 {len(acoes)} ações:\n",
    ]
    for i, a in enumerate(acoes, 1):
        linhas.append(f"  {i}. `{a['funcao']}({a.get('args', '')})`")
    linhas.append(f"\n🔁 Execução #{tarefa['execucoes']}")

    return "\n".join(linhas)


def listar_tarefas_clonadas() -> str:
    """Lista tarefas clonáveis."""
    dados = _store.load()
    tarefas = dados.get("tarefas", [])
    if not tarefas:
        return "📋 Nenhuma tarefa clonada."

    linhas = [f"📋 **Tarefas Clonadas ({len(tarefas)}):**\n"]
    for t in tarefas:
        linhas.append(
            f"  🔄 **{t['nome']}** — "
            f"{len(t.get('acoes', []))} ações | "
            f"Executada {t.get('execucoes', 0)}×"
        )
    return "\n".join(linhas)


def esta_gravando() -> bool:
    return _gravando
