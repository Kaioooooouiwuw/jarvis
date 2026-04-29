"""
═══════════════════════════════════════════════════════════════
  JARVIS MEMORY PERSISTENT v2.0 — MENTE AVANÇADA
  ✅ Memória de longo prazo com recuperação inteligente
  ✅ Salva ALL conversas automaticamente a cada sessão
  ✅ Guarda informações explícitas quando pedido pelo usuário
  ✅ Recupera contexto completo ao iniciar nova sessão
  ✅ Extrai automaticamente fatos, planos e compromissos
  ✅ Gera saudação personalizada com base no contexto anterior
  ✅ Timeline de informações importantes (tipo memória humana)
═══════════════════════════════════════════════════════════════
"""

import os
import json
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional
from .core import DataStore, agora_brasil_iso, agora_brasil, saudacao, DATA_DIR

logger = logging.getLogger(__name__)

# ── Diretórios ────────────────────────────────────────────────
MEMORY_DIR = os.path.join(DATA_DIR, "memory")
CONVERSATIONS_DIR = os.path.join(MEMORY_DIR, "conversations")
SUMMARIES_DIR = os.path.join(MEMORY_DIR, "summaries")
CONTEXT_DIR = os.path.join(MEMORY_DIR, "context")

for d in [MEMORY_DIR, CONVERSATIONS_DIR, SUMMARIES_DIR, CONTEXT_DIR]:
    os.makedirs(d, exist_ok=True)

# ── Stores ────────────────────────────────────────────────────
_sessions_store = DataStore("memory_sessions", default=[], subdir="memory")
_facts_store = DataStore("memory_facts", default=[], subdir="memory")
_preferences_store = DataStore("memory_preferences", default={}, subdir="memory")
_explicit_memories_store = DataStore("memory_explicit", default=[], subdir="memory")
_commitments_store = DataStore("memory_commitments", default=[], subdir="memory")

_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════
#  1. GERENCIAMENTO DE SESSÕES DE CONVERSA
# ═══════════════════════════════════════════════════════════════

def iniciar_sessao() -> dict:
    """Registra início de nova sessão de conversa."""
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    sessao = {
        "id": session_id,
        "inicio": agora_brasil_iso(),
        "fim": None,
        "mensagens": 0,
        "topicos": [],
        "resumo": "",
        "arquivo": os.path.join(CONVERSATIONS_DIR, f"conv_{session_id}.json"),
    }
    
    sessoes = _sessions_store.load()
    sessoes.append(sessao)
    if len(sessoes) > 200:
        sessoes = sessoes[-200:]
    _sessions_store.save(sessoes)
    
    conversa = {
        "session_id": session_id,
        "inicio": agora_brasil_iso(),
        "mensagens": [],
    }
    with open(sessao["arquivo"], "w", encoding="utf-8") as f:
        json.dump(conversa, f, ensure_ascii=False, indent=2)
    
    logger.info(f"[Memory] Nova sessão: {session_id}")
    return sessao


def salvar_mensagem(session_id: str, role: str, content: str):
    """Salva uma mensagem individual na sessão."""
    with _lock:
        try:
            filepath = os.path.join(CONVERSATIONS_DIR, f"conv_{session_id}.json")
            
            if not os.path.exists(filepath):
                data = {"session_id": session_id, "inicio": agora_brasil_iso(), "mensagens": []}
            else:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            data["mensagens"].append({
                "role": role,
                "content": content[:5000],
                "timestamp": agora_brasil_iso(),
            })
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.warning(f"[Memory] Erro ao salvar mensagem: {e}")


def finalizar_sessao(session_id: str, mensagens: list = None) -> str:
    """Finaliza sessão, gera resumo e salva tudo."""
    with _lock:
        try:
            sessoes = _sessions_store.load()
            
            for sessao in sessoes:
                if sessao.get("id") == session_id:
                    sessao["fim"] = agora_brasil_iso()
                    
                    if mensagens:
                        filepath = sessao.get("arquivo", "")
                        if filepath and os.path.exists(filepath):
                            with open(filepath, "r", encoding="utf-8") as f:
                                data = json.load(f)
                        else:
                            filepath = os.path.join(CONVERSATIONS_DIR, f"conv_{session_id}.json")
                            data = {"session_id": session_id, "mensagens": []}
                        
                        for msg in mensagens:
                            data["mensagens"].append({
                                "role": msg.get("role", "user"),
                                "content": msg.get("content", "")[:5000],
                                "timestamp": agora_brasil_iso(),
                            })
                        
                        with open(filepath, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        
                        sessao["mensagens"] = len(data["mensagens"])
                    
                    resumo = _gerar_resumo_sessao(session_id)
                    sessao["resumo"] = resumo
                    
                    topicos = _extrair_topicos(session_id)
                    sessao["topicos"] = topicos
                    
                    break
            
            _sessions_store.save(sessoes)
            
            logger.info(f"[Memory] Sessão {session_id} finalizada")
            return f"✅ Sessão salva com {len(mensagens or [])} mensagens."
            
        except Exception as e:
            logger.warning(f"[Memory] Erro ao finalizar sessão: {e}")
            return f"❌ Erro ao finalizar sessão: {e}"


# ═══════════════════════════════════════════════════════════════
#  2. SALVAMENTO AUTOMÁTICO DE CONVERSAS
# ═══════════════════════════════════════════════════════════════

def salvar_conversa_completa(mensagens: list, user_id: str = "Senhor") -> str:
    """
    Salva conversa completa automaticamente.
    Chamado no shutdown do agente.
    """
    if not mensagens:
        return "Nenhuma mensagem para salvar."
    
    try:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(CONVERSATIONS_DIR, f"conv_{session_id}.json")
        
        data = {
            "session_id": session_id,
            "user_id": user_id,
            "inicio": agora_brasil_iso(),
            "mensagens": [],
        }
        
        for msg in mensagens:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            
            data["mensagens"].append({
                "role": role,
                "content": content[:5000],
                "timestamp": agora_brasil_iso(),
            })
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        resumo = _gerar_resumo_de_lista(mensagens)
        topicos = _extrair_topicos_de_lista(mensagens)
        
        sessoes = _sessions_store.load()
        sessoes.append({
            "id": session_id,
            "inicio": agora_brasil_iso(),
            "fim": agora_brasil_iso(),
            "mensagens": len(mensagens),
            "topicos": topicos,
            "resumo": resumo,
            "arquivo": filepath,
        })
        if len(sessoes) > 200:
            sessoes = sessoes[-200:]
        _sessions_store.save(sessoes)
        
        # Extrair fatos, compromissos e memórias explícitas automaticamente
        _extrair_fatos(mensagens, user_id)
        _extrair_compromissos(mensagens)
        _extrair_memorias_explicitas(mensagens)
        
        logger.info(f"[Memory] Conversa {session_id} salva ({len(mensagens)} msgs)")
        return f"✅ Conversa salva: {session_id} ({len(mensagens)} mensagens)"
        
    except Exception as e:
        logger.warning(f"[Memory] Erro ao salvar conversa: {e}")
        return f"❌ Erro ao salvar conversa: {e}"



# ═══════════════════════════════════════════════════════════════
#  3. RECUPERAÇÃO DE MEMÓRIAS
# ═══════════════════════════════════════════════════════════════

def carregar_ultima_conversa() -> str:
    """Carrega a última conversa salva."""
    sessoes = _sessions_store.load()
    if not sessoes:
        return "Nenhuma conversa anterior encontrada."
    
    ultima = sessoes[-1]
    filepath = ultima.get("arquivo", "")
    
    if not filepath or not os.path.exists(filepath):
        return f"Última sessão: {ultima.get('id')} — Resumo: {ultima.get('resumo', 'N/A')}"
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        msgs = data.get("mensagens", [])
        
        linhas = [
            f"📜 **Última conversa** (sessão: {ultima.get('id')})\n",
            f"📅 Início: {ultima.get('inicio', 'N/A')}",
            f"💬 Mensagens: {len(msgs)}\n",
        ]
        
        if ultima.get("resumo"):
            linhas.append(f"📝 Resumo: {ultima['resumo']}\n")
        
        linhas.append("📨 **Últimas mensagens:**\n")
        for msg in msgs[-10:]:
            role = "👤" if msg.get("role") == "user" else "🤖"
            content = msg.get("content", "")[:200]
            linhas.append(f"  {role} {content}")
        
        return "\n".join(linhas)
    
    except Exception as e:
        return f"❌ Erro ao carregar conversa: {e}"


def buscar_em_conversas(termo: str, limite: int = 5) -> str:
    """Busca um termo em todas as conversas salvas."""
    sessoes = _sessions_store.load()
    resultados = []
    
    for sessao in reversed(sessoes):
        filepath = sessao.get("arquivo", "")
        if not filepath or not os.path.exists(filepath):
            continue
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for msg in data.get("mensagens", []):
                content = msg.get("content", "").lower()
                if termo.lower() in content:
                    resultados.append({
                        "sessao": sessao.get("id"),
                        "role": msg.get("role"),
                        "content": msg.get("content", "")[:200],
                        "timestamp": msg.get("timestamp", ""),
                    })
                    if len(resultados) >= limite:
                        break
        except Exception:
            continue
        
        if len(resultados) >= limite:
            break
    
    if not resultados:
        return f"Nenhum resultado encontrado para '{termo}'."
    
    linhas = [f"🔍 **{len(resultados)} resultado(s) para '{termo}':**\n"]
    for r in resultados:
        role = "👤" if r["role"] == "user" else "🤖"
        linhas.append(f"  {role} [sessão {r['sessao']}] {r['content']}")
        linhas.append(f"     ↳ {r['timestamp']}\n")
    
    return "\n".join(linhas)


def listar_sessoes_recentes(quantidade: int = 10) -> str:
    """Lista sessões de conversa recentes."""
    sessoes = _sessions_store.load()
    if not sessoes:
        return "Nenhuma sessão encontrada."
    
    recentes = sessoes[-quantidade:]
    recentes.reverse()
    
    linhas = [f"📜 **Últimas {len(recentes)} sessões:**\n"]
    for s in recentes:
        linhas.append(f"  📅 {s.get('id')} — {s.get('mensagens', '?')} msgs")
        if s.get("resumo"):
            linhas.append(f"     📝 {s['resumo'][:100]}")
        if s.get("topicos"):
            linhas.append(f"     🏷️ {', '.join(s['topicos'][:5])}")
        linhas.append("")
    
    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════
#  4. MEMÓRIAS EXPLÍCITAS (Quando o usuário pede para guardar)
# ═══════════════════════════════════════════════════════════════

def guardar_memoria_explicita(informacao: str, categoria: str = "geral") -> str:
    """
    Guarda uma informação explicitamente pedida pelo usuário.
    Ex: 'Jarvis, guarde na sua memória que vou ao parque hoje à noite.'
    """
    memorias = _explicit_memories_store.load()
    
    # Verificar duplicata
    for m in memorias:
        if m.get("informacao", "").lower() == informacao.lower():
            # Atualizar timestamp
            m["atualizado_em"] = agora_brasil_iso()
            _explicit_memories_store.save(memorias)
            return f"✅ Memória atualizada: {informacao}"
    
    nova_memoria = {
        "id": len(memorias) + 1,
        "informacao": informacao,
        "categoria": categoria,
        "salvo_em": agora_brasil_iso(),
        "atualizado_em": agora_brasil_iso(),
        "ativo": True,
        "vezes_lembrada": 0,
        "contexto_temporal": _detectar_contexto_temporal(informacao),
    }
    
    memorias.append(nova_memoria)
    
    if len(memorias) > 1000:
        memorias = memorias[-1000:]
    
    _explicit_memories_store.save(memorias)
    
    logger.info(f"[Memory] Memória explícita guardada: {informacao[:50]}")
    return f"✅ Entendido, Senhor. Guardei na minha memória: {informacao}"


def listar_memorias_explicitas(categoria: str = "", quantidade: int = 20) -> str:
    """Lista memórias explicitamente guardadas."""
    memorias = _explicit_memories_store.load()
    
    if categoria:
        memorias = [m for m in memorias if m.get("categoria", "").lower() == categoria.lower()]
    
    # Filtrar apenas ativas
    memorias = [m for m in memorias if m.get("ativo", True)]
    
    if not memorias:
        return "Nenhuma memória explícita guardada."
    
    recentes = memorias[-quantidade:]
    recentes.reverse()
    
    linhas = [f"🧠 **Memórias guardadas ({len(recentes)}):**\n"]
    for m in recentes:
        ctx = m.get("contexto_temporal", {})
        temporal = ""
        if ctx.get("quando"):
            temporal = f" ⏰ {ctx['quando']}"
        
        linhas.append(f"  💭 {m.get('informacao', '')}{temporal}")
        linhas.append(f"     📅 Guardado: {m.get('salvo_em', 'N/A')}")
        linhas.append("")
    
    return "\n".join(linhas)


def buscar_memoria_explicita(termo: str) -> list:
    """Busca em memórias explícitas."""
    memorias = _explicit_memories_store.load()
    resultados = []
    
    for m in memorias:
        if not m.get("ativo", True):
            continue
        info = m.get("informacao", "").lower()
        if termo.lower() in info:
            resultados.append(m)
    
    return resultados


def remover_memoria_explicita(termo: str) -> str:
    """Remove uma memória explícita."""
    memorias = _explicit_memories_store.load()
    
    for m in memorias:
        if termo.lower() in m.get("informacao", "").lower():
            m["ativo"] = False
            _explicit_memories_store.save(memorias)
            return f"✅ Memória removida: {m['informacao'][:50]}"
    
    return f"❌ Nenhuma memória encontrada contendo '{termo}'."


def _detectar_contexto_temporal(texto: str) -> dict:
    """Detecta referências temporais na informação guardada."""
    texto_lower = texto.lower()
    agora = agora_brasil()
    ctx = {}
    
    # Hoje
    if any(p in texto_lower for p in ["hoje", "agora", "neste momento"]):
        ctx["quando"] = "hoje"
        ctx["data_ref"] = agora.strftime("%Y-%m-%d")
    
    # Amanhã
    elif any(p in texto_lower for p in ["amanhã", "amanha"]):
        amanha = agora + timedelta(days=1)
        ctx["quando"] = "amanhã"
        ctx["data_ref"] = amanha.strftime("%Y-%m-%d")
    
    # Noite, manhã, tarde
    if "noite" in texto_lower:
        ctx["periodo"] = "noite"
    elif "manhã" in texto_lower or "manha" in texto_lower:
        ctx["periodo"] = "manhã"
    elif "tarde" in texto_lower:
        ctx["periodo"] = "tarde"
    
    # Dias da semana
    dias = {
        "segunda": 0, "terça": 1, "quarta": 2, "quinta": 3,
        "sexta": 4, "sábado": 5, "sabado": 5, "domingo": 6,
    }
    for dia, num in dias.items():
        if dia in texto_lower:
            ctx["dia_semana"] = dia
            break
    
    return ctx


# ═══════════════════════════════════════════════════════════════
#  5. COMPROMISSOS E PLANOS EXTRAÍDOS AUTOMATICAMENTE
# ═══════════════════════════════════════════════════════════════

def _extrair_compromissos(mensagens: list):
    """Extrai compromissos e planos das mensagens automaticamente."""
    marcadores_compromisso = [
        "vou", "irei", "preciso", "tenho que", "vou fazer",
        "marquei", "agendei", "combinei", "prometo", "não posso esquecer",
        "lembre-me", "lembra que", "depois vou", "à noite vou",
        "amanhã vou", "hoje vou", "na semana que vem",
    ]
    
    compromissos_existentes = _commitments_store.load()
    existentes_set = {c.get("texto", "").lower() for c in compromissos_existentes}
    novos = []
    
    for msg in mensagens:
        if msg.get("role") != "user":
            continue
        
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        
        content_lower = content.lower()
        
        for marcador in marcadores_compromisso:
            if marcador in content_lower and content_lower not in existentes_set:
                novo = {
                    "texto": content[:300].strip(),
                    "marcador": marcador,
                    "extraido_em": agora_brasil_iso(),
                    "contexto_temporal": _detectar_contexto_temporal(content),
                    "concluido": False,
                }
                novos.append(novo)
                existentes_set.add(content_lower)
                break
    
    if novos:
        compromissos_existentes.extend(novos)
        if len(compromissos_existentes) > 500:
            compromissos_existentes = compromissos_existentes[-500:]
        _commitments_store.save(compromissos_existentes)
        logger.info(f"[Memory] {len(novos)} compromissos extraídos")


def _extrair_memorias_explicitas(mensagens: list):
    """
    Detecta quando o usuário pede explicitamente para o Jarvis guardar algo.
    Ex: 'guarde isso', 'lembre-se disso', 'salve na memória', etc.
    """
    marcadores = [
        "guarde", "guarda", "lembre-se", "lembra", "salve na memória",
        "salva na memória", "memorize", "não esqueça", "anote", "anota",
        "lembre disso", "guarde essa informação", "guarde isso na memória",
        "grave na memória", "memoriza", "registre", "registra",
    ]
    
    for i, msg in enumerate(mensagens):
        if msg.get("role") != "user":
            continue
        
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        
        content_lower = content.lower()
        
        for marcador in marcadores:
            if marcador in content_lower:
                # A informação a guardar é o conteúdo
                # Remove o marcador para pegar a informação limpa
                info = content.strip()
                if info:
                    guardar_memoria_explicita(info, "conversa_automatica")
                break


# ═══════════════════════════════════════════════════════════════
#  6. FATOS E PREFERÊNCIAS PERSISTENTES
# ═══════════════════════════════════════════════════════════════

def salvar_fato(categoria: str, fato: str) -> str:
    """Salva um fato permanente sobre o usuário."""
    fatos = _facts_store.load()
    
    # Verificar duplicata
    for f in fatos:
        if f.get("fato", "").lower() == fato.lower():
            return "⚠️ Fato já registrado."
    
    fatos.append({
        "categoria": categoria,
        "fato": fato,
        "timestamp": agora_brasil_iso(),
    })
    
    if len(fatos) > 500:
        fatos = fatos[-500:]
    _facts_store.save(fatos)
    
    return f"✅ Fato registrado: [{categoria}] {fato}"


def listar_fatos(categoria: str = "") -> str:
    """Lista fatos armazenados."""
    fatos = _facts_store.load()
    
    if categoria:
        fatos = [f for f in fatos if f.get("categoria", "").lower() == categoria.lower()]
    
    if not fatos:
        return "Nenhum fato armazenado."
    
    linhas = [f"🧠 **Fatos memorizados ({len(fatos)}):**\n"]
    categorias = {}
    for f in fatos:
        cat = f.get("categoria", "geral")
        categorias.setdefault(cat, []).append(f.get("fato", ""))
    
    for cat, lista in categorias.items():
        linhas.append(f"\n  📁 **{cat.title()}:**")
        for item in lista[-10:]:
            linhas.append(f"    • {item}")
    
    return "\n".join(linhas)


def salvar_preferencia(chave: str, valor: str) -> str:
    """Salva preferência do usuário."""
    prefs = _preferences_store.load()
    prefs[chave] = {
        "valor": valor,
        "atualizado_em": agora_brasil_iso(),
    }
    _preferences_store.save(prefs)
    return f"✅ Preferência salva: {chave} = {valor}"


def obter_preferencia(chave: str) -> Optional[str]:
    """Obtém uma preferência salva."""
    prefs = _preferences_store.load()
    pref = prefs.get(chave)
    return pref.get("valor") if pref else None


def listar_preferencias() -> str:
    """Lista todas as preferências."""
    prefs = _preferences_store.load()
    if not prefs:
        return "Nenhuma preferência salva."
    
    linhas = [f"⚙️ **Preferências ({len(prefs)}):**\n"]
    for chave, dados in prefs.items():
        linhas.append(f"  • {chave}: {dados.get('valor', 'N/A')}")
    
    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════
#  7. CONTEXTO PARA INJEÇÃO NAS INSTRUCTIONS (O GRANDE DIFERENCIAL)
# ═══════════════════════════════════════════════════════════════

def gerar_contexto_memorias(max_chars: int = 4000) -> str:
    """
    Gera bloco de contexto COMPLETO das memórias locais para
    injeção nas instructions do agente.
    
    Inclui:
    - Fatos memorizados
    - Preferências
    - Memórias explícitas (pedidas pelo usuário)
    - Compromissos pendentes
    - Resumo das últimas conversas
    - Saudação contextualizada
    """
    partes = []
    
    # ── Memórias explícitas (PRIORIDADE MÁXIMA) ──
    memorias_explicitas = _explicit_memories_store.load()
    memorias_ativas = [m for m in memorias_explicitas if m.get("ativo", True)]
    
    if memorias_ativas:
        partes.append("[Informações que o Senhor pediu para guardar na memória]")
        # Ordenar por mais recente
        memorias_ativas.sort(key=lambda x: x.get("salvo_em", ""), reverse=True)
        for m in memorias_ativas[:30]:
            info = m.get("informacao", "")
            salvo = m.get("salvo_em", "")
            ctx_temp = m.get("contexto_temporal", {})
            periodo = ctx_temp.get("periodo", "")
            quando = ctx_temp.get("quando", "")
            
            extra = ""
            if quando or periodo:
                extra = f" (referência: {quando} {periodo})".strip()
            
            partes.append(f"- {info}{extra} [guardado em: {salvo}]")
    
    # ── Compromissos pendentes ──
    compromissos = _commitments_store.load()
    pendentes = [c for c in compromissos if not c.get("concluido", False)]
    
    if pendentes:
        partes.append("\n[Compromissos e planos mencionados pelo usuário]")
        for c in pendentes[-15:]:
            ctx = c.get("contexto_temporal", {})
            quando = ctx.get("quando", "")
            periodo = ctx.get("periodo", "")
            
            texto = c.get("texto", "")[:150]
            extra = ""
            if quando or periodo:
                extra = f" ({quando} {periodo})".strip()
            
            partes.append(f"- {texto}{extra}")
    
    # ── Fatos ──
    fatos = _facts_store.load()
    if fatos:
        partes.append("\n[Fatos memorizados sobre o usuário]")
        for f in fatos[-20:]:
            partes.append(f"- [{f.get('categoria', 'geral')}] {f.get('fato', '')}")
    
    # ── Preferências ──
    prefs = _preferences_store.load()
    if prefs:
        partes.append("\n[Preferências do usuário]")
        for k, v in list(prefs.items())[-15:]:
            partes.append(f"- {k}: {v.get('valor', '')}")
    
    # ── Resumos das últimas conversas ──
    sessoes = _sessions_store.load()
    if sessoes:
        dias_semana_pt = {
            0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
            3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo",
        }
        
        ultimas = sessoes[-10:]  # Últimas 10 conversas
        ultimas.reverse()
        
        partes.append("\n[Resumo das últimas conversas — com dia e hora]")
        for s in ultimas:
            resumo = s.get("resumo", "")
            data_str = s.get("inicio", "")
            topicos = s.get("topicos", [])
            num_msgs = s.get("mensagens", 0)
            
            if not resumo or resumo == "Sessão sem mensagens do usuário":
                continue
            
            # Parse da data para exibir dia da semana
            dia_info = ""
            try:
                if "T" in data_str:
                    dt = datetime.fromisoformat(data_str)
                    dt_brasil = dt - timedelta(hours=3) if dt.utcoffset() is None else dt
                    dia_semana = dias_semana_pt.get(dt_brasil.weekday(), "")
                    dia_info = f"{dia_semana} {dt_brasil.strftime('%d/%m às %H:%M')}"
            except Exception:
                dia_info = data_str[:16] if data_str else "?"
            
            if resumo:
                partes.append(f"- [{dia_info}] ({num_msgs} msgs): {resumo[:150]}")
                if topicos:
                    topicos_limpos = [t for t in topicos[:5] if t not in ["<noise>", "<ctrl46>", "<ctrl46><ctrl46>"]]
                    if topicos_limpos:
                        partes.append(f"  Tópicos: {', '.join(topicos_limpos)}")
    
    contexto = "\n".join(partes)
    return contexto[:max_chars]


def gerar_saudacao_contextualizada() -> str:
    """
    Gera saudação personalizada e DETALHADA baseada no contexto anterior.
    Inclui dia da semana, horário, e resumo dos assuntos discutidos.
    Para o JARVIS usar ao iniciar sessão.
    
    Exemplo de saída:
    "Boa tarde, Senhor. Lembro que na segunda-feira às 12 horas 
     o senhor conversou comigo sobre controle de gestos e lâmpada do quarto.
     O senhor também me pediu para guardar na memória que iria ao parque hoje à noite.
     Como posso ajudar?"
    """
    saudacao_texto = saudacao()
    partes = [f"{saudacao_texto}, Senhor."]
    
    agora = agora_brasil()
    
    # ── Nomes dos dias da semana em português ──
    dias_semana_pt = {
        0: "segunda-feira",
        1: "terça-feira",
        2: "quarta-feira",
        3: "quinta-feira",
        4: "sexta-feira",
        5: "sábado",
        6: "domingo",
    }
    
    # ── Verificar conversas anteriores com detalhes de dia/hora ──
    sessoes = _sessions_store.load()
    if sessoes:
        # Filtrar sessões com conteúdo real (não só saudação)
        sessoes_reais = [s for s in sessoes if s.get("mensagens", 0) > 1 and s.get("resumo", "")]
        
        if sessoes_reais:
            # Últimas conversas com detalhes de data/hora
            conversas_mencionadas = 0
            for sessao in reversed(sessoes_reais[-5:]):
                inicio_str = sessao.get("inicio", "")
                resumo = sessao.get("resumo", "")
                topicos = sessao.get("topicos", [])
                
                if not resumo or resumo == "Sessão sem mensagens do usuário":
                    continue
                
                try:
                    # Parse da data da sessão
                    if "T" in inicio_str:
                        dt_sessao = datetime.fromisoformat(inicio_str.replace("+00:00", "+00:00"))
                        # Ajustar para fuso Brasil
                        dt_brasil = dt_sessao - timedelta(hours=3) if dt_sessao.utcoffset() is None else dt_sessao
                    else:
                        continue
                    
                    dia_semana = dias_semana_pt.get(dt_brasil.weekday(), "")
                    hora = dt_brasil.strftime("%H:%M")
                    
                    # Calcular diferença para texto relativo
                    diff_dias = (agora.date() - dt_brasil.date()).days
                    
                    if diff_dias == 0:
                        quando = "hoje"
                    elif diff_dias == 1:
                        quando = "ontem"
                    elif diff_dias < 7:
                        quando = f"na {dia_semana}"
                    else:
                        quando = f"no dia {dt_brasil.strftime('%d/%m')}"
                    
                    # Construir frase sobre a conversa
                    assuntos = ""
                    if topicos:
                        topicos_limpos = [t for t in topicos[:4] if len(t) > 3 and t not in ["<noise>", "<ctrl46>"]]
                        if topicos_limpos:
                            assuntos = ", ".join(topicos_limpos)
                    
                    if not assuntos and resumo:
                        # Extrair assunto do resumo
                        assuntos = resumo[:80].strip()
                    
                    if assuntos and conversas_mencionadas == 0:
                        partes.append(
                            f"Lembro que {quando}, às {hora}, "
                            f"o senhor conversou comigo sobre {assuntos}."
                        )
                        conversas_mencionadas += 1
                    elif assuntos and conversas_mencionadas == 1:
                        partes.append(
                            f"E {quando} também falamos sobre {assuntos}."
                        )
                        conversas_mencionadas += 1
                        break  # Máximo 2 conversas mencionadas
                    
                except Exception:
                    continue
    
    # ── Memórias explícitas (PRIORIDADE: o que o usuário pediu para guardar) ──
    memorias = _explicit_memories_store.load()
    memorias_ativas = [m for m in memorias if m.get("ativo", True)]
    
    # Memórias relevantes para hoje
    memorias_hoje = []
    memorias_recentes = []
    
    for m in memorias_ativas:
        ctx = m.get("contexto_temporal", {})
        info = m.get("informacao", "")
        
        # Ignorar memórias que são lixo de transcrição
        if len(info) < 10 or info.lower().startswith(("para do ", "ya, ", "já se ")):
            continue
        
        if ctx.get("quando") == "hoje" or ctx.get("data_ref") == agora.strftime("%Y-%m-%d"):
            memorias_hoje.append(info)
        elif ctx.get("quando") == "amanhã":
            if ctx.get("data_ref") == agora.strftime("%Y-%m-%d"):
                memorias_hoje.append(f"Ontem o senhor mencionou que hoje: {info[:100]}")
        else:
            memorias_recentes.append(info)
    
    if memorias_hoje:
        for mem in memorias_hoje[:2]:
            partes.append(f"O senhor me pediu para lembrar: {mem[:120]}")
    elif memorias_recentes:
        # Mostrar memória mais recente e relevante
        mem = memorias_recentes[-1]
        if len(mem) > 15:  # Ignorar memórias muito curtas/inválidas
            partes.append(f"Tenho guardado na memória que: {mem[:120]}")
    
    # ── Compromissos pendentes ──
    compromissos = _commitments_store.load()
    pendentes = [c for c in compromissos if not c.get("concluido", False)]
    
    if pendentes:
        for comp in pendentes[-2:]:
            ctx = comp.get("contexto_temporal", {})
            texto = comp.get("texto", "")[:80]
            if ctx.get("quando") == "hoje" or ctx.get("data_ref") == agora.strftime("%Y-%m-%d"):
                partes.append(f"Ah, e o senhor havia mencionado: {texto}")
                break
    
    partes.append("Como posso ajudar?")
    
    return " ".join(partes)


# ═══════════════════════════════════════════════════════════════
#  FUNÇÕES AUXILIARES INTERNAS
# ═══════════════════════════════════════════════════════════════

def _gerar_resumo_sessao(session_id: str) -> str:
    """Gera resumo de uma sessão a partir das mensagens salvas."""
    filepath = os.path.join(CONVERSATIONS_DIR, f"conv_{session_id}.json")
    if not os.path.exists(filepath):
        return ""
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        msgs = data.get("mensagens", [])
        return _gerar_resumo_de_lista([
            {"role": m.get("role"), "content": m.get("content", "")}
            for m in msgs
        ])
    except Exception:
        return ""


def _gerar_resumo_de_lista(mensagens: list) -> str:
    """Gera resumo simples a partir de lista de mensagens."""
    if not mensagens:
        return ""
    
    user_msgs = [
        m.get("content", "")
        for m in mensagens
        if m.get("role") == "user" and m.get("content")
    ]
    
    if not user_msgs:
        return "Sessão sem mensagens do usuário"
    
    resumo_parts = []
    for msg in user_msgs[:3]:
        if isinstance(msg, list):
            msg = " ".join(str(m) for m in msg)
        texto = str(msg).strip()[:100]
        if texto:
            resumo_parts.append(texto)
    
    return " | ".join(resumo_parts) if resumo_parts else "Conversa geral"


def _extrair_topicos(session_id: str) -> list:
    """Extrai tópicos de uma sessão."""
    filepath = os.path.join(CONVERSATIONS_DIR, f"conv_{session_id}.json")
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        msgs = [m.get("content", "") for m in data.get("mensagens", [])]
        return _extrair_topicos_de_lista([{"content": m} for m in msgs])
    except Exception:
        return []


def _extrair_topicos_de_lista(mensagens: list) -> list:
    """Extrai tópicos-chave de uma lista de mensagens."""
    palavras_chave = {}
    stop_words = {
        "eu", "de", "que", "o", "a", "não", "do", "da", "em", "um", "uma",
        "para", "com", "me", "se", "por", "no", "na", "os", "as", "mais",
        "como", "mas", "ao", "ele", "das", "tem", "à", "seu", "sua", "ou",
        "ser", "quando", "muito", "há", "nos", "já", "está", "também",
        "só", "pelo", "pela", "até", "isso", "ela", "entre", "era",
        "depois", "sem", "mesmo", "aos", "ter", "seus", "quem", "nas",
        "meu", "esse", "eles", "está", "você", "sim", "pode", "então",
        "the", "is", "in", "it", "to", "and", "of", "for", "on", "that",
        "this", "was", "are", "be", "have", "from", "jarvis", "senhor",
        "favor", "quero", "pode", "fala", "fale",
    }
    
    for msg in mensagens:
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        
        palavras = str(content).lower().split()
        for p in palavras:
            p = p.strip(".,!?;:()[]{}\"'")
            if len(p) > 3 and p not in stop_words:
                palavras_chave[p] = palavras_chave.get(p, 0) + 1
    
    # Top 5 palavras mais frequentes
    top = sorted(palavras_chave.items(), key=lambda x: -x[1])[:5]
    return [p[0] for p in top]


def _extrair_fatos(mensagens: list, user_id: str):
    """Extrai fatos importantes das mensagens automaticamente."""
    marcadores = {
        "pessoal": ["meu nome", "moro em", "minha idade", "trabalho com", "estudo"],
        "preferencia": ["gosto de", "prefiro", "favorito", "adoro", "odeio"],
        "projeto": ["projeto", "empresa", "negócio", "app", "site"],
        "rotina": ["sempre", "toda manhã", "todo dia", "costumo", "rotina"],
        "saude": ["médico", "consulta", "academia", "treino", "dieta"],
        "financeiro": ["salário", "conta", "pagamento", "investimento", "dinheiro"],
    }
    
    fatos_existentes = {f.get("fato", "").lower() for f in _facts_store.load()}
    novos_fatos = []
    
    for msg in mensagens:
        if msg.get("role") != "user":
            continue
        
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        
        content_lower = content.lower()
        
        for categoria, termos in marcadores.items():
            for termo in termos:
                if termo in content_lower and content_lower not in fatos_existentes:
                    fato = content[:200].strip()
                    if fato and fato.lower() not in fatos_existentes:
                        novos_fatos.append({
                            "categoria": categoria,
                            "fato": fato,
                            "timestamp": agora_brasil_iso(),
                        })
                        fatos_existentes.add(fato.lower())
                        break
    
    if novos_fatos:
        fatos = _facts_store.load()
        fatos.extend(novos_fatos)
        if len(fatos) > 500:
            fatos = fatos[-500:]
        _facts_store.save(fatos)
        logger.info(f"[Memory] {len(novos_fatos)} fatos extraídos automaticamente")
