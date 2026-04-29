"""
═══════════════════════════════════════════════════════════════
  JARVIS SITE ANALYZER v1.0
  Análise completa de sites: conteúdo, título, resumo,
  segurança, risco de dados, certificados SSL, reputação
═══════════════════════════════════════════════════════════════
"""

import os
import json
import ssl
import socket
import hashlib
import re
import logging
from datetime import datetime
from urllib.parse import urlparse
from .core import DataStore, agora_brasil_iso, DATA_DIR

logger = logging.getLogger(__name__)

# ── Store ─────────────────────────────────────────────────────
_analises_store = DataStore("site_analyses", default=[])

# Diretório para relatórios
REPORTS_DIR = os.path.join(DATA_DIR, "site_reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  DOMÍNIOS CONHECIDOS COMO PERIGOSOS / SUSPEITOS
# ═══════════════════════════════════════════════════════════════

_DOMINIOS_SUSPEITOS_PATTERNS = [
    r".*\.tk$", r".*\.ml$", r".*\.ga$", r".*\.cf$", r".*\.gq$",
    r".*phish.*", r".*scam.*", r".*hack.*", r".*crack.*",
    r".*free.*gift.*", r".*login.*verify.*", r".*account.*secure.*",
    r".*update.*bank.*", r".*paypal.*(?!paypal\.com$)",
    r".*google.*(?!google\.com$|google\.com\.br$)",
    r".*facebook.*(?!facebook\.com$)",
    r".*microsoft.*(?!microsoft\.com$)",
]

_INDICADORES_PHISHING = [
    "insira sua senha", "confirme seus dados", "cartão de crédito",
    "atualize seu cadastro", "conta será bloqueada", "clique aqui urgente",
    "verificação de segurança", "ganhou um prêmio", "oferta exclusiva",
    "enter your password", "verify your account", "credit card",
    "update your information", "account suspended", "click here now",
    "limited time offer", "you have won",
]

_HEADERS_SEGURANCA = [
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "X-XSS-Protection",
    "Referrer-Policy",
    "Permissions-Policy",
]


# ═══════════════════════════════════════════════════════════════
#  1. ANÁLISE COMPLETA DE SITE
# ═══════════════════════════════════════════════════════════════

async def analisar_site_completo(url: str) -> str:
    """
    Análise completa de um site: título, conteúdo, resumo,
    segurança, SSL, headers, risco de phishing.
    
    Retorna relatório detalhado em texto.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "❌ Playwright não instalado. Execute: pip install playwright && playwright install chromium"

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    dominio = parsed.netloc

    resultado = {
        "url": url,
        "dominio": dominio,
        "timestamp": agora_brasil_iso(),
        "conteudo": {},
        "seguranca": {},
        "resumo": "",
        "score_confianca": 0,
        "alertas": [],
    }

    # ── 1. Verificar SSL ──────────────────────────────────────
    ssl_info = _verificar_ssl(dominio)
    resultado["seguranca"]["ssl"] = ssl_info

    # ── 2. Verificar padrões de domínio suspeito ──────────────
    dominio_check = _verificar_dominio_suspeito(dominio)
    resultado["seguranca"]["dominio"] = dominio_check

    # ── 3. Navegar e extrair conteúdo ─────────────────────────
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await ctx.new_page()

            # Capturar headers de resposta
            response_headers = {}
            page.on("response", lambda resp: _capturar_headers(resp, response_headers))

            try:
                response = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                status_code = response.status if response else 0
            except Exception as e:
                resultado["alertas"].append(f"⚠️ Erro ao acessar: {e}")
                await browser.close()
                return _formatar_relatorio(resultado)

            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # Extrair dados da página
            dados_pagina = await page.evaluate("""
                () => {
                    const title = document.title || '';
                    const meta_desc = document.querySelector('meta[name="description"]')?.content || '';
                    const meta_keywords = document.querySelector('meta[name="keywords"]')?.content || '';
                    const meta_author = document.querySelector('meta[name="author"]')?.content || '';
                    const canonical = document.querySelector('link[rel="canonical"]')?.href || '';
                    const favicon = document.querySelector('link[rel="icon"]')?.href || 
                                   document.querySelector('link[rel="shortcut icon"]')?.href || '';
                    
                    const h1 = Array.from(document.querySelectorAll('h1')).map(h => h.innerText.trim()).filter(t => t);
                    const h2 = Array.from(document.querySelectorAll('h2')).map(h => h.innerText.trim()).filter(t => t);
                    
                    const body_text = document.body.innerText.slice(0, 10000);
                    
                    const links = Array.from(document.querySelectorAll('a[href]'))
                        .map(a => ({text: a.innerText.trim().slice(0, 50), href: a.href}))
                        .filter(l => l.text && l.href.startsWith('http'))
                        .slice(0, 20);
                    
                    const forms = Array.from(document.querySelectorAll('form')).map(f => ({
                        action: f.action || '',
                        method: f.method || 'GET',
                        inputs: Array.from(f.querySelectorAll('input')).map(i => ({
                            type: i.type, name: i.name, placeholder: i.placeholder
                        }))
                    }));
                    
                    const scripts_external = Array.from(document.querySelectorAll('script[src]'))
                        .map(s => s.src).slice(0, 10);
                    
                    const iframes = Array.from(document.querySelectorAll('iframe'))
                        .map(f => f.src).filter(s => s).slice(0, 5);
                    
                    const password_fields = document.querySelectorAll('input[type="password"]').length;
                    const cookie_banners = document.querySelectorAll('[class*="cookie"], [id*="cookie"], [class*="consent"]').length;
                    
                    return {
                        title, meta_desc, meta_keywords, meta_author, canonical, favicon,
                        h1, h2, body_text, links, forms, scripts_external, iframes,
                        password_fields, cookie_banners,
                        language: document.documentElement.lang || '',
                    };
                }
            """)

            await browser.close()

            # Preencher resultado
            resultado["conteudo"] = {
                "titulo": dados_pagina.get("title", ""),
                "descricao": dados_pagina.get("meta_desc", ""),
                "keywords": dados_pagina.get("meta_keywords", ""),
                "autor": dados_pagina.get("meta_author", ""),
                "idioma": dados_pagina.get("language", ""),
                "h1": dados_pagina.get("h1", []),
                "h2": dados_pagina.get("h2", [])[:5],
                "texto_corpo": dados_pagina.get("body_text", "")[:3000],
                "links_count": len(dados_pagina.get("links", [])),
                "formularios": len(dados_pagina.get("forms", [])),
                "scripts_externos": len(dados_pagina.get("scripts_external", [])),
                "iframes": len(dados_pagina.get("iframes", [])),
            }

            # ── 4. Análise de segurança ───────────────────────
            seg = resultado["seguranca"]
            seg["status_code"] = status_code
            seg["tem_formulario_senha"] = dados_pagina.get("password_fields", 0) > 0
            seg["cookie_banner"] = dados_pagina.get("cookie_banners", 0) > 0

            # Verificar headers de segurança da resposta
            seg["headers_seguranca"] = {}
            for header in _HEADERS_SEGURANCA:
                seg["headers_seguranca"][header] = header.lower() in {
                    k.lower() for k in response_headers.keys()
                }

            # ── 5. Verificar phishing ─────────────────────────
            texto_lower = dados_pagina.get("body_text", "").lower()
            indicadores_encontrados = [
                ind for ind in _INDICADORES_PHISHING
                if ind.lower() in texto_lower
            ]
            seg["indicadores_phishing"] = indicadores_encontrados

            # Formulários suspeitos (pedem senha em HTTP)
            if not url.startswith("https://") and dados_pagina.get("password_fields", 0) > 0:
                resultado["alertas"].append(
                    "🚨 ALERTA CRÍTICO: Formulário de senha em conexão HTTP (sem criptografia)!"
                )

            # ── 6. Calcular score de confiança ────────────────
            score = _calcular_score_confianca(resultado)
            resultado["score_confianca"] = score

            # ── 7. Gerar resumo inteligente ───────────────────
            resultado["resumo"] = _gerar_resumo(resultado)

    except Exception as e:
        resultado["alertas"].append(f"❌ Erro na análise: {e}")

    # Salvar análise
    _salvar_analise(resultado)

    return _formatar_relatorio(resultado)


# ═══════════════════════════════════════════════════════════════
#  2. ANÁLISE RÁPIDA (só segurança)
# ═══════════════════════════════════════════════════════════════

async def analise_rapida_seguranca(url: str) -> str:
    """Análise rápida focada em segurança sem navegar no site."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    dominio = parsed.netloc

    ssl_info = _verificar_ssl(dominio)
    dominio_check = _verificar_dominio_suspeito(dominio)

    alertas = []
    score = 100

    # SSL
    if not ssl_info.get("valido"):
        alertas.append("🔴 SSL inválido ou ausente")
        score -= 30
    elif ssl_info.get("dias_restantes", 0) < 30:
        alertas.append(f"🟡 SSL expira em {ssl_info.get('dias_restantes')} dias")
        score -= 10

    # Domínio
    if dominio_check.get("suspeito"):
        alertas.append(f"🔴 Domínio suspeito: {dominio_check.get('motivo')}")
        score -= 40

    # HTTP
    if url.startswith("http://"):
        alertas.append("🟡 Conexão HTTP (sem criptografia)")
        score -= 20

    # Determinar nível
    if score >= 80:
        nivel = "🟢 SEGURO"
    elif score >= 50:
        nivel = "🟡 MODERADO"
    else:
        nivel = "🔴 ARRISCADO"

    linhas = [
        f"🔒 **Análise Rápida de Segurança**\n",
        f"🌐 URL: `{url}`",
        f"📊 Score: **{score}/100** — {nivel}\n",
    ]

    if ssl_info.get("valido"):
        linhas.append(f"🔐 SSL: ✅ Válido (emitido por: {ssl_info.get('emissor', 'N/A')})")
        linhas.append(f"   Expira em: {ssl_info.get('dias_restantes', '?')} dias")
    else:
        linhas.append(f"🔐 SSL: ❌ {ssl_info.get('erro', 'Inválido')}")

    if alertas:
        linhas.append("\n⚠️ **Alertas:**")
        for a in alertas:
            linhas.append(f"  {a}")
    else:
        linhas.append("\n✅ Nenhum alerta de segurança encontrado.")

    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════
#  3. LER E RESUMIR SITE
# ═══════════════════════════════════════════════════════════════

async def ler_e_resumir_site(url: str) -> str:
    """
    Acessa um site, lê o conteúdo, identifica o título
    e gera um resumo claro do que o site se trata.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "❌ Playwright não instalado."

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")

            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            titulo = await page.title()
            meta_desc = await page.evaluate(
                "document.querySelector('meta[name=\"description\"]')?.content || ''"
            )
            texto = await page.evaluate("document.body.innerText")
            idioma = await page.evaluate("document.documentElement.lang || ''")

            # H1 e H2
            headings = await page.evaluate("""
                () => {
                    const h1 = Array.from(document.querySelectorAll('h1'))
                        .map(h => h.innerText.trim()).filter(t => t).slice(0, 3);
                    const h2 = Array.from(document.querySelectorAll('h2'))
                        .map(h => h.innerText.trim()).filter(t => t).slice(0, 5);
                    return {h1, h2};
                }
            """)

            await browser.close()

        # Compor resposta
        linhas = [
            f"📄 **Análise do Site**\n",
            f"🌐 URL: `{url}`",
            f"📌 Título: **{titulo}**",
        ]

        if meta_desc:
            linhas.append(f"📝 Descrição: {meta_desc}")

        if idioma:
            linhas.append(f"🌍 Idioma: {idioma}")

        if headings.get("h1"):
            linhas.append(f"\n📖 **Tópicos principais:**")
            for h in headings["h1"]:
                linhas.append(f"  • {h}")

        if headings.get("h2"):
            linhas.append(f"\n📋 **Subtópicos:**")
            for h in headings["h2"]:
                linhas.append(f"  • {h}")

        # Texto parcial como contexto
        texto_limpo = texto[:5000].strip()
        linhas.append(f"\n📃 **Conteúdo (primeiros caracteres):**\n{texto_limpo[:2000]}")

        if len(texto) > 2000:
            linhas.append(f"\n… (total: {len(texto)} caracteres)")

        return "\n".join(linhas)

    except Exception as e:
        return f"❌ Erro ao ler site: {e}"


# ═══════════════════════════════════════════════════════════════
#  FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def _verificar_ssl(dominio: str) -> dict:
    """Verifica certificado SSL de um domínio."""
    try:
        # Remover porta se presente
        host = dominio.split(":")[0]
        
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()

                # Datas
                not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
                dias_restantes = (not_after - datetime.utcnow()).days

                # Emissor
                emissor = ""
                for campo in cert.get("issuer", ()):
                    for k, v in campo:
                        if k == "organizationName":
                            emissor = v
                            break

                # Subject
                subject = ""
                for campo in cert.get("subject", ()):
                    for k, v in campo:
                        if k == "commonName":
                            subject = v
                            break

                return {
                    "valido": True,
                    "emissor": emissor,
                    "subject": subject,
                    "validade_inicio": not_before.isoformat(),
                    "validade_fim": not_after.isoformat(),
                    "dias_restantes": dias_restantes,
                    "protocolo": ssock.version(),
                }
    except ssl.SSLCertVerificationError as e:
        return {"valido": False, "erro": f"Certificado inválido: {e}"}
    except socket.timeout:
        return {"valido": False, "erro": "Timeout ao verificar SSL"}
    except socket.gaierror:
        return {"valido": False, "erro": "Domínio não encontrado (DNS falhou)"}
    except ConnectionRefusedError:
        return {"valido": False, "erro": "Conexão recusada na porta 443"}
    except Exception as e:
        return {"valido": False, "erro": str(e)}


def _verificar_dominio_suspeito(dominio: str) -> dict:
    """Verifica se o domínio tem padrões suspeitos."""
    dominio_lower = dominio.lower()

    for pattern in _DOMINIOS_SUSPEITOS_PATTERNS:
        if re.match(pattern, dominio_lower):
            return {
                "suspeito": True,
                "motivo": f"Padrão suspeito detectado: {pattern}",
            }

    # Verificar comprimento excessivo (domínios phishing costumam ser longos)
    if len(dominio) > 50:
        return {
            "suspeito": True,
            "motivo": f"Domínio muito longo ({len(dominio)} chars) — comum em phishing",
        }

    # Verificar muitos subdomínios
    partes = dominio.split(".")
    if len(partes) > 5:
        return {
            "suspeito": True,
            "motivo": f"Excesso de subdomínios ({len(partes)}) — suspeito",
        }

    # Verificar caracteres estranhos (homoglyphs)
    if any(ord(c) > 127 for c in dominio):
        return {
            "suspeito": True,
            "motivo": "Caracteres Unicode detectados — possível homoglyph attack",
        }

    return {"suspeito": False, "motivo": ""}


def _capturar_headers(resp, headers_dict):
    """Callback para capturar headers da resposta principal."""
    try:
        if resp.url and not headers_dict:
            for k, v in resp.headers.items():
                headers_dict[k] = v
    except Exception:
        pass


def _calcular_score_confianca(resultado: dict) -> int:
    """Calcula score de confiança de 0-100."""
    score = 100
    seg = resultado.get("seguranca", {})

    # SSL
    ssl_info = seg.get("ssl", {})
    if not ssl_info.get("valido"):
        score -= 25
    elif ssl_info.get("dias_restantes", 999) < 30:
        score -= 10

    # Domínio suspeito
    if seg.get("dominio", {}).get("suspeito"):
        score -= 35

    # Headers de segurança
    headers = seg.get("headers_seguranca", {})
    headers_ausentes = sum(1 for v in headers.values() if not v)
    score -= min(15, headers_ausentes * 2)

    # Formulário de senha em HTTP
    if seg.get("tem_formulario_senha") and not resultado["url"].startswith("https://"):
        score -= 30

    # Indicadores de phishing
    phishing = seg.get("indicadores_phishing", [])
    score -= min(30, len(phishing) * 10)

    # Alertas
    score -= min(10, len(resultado.get("alertas", [])) * 5)

    return max(0, min(100, score))


def _gerar_resumo(resultado: dict) -> str:
    """Gera resumo legível do site."""
    conteudo = resultado.get("conteudo", {})
    titulo = conteudo.get("titulo", "Sem título")
    descricao = conteudo.get("descricao", "")
    texto = conteudo.get("texto_corpo", "")[:500]

    if descricao:
        resumo = f"{titulo} — {descricao}"
    elif texto:
        # Primeira frase significativa
        frases = [f.strip() for f in texto.split(".") if len(f.strip()) > 20]
        resumo = f"{titulo} — {frases[0]}." if frases else titulo
    else:
        resumo = titulo

    return resumo[:500]


def _formatar_relatorio(resultado: dict) -> str:
    """Formata o resultado em relatório legível."""
    conteudo = resultado.get("conteudo", {})
    seg = resultado.get("seguranca", {})
    score = resultado.get("score_confianca", 0)

    if score >= 80:
        nivel = "🟢 CONFIÁVEL"
        emoji = "✅"
    elif score >= 50:
        nivel = "🟡 MODERADO"
        emoji = "⚠️"
    else:
        nivel = "🔴 ARRISCADO"
        emoji = "🚨"

    linhas = [
        f"{'═' * 50}",
        f"  {emoji} ANÁLISE COMPLETA DE SITE",
        f"{'═' * 50}\n",
        f"🌐 **URL:** `{resultado['url']}`",
        f"📌 **Título:** {conteudo.get('titulo', 'N/A')}",
        f"📊 **Score de Confiança:** **{score}/100** — {nivel}",
    ]

    # Resumo
    if resultado.get("resumo"):
        linhas.append(f"\n📝 **Sobre o site:**\n  {resultado['resumo']}")

    # Conteúdo
    if conteudo.get("descricao"):
        linhas.append(f"\n📋 **Descrição:** {conteudo['descricao']}")
    if conteudo.get("idioma"):
        linhas.append(f"🌍 **Idioma:** {conteudo['idioma']}")
    if conteudo.get("h1"):
        linhas.append(f"📖 **Tópicos:** {', '.join(conteudo['h1'][:3])}")

    # Segurança
    linhas.append(f"\n{'─' * 50}")
    linhas.append(f"  🔒 SEGURANÇA")
    linhas.append(f"{'─' * 50}")

    ssl_info = seg.get("ssl", {})
    if ssl_info.get("valido"):
        linhas.append(f"  🔐 SSL: ✅ Válido (emissor: {ssl_info.get('emissor', 'N/A')})")
        linhas.append(f"     Expira em: {ssl_info.get('dias_restantes', '?')} dias")
    else:
        linhas.append(f"  🔐 SSL: ❌ {ssl_info.get('erro', 'Inválido')}")

    dom = seg.get("dominio", {})
    if dom.get("suspeito"):
        linhas.append(f"  🚩 Domínio: ⚠️ {dom['motivo']}")
    else:
        linhas.append(f"  🌐 Domínio: ✅ Normal")

    # Headers
    headers = seg.get("headers_seguranca", {})
    if headers:
        presentes = sum(1 for v in headers.values() if v)
        total = len(headers)
        linhas.append(f"  🛡️ Headers de segurança: {presentes}/{total}")

    # Phishing
    phishing = seg.get("indicadores_phishing", [])
    if phishing:
        linhas.append(f"\n  🚨 **INDICADORES DE PHISHING DETECTADOS:**")
        for ind in phishing[:5]:
            linhas.append(f"    ⚠️ \"{ind}\"")

    if seg.get("tem_formulario_senha"):
        proto = "HTTPS" if resultado["url"].startswith("https://") else "HTTP ⚠️"
        linhas.append(f"  🔑 Formulário de senha detectado (via {proto})")

    # Alertas
    if resultado.get("alertas"):
        linhas.append(f"\n{'─' * 50}")
        linhas.append(f"  ⚠️ ALERTAS")
        linhas.append(f"{'─' * 50}")
        for alerta in resultado["alertas"]:
            linhas.append(f"  {alerta}")

    # Estatísticas
    linhas.append(f"\n{'─' * 50}")
    linhas.append(f"  📊 ESTATÍSTICAS")
    linhas.append(f"{'─' * 50}")
    linhas.append(f"  Links: {conteudo.get('links_count', 0)}")
    linhas.append(f"  Formulários: {conteudo.get('formularios', 0)}")
    linhas.append(f"  Scripts externos: {conteudo.get('scripts_externos', 0)}")
    linhas.append(f"  iFrames: {conteudo.get('iframes', 0)}")

    linhas.append(f"\n{'═' * 50}")

    return "\n".join(linhas)


def _salvar_analise(resultado: dict):
    """Salva análise no histórico."""
    try:
        dados = _analises_store.load()
        # Salvar versão resumida
        dados.append({
            "url": resultado["url"],
            "dominio": resultado["dominio"],
            "titulo": resultado.get("conteudo", {}).get("titulo", ""),
            "score": resultado["score_confianca"],
            "resumo": resultado.get("resumo", ""),
            "alertas_count": len(resultado.get("alertas", [])),
            "timestamp": resultado["timestamp"],
        })
        # Manter últimas 100
        if len(dados) > 100:
            dados = dados[-100:]
        _analises_store.save(dados)

        # Salvar relatório completo em arquivo separado
        dominio_safe = re.sub(r'[^\w\-.]', '_', resultado["dominio"])
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(REPORTS_DIR, f"{dominio_safe}_{ts}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        logger.warning(f"Erro ao salvar análise: {e}")


def historico_analises() -> str:
    """Retorna histórico de análises de sites."""
    dados = _analises_store.load()
    if not dados:
        return "Nenhuma análise de site realizada ainda."

    linhas = [f"📊 **Histórico de Análises ({len(dados)}):**\n"]
    for analise in reversed(dados[-20:]):
        score = analise.get("score", 0)
        if score >= 80:
            emoji = "🟢"
        elif score >= 50:
            emoji = "🟡"
        else:
            emoji = "🔴"

        linhas.append(f"  {emoji} [{score}/100] {analise.get('titulo', 'N/A')}")
        linhas.append(f"     ↳ {analise.get('url', '')}")
        linhas.append(f"     ↳ {analise.get('timestamp', '')}\n")

    return "\n".join(linhas)
