"""
═══════════════════════════════════════════════════════════════
  [22] salvar_conhecimento  /  [23] ler_conhecimento
═══════════════════════════════════════════════════════════════

Base de conhecimento permanente — arquivo Markdown que o Jarvis
lê automaticamente a cada sessão. Só o usuário altera.

Categorias: rotina · preferência · contato · projeto · geral
"""

from datetime import datetime, timezone
from .core import agora_brasil
from .core import DataStoreMD

# ── Store ─────────────────────────────────────────────────────
_HEADER = (
    "# 🧠 Base de Conhecimento Pessoal do Jarvis\n\n"
    "> Este arquivo é lido automaticamente a cada sessão.\n\n---\n\n"
)

CATEGORIAS = {
    "rotina":       "## 📋 Rotina",
    "preferência":  "## ⭐ Preferências",
    "preferencia":  "## ⭐ Preferências",
    "contato":      "## 👥 Contatos",
    "projeto":      "## 💻 Projetos",
    "geral":        "## 📝 Geral",
}

_store = DataStoreMD("conhecimento-pessoal")
_store.garantir(_HEADER + "\n".join(f"{h}\n" for h in dict.fromkeys(CATEGORIAS.values())) + "\n")


# ═══════════════════════════════════════════════════════════════
#  Funções públicas
# ═══════════════════════════════════════════════════════════════

def salvar_conhecimento(categoria: str, conteudo: str) -> str:
    """
    Salva informação permanente.

    Args:
        categoria: rotina | preferência | contato | projeto | geral
        conteudo:  texto livre
    """
    header = CATEGORIAS.get(categoria.lower().strip())
    if not header:
        cats = ", ".join(dict.fromkeys(CATEGORIAS.values()))
        return f"Categoria inválida. Use uma de: {cats}"

    existente = _store.read()
    if conteudo.strip() in existente:
        return f"Essa informação já existe em '{categoria}'."

    ts = agora_brasil().strftime("%Y-%m-%d %H:%M")
    linha = f"- {conteudo.strip()} *(salvo em {ts})*"
    _store.append_to_section(header, linha)

    return f"✅ Conhecimento salvo ({categoria}): {conteudo.strip()}"


def ler_conhecimento() -> str:
    """Retorna toda a base de conhecimento formatada."""
    conteudo = _store.read()
    itens = [l for l in conteudo.split("\n") if l.strip().startswith("- ")]
    if not itens:
        return "A base de conhecimento está vazia."
    return conteudo


def ler_conhecimento_para_contexto() -> str:
    """Versão compacta para injeção no prompt do agente."""
    conteudo = _store.read()
    resultado = []
    secao_atual = ""
    for line in conteudo.split("\n"):
        if line.startswith("## "):
            secao_atual = line
        elif line.strip().startswith("- "):
            if secao_atual and secao_atual not in resultado:
                resultado.append(secao_atual)
            resultado.append(line)
    return "\n".join(resultado) if resultado else ""
