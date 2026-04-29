"""
═══════════════════════════════════════════════════════════════
  JARVIS NLU ENGINE v1.0 — Natural Language Understanding
  Arquitetura: Intenção + Slots + Sinônimos + Compostos + Contexto
═══════════════════════════════════════════════════════════════
"""

import re
import time
import json
import logging
import threading
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from .core import DataStore, agora_brasil_iso

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  ESTRUTURAS DE DADOS
# ═══════════════════════════════════════════════════════════════

@dataclass
class Slot:
    nome: str
    valor: Any
    confianca: float = 1.0

@dataclass
class IntencaoResolvida:
    intencao: str
    slots: dict = field(default_factory=dict)
    texto_original: str = ""
    confianca: float = 0.0
    sub_acoes: list = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["sub_acoes"] = [asdict(s) if hasattr(s, "__dataclass_fields__") else s for s in self.sub_acoes]
        return d

# ═══════════════════════════════════════════════════════════════
#  SINÔNIMOS — Mapeamento de variações linguísticas
# ═══════════════════════════════════════════════════════════════

SINONIMOS_ACAO = {
    "ligar": [
        "liga", "ligue", "acende", "acenda", "ativa", "ative",
        "põe", "poem", "coloca", "abre", "inicia", "conecta",
        "bota", "aciona", "habilita", "dispara", "ascende",
    ],
    "desligar": [
        "desliga", "desligue", "apaga", "apague", "desativa",
        "desative", "corta", "corte", "fecha", "para", "pare",
        "encerra", "mata", "remove", "tira", "desconecta",
    ],
    "aumentar": [
        "aumenta", "aumente", "sobe", "suba", "mais forte",
        "mais alto", "eleva", "eleve", "intensifica", "amplia",
        "levanta", "bota mais", "coloca mais", "subi",
    ],
    "diminuir": [
        "diminui", "diminua", "abaixa", "abaixe", "mais fraco",
        "mais fraca", "mais baixo", "mais baixa", "reduz", "reduza",
        "baixa", "menos", "enfraquece", "suaviza",
    ],
    "ajustar": [
        "ajusta", "ajuste", "define", "defina", "seta", "configura",
        "configure", "regula", "regule", "muda", "mude", "troca",
        "altera", "modifica", "coloca em", "bota em", "põe em",
    ],
    "pausar": [
        "pausa", "pause", "espera", "segura", "hold",
        "congela", "suspende", "interrompe",
    ],
    "continuar": [
        "continua", "continue", "retoma", "retome", "volta",
        "prossiga", "despausa", "play", "toca", "roda",
    ],
    "pular": [
        "pula", "pule", "avança", "avance", "próxima",
        "próximo", "skip", "seguinte", "passa",
    ],
    "voltar": [
        "volta", "anterior", "prévia", "última", "atrás",
        "retrocede", "rebobina",
    ],
    "tocar": [
        "toca", "toque", "reproduz", "reproduza", "roda",
        "bota pra tocar", "coloca pra tocar", "play",
    ],
    "pesquisar": [
        "pesquisa", "pesquise", "busca", "busque", "procura",
        "procure", "acha", "ache", "encontra", "encontre",
        "google", "googla",
    ],
    "criar": [
        "cria", "crie", "gera", "gere", "faz", "faça",
        "monta", "monte", "constrói", "construa", "novo",
    ],
    "deletar": [
        "deleta", "delete", "exclui", "exclua", "remove",
        "remova", "apaga", "apague", "elimina",
    ],
    "enviar": [
        "envia", "envie", "manda", "mande", "despacha",
        "dispara", "encaminha",
    ],
    "lembrar": [
        "lembra", "lembre", "memoriza", "memorize", "guarda",
        "guarde", "anota", "anote", "salva", "salve",
        "registra", "registre", "grava",
    ],
}

SINONIMOS_DISPOSITIVO = {
    "luz": ["lâmpada", "lampada", "iluminação", "iluminacao", "luminária", "luminaria", "led"],
    "ar_condicionado": ["ar condicionado", "climatizador", "split"],
    "tv": ["televisão", "televisao", "televisor", "smart tv"],
    "ventilador": ["ventoinha", "circulador"],
    "cortina": ["persiana", "blackout", "cortinas"],
    "musica": ["música", "musica", "player", "tocador", "spotify", "youtube music"],
    "alarme": ["alarmes", "despertador", "timer", "temporizador"],
    "camera": ["câmera", "webcam", "vigilância", "vigilancia"],
    "volume": ["volume"],
}

SINONIMOS_COMODO = {
    "sala": ["sala de estar", "living", "sala principal"],
    "quarto": ["dormitório", "dormitorio", "suíte", "suite", "bedroom"],
    "cozinha": ["copa", "cozinha americana"],
    "banheiro": ["wc", "lavabo", "toalete", "toilette"],
    "escritorio": ["escritório", "office", "home office", "estúdio", "estudio"],
    "garagem": ["garage", "estacionamento"],
    "varanda": ["sacada", "terraço", "terraco", "alpendre"],
    "corredor": ["hall", "entrada"],
    "lavanderia": ["área de serviço", "area de servico"],
}

SINONIMOS_INTENSIDADE = {
    100: ["máximo", "maximo", "máxima", "maxima", "total", "tudo", "full", "max"],
    75: ["alto", "alta", "forte", "bastante", "muito"],
    50: ["médio", "medio", "média", "media", "metade", "meio"],
    25: ["baixo", "baixa", "fraco", "fraca", "pouco", "pouquinho"],
    10: ["mínimo", "minimo", "mínima", "minima", "quase nada", "só um pouco"],
    0: ["nada", "zero", "nenhum", "nenhuma", "desligado", "mudo", "mute"],
}

# ═══════════════════════════════════════════════════════════════
#  INTENÇÕES — Mapeamento de padrões para intenções
# ═══════════════════════════════════════════════════════════════

INTENCOES = {
    "controlar_luz": {
        "palavras": ["luz", "lâmpada", "lampada", "iluminação", "iluminacao", "led", "luminária"],
        "acoes_validas": ["ligar", "desligar", "aumentar", "diminuir", "ajustar"],
    },
    "controlar_volume": {
        "palavras": ["volume", "som"],
        "acoes_validas": ["aumentar", "diminuir", "ajustar"],
    },
    "controlar_musica": {
        "palavras": ["música", "musica", "tocando", "player", "spotify", "youtube"],
        "acoes_validas": ["tocar", "pausar", "continuar", "pular", "voltar", "ajustar"],
    },
    "controlar_temperatura": {
        "palavras": ["temperatura", "ar condicionado", "ar", "climatizador", "aquecedor"],
        "acoes_validas": ["ligar", "desligar", "aumentar", "diminuir", "ajustar"],
    },
    "controlar_cortina": {
        "palavras": ["cortina", "persiana", "blackout"],
        "acoes_validas": ["ligar", "desligar", "aumentar", "diminuir", "ajustar"],
    },
    "controlar_tv": {
        "palavras": ["tv", "televisão", "televisao"],
        "acoes_validas": ["ligar", "desligar", "ajustar"],
    },
    "gerenciar_alarme": {
        "palavras": ["alarme", "despertador", "timer", "lembrete"],
        "acoes_validas": ["criar", "deletar", "ligar", "desligar", "ajustar"],
    },
    "pesquisar_web": {
        "palavras": ["pesquisa", "busca", "procura", "google", "web"],
        "acoes_validas": ["pesquisar"],
    },
    "enviar_mensagem": {
        "palavras": ["mensagem", "whatsapp", "zap", "msg", "torpedo"],
        "acoes_validas": ["enviar"],
    },
    "memorizar": {
        "palavras": ["lembra", "guarda", "memoriza", "anota", "salva na memória"],
        "acoes_validas": ["lembrar"],
    },
    "gerenciar_arquivo": {
        "palavras": ["pasta", "arquivo", "diretório", "diretorio", "documento"],
        "acoes_validas": ["criar", "deletar", "ligar"],
    },
    "controlar_gestos": {
        "palavras": ["gesto", "gestos", "controle de gesto", "mão", "mao"],
        "acoes_validas": ["ligar", "desligar"],
    },
    "seguranca": {
        "palavras": ["segurança", "seguranca", "câmera de segurança", "vigilância", "alerta"],
        "acoes_validas": ["ligar", "desligar"],
    },
    "abrir_aplicativo": {
        "palavras": ["abre", "abra", "abrindo", "inicia", "roda", "executa"],
        "acoes_validas": ["ligar", "criar"],
    },
    "fechar_aplicativo": {
        "palavras": ["fecha", "feche", "encerra", "mata", "kill"],
        "acoes_validas": ["desligar", "deletar"],
    },
}

# ═══════════════════════════════════════════════════════════════
#  CONTEXTO CONVERSACIONAL
# ═══════════════════════════════════════════════════════════════

class ContextoConversacional:
    """Mantém contexto entre comandos para resolução de referências."""

    def __init__(self, ttl_segundos: int = 120):
        self._lock = threading.Lock()
        self._ttl = ttl_segundos
        self._ultimo_comodo: Optional[str] = None
        self._ultimo_dispositivo: Optional[str] = None
        self._ultima_intencao: Optional[str] = None
        self._ultimo_tempo: float = 0
        self._historico: list = []
        self._store = DataStore("nlu_contexto", default={
            "ultimo_comodo": None,
            "ultimo_dispositivo": None,
            "ultima_intencao": None,
            "historico": [],
        })
        self._carregar()

    def _carregar(self):
        dados = self._store.load()
        self._ultimo_comodo = dados.get("ultimo_comodo")
        self._ultimo_dispositivo = dados.get("ultimo_dispositivo")
        self._ultima_intencao = dados.get("ultima_intencao")
        self._historico = dados.get("historico", [])[-20:]

    def _salvar(self):
        self._store.save({
            "ultimo_comodo": self._ultimo_comodo,
            "ultimo_dispositivo": self._ultimo_dispositivo,
            "ultima_intencao": self._ultima_intencao,
            "historico": self._historico[-20:],
        })

    def _expirado(self) -> bool:
        return (time.time() - self._ultimo_tempo) > self._ttl

    def atualizar(self, intencao: IntencaoResolvida):
        with self._lock:
            self._ultimo_tempo = time.time()
            self._ultima_intencao = intencao.intencao
            if intencao.slots.get("comodo"):
                self._ultimo_comodo = intencao.slots["comodo"]
            if intencao.slots.get("dispositivo"):
                self._ultimo_dispositivo = intencao.slots["dispositivo"]
            self._historico.append({
                "intencao": intencao.intencao,
                "slots": intencao.slots,
                "timestamp": agora_brasil_iso(),
            })
            self._salvar()

    def resolver_contexto(self, intencao: IntencaoResolvida) -> IntencaoResolvida:
        with self._lock:
            if self._expirado():
                return intencao
            if not intencao.slots.get("comodo") and self._ultimo_comodo:
                intencao.slots["comodo"] = self._ultimo_comodo
                intencao.confianca *= 0.9
            if not intencao.slots.get("dispositivo") and self._ultimo_dispositivo:
                intencao.slots["dispositivo"] = self._ultimo_dispositivo
                intencao.confianca *= 0.9
            return intencao

    @property
    def ultimo_comodo(self):
        return self._ultimo_comodo if not self._expirado() else None

    @property
    def ultimo_dispositivo(self):
        return self._ultimo_dispositivo if not self._expirado() else None

    @property
    def ultima_intencao(self):
        return self._ultima_intencao if not self._expirado() else None

    def resumo(self) -> str:
        if self._expirado():
            return "Sem contexto ativo."
        partes = []
        if self._ultimo_comodo:
            partes.append(f"Cômodo: {self._ultimo_comodo}")
        if self._ultimo_dispositivo:
            partes.append(f"Dispositivo: {self._ultimo_dispositivo}")
        if self._ultima_intencao:
            partes.append(f"Última intenção: {self._ultima_intencao}")
        return " | ".join(partes) if partes else "Contexto vazio."


# ═══════════════════════════════════════════════════════════════
#  NLU ENGINE — Motor Principal
# ═══════════════════════════════════════════════════════════════

# Singleton do contexto
_contexto = ContextoConversacional(ttl_segundos=120)


def _normalizar(texto: str) -> str:
    """Normaliza texto removendo acentos extras e pontuação."""
    texto = texto.lower().strip()
    texto = re.sub(r"[!?.,;:]+$", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _resolver_acao(texto: str) -> Optional[str]:
    """Resolve a ação principal do texto usando sinônimos."""
    for acao_canonica, sinonimos in SINONIMOS_ACAO.items():
        for sin in sinonimos:
            pattern = r"(?:^|\s)" + re.escape(sin) + r"(?:\s|$|[aeiou])"
            if re.search(pattern, texto):
                return acao_canonica
        if re.search(r"(?:^|\s)" + re.escape(acao_canonica) + r"(?:\s|$)", texto):
            return acao_canonica
    return None


def _resolver_comodo(texto: str) -> Optional[str]:
    """Extrai o cômodo do texto usando sinônimos."""
    for comodo_canonico, sinonimos in SINONIMOS_COMODO.items():
        for sin in sorted(sinonimos, key=len, reverse=True):
            if sin in texto:
                return comodo_canonico
        if comodo_canonico in texto:
            return comodo_canonico
    return None


def _resolver_dispositivo(texto: str) -> Optional[str]:
    """Extrai o dispositivo do texto usando sinônimos com word-boundary."""
    melhor = None
    melhor_len = 0
    for disp_canonico, sinonimos in SINONIMOS_DISPOSITIVO.items():
        for sin in sinonimos:
            # Usar word boundary para evitar match parcial (ex: "ar" em "fraca")
            pattern = r"(?:^|\b)" + re.escape(sin) + r"(?:\b|$)"
            if re.search(pattern, texto) and len(sin) > melhor_len:
                melhor = disp_canonico
                melhor_len = len(sin)
        pattern = r"(?:^|\b)" + re.escape(disp_canonico) + r"(?:\b|$)"
        if re.search(pattern, texto) and len(disp_canonico) > melhor_len:
            melhor = disp_canonico
            melhor_len = len(disp_canonico)
    return melhor


def _resolver_intensidade(texto: str) -> Optional[int]:
    """Extrai valor de intensidade do texto."""
    # Porcentagem explícita
    m = re.search(r"(\d{1,3})\s*%", texto)
    if m:
        return min(100, max(0, int(m.group(1))))

    # Valor numérico solto (ex: "brilho 70", "volume 50")
    m = re.search(r"(?:em|para|no|na|a)\s+(\d{1,3})(?:\s|$)", texto)
    if m:
        val = int(m.group(1))
        if 0 <= val <= 100:
            return val

    # Incremento/decremento relativo
    m = re.search(r"[+\-]\s*(\d{1,3})\s*%?", texto)
    if m:
        return int(m.group(1))

    # Palavras-chave de intensidade
    for valor, palavras in SINONIMOS_INTENSIDADE.items():
        for p in palavras:
            if p in texto:
                return valor

    return None


def _resolver_intencao(texto: str, acao: Optional[str]) -> Optional[str]:
    """Identifica a intenção do comando."""
    melhor_intencao = None
    melhor_score = 0

    for intent_name, config in INTENCOES.items():
        score = 0
        for palavra in config["palavras"]:
            if palavra in texto:
                score += len(palavra)
        if acao and acao in config["acoes_validas"]:
            score += 5
        if score > melhor_score:
            melhor_score = score
            melhor_intencao = intent_name

    return melhor_intencao


def _extrair_alvo_texto(texto: str) -> Optional[str]:
    """Extrai alvo genérico (nome de app, contato, música, etc)."""
    # "abre o X", "toca X", "pesquisa X"
    patterns = [
        r"(?:abre|abra|inicia|executa|roda)\s+(?:o\s+|a\s+)?(.+?)(?:\s+no|\s+na|\s+do|\s+da|$)",
        r"(?:toca|reproduz|coloca)\s+(?:a?\s*música?\s*)?(.+?)(?:\s+no|\s+na|$)",
        r"(?:pesquisa|busca|procura|google)\s+(.+?)(?:\s+no|\s+na|$)",
        r"(?:envia|manda)\s+(?:mensagem\s+)?(?:para?\s+)?(.+?)(?:\s+dizendo|\s+falando|$)",
    ]
    for p in patterns:
        m = re.search(p, texto)
        if m:
            return m.group(1).strip()
    return None


# ═══════════════════════════════════════════════════════════════
#  DECOMPOSIÇÃO DE COMANDOS COMPOSTOS
# ═══════════════════════════════════════════════════════════════

_SEPARADORES = re.compile(
    r"\s+(?:e\s+(?:também\s+)?|depois\s+|e\s+depois\s+|aí\s+|então\s+|,\s*e?\s*)"
)


def decompor_comando(texto: str) -> list[str]:
    """Decompõe comando composto em sub-comandos."""
    texto = _normalizar(texto)
    partes = _SEPARADORES.split(texto)
    partes = [p.strip() for p in partes if p.strip() and len(p.strip()) > 2]
    return partes if partes else [texto]


# ═══════════════════════════════════════════════════════════════
#  API PÚBLICA
# ═══════════════════════════════════════════════════════════════

def interpretar_comando(texto: str) -> dict:
    """
    Interpreta um comando em linguagem natural.

    Retorna dict com:
        sucesso: bool
        intencao: str
        slots: dict
        sub_acoes: list (se composto)
        confianca: float
        contexto: str (contexto atual)
    """
    texto_original = texto
    texto = _normalizar(texto)

    # Decompor comandos compostos
    sub_textos = decompor_comando(texto)
    is_composto = len(sub_textos) > 1

    resultados = []

    for sub in sub_textos:
        acao = _resolver_acao(sub)
        comodo = _resolver_comodo(sub)
        dispositivo = _resolver_dispositivo(sub)
        intensidade = _resolver_intensidade(sub)
        intencao_nome = _resolver_intencao(sub, acao)
        alvo = _extrair_alvo_texto(sub)

        slots = {}
        if acao:
            slots["acao"] = acao
        if comodo:
            slots["comodo"] = comodo
        if dispositivo:
            slots["dispositivo"] = dispositivo
        if intensidade is not None:
            slots["intensidade"] = intensidade
        if alvo:
            slots["alvo"] = alvo

        confianca = 0.0
        if intencao_nome:
            confianca += 0.4
        if acao:
            confianca += 0.3
        if comodo or dispositivo:
            confianca += 0.2
        if intensidade is not None:
            confianca += 0.1

        resultado = IntencaoResolvida(
            intencao=intencao_nome or "desconhecida",
            slots=slots,
            texto_original=sub,
            confianca=min(1.0, confianca),
        )

        # Resolver contexto conversacional
        resultado = _contexto.resolver_contexto(resultado)
        resultados.append(resultado)

    # Atualizar contexto com o último resultado
    if resultados:
        _contexto.atualizar(resultados[-1])

    if is_composto:
        principal = IntencaoResolvida(
            intencao="comando_composto",
            slots={"total_subcomandos": len(resultados)},
            texto_original=texto_original,
            confianca=min(r.confianca for r in resultados),
            sub_acoes=resultados,
        )
        return {
            "sucesso": True,
            "composto": True,
            "intencao": "comando_composto",
            "slots": {"total_subcomandos": len(resultados)},
            "sub_acoes": [r.to_dict() for r in resultados],
            "confianca": principal.confianca,
            "contexto": _contexto.resumo(),
        }

    r = resultados[0]
    return {
        "sucesso": r.intencao != "desconhecida",
        "composto": False,
        "intencao": r.intencao,
        "slots": r.slots,
        "sub_acoes": [],
        "confianca": r.confianca,
        "contexto": _contexto.resumo(),
    }


def executar_nlu(texto: str) -> str:
    """Wrapper que retorna string formatada para o agente."""
    resultado = interpretar_comando(texto)

    if not resultado["sucesso"] and not resultado.get("composto"):
        return (
            f"⚠️ Não consegui interpretar completamente: '{texto}'\n"
            f"Contexto atual: {resultado['contexto']}\n"
            f"Slots parciais: {json.dumps(resultado['slots'], ensure_ascii=False)}"
        )

    linhas = [f"✅ Comando interpretado (confiança: {resultado['confianca']:.0%})"]
    linhas.append(f"   Intenção: {resultado['intencao']}")
    linhas.append(f"   Slots: {json.dumps(resultado['slots'], ensure_ascii=False)}")

    if resultado.get("composto") and resultado.get("sub_acoes"):
        linhas.append(f"\n📋 Comando composto — {len(resultado['sub_acoes'])} sub-ações:")
        for i, sub in enumerate(resultado["sub_acoes"], 1):
            linhas.append(f"   {i}. [{sub['intencao']}] {json.dumps(sub['slots'], ensure_ascii=False)}")

    linhas.append(f"\n🧠 Contexto: {resultado['contexto']}")
    return "\n".join(linhas)


def contexto_atual() -> str:
    """Retorna resumo do contexto conversacional."""
    return _contexto.resumo()


def limpar_contexto() -> str:
    """Limpa o contexto conversacional."""
    global _contexto
    _contexto = ContextoConversacional(ttl_segundos=120)
    return "✅ Contexto conversacional limpo."


def historico_comandos(quantidade: int = 10) -> str:
    """Retorna histórico dos últimos comandos interpretados."""
    dados = _contexto._store.load()
    hist = dados.get("historico", [])[-quantidade:]
    if not hist:
        return "Nenhum comando no histórico."
    linhas = [f"📜 Últimos {len(hist)} comandos:"]
    for i, h in enumerate(hist, 1):
        linhas.append(f"  {i}. [{h.get('intencao', '?')}] {json.dumps(h.get('slots', {}), ensure_ascii=False)}")
    return "\n".join(linhas)
