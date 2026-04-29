"""
═══════════════════════════════════════════════════════════════
  TUYA SERVICE — Integração com a API da Tuya (Cloud)
  v1.0 — Autenticação HMAC-SHA256 + Controle de Dispositivos
═══════════════════════════════════════════════════════════════

Módulo de integração com Tuya Cloud API para controle de
dispositivos IoT: lâmpadas, tomadas, switches etc.

Data Center: Western America (https://openapi.tuyaus.com)
Autenticação: HMAC-SHA256 conforme padrão oficial Tuya

Uso:
    from tuya_service import (
        ligar_dispositivo, desligar_dispositivo,
        status_dispositivo, mudar_cor, ajustar_brilho
    )
"""

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tuya_service")

# ═══════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════

ACCESS_ID: str = os.getenv("TUYA_ACCESS_ID", "")
ACCESS_SECRET: str = os.getenv("TUYA_ACCESS_SECRET", "")

# Data Centers disponíveis
_DATA_CENTERS = {
    "china":           "https://openapi.tuyacn.com",
    "western_america": "https://openapi.tuyaus.com",
    "eastern_america": "https://openapi-ueaz.tuyaus.com",
    "central_europe":  "https://openapi.tuyaeu.com",
    "western_europe":  "https://openapi-weaz.tuyaeu.com",
    "india":           "https://openapi.tuyain.com",
}

# Data Center do projeto (Western America conforme configuração do usuário)
BASE_URL: str = os.getenv(
    "TUYA_BASE_URL",
    _DATA_CENTERS["western_america"]
)

# Cache de token em memória
_token_cache: Dict[str, Any] = {
    "access_token": "",
    "refresh_token": "",
    "expire_time": 0,
    "uid": "",
}

# Cache de dispositivos para resolução nome → ID
_device_cache: Dict[str, Dict] = {}
_device_cache_time: float = 0


# ═══════════════════════════════════════════════════════════════
# AUTENTICAÇÃO — HMAC-SHA256 (PADRÃO OFICIAL TUYA)
# ═══════════════════════════════════════════════════════════════

def _sha256_hex(data: str) -> str:
    """Calcula SHA256 de uma string e retorna hex lowercase."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _hmac_sha256(key: str, msg: str) -> str:
    """Calcula HMAC-SHA256 e retorna em uppercase (padrão Tuya)."""
    return hmac.new(
        key.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()


def _build_string_to_sign(
    method: str,
    path: str,
    headers_to_sign: str = "",
    body: str = "",
) -> str:
    """
    Constrói a stringToSign:
        HTTPMethod\n
        Content-SHA256\n
        Headers\n
        URL
    """
    content_sha256 = _sha256_hex(body)
    return f"{method}\n{content_sha256}\n{headers_to_sign}\n{path}"


def _sign_request(
    method: str,
    path: str,
    body: str = "",
    access_token: str = "",
) -> Dict[str, str]:
    """
    Gera os headers assinados para qualquer requisição à API Tuya.

    Retorna dict com todos os headers necessários:
        client_id, sign, sign_method, t, nonce, (access_token)
    """
    t = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    string_to_sign = _build_string_to_sign(method, path, "", body)

    # Fórmula:
    # Token request:  HMAC(client_id + t + nonce + stringToSign, secret)
    # Business API:   HMAC(client_id + access_token + t + nonce + stringToSign, secret)
    if access_token:
        raw = ACCESS_ID + access_token + t + nonce + string_to_sign
    else:
        raw = ACCESS_ID + t + nonce + string_to_sign

    sign = _hmac_sha256(ACCESS_SECRET, raw)

    headers = {
        "client_id": ACCESS_ID,
        "sign": sign,
        "sign_method": "HMAC-SHA256",
        "t": t,
        "nonce": nonce,
        "Content-Type": "application/json",
    }
    if access_token:
        headers["access_token"] = access_token

    return headers


# ═══════════════════════════════════════════════════════════════
# TOKEN MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def get_token(force_refresh: bool = False) -> str:
    """
    Obtém token de acesso da API Tuya.

    Usa cache em memória; renova automaticamente quando expirado.
    Endpoint: GET /v1.0/token?grant_type=1

    Retorna:
        access_token (str)

    Raises:
        RuntimeError se a API retornar erro
    """
    global _token_cache

    # Verificar se token em cache ainda é válido (margem de 60s)
    agora_ms = int(time.time() * 1000)
    if (
        not force_refresh
        and _token_cache["access_token"]
        and _token_cache["expire_time"] > agora_ms + 60_000
    ):
        return _token_cache["access_token"]

    if not ACCESS_ID or not ACCESS_SECRET:
        raise RuntimeError(
            "Credenciais Tuya não configuradas. "
            "Defina TUYA_ACCESS_ID e TUYA_ACCESS_SECRET no .env"
        )

    path = "/v1.0/token?grant_type=1"
    headers = _sign_request("GET", path, body="", access_token="")
    url = f"{BASE_URL}{path}"

    logger.info("[Tuya] Solicitando novo access_token...")

    resp = requests.get(url, headers=headers, timeout=10)
    data = resp.json()

    if not data.get("success"):
        code = data.get("code", "?")
        msg = data.get("msg", "Erro desconhecido")
        raise RuntimeError(f"[Tuya] Falha ao obter token — code={code}: {msg}")

    result = data["result"]
    _token_cache = {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "expire_time": agora_ms + result.get("expire_time", 7200) * 1000,
        "uid": result.get("uid", ""),
    }

    logger.info("[Tuya] Token obtido com sucesso (expira em %ds)", result.get("expire_time", 0))
    return _token_cache["access_token"]


def _refresh_token() -> str:
    """Renova token usando refresh_token."""
    global _token_cache

    if not _token_cache["refresh_token"]:
        return get_token(force_refresh=True)

    path = f"/v1.0/token/{_token_cache['refresh_token']}"
    headers = _sign_request("GET", path, body="", access_token="")
    url = f"{BASE_URL}{path}"

    resp = requests.get(url, headers=headers, timeout=10)
    data = resp.json()

    if not data.get("success"):
        # Fallback: obter novo token do zero
        return get_token(force_refresh=True)

    result = data["result"]
    agora_ms = int(time.time() * 1000)
    _token_cache = {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "expire_time": agora_ms + result.get("expire_time", 7200) * 1000,
        "uid": result.get("uid", ""),
    }

    logger.info("[Tuya] Token renovado via refresh_token.")
    return _token_cache["access_token"]


# ═══════════════════════════════════════════════════════════════
# REQUISIÇÃO GENÉRICA (COM RETRY E TOKEN AUTO-REFRESH)
# ═══════════════════════════════════════════════════════════════

def _api_request(
    method: str,
    path: str,
    body: Optional[Dict] = None,
    retries: int = 1,
) -> Dict:
    """
    Realiza requisição autenticada à API Tuya.

    Parâmetros:
        method  — GET ou POST
        path    — Endpoint (ex: /v1.0/devices/{id})
        body    — Corpo JSON (para POST)
        retries — Tentativas restantes em caso de token expirado

    Retorna:
        Dict com a resposta JSON completa da API
    """
    token = get_token()
    body_str = json.dumps(body) if body else ""
    headers = _sign_request(method, path, body=body_str, access_token=token)
    url = f"{BASE_URL}{path}"

    if method == "GET":
        resp = requests.get(url, headers=headers, timeout=15)
    elif method == "POST":
        resp = requests.post(url, headers=headers, data=body_str, timeout=15)
    else:
        raise ValueError(f"Método HTTP não suportado: {method}")

    data = resp.json()

    # Auto-refresh se token expirou (code 1010)
    if not data.get("success") and data.get("code") == 1010 and retries > 0:
        logger.warning("[Tuya] Token expirado — renovando...")
        _refresh_token()
        return _api_request(method, path, body, retries - 1)

    return data


# ═══════════════════════════════════════════════════════════════
# RESOLUÇÃO DE NOMES → DEVICE IDs
# ═══════════════════════════════════════════════════════════════

def _carregar_cache_dispositivos(force: bool = False) -> None:
    """Carrega cache de dispositivos para resolução nome→ID."""
    global _device_cache, _device_cache_time

    agora = time.time()
    if not force and _device_cache and (agora - _device_cache_time) < 600:  # 10 min
        return

    try:
        path = "/v1.0/iot-03/devices"
        resp = _api_request("GET", path)
        if resp.get("success"):
            devices = resp.get("result", {}).get("list", [])
            _device_cache.clear()
            for d in devices:
                did = d.get("id", "")
                nome = (d.get("name") or "").strip().lower()
                if did:
                    _device_cache[did] = d  # ID exato
                    if nome:
                        _device_cache[nome] = d  # nome amigável
            _device_cache_time = agora
            logger.info("[Tuya] Cache de dispositivos atualizado: %d device(s)", len(devices))
    except Exception as e:
        logger.warning("[Tuya] Falha ao carregar cache de dispositivos: %s", e)


def _resolver_device_id(device_id_ou_nome: str) -> str:
    """
    Resolve um nome amigável ou ID parcial para o device_id real.

    Se o valor já for um ID válido (>15 chars alfanuméricos), retorna direto.
    Senão, busca no cache de dispositivos por nome.

    Retorna:
        device_id real (str)

    Raises:
        ValueError se não encontrar o dispositivo
    """
    entrada = device_id_ou_nome.strip()

    # Se parece ser um device_id real (alfanumérico longo), usar direto
    if len(entrada) >= 15 and entrada.replace("_", "").isalnum():
        return entrada

    # Buscar por nome no cache
    _carregar_cache_dispositivos()
    chave = entrada.lower()

    if chave in _device_cache:
        real_id = _device_cache[chave].get("id", entrada)
        logger.info("[Tuya] Resolvido '%s' → '%s'", entrada, real_id)
        return real_id

    # Busca parcial (contém o nome)
    for nome_cache, info in _device_cache.items():
        if chave in nome_cache or nome_cache in chave:
            real_id = info.get("id", entrada)
            logger.info("[Tuya] Resolvido parcial '%s' → '%s' (%s)", entrada, real_id, nome_cache)
            return real_id

    # Não encontrado — retorna original (a API vai dar erro claro)
    logger.warning("[Tuya] Dispositivo '%s' nao encontrado no cache. Usando como ID direto.", entrada)
    return entrada


# ═══════════════════════════════════════════════════════════════
# CONTROLE DE DISPOSITIVOS
# ═══════════════════════════════════════════════════════════════

_ERRO_1106_MSG = (
    "Permissao negada (code 1106). Verifique no Tuya IoT Platform:\n"
    "1. Cloud > Development > seu projeto > Devices > Link Tuya App Account (escaneie o QR code)\n"
    "2. Cloud > Development > seu projeto > Service API > autorize 'IoT Core'\n"
    "3. Confirme que o Data Center do projeto corresponde ao da sua conta no app Tuya/Smart Life"
)


def _enviar_comandos(device_id: str, commands: List[Dict]) -> Dict:
    """
    Envia comandos para um dispositivo via endpoint oficial.
    POST /v1.0/iot-03/devices/{device_id}/commands

    Parâmetros:
        device_id — ID do dispositivo Tuya (ou nome amigável)
        commands  — Lista de dicts {"code": ..., "value": ...}

    Retorna:
        Dict com resposta da API
    """
    # Resolver nome → ID real
    real_id = _resolver_device_id(device_id)

    path = f"/v1.0/iot-03/devices/{real_id}/commands"
    payload = {"commands": commands}

    logger.info("[Tuya] Enviando %d comando(s) para %s", len(commands), real_id)
    result = _api_request("POST", path, payload)

    if result.get("success"):
        logger.info("[Tuya] Comando(s) executado(s) com sucesso em %s", real_id)
    else:
        code = result.get("code")
        msg = result.get("msg", "")
        if code == 1106:
            logger.error("[Tuya] PERMISSAO NEGADA para %s — %s", real_id, _ERRO_1106_MSG)
            result["msg"] = _ERRO_1106_MSG
        else:
            logger.error(
                "[Tuya] Erro ao enviar comando para %s: code=%s msg=%s",
                real_id, code, msg,
            )

    return result


def ligar_dispositivo(device_id: str) -> Dict:
    """
    Liga um dispositivo Tuya.

    Parâmetros:
        device_id — ID do dispositivo

    Retorna:
        Dict {"sucesso": bool, "mensagem": str, "resposta": dict}
    """
    resp = _enviar_comandos(device_id, [{"code": "switch_led", "value": True}])

    if not resp.get("success"):
        # Tenta código alternativo (switch, switch_1)
        resp = _enviar_comandos(device_id, [{"code": "switch", "value": True}])

    if not resp.get("success"):
        resp = _enviar_comandos(device_id, [{"code": "switch_1", "value": True}])

    return {
        "sucesso": resp.get("success", False),
        "mensagem": "✅ Dispositivo ligado" if resp.get("success") else f"❌ Erro: {resp.get('msg', 'desconhecido')}",
        "resposta": resp,
    }


def desligar_dispositivo(device_id: str) -> Dict:
    """
    Desliga um dispositivo Tuya.

    Parâmetros:
        device_id — ID do dispositivo

    Retorna:
        Dict {"sucesso": bool, "mensagem": str, "resposta": dict}
    """
    resp = _enviar_comandos(device_id, [{"code": "switch_led", "value": False}])

    if not resp.get("success"):
        resp = _enviar_comandos(device_id, [{"code": "switch", "value": False}])

    if not resp.get("success"):
        resp = _enviar_comandos(device_id, [{"code": "switch_1", "value": False}])

    return {
        "sucesso": resp.get("success", False),
        "mensagem": "✅ Dispositivo desligado" if resp.get("success") else f"❌ Erro: {resp.get('msg', 'desconhecido')}",
        "resposta": resp,
    }


def status_dispositivo(device_id: str) -> Dict:
    """
    Consulta o status atual de um dispositivo Tuya.
    GET /v1.0/iot-03/devices/{device_id}/status

    Parâmetros:
        device_id — ID do dispositivo (ou nome amigável)

    Retorna:
        Dict com status_list e metadados
    """
    real_id = _resolver_device_id(device_id)

    # Status via endpoint de status funcional
    path_status = f"/v1.0/iot-03/devices/{real_id}/status"
    resp_status = _api_request("GET", path_status)

    # Info geral do dispositivo
    path_info = f"/v1.0/devices/{real_id}"
    resp_info = _api_request("GET", path_info)

    status_list = resp_status.get("result", []) if resp_status.get("success") else []
    info = resp_info.get("result", {}) if resp_info.get("success") else {}

    # Extrair campos úteis
    ligado = None
    brilho = None
    cor = None
    for item in status_list:
        code = item.get("code", "")
        value = item.get("value")
        if code in ("switch_led", "switch", "switch_1"):
            ligado = value
        elif code in ("bright_value", "bright_value_v2"):
            brilho = value
        elif code in ("colour_data", "colour_data_v2"):
            cor = value

    return {
        "sucesso": resp_status.get("success", False),
        "device_id": real_id,
        "nome": info.get("name", "Desconhecido"),
        "online": info.get("online", False),
        "categoria": info.get("category", ""),
        "ligado": ligado,
        "brilho": brilho,
        "cor_raw": cor,
        "status_completo": status_list,
        "info_completa": info,
    }


# ═══════════════════════════════════════════════════════════════
# CONVERSÃO DE CORES — RGB ↔ HSV (FORMATO TUYA)
# ═══════════════════════════════════════════════════════════════

def _rgb_para_hsv(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """
    Converte RGB (0-255) para HSV no formato Tuya.

    Formato Tuya:
        H: 0–360  (matiz)
        S: 0–1000 (saturação, 0–100% mapeado para 0–1000)
        V: 0–1000 (valor/brilho, 0–100% mapeado para 0–1000)

    Retorna:
        Tuple (h, s, v) no formato Tuya
    """
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    c_max = max(r_norm, g_norm, b_norm)
    c_min = min(r_norm, g_norm, b_norm)
    delta = c_max - c_min

    # Matiz (H)
    if delta == 0:
        h = 0
    elif c_max == r_norm:
        h = 60 * (((g_norm - b_norm) / delta) % 6)
    elif c_max == g_norm:
        h = 60 * (((b_norm - r_norm) / delta) + 2)
    else:
        h = 60 * (((r_norm - g_norm) / delta) + 4)

    h = int(round(h)) % 360

    # Saturação (S) — escala 0–1000
    s = 0 if c_max == 0 else int(round((delta / c_max) * 1000))

    # Valor (V) — escala 0–1000
    v = int(round(c_max * 1000))

    return h, s, v


def _hsv_para_tuya_json(h: int, s: int, v: int) -> str:
    """
    Converte HSV para o formato JSON string usado pela Tuya:
        {"h": 0-360, "s": 0-1000, "v": 0-1000}
    """
    return json.dumps({"h": h, "s": s, "v": v})


def mudar_cor(device_id: str, r: int, g: int, b: int) -> Dict:
    """
    Muda a cor de um dispositivo Tuya compatível com RGB.

    Converte RGB para HSV (formato Tuya) e envia o comando.

    Parâmetros:
        device_id — ID do dispositivo
        r         — Vermelho (0–255)
        g         — Verde (0–255)
        b         — Azul (0–255)

    Retorna:
        Dict {"sucesso": bool, "mensagem": str, "hsv": tuple, "resposta": dict}
    """
    # Clampar valores
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))

    h, s, v = _rgb_para_hsv(r, g, b)
    colour_data = _hsv_para_tuya_json(h, s, v)

    logger.info(
        "[Tuya] Mudando cor de %s: RGB(%d,%d,%d) → HSV(%d,%d,%d)",
        device_id, r, g, b, h, s, v,
    )

    # Primeiro, garantir que está no modo cor
    # Depois, enviamos o dado da cor (tentando ambas versões de DP)
    commands = [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": colour_data},
    ]
    resp = _enviar_comandos(device_id, commands)

    if not resp.get("success"):
        # Tentar versão v1 do DP
        commands_v1 = [
            {"code": "work_mode", "value": "colour"},
            {"code": "colour_data", "value": colour_data},
        ]
        resp = _enviar_comandos(device_id, commands_v1)

    return {
        "sucesso": resp.get("success", False),
        "mensagem": (
            f"✅ Cor alterada para RGB({r},{g},{b})"
            if resp.get("success")
            else f"❌ Erro ao mudar cor: {resp.get('msg', 'desconhecido')}"
        ),
        "rgb": [r, g, b],
        "hsv": (h, s, v),
        "resposta": resp,
    }


# ═══════════════════════════════════════════════════════════════
# CONTROLE DE BRILHO
# ═══════════════════════════════════════════════════════════════

def ajustar_brilho(device_id: str, valor: int) -> Dict:
    """
    Ajusta o brilho de um dispositivo Tuya.

    Parâmetros:
        device_id — ID do dispositivo
        valor     — Brilho de 0 a 100 (convertido para escala Tuya 10–1000)

    Retorna:
        Dict {"sucesso": bool, "mensagem": str, "resposta": dict}
    """
    # Clampar e converter para escala Tuya (10–1000)
    valor = max(0, min(100, int(valor)))
    tuya_brightness = max(10, int(valor * 10))

    logger.info(
        "[Tuya] Ajustando brilho de %s: %d%% (tuya=%d)",
        device_id, valor, tuya_brightness,
    )

    # Tentar v2 primeiro, depois v1
    resp = _enviar_comandos(device_id, [{"code": "bright_value_v2", "value": tuya_brightness}])

    if not resp.get("success"):
        resp = _enviar_comandos(device_id, [{"code": "bright_value", "value": tuya_brightness}])

    return {
        "sucesso": resp.get("success", False),
        "mensagem": (
            f"✅ Brilho ajustado para {valor}%"
            if resp.get("success")
            else f"❌ Erro ao ajustar brilho: {resp.get('msg', 'desconhecido')}"
        ),
        "valor_percentual": valor,
        "valor_tuya": tuya_brightness,
        "resposta": resp,
    }


# ═══════════════════════════════════════════════════════════════
# UTILITÁRIOS EXTRAS
# ═══════════════════════════════════════════════════════════════

def listar_dispositivos() -> Dict:
    """
    Lista todos os dispositivos vinculados ao projeto.
    GET /v1.0/iot-03/devices

    Retorna:
        Dict com lista de dispositivos
    """
    path = "/v1.0/iot-03/devices"
    resp = _api_request("GET", path)

    if not resp.get("success"):
        return {
            "sucesso": False,
            "mensagem": f"❌ Erro: {resp.get('msg', 'desconhecido')}",
            "resposta": resp,
        }

    devices = resp.get("result", {}).get("list", [])
    resumo = []
    for d in devices:
        resumo.append({
            "id": d.get("id"),
            "nome": d.get("name"),
            "categoria": d.get("category"),
            "online": d.get("online"),
            "ip": d.get("ip", ""),
        })

    return {
        "sucesso": True,
        "mensagem": f"✅ {len(resumo)} dispositivo(s) encontrado(s)",
        "dispositivos": resumo,
        "resposta": resp,
    }


def obter_funcionalidades(device_id: str) -> Dict:
    """
    Obtém as funcionalidades (DPs) suportadas por um dispositivo.
    GET /v1.0/iot-03/devices/{device_id}/functions

    Parâmetros:
        device_id — ID do dispositivo (ou nome amigável)

    Retorna:
        Dict com lista de funções suportadas
    """
    real_id = _resolver_device_id(device_id)
    path = f"/v1.0/iot-03/devices/{real_id}/functions"
    resp = _api_request("GET", path)

    if not resp.get("success"):
        return {
            "sucesso": False,
            "mensagem": f"❌ Erro: {resp.get('msg', 'desconhecido')}",
            "resposta": resp,
        }

    functions = resp.get("result", {}).get("functions", [])
    return {
        "sucesso": True,
        "mensagem": f"✅ {len(functions)} função(ões) encontrada(s)",
        "funcionalidades": functions,
        "resposta": resp,
    }


# ═══════════════════════════════════════════════════════════════
# EXEMPLOS DE USO
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Exemplos de uso direto — substitua DEVICE_ID pelo ID real
    do dispositivo exibido em listar_dispositivos().
    """
    print("=" * 60)
    print("  TUYA SERVICE — Teste de Integração")
    print("=" * 60)

    # 1. Listar dispositivos
    print("\n📋 Listando dispositivos...")
    devs = listar_dispositivos()
    print(json.dumps(devs, indent=2, ensure_ascii=False))

    if not devs.get("dispositivos"):
        print("Nenhum dispositivo encontrado. Verifique ACCESS_ID/ACCESS_SECRET.")
        exit(0)

    DEVICE_ID = devs["dispositivos"][0]["id"]
    print(f"\n🔧 Usando dispositivo: {DEVICE_ID}")

    # 2. Status
    print("\n📊 Status do dispositivo:")
    st = status_dispositivo(DEVICE_ID)
    print(json.dumps(st, indent=2, ensure_ascii=False, default=str))

    # 3. Ligar
    print("\n🟢 Ligando dispositivo...")
    print(ligar_dispositivo(DEVICE_ID))

    import time as _t
    _t.sleep(2)

    # 4. Mudar cor para azul
    print("\n🔵 Mudando cor para AZUL (0, 0, 255)...")
    print(mudar_cor(DEVICE_ID, 0, 0, 255))

    _t.sleep(2)

    # 5. Mudar cor para vermelho
    print("\n🔴 Mudando cor para VERMELHO (255, 0, 0)...")
    print(mudar_cor(DEVICE_ID, 255, 0, 0))

    _t.sleep(2)

    # 6. Desligar
    print("\n🔴 Desligando dispositivo...")
    print(desligar_dispositivo(DEVICE_ID))
