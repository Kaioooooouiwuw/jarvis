"""
═══════════════════════════════════════════════════════════════
  [49] sistema_plugins
═══════════════════════════════════════════════════════════════

Sistema de plugins dinâmicos — permite adicionar novas funções
ao Jarvis em runtime via arquivos Python.
"""

import os
import importlib
import importlib.util
from datetime import datetime, timezone
from .core import agora_brasil_iso
from .core import DataStore, BASE_DIR


# ── Store ─────────────────────────────────────────────────────
PLUGINS_DIR = os.path.join(BASE_DIR, "data", "plugins")
os.makedirs(PLUGINS_DIR, exist_ok=True)

_index = DataStore("index", default={"plugins": []}, subdir="plugins")


# ═══════════════════════════════════════════════════════════════
#  API Pública
# ═══════════════════════════════════════════════════════════════

def instalar_plugin(nome: str, descricao: str, codigo_python: str) -> str:
    """Instala plugin como arquivo Python."""
    dados = _index.load()

    for p in dados["plugins"]:
        if p["nome"] == nome:
            return f"⚠️ Plugin '{nome}' já existe. Remova antes de reinstalar."

    arquivo = os.path.join(PLUGINS_DIR, f"{nome}.py")
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(f'"""\nPlugin: {nome}\n{descricao}\nInstalado: {agora_brasil_iso()}\n"""\n\n')
        f.write(codigo_python)

    dados["plugins"].append({
        "nome": nome,
        "descricao": descricao,
        "arquivo": arquivo,
        "instalado_em": agora_brasil_iso(),
        "ativo": True,
        "execucoes": 0,
    })
    _index.save(dados)

    return f"✅ Plugin **'{nome}'** instalado!\n📁 `{arquivo}`"


def carregar_plugin(nome: str) -> str:
    """Carrega e executa plugin."""
    dados = _index.load()
    plugin = next((p for p in dados["plugins"] if p["nome"] == nome and p.get("ativo")), None)

    if not plugin:
        return f"Plugin '{nome}' não encontrado ou inativo."

    arquivo = plugin["arquivo"]
    if not os.path.exists(arquivo):
        return f"❌ Arquivo do plugin não encontrado: {arquivo}"

    try:
        spec = importlib.util.spec_from_file_location(nome, arquivo)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        plugin["execucoes"] = plugin.get("execucoes", 0) + 1
        _index.save(dados)

        if hasattr(mod, "main"):
            resultado = mod.main()
            return f"✅ Plugin '{nome}' executado.\n📤 Resultado: {resultado}"

        funcoes = [f for f in dir(mod) if callable(getattr(mod, f)) and not f.startswith("_")]
        return f"✅ Plugin '{nome}' carregado.\n⚙️ Funções: {', '.join(funcoes)}"
    except Exception as e:
        return f"❌ Erro no plugin '{nome}': {e}"


def listar_plugins() -> str:
    """Lista plugins instalados."""
    dados = _index.load()
    plugins = dados.get("plugins", [])
    if not plugins:
        return "🔌 Nenhum plugin instalado."

    linhas = [f"🔌 **Plugins ({len(plugins)}):**\n"]
    for p in plugins:
        status = "🟢" if p.get("ativo") else "🔴"
        exec_count = p.get("execucoes", 0)
        linhas.append(f"  {status} **{p['nome']}** — {p.get('descricao', '')}")
        linhas.append(f"      Execuções: {exec_count}×")
    return "\n".join(linhas)


def remover_plugin(nome: str) -> str:
    """Remove plugin."""
    dados = _index.load()
    plugin = next((p for p in dados["plugins"] if p["nome"] == nome), None)
    if not plugin:
        return f"Plugin '{nome}' não encontrado."

    if os.path.exists(plugin.get("arquivo", "")):
        os.remove(plugin["arquivo"])
    dados["plugins"] = [p for p in dados["plugins"] if p["nome"] != nome]
    _index.save(dados)
    return f"🗑️ Plugin **'{nome}'** removido."


def toggle_plugin(nome: str) -> str:
    """Ativa/desativa plugin."""
    dados = _index.load()
    for p in dados["plugins"]:
        if p["nome"] == nome:
            p["ativo"] = not p.get("ativo", True)
            _index.save(dados)
            status = "ativado ✅" if p["ativo"] else "desativado 🔴"
            return f"Plugin '{nome}' {status}."
    return f"Plugin '{nome}' não encontrado."
