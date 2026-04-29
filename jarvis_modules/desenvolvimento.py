"""
═══════════════════════════════════════════════════════════════
  [32] gerar_projeto_completo
  [33] debug_autonomo
  [34] refatoracao_inteligente
  [35] explicar_codigo_visual
  [48] gerar_interface_ui
═══════════════════════════════════════════════════════════════

Motor de desenvolvimento automático — gera projetos inteiros,
detecta e corrige erros, refatora código, explica visualmente,
e cria interfaces UI completas.

Nível INSANO de automação para dev.
"""

import os
import re
from datetime import datetime
from .core import BASE_DIR


OUTPUT_DIR = os.path.join(BASE_DIR, "data", "projetos_gerados")


# ═══════════════════════════════════════════════════════════════
#  [32] GERAR PROJETO COMPLETO
# ═══════════════════════════════════════════════════════════════

def gerar_projeto_completo(nome: str, tipo: str, descricao: str) -> str:
    """
    Gera projeto com estrutura real, código funcional, README e config.

    tipo: web | api | fullstack | bot | script | saas
    """
    projeto_dir = os.path.join(OUTPUT_DIR, nome)
    try:
        os.makedirs(projeto_dir, exist_ok=True)
        tipo = tipo.lower().strip()

        geradores = {
            "web": _web, "frontend": _web,
            "api": _api, "backend": _api,
            "fullstack": _fullstack,
            "bot": _bot, "whatsapp": _bot, "discord": _bot, "telegram": _bot,
            "saas": _fullstack,
        }
        gerador = geradores.get(tipo, _script)
        arquivos = gerador(projeto_dir, nome, descricao, tipo)

        _readme(projeto_dir, nome, tipo, descricao, arquivos)
        _gitignore(projeto_dir)

        return (
            f"✅ **Projeto '{nome}' criado!**\n\n"
            f"📁 Local: `{projeto_dir}`\n"
            f"📦 Tipo: {tipo}\n"
            f"📄 Arquivos:\n" +
            "\n".join(f"  ↳ {f}" for f in arquivos + ["README.md", ".gitignore"])
        )
    except Exception as e:
        return f"❌ Erro: {e}"


# ═══════════════════════════════════════════════════════════════
#  [33] DEBUG AUTÔNOMO
# ═══════════════════════════════════════════════════════════════

def debug_autonomo(caminho: str, erro: str = "") -> str:
    """
    Análise estática inteligente de código.

    Detecta:
      • Indentação inconsistente (tabs + espaços)
      • Imports possivelmente não usados
      • except genérico (anti-pattern)
      • print() em produção
      • Variáveis genéricas (x, y, z)
      • Funções muito longas (>50 linhas)
      • Linhas muito extensas (>120 chars)
      • Docstrings ausentes
      • Magic numbers
    """
    if not os.path.exists(caminho):
        return f"❌ Arquivo não encontrado: {caminho}"

    with open(caminho, "r", encoding="utf-8") as f:
        codigo = f.read()

    linhas = codigo.split("\n")
    problemas = []
    func_atual, func_inicio = None, 0

    for i, linha in enumerate(linhas, 1):
        stripped = linha.strip()

        # Indentação mista
        if "\t" in linha and "    " in linha:
            problemas.append(("⚠️", i, "Mistura de tabs e espaços"))

        # Except genérico
        if stripped in ("except:", "except Exception:"):
            problemas.append(("🔴", i, "Except genérico — capture exceções específicas"))

        # Print em produção
        if stripped.startswith("print(") and "if __name__" not in codigo[max(0, i-30):i+1]:
            problemas.append(("🟡", i, "print() — considere logging"))

        # Variáveis genéricas
        if re.match(r'^[xyz]\s*=\s', stripped) and "for" not in stripped:
            problemas.append(("🟡", i, f"Variável genérica: {stripped[:40]}"))

        # Linha muito longa
        if len(linha) > 120 and not stripped.startswith("#"):
            problemas.append(("🟡", i, f"Linha com {len(linha)} chars (max recomendado: 120)"))

        # Import possivelmente não usado
        if stripped.startswith("import ") or stripped.startswith("from "):
            modulo = stripped.split()[-1].split(".")[0]
            restante = codigo.replace(linha, "")
            if modulo not in restante and modulo not in ("os", "sys", "re", "json"):
                problemas.append(("🟡", i, f"Import possivelmente não usado: {stripped[:60]}"))

        # Funções longas
        if stripped.startswith("def "):
            if func_atual and (i - func_inicio) > 50:
                problemas.append(("⚡", func_inicio, f"Função '{func_atual}' tem {i - func_inicio} linhas — divida"))
            func_atual = stripped.split("(")[0].replace("def ", "")
            func_inicio = i

        # Sem docstring
        if stripped.startswith("def ") or stripped.startswith("class "):
            next_line = linhas[i] if i < len(linhas) else ""
            if '"""' not in next_line and "'''" not in next_line:
                nome_item = stripped.split("(")[0].replace("def ", "").replace("class ", "").replace(":", "")
                problemas.append(("📝", i, f"'{nome_item}' sem docstring"))

        # Magic numbers
        if not stripped.startswith("#"):
            nums = re.findall(r'(?<!=)\b\d{3,}\b(?![\.\d])', stripped)
            for n in nums:
                if int(n) not in (0, 1, 100, 200, 201, 301, 400, 404, 500, 1000, 8000, 8080, 3000):
                    problemas.append(("🔢", i, f"Magic number '{n}' — use constante nomeada"))
                    break

    # Resultado
    result = [f"🔍 **Debug Autônomo:** `{os.path.basename(caminho)}`\n"]

    if erro:
        result.append(f"❌ **Erro reportado:** {erro}\n")

    # Estatísticas
    n_func = sum(1 for l in linhas if l.strip().startswith("def "))
    n_class = sum(1 for l in linhas if l.strip().startswith("class "))
    n_import = sum(1 for l in linhas if "import " in l)
    n_comment = sum(1 for l in linhas if l.strip().startswith("#"))
    n_empty = sum(1 for l in linhas if not l.strip())

    result.append("📊 **Estatísticas:**")
    result.append(f"  ↳ Linhas: {len(linhas)} (código: {len(linhas) - n_empty - n_comment} / comentários: {n_comment})")
    result.append(f"  ↳ Classes: {n_class} | Funções: {n_func} | Imports: {n_import}")

    # Pontuação de qualidade
    score = max(0, 100 - len(problemas) * 5)
    result.append(f"\n🏆 **Score de qualidade:** {score}/100\n")

    if problemas:
        result.append(f"⚠️ **{len(problemas)} problema(s) detectado(s):**\n")
        for emoji, linha_n, msg in problemas[:25]:
            result.append(f"  {emoji} L{linha_n}: {msg}")
    else:
        result.append("✅ **Nenhum problema detectado!** Código limpo.")

    return "\n".join(result)


# ═══════════════════════════════════════════════════════════════
#  [34] REFATORAÇÃO INTELIGENTE
# ═══════════════════════════════════════════════════════════════

def refatoracao_inteligente(caminho: str) -> str:
    """
    Analisa e sugere refatorações avançadas.

    Detecta:
      • Funções muito longas
      • Código duplicado
      • Alta complexidade ciclomática
      • Ausência de type hints
      • Padrões de design ausentes
      • Nomenclatura inconsistente
    """
    if not os.path.exists(caminho):
        return f"❌ Arquivo não encontrado: {caminho}"

    with open(caminho, "r", encoding="utf-8") as f:
        codigo = f.read()

    linhas = codigo.split("\n")
    sugestoes = []

    # 1. Funções longas
    func_ranges = []
    func_atual, func_inicio = None, 0
    for i, l in enumerate(linhas, 1):
        if l.strip().startswith("def "):
            if func_atual:
                func_ranges.append((func_atual, func_inicio, i - 1))
            func_atual = l.strip().split("(")[0].replace("def ", "")
            func_inicio = i
    if func_atual:
        func_ranges.append((func_atual, func_inicio, len(linhas)))

    for nome, inicio, fim in func_ranges:
        tamanho = fim - inicio
        if tamanho > 50:
            sugestoes.append(f"⚡ `{nome}()` tem {tamanho} linhas — quebre em sub-funções")
        elif tamanho > 30:
            sugestoes.append(f"🟡 `{nome}()` tem {tamanho} linhas — considere simplificar")

    # 2. Código duplicado
    code_lines = [l.strip() for l in linhas if l.strip() and not l.strip().startswith("#") and len(l.strip()) > 25]
    duplicadas = set()
    seen = set()
    for l in code_lines:
        if l in seen:
            duplicadas.add(l)
        seen.add(l)
    if duplicadas:
        sugestoes.append(f"🔄 {len(duplicadas)} blocos duplicados — extrair em funções reutilizáveis")

    # 3. Complexidade
    controle_flow = sum(1 for l in linhas if any(kw in l for kw in ["if ", "elif ", "else:", "for ", "while ", "try:", "except"]))
    ratio = controle_flow / max(len(linhas), 1)
    if ratio > 0.25:
        sugestoes.append(f"🌀 Alta complexidade ({ratio:.0%} — controle de fluxo) — use guard clauses ou strategy pattern")

    # 4. Sem type hints
    funcs_sem_hints = 0
    for l in linhas:
        if l.strip().startswith("def ") and "->" not in l and l.strip() != "def __init__(self):":
            funcs_sem_hints += 1
    if funcs_sem_hints > 0:
        sugestoes.append(f"📝 {funcs_sem_hints} função(ões) sem type hints — adicione `-> tipo`")

    # 5. Docstrings
    funcs_sem_doc = 0
    for i, l in enumerate(linhas):
        if l.strip().startswith("def ") or l.strip().startswith("class "):
            next_l = linhas[i + 1].strip() if i + 1 < len(linhas) else ""
            if '"""' not in next_l and "'''" not in next_l:
                funcs_sem_doc += 1
    if funcs_sem_doc > 0:
        sugestoes.append(f"📄 {funcs_sem_doc} função(ões) sem docstring")

    # 6. Naming conventions
    bad_names = sum(1 for l in linhas if re.match(r'^\s+(x|y|z|a|b|c|d|tmp|temp|foo|bar)\s*=', l))
    if bad_names > 0:
        sugestoes.append(f"🏷️ {bad_names} variáveis com nome genérico — use nomes descritivos")

    result = [f"🛠️ **Refatoração Inteligente:** `{os.path.basename(caminho)}`\n"]

    if sugestoes:
        result.append(f"📋 **{len(sugestoes)} sugestões de melhoria:**\n")
        for s in sugestoes:
            result.append(f"  {s}")
    else:
        result.append("✅ Código bem estruturado! Nenhuma sugestão.")

    return "\n".join(result)


# ═══════════════════════════════════════════════════════════════
#  [35] EXPLICAR CÓDIGO VISUAL
# ═══════════════════════════════════════════════════════════════

def explicar_codigo(codigo_ou_caminho: str) -> str:
    """Explica código de forma simplificada, nível humano."""
    # Lê arquivo se for caminho
    if os.path.exists(codigo_ou_caminho):
        with open(codigo_ou_caminho, "r", encoding="utf-8") as f:
            codigo = f.read()
    else:
        codigo = codigo_ou_caminho

    linhas = codigo.strip().split("\n")

    # Detecta linguagem
    lang = "Python"
    if any(kw in codigo for kw in ["function ", "const ", "let ", "=>"]):
        lang = "JavaScript"
    elif "<html" in codigo.lower():
        lang = "HTML"
    elif ":" in codigo and "{" in codigo and ";" in codigo and "import " not in codigo:
        lang = "CSS"

    result = ["📖 **Explicação do Código**\n"]
    result.append(f"🔤 Linguagem: **{lang}**")
    result.append(f"📊 Linhas: {len(linhas)}\n")

    if lang == "Python":
        imports = [l.strip() for l in linhas if l.strip().startswith(("import ", "from "))]
        classes = [l.strip() for l in linhas if l.strip().startswith("class ")]
        funcs = [l.strip() for l in linhas if l.strip().startswith("def ")]

        if imports:
            result.append("📦 **Dependências:**")
            for imp in imports[:12]:
                result.append(f"  ↳ `{imp}`")
            result.append("")

        if classes:
            result.append("🏗️ **Classes:**")
            for cls in classes:
                nome = cls.split("(")[0].replace("class ", "").replace(":", "")
                result.append(f"  ↳ `{nome}`")
            result.append("")

        if funcs:
            result.append("⚙️ **Funções:**")
            for func in funcs:
                nome = func.split("(")[0].replace("def ", "")
                # Tenta pegar docstring
                idx = linhas.index(func) if func in linhas else -1
                doc = ""
                if idx >= 0 and idx + 1 < len(linhas) and '"""' in linhas[idx + 1]:
                    doc = linhas[idx + 1].strip().strip('"').strip()
                desc = f" — {doc}" if doc else ""
                result.append(f"  ↳ `{nome}()`{desc}")
            result.append("")

        # Padrões
        padroes = []
        if "async def" in codigo:
            padroes.append("⚡ Programação assíncrona (async/await)")
        if "__init__" in codigo:
            padroes.append("🏗️ Programação Orientada a Objetos")
        if "@" in codigo and "def" in codigo:
            padroes.append("🎨 Usa decoradores")
        if "with " in codigo:
            padroes.append("🔒 Gerenciadores de contexto")
        if "yield " in codigo:
            padroes.append("🔄 Generators")

        if padroes:
            result.append("🧬 **Padrões detectados:**")
            for p in padroes:
                result.append(f"  {p}")

    result.append(
        f"\n💡 **Resumo:** Este código contém {len([l for l in linhas if l.strip().startswith('def ')])} funções "
        f"e {len([l for l in linhas if l.strip().startswith('class ')])} classes, "
        f"usando {len(linhas)} linhas de {lang}."
    )

    return "\n".join(result)


# ═══════════════════════════════════════════════════════════════
#  [48] GERAR INTERFACE UI
# ═══════════════════════════════════════════════════════════════

def gerar_interface_ui(nome: str, descricao: str, cor_primaria: str = "#6C63FF", estilo: str = "moderno_dark") -> str:
    """Gera interface HTML/CSS/JS completa com design premium."""
    output_dir = os.path.join(BASE_DIR, "data", "ui_geradas", nome.replace(" ", "-").lower())
    os.makedirs(output_dir, exist_ok=True)

    temas = {
        "moderno_dark": {"bg": "#0A0A12", "card": "#14142B", "text": "#F5F5FA", "sec": "#8888AA", "accent": "#E040FB"},
        "rosa":         {"bg": "#120812", "card": "#1E0E1E", "text": "#FFFFFF", "sec": "#C080C0", "accent": "#FF4081"},
        "azul":         {"bg": "#060E18", "card": "#0E1A2E", "text": "#F5F8FF", "sec": "#7090B0", "accent": "#448AFF"},
        "verde":        {"bg": "#061208", "card": "#0E1E12", "text": "#F5FFF5", "sec": "#70B080", "accent": "#69F0AE"},
        "claro":        {"bg": "#F5F5F7", "card": "#FFFFFF", "text": "#1A1A2E", "sec": "#666688", "accent": "#6C63FF"},
    }
    c = temas.get(estilo, temas["moderno_dark"])
    ano = datetime.now().year

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{nome}</title>
<meta name="description" content="{descricao}">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head>
<body>
<div class="cursor-glow" id="cursorGlow"></div>

<nav class="navbar" id="nav">
  <div class="nav-container">
    <a href="#" class="logo">{nome}</a>
    <div class="nav-links" id="navLinks">
      <a href="#home">Home</a>
      <a href="#features">Features</a>
      <a href="#about">Sobre</a>
      <a href="#contact">Contato</a>
    </div>
    <button class="menu-toggle" id="menuToggle" aria-label="Menu">
      <span></span><span></span><span></span>
    </button>
  </div>
</nav>

<section id="home" class="hero">
  <div class="hero-bg">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
  </div>
  <div class="hero-content">
    <span class="badge">✨ {nome}</span>
    <h1>{nome}</h1>
    <p class="subtitle">{descricao}</p>
    <div class="hero-actions">
      <button class="btn btn-glow">Começar Agora</button>
      <button class="btn btn-ghost">Saiba Mais →</button>
    </div>
  </div>
</section>

<section id="features" class="section">
  <h2 class="section-title">Features</h2>
  <p class="section-subtitle">Tudo que você precisa em um só lugar</p>
  <div class="cards-grid">
    <div class="card"><div class="card-icon">🚀</div><h3>Ultra Rápido</h3><p>Performance otimizada para qualquer escala</p></div>
    <div class="card"><div class="card-icon">🛡️</div><h3>Segurança Total</h3><p>Criptografia de ponta a ponta</p></div>
    <div class="card"><div class="card-icon">🎨</div><h3>Design Premium</h3><p>Interface minimalista e sofisticada</p></div>
    <div class="card"><div class="card-icon">⚡</div><h3>Automação</h3><p>Inteligência artificial integrada</p></div>
    <div class="card"><div class="card-icon">📊</div><h3>Analytics</h3><p>Dashboards em tempo real</p></div>
    <div class="card"><div class="card-icon">🔗</div><h3>Integrações</h3><p>Conecte com suas ferramentas favoritas</p></div>
  </div>
</section>

<section id="about" class="section">
  <h2 class="section-title">Sobre</h2>
  <div class="about-grid">
    <div class="about-text">
      <p>{descricao}</p>
      <ul class="check-list">
        <li>✅ Tecnologia de ponta</li>
        <li>✅ Suporte 24/7</li>
        <li>✅ Atualizações constantes</li>
        <li>✅ Comunidade ativa</li>
      </ul>
    </div>
    <div class="about-stats">
      <div class="stat"><span class="stat-num">99.9%</span><span class="stat-label">Uptime</span></div>
      <div class="stat"><span class="stat-num">10K+</span><span class="stat-label">Usuários</span></div>
      <div class="stat"><span class="stat-num">50+</span><span class="stat-label">Integrações</span></div>
    </div>
  </div>
</section>

<section id="contact" class="section">
  <h2 class="section-title">Contato</h2>
  <form class="contact-form" onsubmit="event.preventDefault();alert('Mensagem enviada!')">
    <div class="form-row">
      <input type="text" placeholder="Nome" required>
      <input type="email" placeholder="Email" required>
    </div>
    <textarea placeholder="Sua mensagem" rows="4" required></textarea>
    <button type="submit" class="btn btn-glow">Enviar Mensagem</button>
  </form>
</section>

<footer class="footer">
  <p>&copy; {ano} {nome}. Todos os direitos reservados.</p>
</footer>

<script src="script.js"></script>
</body>
</html>"""

    css = f""":root {{
  --primary: {cor_primaria};
  --accent: {c['accent']};
  --bg: {c['bg']};
  --card: {c['card']};
  --text: {c['text']};
  --sec: {c['sec']};
  --font: 'Inter', -apple-system, sans-serif;
  --glow: {cor_primaria}40;
  --gradient: linear-gradient(135deg, var(--primary), var(--accent));
}}

*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{ font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.7; overflow-x: hidden; }}

/* ── Cursor Glow ──────────────────────── */
.cursor-glow {{
  position: fixed; width: 600px; height: 600px; border-radius: 50%;
  background: radial-gradient(circle, var(--glow), transparent 70%);
  pointer-events: none; z-index: 0; transition: transform 0.1s;
  transform: translate(-50%, -50%);
}}

/* ── Navbar ───────────────────────────── */
.navbar {{
  position: fixed; top: 0; width: 100%; padding: 1rem 2rem;
  backdrop-filter: blur(24px) saturate(1.5);
  background: rgba({int(c['bg'][1:3], 16)}, {int(c['bg'][3:5], 16)}, {int(c['bg'][5:7], 16)}, 0.85);
  z-index: 1000; border-bottom: 1px solid rgba(255,255,255,0.06);
  transition: all 0.3s;
}}
.navbar.scrolled {{ padding: 0.6rem 2rem; box-shadow: 0 4px 30px rgba(0,0,0,0.3); }}
.nav-container {{ max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }}
.logo {{
  font-size: 1.5rem; font-weight: 800; text-decoration: none;
  background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.nav-links {{ display: flex; gap: 2rem; }}
.nav-links a {{ text-decoration: none; color: var(--sec); transition: 0.3s; font-weight: 500; position: relative; }}
.nav-links a::after {{ content: ''; position: absolute; bottom: -4px; left: 0; width: 0; height: 2px; background: var(--gradient); transition: width 0.3s; }}
.nav-links a:hover {{ color: var(--text); }}
.nav-links a:hover::after {{ width: 100%; }}
.menu-toggle {{ display: none; background: none; border: none; cursor: pointer; padding: 0.5rem; }}
.menu-toggle span {{ display: block; width: 24px; height: 2px; background: var(--text); margin: 5px 0; transition: 0.3s; }}

/* ── Hero ─────────────────────────────── */
.hero {{
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  text-align: center; padding: 6rem 2rem 4rem; position: relative; overflow: hidden;
}}
.hero-bg {{ position: absolute; inset: 0; overflow: hidden; z-index: 0; }}
.orb {{
  position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.4;
  animation: float 8s ease-in-out infinite;
}}
.orb-1 {{ width: 500px; height: 500px; background: var(--primary); top: 10%; left: 15%; animation-delay: 0s; }}
.orb-2 {{ width: 400px; height: 400px; background: var(--accent); bottom: 10%; right: 15%; animation-delay: -3s; }}
.orb-3 {{ width: 300px; height: 300px; background: var(--primary); top: 50%; left: 50%; animation-delay: -5s; }}
@keyframes float {{
  0%, 100% {{ transform: translate(0, 0) scale(1); }}
  33% {{ transform: translate(30px, -30px) scale(1.05); }}
  66% {{ transform: translate(-20px, 20px) scale(0.95); }}
}}
.hero-content {{ position: relative; z-index: 1; max-width: 800px; }}
.badge {{
  display: inline-block; padding: 0.4rem 1.2rem; border-radius: 50px; font-size: 0.85rem;
  background: rgba({int(cor_primaria[1:3], 16)}, {int(cor_primaria[3:5], 16)}, {int(cor_primaria[5:7], 16)}, 0.15);
  border: 1px solid var(--primary); color: var(--primary); font-weight: 600;
  animation: pulse-badge 2s ease-in-out infinite;
}}
@keyframes pulse-badge {{
  0%, 100% {{ box-shadow: 0 0 0 0 var(--glow); }}
  50% {{ box-shadow: 0 0 20px 4px var(--glow); }}
}}
.hero h1 {{
  font-size: clamp(2.5rem, 6vw, 5rem); font-weight: 800; margin: 1rem 0;
  background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  line-height: 1.1;
}}
.subtitle {{ color: var(--sec); font-size: 1.2rem; max-width: 600px; margin: 0 auto 2rem; }}
.hero-actions {{ display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }}
.btn {{
  padding: 0.85rem 2.2rem; border-radius: 50px; font-size: 1rem; font-weight: 600;
  cursor: pointer; transition: all 0.3s; border: none; font-family: var(--font);
}}
.btn-glow {{
  background: var(--gradient); color: #fff;
  box-shadow: 0 4px 20px var(--glow);
}}
.btn-glow:hover {{ transform: translateY(-3px); box-shadow: 0 8px 40px var(--glow); }}
.btn-ghost {{ background: transparent; border: 2px solid rgba(255,255,255,0.15); color: var(--text); }}
.btn-ghost:hover {{ background: rgba(255,255,255,0.05); border-color: var(--primary); }}

/* ── Sections ─────────────────────────── */
.section {{ max-width: 1200px; margin: 0 auto; padding: 8rem 2rem; }}
.section-title {{
  font-size: 2.8rem; text-align: center; margin-bottom: 0.5rem; font-weight: 800;
  background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.section-subtitle {{ text-align: center; color: var(--sec); font-size: 1.1rem; margin-bottom: 4rem; }}

/* ── Cards ────────────────────────────── */
.cards-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }}
.card {{
  background: var(--card); padding: 2rem; border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.06); transition: all 0.4s;
  position: relative; overflow: hidden;
}}
.card::before {{
  content: ''; position: absolute; inset: 0; border-radius: 20px;
  background: var(--gradient); opacity: 0; transition: opacity 0.4s;
  z-index: 0;
}}
.card:hover {{ transform: translateY(-8px); border-color: transparent; }}
.card:hover::before {{ opacity: 0.06; }}
.card > * {{ position: relative; z-index: 1; }}
.card-icon {{ font-size: 2.5rem; margin-bottom: 1rem; }}
.card h3 {{ margin-bottom: 0.5rem; font-size: 1.2rem; }}
.card p {{ color: var(--sec); font-size: 0.95rem; }}

/* ── About ────────────────────────────── */
.about-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: center; }}
.about-text p {{ color: var(--sec); font-size: 1.1rem; margin-bottom: 1.5rem; }}
.check-list {{ list-style: none; }}
.check-list li {{ padding: 0.4rem 0; color: var(--text); font-weight: 500; }}
.about-stats {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }}
.stat {{
  background: var(--card); padding: 2rem; border-radius: 16px; text-align: center;
  border: 1px solid rgba(255,255,255,0.06);
}}
.stat-num {{
  display: block; font-size: 2rem; font-weight: 800;
  background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.stat-label {{ color: var(--sec); font-size: 0.85rem; margin-top: 0.3rem; display: block; }}

/* ── Contact ──────────────────────────── */
.contact-form {{ max-width: 600px; margin: 0 auto; display: flex; flex-direction: column; gap: 1rem; }}
.form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
.contact-form input, .contact-form textarea {{
  padding: 1rem 1.2rem; background: var(--card); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px; color: var(--text); font-family: var(--font); font-size: 1rem;
  outline: none; transition: 0.3s;
}}
.contact-form input:focus, .contact-form textarea:focus {{
  border-color: var(--primary); box-shadow: 0 0 20px var(--glow);
}}

/* ── Footer ───────────────────────────── */
.footer {{ text-align: center; padding: 3rem 2rem; border-top: 1px solid rgba(255,255,255,0.06); color: var(--sec); }}

/* ── Animations ───────────────────────── */
.reveal {{ opacity: 0; transform: translateY(30px); transition: all 0.7s cubic-bezier(0.22, 1, 0.36, 1); }}
.reveal.visible {{ opacity: 1; transform: translateY(0); }}

/* ── Responsive ───────────────────────── */
@media (max-width: 768px) {{
  .nav-links {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100vh; background: var(--bg); flex-direction: column; justify-content: center; align-items: center; gap: 2rem; z-index: 999; }}
  .nav-links.active {{ display: flex; }}
  .menu-toggle {{ display: block; z-index: 1001; }}
  .menu-toggle.active span:nth-child(1) {{ transform: rotate(45deg) translate(5px, 5px); }}
  .menu-toggle.active span:nth-child(2) {{ opacity: 0; }}
  .menu-toggle.active span:nth-child(3) {{ transform: rotate(-45deg) translate(5px, -5px); }}
  .hero h1 {{ font-size: 2.5rem; }}
  .about-grid {{ grid-template-columns: 1fr; }}
  .about-stats {{ grid-template-columns: repeat(3, 1fr); }}
  .form-row {{ grid-template-columns: 1fr; }}
  .cards-grid {{ grid-template-columns: 1fr; }}
}}"""

    js = """// ── Cursor Glow ─────────────────────────
const glow = document.getElementById('cursorGlow');
if (window.innerWidth > 768) {
  document.addEventListener('mousemove', e => {
    glow.style.transform = `translate(${e.clientX - 300}px, ${e.clientY - 300}px)`;
  });
}

// ── Navbar Scroll ───────────────────────
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 50);
});

// ── Mobile Menu ─────────────────────────
const toggle = document.getElementById('menuToggle');
const links = document.getElementById('navLinks');
toggle.addEventListener('click', () => {
  toggle.classList.toggle('active');
  links.classList.toggle('active');
});
links.querySelectorAll('a').forEach(a => {
  a.addEventListener('click', () => {
    toggle.classList.remove('active');
    links.classList.remove('active');
  });
});

// ── Reveal Animations ───────────────────
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

document.querySelectorAll('.card, .section, .stat, .about-text, .contact-form').forEach(el => {
  el.classList.add('reveal');
  observer.observe(el);
});

// ── Smooth Scroll ───────────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', e => {
    e.preventDefault();
    const target = document.querySelector(anchor.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

// ── Number Counter Animation ────────────
const counters = document.querySelectorAll('.stat-num');
const countObserver = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const el = entry.target;
      const text = el.textContent;
      const num = parseInt(text.replace(/[^0-9]/g, ''));
      const suffix = text.replace(/[0-9.]/g, '');
      if (!isNaN(num) && num > 0) {
        let current = 0;
        const step = Math.ceil(num / 40);
        const timer = setInterval(() => {
          current = Math.min(current + step, num);
          el.textContent = current + suffix;
          if (current >= num) clearInterval(timer);
        }, 30);
      }
      countObserver.unobserve(el);
    }
  });
}, { threshold: 0.5 });
counters.forEach(c => countObserver.observe(c));"""

    _escrever(os.path.join(output_dir, "index.html"), html)
    _escrever(os.path.join(output_dir, "style.css"), css)
    _escrever(os.path.join(output_dir, "script.js"), js)

    return (
        f"✅ **Interface '{nome}' gerada!**\n\n"
        f"📁 Local: `{output_dir}`\n"
        f"📄 index.html + style.css + script.js\n"
        f"🎨 Estilo: {estilo} | Cor: {cor_primaria}\n"
        f"✨ Micro-animações, cursor glow, orbs, scroll reveal, contadores"
    )


# ═══════════════════════════════════════════════════════════════
#  Geradores internos de projeto
# ═══════════════════════════════════════════════════════════════

def _escrever(caminho: str, conteudo: str):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)


def _web(base, nome, desc, tipo="web"):
    year = datetime.now().year
    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{nome}</title>
    <link rel="stylesheet" href="css/style.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body>
    <header class="header">
        <nav class="nav">
            <div class="logo">{nome}</div>
            <ul class="nav-links">
                <li><a href="#home">Home</a></li>
                <li><a href="#about">Sobre</a></li>
                <li><a href="#contact">Contato</a></li>
            </ul>
        </nav>
    </header>
    <main>
        <section id="home" class="hero">
            <h1>{nome}</h1>
            <p>{desc}</p>
            <button class="btn-primary">Começar</button>
        </section>
        <section id="about" class="section"><h2>Sobre</h2><p>Mais sobre o projeto.</p></section>
        <section id="contact" class="section"><h2>Contato</h2><p>Entre em contato.</p></section>
    </main>
    <footer class="footer"><p>&copy; {year} {nome}</p></footer>
    <script src="js/main.js"></script>
</body>
</html>'''

    css = ''':root { --primary: #6C63FF; --bg: #0A0A12; --card: #14142B; --text: #F5F5FA; --sec: #8888AA; --font: 'Inter', sans-serif; }
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.7; }
.header { position: fixed; top: 0; width: 100%; padding: 1rem 2rem; backdrop-filter: blur(20px); background: rgba(10,10,18,.85); z-index: 100; border-bottom: 1px solid rgba(255,255,255,.06); }
.nav { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
.logo { font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, var(--primary), #E040FB); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.nav-links { display: flex; list-style: none; gap: 2rem; }
.nav-links a { text-decoration: none; color: var(--sec); transition: .3s; }
.nav-links a:hover { color: var(--primary); }
.hero { min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 2rem; }
.hero h1 { font-size: 4rem; font-weight: 800; background: linear-gradient(135deg, var(--primary), #E040FB); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 1rem; }
.hero p { color: var(--sec); font-size: 1.2rem; margin-bottom: 2rem; max-width: 600px; }
.btn-primary { padding: .85rem 2.2rem; background: linear-gradient(135deg, var(--primary), #E040FB); border: none; border-radius: 50px; color: #fff; font-size: 1rem; font-weight: 600; cursor: pointer; transition: .3s; }
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(108,99,255,.3); }
.section { max-width: 1200px; margin: 0 auto; padding: 6rem 2rem; }
.section h2 { font-size: 2.5rem; margin-bottom: 1rem; background: linear-gradient(135deg, var(--primary), #E040FB); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.footer { text-align: center; padding: 2rem; border-top: 1px solid rgba(255,255,255,.06); color: var(--sec); }
@media (max-width: 768px) { .hero h1 { font-size: 2.5rem; } }'''

    js = '''document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('a[href^="#"]').forEach(a => {
        a.addEventListener('click', e => { e.preventDefault(); document.querySelector(a.getAttribute('href')).scrollIntoView({ behavior: 'smooth' }); });
    });
    const obs = new IntersectionObserver(e => { e.forEach(en => { if (en.isIntersecting) { en.target.style.opacity='1'; en.target.style.transform='translateY(0)'; } }); }, { threshold: .1 });
    document.querySelectorAll('.section').forEach(el => { el.style.opacity='0'; el.style.transform='translateY(20px)'; el.style.transition='all .6s ease'; obs.observe(el); });
});'''

    for d in ("css", "js", "assets"):
        os.makedirs(os.path.join(base, d), exist_ok=True)
    _escrever(os.path.join(base, "index.html"), html)
    _escrever(os.path.join(base, "css", "style.css"), css)
    _escrever(os.path.join(base, "js", "main.js"), js)
    return ["index.html", "css/style.css", "js/main.js", "assets/"]


def _api(base, nome, desc, tipo="api"):
    main = f'''"""
{nome} — {desc}
API gerada pelo Jarvis.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="{nome}", description="{desc}")

class Item(BaseModel):
    id: Optional[int] = None
    nome: str
    descricao: str = ""
    ativo: bool = True

db: list[Item] = []
next_id = 1

@app.get("/")
async def root():
    return {{"msg": "API {nome} funcionando!", "docs": "/docs"}}

@app.get("/items")
async def listar(): return db

@app.post("/items", status_code=201)
async def criar(item: Item):
    global next_id
    item.id = next_id; next_id += 1
    db.append(item); return item

@app.get("/items/{{item_id}}")
async def obter(item_id: int):
    for i in db:
        if i.id == item_id: return i
    raise HTTPException(404, "Não encontrado")

@app.delete("/items/{{item_id}}")
async def deletar(item_id: int):
    global db
    db = [i for i in db if i.id != item_id]
    return {{"msg": "Deletado"}}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
'''
    reqs = "fastapi\\nuvicorn[standard]\\npydantic\\n"
    _escrever(os.path.join(base, "main.py"), main)
    _escrever(os.path.join(base, "requirements.txt"), reqs)
    return ["main.py", "requirements.txt"]


def _fullstack(base, nome, desc, tipo="fullstack"):
    front = _web(os.path.join(base, "frontend"), nome, desc)
    back = _api(os.path.join(base, "backend"), nome, desc)
    return [f"frontend/{f}" for f in front] + [f"backend/{f}" for f in back]


def _bot(base, nome, desc, tipo="bot"):
    bot_code = f'''"""
{nome} — Bot {tipo}
{desc}
"""
import os, logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class {nome.replace("-","_").title().replace("_","")}Bot:
    def __init__(self):
        self.running = False
        logger.info("Bot inicializado")

    async def start(self):
        self.running = True
        logger.info("Bot iniciado!")

    async def stop(self):
        self.running = False
        logger.info("Bot parado.")

    async def on_message(self, message: str, sender: str):
        logger.info(f"{{sender}}: {{message}}")
        return f"Resposta para: {{message}}"

if __name__ == "__main__":
    import asyncio
    bot = {nome.replace("-","_").title().replace("_","")}Bot()
    asyncio.run(bot.start())
'''
    _escrever(os.path.join(base, "bot.py"), bot_code)
    _escrever(os.path.join(base, ".env.example"), f"# {nome}\\nBOT_TOKEN=\\n")
    _escrever(os.path.join(base, "requirements.txt"), "python-dotenv\\nrequests\\n")
    return ["bot.py", ".env.example", "requirements.txt"]


def _script(base, nome, desc, tipo="script"):
    code = f'''"""
{nome} — {desc}
Gerado pelo Jarvis em {datetime.now().strftime("%Y-%m-%d")}
"""
import os, logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Iniciando {nome}...")
    print("Executado com sucesso!")

if __name__ == "__main__":
    main()
'''
    _escrever(os.path.join(base, "main.py"), code)
    _escrever(os.path.join(base, "requirements.txt"), "# Dependências\\n")
    return ["main.py", "requirements.txt"]


def _readme(base, nome, tipo, desc, arquivos):
    readme = f"""# {nome}

> {desc}

## 📋 Info
- **Tipo:** {tipo}
- **Gerado por:** Jarvis AI
- **Data:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

## 📁 Estrutura
```
{nome}/
{"".join(f"├── {f}" + chr(10) for f in arquivos)}└── README.md
```

## 🚀 Uso
```bash
pip install -r requirements.txt
python main.py
```
"""
    _escrever(os.path.join(base, "README.md"), readme)


def _gitignore(base):
    gi = """__pycache__/
*.pyc
.env
.venv/
venv/
node_modules/
.DS_Store
*.log
"""
    _escrever(os.path.join(base, ".gitignore"), gi)
