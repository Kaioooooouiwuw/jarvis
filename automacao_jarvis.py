#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  JARVIS Casa Inteligente — Módulo de Automação Completo
  v5.0 — RGB + Controle de Sistema + Arquivos + Aplicativos
═══════════════════════════════════════════════════════════════
"""

import asyncio
import aiohttp
import os
import re
import shutil
import webbrowser
import zipfile
import subprocess
import urllib.parse
from dotenv import load_dotenv

# ── Dependências Windows (volume/brilho) ─────────────────────
try:
    from pycaw.pycaw import AudioUtilities
    _PYCAW_OK = True
except ImportError:
    _PYCAW_OK = False

try:
    import screen_brightness_control as sbc
    _SBC_OK = True
except ImportError:
    _SBC_OK = False

load_dotenv()

# ─────────────────────────────────────────────────────────────
#  CONSTANTES — Paleta de cores nomeadas (RGB)
# ─────────────────────────────────────────────────────────────

CORES_NOMEADAS: dict[str, list[int]] = {
    # Cores primárias e básicas
    "vermelho":     [255,   0,   0],
    "verde":        [  0, 255,   0],
    "azul":         [  0,   0, 255],
    "branco":       [255, 255, 255],
    "preto":        [  0,   0,   0],
    # Cores secundárias
    "amarelo":      [255, 255,   0],
    "ciano":        [  0, 255, 255],
    "magenta":      [255,   0, 255],
    # Cores populares
    "roxo":         [128,   0, 128],
    "violeta":      [148,   0, 211],
    "rosa":         [255, 105, 180],
    "laranja":      [255, 165,   0],
    "salmao":       [250, 128, 114],
    "coral":        [255, 127,  80],
    "dourado":      [255, 215,   0],
    "marrom":       [139,  69,  19],
    "bege":         [245, 245, 220],
    "cinza":        [128, 128, 128],
    "lima":         [191, 255,   0],
    "turquesa":     [ 64, 224, 208],
    "indigo":       [ 75,   0, 130],
    "lavanda":      [230, 230, 250],
    "menta":        [152, 255, 152],
    "pêssego":      [255, 218, 185],
    "pessego":      [255, 218, 185],
    # Tons de branco quente/frio
    "branco quente": [255, 200, 120],
    "branco frio":   [220, 230, 255],
}

# ─────────────────────────────────────────────────────────────
#  PRESETS DE AMBIENTE
# ─────────────────────────────────────────────────────────────

MODOS_AMBIENTE: dict[str, list[int] | str] = {
    "gamer":       [  0, 255, 255],   # Ciano elétrico
    "romantico":   [255,  50,  50],   # Vermelho suave
    "cinema":      [  0,   0,  80],   # Azul escuro
    "festa":       "colorloop",       # Modo colorido dinâmico (HA nativo)
    "relaxar":     [255, 180,  80],   # Laranja quente
    "leitura":     [255, 240, 200],   # Branco quente
    "concentrar":  [200, 220, 255],   # Azul frio
    "energia":     [255, 255,   0],   # Amarelo vibrante
    "natureza":    [ 80, 200,  80],   # Verde suave
    "aurora":      [  0, 255, 128],   # Verde-azulado
}

# ─────────────────────────────────────────────────────────────
#  MAPEAMENTO DE CÔMODOS → entity_id (ajuste conforme seu HA)
# ─────────────────────────────────────────────────────────────

COMODOS_MAPA: dict[str, str] = {
    "sala":        "light.sala",
    "quarto":      "light.quarto",
    "cozinha":     "light.cozinha",
    "banheiro":    "light.banheiro",
    "escritorio":  "light.escritorio",
    "garagem":     "light.garagem",
    "varanda":     "light.varanda",
    "corredor":    "light.corredor",
    "lavanderia":  "light.lavanderia",
}


# ═══════════════════════════════════════════════════════════════
#  PARSING DE CORES
# ═══════════════════════════════════════════════════════════════

def interpretar_cor(comando: str) -> list[int] | None:
    """
    Interpreta uma cor a partir de texto em português.

    Suporta:
      - Nomes comuns: 'azul', 'vermelho', 'branco quente', etc.
      - Modos de ambiente: 'romantico', 'gamer', etc.

    Retorna lista [R, G, B] ou None se não reconhecido.
    """
    texto = comando.lower().strip()

    # Verificar modos de ambiente (retornam RGB fixo, não colorloop)
    for modo, valor in MODOS_AMBIENTE.items():
        if modo in texto and isinstance(valor, list):
            return valor

    # Verificar cores de dois tokens (ex: "branco quente")
    for nome, rgb in CORES_NOMEADAS.items():
        if nome in texto:
            return rgb

    return None


def parse_color_input(texto: str) -> list[int] | None:
    """
    Parser universal de cores. Aceita:
      1. Nomes em português        → "azul", "roxo"
      2. RGB direto                → "rgb 255 100 50" ou "255 100 50"
      3. HEX com #                 → "#ff5733" ou "ff5733"
      4. Modos de ambiente         → "gamer", "cinema"

    Retorna [R, G, B] (0–255 cada) ou None.
    """
    texto = texto.lower().strip()

    # ── 1. Cor nomeada ou modo ───────────────────────────────
    resultado = interpretar_cor(texto)
    if resultado:
        return resultado

    # ── 2. HEX (#rrggbb ou rrggbb) ──────────────────────────
    hex_match = re.search(r"#?([0-9a-f]{6})", texto)
    if hex_match:
        h = hex_match.group(1)
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]

    # ── 3. RGB numérico (ex: "rgb 255 0 128" ou "255 0 128") ─
    rgb_match = re.search(r"(?:rgb\s*)?(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})", texto)
    if rgb_match:
        r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
        if all(0 <= v <= 255 for v in [r, g, b]):
            return [r, g, b]

    return None


def validar_rgb(rgb: list[int]) -> list[int]:
    """Garante que cada canal está no intervalo [0, 255]."""
    return [max(0, min(255, int(v))) for v in rgb]


# ═══════════════════════════════════════════════════════════════
#  INTEGRAÇÃO COM HOME ASSISTANT
# ═══════════════════════════════════════════════════════════════

def _headers() -> dict:
    token = os.getenv("HOMEASSISTANT_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

def _base_url() -> str:
    url = os.getenv("HOMEASSISTANT_URL", "http://homeassistant.local:8123")
    return url.rstrip("/")


async def set_light_color(
    entity_id: str,
    rgb: list[int],
    brightness: int | None = None,
    transition: float | None = None,
) -> dict:
    """
    Define a cor de uma lâmpada RGB via Home Assistant.

    Parâmetros:
        entity_id  — Ex: 'light.sala'
        rgb        — Lista [R, G, B] com valores 0–255
        brightness — Brilho de 0 a 255 (opcional)
        transition — Duração da transição em segundos (opcional)

    Retorna dict com:
        sucesso   : bool
        mensagem  : str
        entity_id : str
        rgb       : list[int]
    """
    rgb = validar_rgb(rgb)
    url = f"{_base_url()}/api/services/light/turn_on"

    payload: dict = {
        "entity_id": entity_id,
        "rgb_color": rgb,
    }
    if brightness is not None:
        payload["brightness"] = max(0, min(255, int(brightness)))
    if transition is not None:
        payload["transition"] = transition

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return {
                        "sucesso": True,
                        "mensagem": f"✅ Cor {rgb} aplicada em {entity_id}",
                        "entity_id": entity_id,
                        "rgb": rgb,
                    }
                else:
                    texto = await resp.text()
                    return {
                        "sucesso": False,
                        "mensagem": f"❌ Erro HTTP {resp.status}: {texto}",
                        "entity_id": entity_id,
                        "rgb": rgb,
                    }

    except aiohttp.ClientConnectorError:
        return {
            "sucesso": False,
            "mensagem": "❌ Não foi possível conectar ao Home Assistant. Verifique a URL no .env.",
            "entity_id": entity_id,
            "rgb": rgb,
        }
    except asyncio.TimeoutError:
        return {
            "sucesso": False,
            "mensagem": "❌ Timeout: Home Assistant não respondeu em 10s.",
            "entity_id": entity_id,
            "rgb": rgb,
        }
    except Exception as e:
        return {
            "sucesso": False,
            "mensagem": f"❌ Erro inesperado: {e}",
            "entity_id": entity_id,
            "rgb": rgb,
        }


async def set_light_effect(entity_id: str, effect: str) -> dict:
    """
    Aplica um efeito especial na luz (ex: 'colorloop').
    Usado para o modo 'festa'.
    """
    url = f"{_base_url()}/api/services/light/turn_on"
    payload = {"entity_id": entity_id, "effect": effect}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return {"sucesso": True, "mensagem": f"✅ Efeito '{effect}' ativado em {entity_id}"}
                else:
                    return {"sucesso": False, "mensagem": f"❌ Erro {resp.status} ao aplicar efeito"}
    except Exception as e:
        return {"sucesso": False, "mensagem": f"❌ Erro: {e}"}


async def verificar_suporte_rgb(entity_id: str) -> dict:
    """
    Consulta o Home Assistant para verificar se a luz suporta RGB.

    Retorna dict com:
        suporta_rgb   : bool
        modos         : list[str]  — ex: ['color_temp', 'rgb']
        estado_atual  : str
        rgb_atual     : list[int] | None
    """
    url = f"{_base_url()}/api/states/{entity_id}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    dados = await resp.json()
                    atributos = dados.get("attributes", {})
                    modos = atributos.get("supported_color_modes", [])
                    suporta = any(m in modos for m in ["rgb", "rgbw", "rgbww", "hs", "xy"])
                    return {
                        "sucesso": True,
                        "suporta_rgb": suporta,
                        "modos": modos,
                        "estado_atual": dados.get("state", "unknown"),
                        "rgb_atual": atributos.get("rgb_color"),
                        "nome_amigavel": atributos.get("friendly_name", entity_id),
                    }
                elif resp.status == 404:
                    return {"sucesso": False, "mensagem": f"❌ Entidade '{entity_id}' não encontrada"}
                else:
                    return {"sucesso": False, "mensagem": f"❌ Erro HTTP {resp.status}"}
    except Exception as e:
        return {"sucesso": False, "mensagem": f"❌ Erro: {e}"}


# ═══════════════════════════════════════════════════════════════
#  PARSER DE COMANDOS NATURAIS
# ═══════════════════════════════════════════════════════════════

# Verbos de cor que ativam o parser
_VERBOS_COR = (
    r"coloca|deixa|muda|define|troca|ativa|acende|seta|bota|"
    r"coloque|deixe|mude|defina|troque|ative|acenda"
)

# Preposições entre ação e destino
_PREPS = r"(?:para|em|na|no|com|a)?\s*"


def extrair_comodo(texto: str) -> str | None:
    """Extrai nome do cômodo a partir do texto do comando."""
    texto = texto.lower()
    for comodo in sorted(COMODOS_MAPA.keys(), key=len, reverse=True):
        if comodo in texto:
            return comodo
    return None


def parse_comando_cor(comando: str) -> dict | None:
    """
    Interpreta comandos naturais de cor para lâmpadas.

    Exemplos reconhecidos:
      "deixa a luz da sala azul"
      "muda a luz do quarto para vermelho"
      "coloca luz roxa no escritório"
      "luz rgb 255 0 255 na sala"
      "define cor #00ffcc na cozinha"
      "ativa modo gamer na sala"
      "modo romantico no quarto"

    Retorna dict com:
        entity_id : str
        rgb       : list[int]
        modo      : str | None   — se for efeito especial como 'colorloop'
        comodo    : str
    Ou None se não reconhecido.
    """
    texto = comando.lower().strip()

    # ── Detectar cômodo ─────────────────────────────────────
    comodo = extrair_comodo(texto)
    entity_id = COMODOS_MAPA.get(comodo) if comodo else None

    # ── Detectar modo de ambiente especial (colorloop etc.) ─
    for modo_nome, valor in MODOS_AMBIENTE.items():
        if modo_nome in texto:
            if isinstance(valor, str):
                # Ex: "festa" → colorloop
                return {
                    "entity_id": entity_id,
                    "rgb": None,
                    "modo": valor,
                    "comodo": comodo,
                }
            else:
                return {
                    "entity_id": entity_id,
                    "rgb": valor,
                    "modo": None,
                    "comodo": comodo,
                }

    # ── Detectar cor por HEX, RGB numérico ou nome ──────────
    rgb = parse_color_input(texto)
    if rgb:
        return {
            "entity_id": entity_id,
            "rgb": rgb,
            "modo": None,
            "comodo": comodo,
        }

    return None


# ═══════════════════════════════════════════════════════════════
#  EXECUTOR PRINCIPAL DE COMANDOS
# ═══════════════════════════════════════════════════════════════

async def executar_comando_cor(
    comando: str,
    entity_id_override: str | None = None,
    brightness: int | None = None,
    transition: float | None = 1.0,
) -> dict:
    """
    Ponto de entrada principal para comandos de cor do JARVIS.

    Parâmetros:
        comando             — Texto natural ou entidade direta
        entity_id_override  — Força uma entidade específica (ignora cômodo)
        brightness          — Brilho 0–255
        transition          — Transição em segundos

    Exemplos:
        await executar_comando_cor("deixa a luz da sala azul")
        await executar_comando_cor("luz rgb 255 0 255", "light.quarto")
        await executar_comando_cor("modo gamer", "light.escritorio")
    """
    parsed = parse_comando_cor(comando)

    if not parsed:
        # Tentar parse direto de cor (sem cômodo no texto)
        rgb = parse_color_input(comando)
        if rgb and entity_id_override:
            parsed = {"entity_id": entity_id_override, "rgb": rgb, "modo": None, "comodo": None}
        else:
            return {
                "sucesso": False,
                "mensagem": f"❌ Não entendi o comando de cor: '{comando}'",
            }

    # Prioridade: entity_id_override > mapa de cômodos
    entity_id = entity_id_override or parsed.get("entity_id")

    if not entity_id:
        comodo = parsed.get("comodo")
        return {
            "sucesso": False,
            "mensagem": (
                f"❌ Cômodo '{comodo}' não mapeado. "
                f"Disponíveis: {', '.join(COMODOS_MAPA.keys())}"
            ),
        }

    # ── Verificar suporte a RGB antes de enviar ──────────────
    suporte = await verificar_suporte_rgb(entity_id)
    if suporte.get("sucesso") and not suporte.get("suporta_rgb"):
        modos = suporte.get("modos", [])
        return {
            "sucesso": False,
            "mensagem": (
                f"⚠️ '{entity_id}' não suporta RGB. "
                f"Modos disponíveis: {modos}"
            ),
        }

    # ── Aplicar efeito ou cor ────────────────────────────────
    modo = parsed.get("modo")
    if modo:
        return await set_light_effect(entity_id, modo)

    rgb = parsed.get("rgb")
    if rgb:
        return await set_light_color(entity_id, rgb, brightness=brightness, transition=transition)

    return {"sucesso": False, "mensagem": "❌ Nenhuma cor identificada no comando."}


# ═══════════════════════════════════════════════════════════════
#  UTILITÁRIOS EXTRAS
# ═══════════════════════════════════════════════════════════════

def listar_cores_disponiveis() -> str:
    """Retorna string formatada com todas as cores suportadas."""
    linhas = ["🎨 Cores disponíveis:\n"]
    for nome, rgb in sorted(CORES_NOMEADAS.items()):
        r, g, b = rgb
        linhas.append(f"  • {nome:<20} → RGB({r:3}, {g:3}, {b:3})  |  #{r:02x}{g:02x}{b:02x}")
    linhas.append("\n🎭 Modos de ambiente:")
    for modo, valor in MODOS_AMBIENTE.items():
        if isinstance(valor, list):
            r, g, b = valor
            linhas.append(f"  • {modo:<20} → RGB({r:3}, {g:3}, {b:3})")
        else:
            linhas.append(f"  • {modo:<20} → Efeito: {valor}")
    return "\n".join(linhas)


def rgb_para_hex(rgb: list[int]) -> str:
    """Converte [R, G, B] para string '#rrggbb'."""
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, v)) for v in rgb])


# ═══════════════════════════════════════════════════════════════
#  JARVIS CONTROL — Sistema, Arquivos e Aplicativos (Windows)
# ═══════════════════════════════════════════════════════════════

class JarvisControl:
    """
    Controle local do sistema operacional Windows:
      • Manipulação de arquivos e pastas
      • Controle de volume e brilho
      • Abertura de aplicativos e sites
      • Gestão de energia do PC

    Todas as operações de I/O pesadas devem ser chamadas via
    asyncio.to_thread() quando usadas em contexto assíncrono.
    """

    def __init__(self):
        self.shortcuts = {
            "youtube":   "https://www.youtube.com",
            "github":    "https://www.github.com",
            "chatgpt":   "https://chat.openai.com",
            "google":    "https://www.google.com",
            "instagram": "https://www.instagram.com",
        }
        self.home      = os.path.expanduser("~")
        self.desktop   = os.path.join(self.home, "Desktop")
        self.documents = os.path.join(self.home, "Documents")
        self.downloads = os.path.join(self.home, "Downloads")

        self.base_folders = {
            "area de trabalho": self.desktop,
            "área de trabalho": self.desktop,
            "desktop":          self.desktop,
            "documentos":       self.documents,
            "documents":        self.documents,
            "downloads":        self.downloads,
        }
        self.ignore_folders = {
            "venv", ".venv", "env", "node_modules",
            "__pycache__", ".git", ".idea", ".vscode",
        }

    # ──────────────────────────────────────────────────────────
    #  UTILITÁRIOS INTERNOS
    # ──────────────────────────────────────────────────────────

    def _resolver_caminho(self, caminho: str) -> str:
        """Resolve aliases de pastas comuns e caminhos relativos."""
        caminho       = caminho.strip("'\"").replace("\\", "/")
        caminho_lower = caminho.lower()
        for alias, real_path in self.base_folders.items():
            if caminho_lower == alias:
                return real_path
            if caminho_lower.startswith(alias + "/"):
                return os.path.abspath(
                    os.path.join(real_path, caminho[len(alias) + 1:])
                )
        if not os.path.isabs(caminho) and not caminho.startswith("."):
            return os.path.abspath(os.path.join(self.desktop, caminho))
        return os.path.abspath(os.path.expanduser(caminho))

    def _walk_seguro(self, base: str):
        """os.walk ignorando pastas de ambiente virtual e build."""
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [
                d for d in dirnames
                if d not in self.ignore_folders and not d.startswith(".")
            ]
            yield dirpath, dirnames, filenames

    # ──────────────────────────────────────────────────────────
    #  MANIPULAÇÃO DE ARQUIVOS E PASTAS
    # ──────────────────────────────────────────────────────────

    def cria_pasta(self, caminho: str) -> str:
        try:
            caminho_abs = self._resolver_caminho(caminho)
            os.makedirs(caminho_abs, exist_ok=True)
            return f"✅ Pasta criada: {caminho_abs}"
        except Exception as e:
            return f"❌ Erro ao criar pasta: {e}"

    def abrir_pasta(self, nome_pasta: str) -> str:
        try:
            caminho_direto = self.base_folders.get(nome_pasta.lower())
            if caminho_direto and os.path.exists(caminho_direto):
                os.startfile(caminho_direto)
                return f"✅ Abrindo {nome_pasta}."
            for _, base_path in self.base_folders.items():
                for dirpath, dirnames, _ in self._walk_seguro(base_path):
                    for d in dirnames:
                        if d.lower() == nome_pasta.lower():
                            full_path = os.path.join(dirpath, d)
                            os.startfile(full_path)
                            return f"✅ Pasta aberta: {full_path}"
            return f"❌ Pasta '{nome_pasta}' não encontrada."
        except Exception as e:
            return f"❌ Erro ao abrir pasta: {e}"

    def buscar_e_abrir_arquivo(self, nome_arquivo: str) -> str:
        try:
            for _, base_path in self.base_folders.items():
                for dirpath, _, filenames in self._walk_seguro(base_path):
                    for f in filenames:
                        if nome_arquivo.lower() in f.lower():
                            full_path = os.path.join(dirpath, f)
                            os.startfile(full_path)
                            return f"✅ Arquivo aberto: {full_path}"
            return f"❌ Arquivo '{nome_arquivo}' não encontrado."
        except Exception as e:
            return f"❌ Erro ao buscar arquivo: {e}"

    def deletar_arquivo(self, caminho: str) -> str:
        try:
            path_abs = self._resolver_caminho(caminho)
            if os.path.isfile(path_abs):
                os.remove(path_abs)
                return f"✅ Arquivo deletado: {path_abs}"
            elif os.path.isdir(path_abs):
                shutil.rmtree(path_abs)
                return f"✅ Diretório deletado: {path_abs}"
            return f"❌ Caminho não encontrado: {path_abs}"
        except Exception as e:
            return f"❌ Erro ao deletar: {e}"

    def limpar_diretorio(self, caminho: str) -> str:
        try:
            path_abs = self._resolver_caminho(caminho)
            if os.path.exists(path_abs):
                for item in os.listdir(path_abs):
                    item_path = os.path.join(path_abs, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                return f"✅ Diretório limpo: {path_abs}"
            return "❌ Diretório não encontrado."
        except Exception as e:
            return f"❌ Erro ao limpar diretório: {e}"

    def mover_item(self, origem: str, destino: str) -> str:
        try:
            shutil.move(
                self._resolver_caminho(origem),
                self._resolver_caminho(destino),
            )
            return f"✅ Item movido para {destino}."
        except Exception as e:
            return f"❌ Erro ao mover: {e}"

    def copiar_item(self, origem: str, destino: str) -> str:
        try:
            origem_abs  = self._resolver_caminho(origem)
            destino_abs = self._resolver_caminho(destino)
            if os.path.isdir(origem_abs):
                shutil.copytree(origem_abs, destino_abs)
            else:
                shutil.copy2(origem_abs, destino_abs)
            return f"✅ Copiado para {destino_abs}."
        except Exception as e:
            return f"❌ Erro ao copiar: {e}"

    def renomear_item(self, caminho: str, novo_nome: str) -> str:
        try:
            path_abs    = self._resolver_caminho(caminho)
            novo_caminho = os.path.join(os.path.dirname(path_abs), novo_nome)
            os.rename(path_abs, novo_caminho)
            return f"✅ Renomeado para {novo_nome}."
        except Exception as e:
            return f"❌ Erro ao renomear: {e}"

    def organizar_pasta(self, caminho: str) -> str:
        """Organiza arquivos em subpastas por tipo (Imagens, Documentos, etc.)."""
        try:
            path_abs = self._resolver_caminho(caminho)
            extensoes = {
                "Imagens":      [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
                "Documentos":   [".pdf", ".doc", ".docx", ".txt", ".xlsx", ".pptx", ".csv"],
                "Videos":       [".mp4", ".mkv", ".avi", ".mov"],
                "Musicas":      [".mp3", ".wav", ".flac"],
                "Compactados":  [".zip", ".rar", ".7z"],
                "Executaveis":  [".exe", ".msi", ".bat"],
            }
            for item in os.listdir(path_abs):
                item_path = os.path.join(path_abs, item)
                if not os.path.isfile(item_path):
                    continue
                ext    = os.path.splitext(item)[1].lower()
                movido = False
                for pasta, exts in extensoes.items():
                    if ext in exts:
                        pasta_destino = os.path.join(path_abs, pasta)
                        os.makedirs(pasta_destino, exist_ok=True)
                        shutil.move(item_path, os.path.join(pasta_destino, item))
                        movido = True
                        break
                if not movido:
                    outros = os.path.join(path_abs, "Outros")
                    os.makedirs(outros, exist_ok=True)
                    shutil.move(item_path, os.path.join(outros, item))
            return "✅ Pasta organizada com sucesso."
        except Exception as e:
            return f"❌ Erro ao organizar pasta: {e}"

    def compactar_pasta(self, caminho: str) -> str:
        try:
            path_abs = self._resolver_caminho(caminho).rstrip("/\\")
            shutil.make_archive(path_abs, "zip", path_abs)
            return f"✅ Compactado em: {path_abs}.zip"
        except Exception as e:
            return f"❌ Erro ao compactar: {e}"

    def abrir_arquivo(self, caminho: str) -> str:
        try:
            path_abs = self._resolver_caminho(caminho)
            if os.path.exists(path_abs):
                os.startfile(path_abs)
                return f"✅ Abrindo: {path_abs}"
            return f"❌ Arquivo não encontrado: {path_abs}"
        except Exception as e:
            return f"❌ Erro ao abrir arquivo: {e}"

    # ──────────────────────────────────────────────────────────
    #  CONTROLE DE SISTEMA (Volume, Brilho, Energia)
    # ──────────────────────────────────────────────────────────

    def controle_volume(self, nivel: int) -> str:
        """Define o volume do sistema entre 0 e 100."""
        if not _PYCAW_OK:
            return "❌ pycaw não instalado. Execute: pip install pycaw"
        try:
            nivel = max(0, min(100, int(nivel)))
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            volume.SetMasterVolumeLevelScalar(nivel / 100, None)
            return f"✅ Volume ajustado para {nivel}%."
        except Exception as e:
            return f"❌ Erro ao ajustar volume: {e}"

    def obter_volume(self) -> int:
        """Retorna o volume atual do sistema (0-100)."""
        if not _PYCAW_OK:
            return -1
        try:
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            nivel = volume.GetMasterVolumeLevelScalar()
            return int(round(nivel * 100))
        except Exception:
            return -1

    def aumentar_volume(self, passo: int = 10) -> str:
        """Aumenta o volume do sistema em 'passo' porcentagem."""
        atual = self.obter_volume()
        if atual < 0:
            return "❌ Não foi possível obter o volume atual."
        novo = min(100, atual + passo)
        return self.controle_volume(novo)

    def diminuir_volume(self, passo: int = 10) -> str:
        """Diminui o volume do sistema em 'passo' porcentagem."""
        atual = self.obter_volume()
        if atual < 0:
            return "❌ Não foi possível obter o volume atual."
        novo = max(0, atual - passo)
        return self.controle_volume(novo)

    def controle_brilho(self, nivel: int) -> str:
        """Define o brilho da tela entre 0 e 100."""
        if not _SBC_OK:
            return "❌ screen_brightness_control não instalado. Execute: pip install screen-brightness-control"
        try:
            nivel = max(0, min(100, int(nivel)))
            sbc.set_brightness(nivel)
            return f"✅ Brilho ajustado para {nivel}%."
        except Exception as e:
            return f"❌ Erro ao ajustar brilho: {e}"

    def energia_pc(self, acao: str) -> str:
        """Ações de energia: 'desligar', 'reiniciar' ou 'bloquear'."""
        try:
            acoes = {
                "desligar":  lambda: os.system("shutdown /s /t 1"),
                "reiniciar": lambda: os.system("shutdown /r /t 1"),
                "bloquear":  lambda: subprocess.run(
                    ["rundll32.exe", "user32.dll,LockWorkStation"]
                ),
            }
            fn = acoes.get(acao.lower())
            if fn:
                fn()
                msgs = {
                    "desligar":  "✅ Desligando o computador.",
                    "reiniciar": "✅ Reiniciando o computador.",
                    "bloquear":  "✅ Computador bloqueado.",
                }
                return msgs[acao.lower()]
            return f"❌ Ação inválida: '{acao}'. Use: desligar, reiniciar ou bloquear."
        except Exception as e:
            return f"❌ Erro: {e}"

    # ──────────────────────────────────────────────────────────
    #  APLICATIVOS E NAVEGAÇÃO WEB
    # ──────────────────────────────────────────────────────────

    def abrir_aplicativo(self, nome_app: str) -> str:
        """Abre aplicativos do Windows por nome amigável."""
        apps = {
            "bloco de notas":        "notepad.exe",
            "calculadora":           "calc.exe",
            "paint":                 "mspaint.exe",
            "cmd":                   "cmd.exe",
            "navegador":             "msedge",
            "word":                  "winword",
            "excel":                 "excel",
            "powerpoint":            "powerpnt",
            "explorador de arquivos":"explorer.exe",
            "configuracoes":         "ms-settings:",
        }
        try:
            comando = apps.get(nome_app.lower())
            if comando:
                try:
                    os.startfile(comando)
                except Exception:
                    subprocess.Popen(["cmd", "/c", "start", "", comando], shell=True)
                return f"✅ Abrindo {nome_app}."
            # Tentativa genérica
            try:
                os.startfile(nome_app)
            except Exception:
                subprocess.Popen(["cmd", "/c", "start", "", nome_app], shell=True)
            return f"✅ Tentando abrir '{nome_app}'."
        except Exception as e:
            return f"❌ Erro ao abrir aplicativo: {e}"

    def atalhos_navegacao(self, site: str) -> str:
        """Abre sites cadastrados no navegador padrão."""
        try:
            url = self.shortcuts.get(site.lower())
            if url:
                os.startfile(url)
                return f"✅ Abrindo {site}."
            return f"❌ Site '{site}' não cadastrado. Disponíveis: {', '.join(self.shortcuts)}"
        except Exception as e:
            return f"❌ Erro ao abrir site: {e}"

    def pesquisar_no_google(self, termo: str) -> str:
        """Pesquisa um termo diretamente no Google."""
        try:
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(termo)}"
            os.startfile(url)
            return f"✅ Pesquisando por '{termo}'."
        except Exception as e:
            return f"❌ Erro ao pesquisar: {e}"

    # ──────────────────────────────────────────────────────────
    #  WRAPPERS ASSÍNCRONOS (para uso com await)
    # ──────────────────────────────────────────────────────────

    async def async_cria_pasta(self, caminho: str) -> str:
        return await asyncio.to_thread(self.cria_pasta, caminho)

    async def async_deletar_arquivo(self, caminho: str) -> str:
        return await asyncio.to_thread(self.deletar_arquivo, caminho)

    async def async_organizar_pasta(self, caminho: str) -> str:
        return await asyncio.to_thread(self.organizar_pasta, caminho)

    async def async_buscar_e_abrir_arquivo(self, nome: str) -> str:
        return await asyncio.to_thread(self.buscar_e_abrir_arquivo, nome)

    async def async_controle_volume(self, nivel: int) -> str:
        return await asyncio.to_thread(self.controle_volume, nivel)

    async def async_controle_brilho(self, nivel: int) -> str:
        return await asyncio.to_thread(self.controle_brilho, nivel)


# ── Instância global (opcional — importar diretamente se preferir) ──
jarvis_control = JarvisControl()


# ═══════════════════════════════════════════════════════════════
#  DEMO / TESTE RÁPIDO
# ═══════════════════════════════════════════════════════════════

async def _demo():
    print("═" * 62)
    print("  JARVIS v5.0 — Demo Completo")
    print("═" * 62)

    # ── Cores RGB ─────────────────────────────────────────────
    print("\n🎨 Testando parser de cores:\n")
    exemplos_cor = [
        "deixa a luz da sala azul",
        "muda a luz do quarto para vermelho",
        "coloca luz roxa no escritório",
        "luz rgb 255 0 255 na sala",
        "define cor #00ffcc na cozinha",
        "ativa modo gamer na sala",
        "modo romantico no quarto",
        "modo festa na sala",
        "luz branca fria no banheiro",
    ]
    for cmd in exemplos_cor:
        resultado = parse_comando_cor(cmd)
        if resultado:
            rgb   = resultado.get("rgb")
            modo  = resultado.get("modo")
            comodo = resultado.get("comodo") or "?"
            cor_str = rgb_para_hex(rgb) if rgb else f"efeito:{modo}"
            print(f"  ✅ '{cmd}'")
            print(f"     → Cômodo: {comodo} | Cor: {cor_str}")
        else:
            print(f"  ❌ '{cmd}' → não reconhecido")

    print("\n" + listar_cores_disponiveis())

    # ── JarvisControl ────────────────────────────────────────
    print("\n\n🖥️  Testando JarvisControl:\n")
    jc = JarvisControl()
    print(f"  Home detectada: {jc.home}")
    print(f"  Desktop:        {jc.desktop}")
    print(f"  Documentos:     {jc.documents}")
    print(f"  Downloads:      {jc.downloads}")
    print(f"\n  Sites disponíveis: {', '.join(jc.shortcuts.keys())}")
    print(f"  Módulo volume:  {'✅ pycaw OK' if _PYCAW_OK else '⚠️  pycaw não instalado'}")
    print(f"  Módulo brilho:  {'✅ sbc OK' if _SBC_OK else '⚠️  screen-brightness-control não instalado'}")

    print("\n═" * 62)
    print("  Para instalar dependências opcionais:")
    print("  pip install pycaw screen-brightness-control")
    print("═" * 62)


if __name__ == "__main__":
    asyncio.run(_demo())