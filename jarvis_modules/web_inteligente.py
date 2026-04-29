"""
═══════════════════════════════════════════════════════════════
  [36] navegar_e_extrair_dados
  [37] monitorar_site
═══════════════════════════════════════════════════════════════

Internet inteligente — scraping avançado + monitoramento contínuo.
Usa Playwright headless para navegar, extrair e observar mudanças.
"""

import os
import json
from datetime import datetime, timedelta, timezone
from .core import agora_brasil_iso
from .core import DataStore


# ── Store ─────────────────────────────────────────────────────
_monitores = DataStore("monitores", default=[])


# ═══════════════════════════════════════════════════════════════
#  [36] NAVEGAR E EXTRAIR DADOS
# ═══════════════════════════════════════════════════════════════

async def navegar_e_extrair_dados(url: str, seletor: str = "", tipo: str = "texto") -> str:
    """
    Navega em URL e extrai dados via Playwright.

    Args:
        url: URL do site
        seletor: CSS selector para dados específicos ('.preco', 'h1', 'table')
        tipo: texto | links | imagens | tabela | tudo
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "❌ Playwright não instalado. Execute: pip install playwright && playwright install chromium"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await ctx.new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")

            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass  # Timeout é ok, DOM já carregou

            result = [f"🌐 **Dados de:** `{url}`\n"]

            if seletor:
                elementos = await page.query_selector_all(seletor)
                result.append(f"📌 Seletor: `{seletor}` — **{len(elementos)} resultado(s)**\n")
                for i, el in enumerate(elementos[:30], 1):
                    texto = (await el.inner_text()).strip()[:200]
                    result.append(f"  {i}. {texto}")

            elif tipo == "links":
                links = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href]'))
                        .map(a => ({ texto: a.innerText.trim().slice(0, 80), url: a.href }))
                        .filter(l => l.texto && l.url.startsWith('http'))
                        .slice(0, 30)
                """)
                result.append(f"🔗 **{len(links)} links:**\n")
                for lk in links:
                    result.append(f"  ↳ [{lk['texto']}]({lk['url']})")

            elif tipo == "imagens":
                imgs = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('img[src]'))
                        .map(i => ({ alt: i.alt || '(sem alt)', src: i.src }))
                        .filter(i => i.src.startsWith('http'))
                        .slice(0, 20)
                """)
                result.append(f"🖼️ **{len(imgs)} imagens:**\n")
                for img in imgs:
                    result.append(f"  ↳ {img['alt']}: {img['src'][:100]}")

            elif tipo == "tabela":
                tabelas = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('table')).map(t =>
                        Array.from(t.querySelectorAll('tr')).map(r =>
                            Array.from(r.querySelectorAll('td, th')).map(c => c.innerText.trim())
                        )
                    ).slice(0, 3)
                """)
                if tabelas:
                    result.append(f"📊 **{len(tabelas)} tabela(s):**\n")
                    for i, tab in enumerate(tabelas, 1):
                        result.append(f"  **Tabela {i}:**")
                        for row in tab[:15]:
                            result.append(f"    | {' | '.join(str(c)[:30] for c in row)} |")
                else:
                    result.append("⚠️ Nenhuma tabela encontrada.")

            elif tipo == "precos" or tipo == "preco":
                precos = await page.evaluate("""
                    () => {
                        const els = document.querySelectorAll('[class*="price"], [class*="preco"], [class*="valor"], .price, .preco');
                        if (els.length) return Array.from(els).map(e => e.innerText.trim()).filter(t => t).slice(0, 20);
                        const all = document.body.innerText;
                        const matches = all.match(/R\\$\\s*[\\d.,]+/g) || [];
                        return matches.slice(0, 20);
                    }
                """)
                result.append(f"💰 **{len(precos)} preços encontrados:**\n")
                for pr in precos:
                    result.append(f"  ↳ {pr}")

            else:
                titulo = await page.title()
                texto = await page.evaluate("() => document.body.innerText")
                result.append(f"📄 **Título:** {titulo}\n")
                result.append(f"📝 **Conteúdo:**\n{texto[:5000]}")
                if len(texto) > 5000:
                    result.append(f"\n… (truncado — total: {len(texto)} chars)")

            await browser.close()
            return "\n".join(result)

    except Exception as e:
        return f"❌ Erro ao extrair: {e}"


# ═══════════════════════════════════════════════════════════════
#  [37] MONITORAR SITE
# ═══════════════════════════════════════════════════════════════

async def monitorar_site(url: str, seletor: str = "body", intervalo_minutos: int = 30, descricao: str = "") -> str:
    """
    Monitora mudanças em site periodicamente.

    Args:
        url: URL para monitorar
        seletor: CSS selector do elemento a observar
        intervalo_minutos: intervalo de verificação
        descricao: descrição do monitoramento
    """
    dados = _monitores.load()

    # Verifica duplicata
    for m in dados:
        if m.get("url") == url and m.get("seletor") == seletor:
            return f"⚠️ Já existe monitor para `{url}` com seletor `{seletor}`."

    # Captura valor inicial
    valor_inicial = ""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            els = await page.query_selector_all(seletor)
            if els:
                valor_inicial = (await els[0].inner_text())[:2000]
            else:
                valor_inicial = (await page.evaluate("() => document.body.innerText.slice(0, 1000)"))
            await browser.close()
    except Exception:
        pass

    monitor = {
        "id": f"{url}_{seletor}"[:100].replace("/", "_").replace(":", "_"),
        "url": url,
        "seletor": seletor,
        "intervalo_minutos": intervalo_minutos,
        "descricao": descricao or f"Monitorando {url}",
        "valor_anterior": valor_inicial,
        "criado_em": agora_brasil_iso(),
        "ultima_verificacao": agora_brasil_iso(),
        "mudancas_detectadas": 0,
        "ativo": True,
    }

    dados.append(monitor)
    _monitores.save(dados)

    return (
        f"✅ **Monitor ativado!**\n\n"
        f"🌐 URL: `{url}`\n"
        f"🎯 Seletor: `{seletor}`\n"
        f"⏰ Intervalo: {intervalo_minutos} min\n"
        f"📝 {descricao or 'Monitorando mudanças'}"
    )


async def verificar_monitores() -> str:
    """Verifica todos os monitores ativos por mudanças."""
    dados = _monitores.load()
    ativos = [m for m in dados if m.get("ativo")]

    if not ativos:
        return "Nenhum monitor ativo."

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "❌ Playwright não disponível."

    mudancas = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for monitor in ativos:
                try:
                    page = await browser.new_page()
                    await page.goto(monitor["url"], timeout=30000)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass

                    els = await page.query_selector_all(monitor["seletor"])
                    valor_atual = (await els[0].inner_text())[:2000] if els else ""

                    if valor_atual and valor_atual != monitor.get("valor_anterior", ""):
                        mudancas.append({
                            "url": monitor["url"],
                            "desc": monitor.get("descricao", ""),
                            "anterior": monitor.get("valor_anterior", "")[:150],
                            "atual": valor_atual[:150],
                        })
                        monitor["valor_anterior"] = valor_atual
                        monitor["mudancas_detectadas"] = monitor.get("mudancas_detectadas", 0) + 1

                    monitor["ultima_verificacao"] = agora_brasil_iso()
                    await page.close()
                except Exception:
                    continue

            await browser.close()
    except Exception as e:
        return f"❌ Erro: {e}"

    _monitores.save(dados)

    if mudancas:
        linhas = [f"🔔 **{len(mudancas)} mudança(s)!**\n"]
        for m in mudancas:
            linhas.append(f"  🌐 {m['url']}")
            linhas.append(f"     {m['desc']}")
            linhas.append(f"     Antes: {m['anterior'][:80]}…")
            linhas.append(f"     Agora: {m['atual'][:80]}…\n")
        return "\n".join(linhas)

    return f"✅ {len(ativos)} monitor(es) verificado(s). Sem mudanças."


def parar_monitoramento(url: str) -> str:
    """Para monitoramento de um site."""
    dados = _monitores.load()
    encontrado = False
    for m in dados:
        if url.lower() in m.get("url", "").lower():
            m["ativo"] = False
            encontrado = True
    _monitores.save(dados)
    return f"⏹️ Monitor parado: {url}" if encontrado else f"Nenhum monitor para: {url}"


def listar_monitores() -> str:
    """Lista monitores configurados."""
    dados = _monitores.load()
    if not dados:
        return "Nenhum monitor configurado."

    linhas = [f"📡 **Monitores ({len(dados)}):**\n"]
    for m in dados:
        status = "🟢 Ativo" if m.get("ativo") else "🔴 Parado"
        linhas.append(f"  {status} | {m.get('descricao', m['url'])}")
        linhas.append(f"    ↳ URL: {m['url']}")
        linhas.append(f"    ↳ Intervalo: {m.get('intervalo_minutos', '?')} min")
        linhas.append(f"    ↳ Mudanças: {m.get('mudancas_detectadas', 0)}\n")
    return "\n".join(linhas)
