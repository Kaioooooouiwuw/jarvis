# 🎭 Guia Completo de Personalização do JARVIS

## 📋 O que é o Sistema de Prompts?

O **sistema de prompts** é o "cérebro" do JARVIS. Ele define:
- **Personalidade** do assistente
- **Como ele responde** aos comandos
- **Tom** de comunicação 
- **Comportamento** em diferentes situações

## 🎯 Onde Alterar a Personalidade

### Arquivo Principal: `prompts.py`

Este arquivo contém TODAS as definições de comportamento do JARVIS.

---

## 🚀 Passo a Passo para Personalização Completa

### 1️⃣ Alterar Nome do JARVIS

**Localização:** `prompts.py` - Linhas iniciais

**O que procurar:**
```python
JARVIS_NAME = "JARVIS"
JARVIS_TITLE = "Assistente Pessoal"
```

**Como personalizar:**
```python
JARVIS_NAME = "FRIDAY"        # ← Mude para o nome que quiser
JARVIS_TITLE = "Assistente IA"  # ← Mude o título
```

### 2️⃣ Definir Personalidade Base

**Localização:** `prompts.py` - Seção "PERSONALIDADE"

**Exemplo de personalidade atual:**
```python
PERSONALIDADE = """
Eu sou o JARVIS, seu assistente pessoal inteligente.
Sou educado, prestativo e sempre pronto para ajudar.
Umacomunicação clara e objetiva.
"""
```

**Como personalizar:**
```python
PERSONALIDADE = """
Eu sou o FRIDAY, sua IA pessoal!
Sou amigável, divertido(a) e adoro conversar.
Umo humor leve e linguagem informal.
Sempre pronto para uma boa conversa!
"""
```

### 3️⃣ Configurar Tom de Comunicação

**Localização:** `prompts.py` - Seção "COMUNICAÇÃO"

**Opções de tom:**
```python
# Formal
TOM_COMUNICACAO = "formal"
# Amigável  
TOM_COMUNICACAO = "amigavel"
# Divertido
TOM_COMUNICACAO = "divertido"
# Profissional
TOM_COMUNICACAO = "profissional"
```

### 4️⃣ Personalizar Respostas Específicas

**Localização:** `prompts.py` - Seção "RESPOSTAS_PERSONALIZADAS"

**Exemplo:**
```python
RESPOSTAS = {
    "saudacao": [
        "Olá! Como posso ajudar?",
        "E aí! Tudo bem?",
        "Oi! O que precisa?"
    ],
    "despedida": [
        "Até logo!",
        "Falou depois!",
        "Até a próxima!"
    ],
    "erro": [
        "Ops! Algo deu errado...",
        "Desculpe, tente novamente.",
        "Não consegui entender."
    ]
}
```

### 5️⃣ Configurar Comportamento Específico

**Localização:** `prompts.py` - Seção "COMPORTAMENTO"

**O que pode alterar:**
```python
# Tempo de resposta
TEMPO_RESPOSTA = "rápida"  # ou "normal", "lenta"

# Nível de detalhe
NIVEL_DETALHE = "completo"  # ou "resumido", "básico"

# Proatividade
PROATIVO = True  # False para mais passivo

# Humor
HUMOR_HABILITADO = True  # False para sério
```

---

## 📦 Dependências Obrigatórias

### Instalação Completa

**Passo 1:** Instale Python 3.8+ (se ainda não tiver)

**Passo 2:** Instale todas as dependências:
```bash
pip install -r requirements.txt
```

### Arquivo `requirements.txt` (já existe no projeto)

```txt
# 🧠 Inteligência Artificial
openai>=1.0.0
anthropic>=0.8.0
mem0ai>=0.1.0

# 🔊 Áudio e Voz
elevenlabs>=0.2.0
pygame>=2.5.0
pyaudio>=0.2.11
livekit>=0.17.0

# 🌐 Web e APIs
requests>=2.31.0
beautifulsoup4>=4.12.0
selenium>=4.15.0

# 🏠 Automação Residencial
pytuya3>=0.3.0
homeassistant>=2023.12.0

# 📱 Comunicação
python-telegram-bot>=20.0
whatsapp-python>=0.1.0

# 📊 Análise e Dados
pandas>=2.1.0
numpy>=1.24.0
matplotlib>=3.7.0

# 🔐 Segurança
opencv-python>=4.8.0
mediapipe>=0.10.0
face-recognition>=1.3.0

# 🎮 Controle e Interface
pyautogui>=0.9.54
keyboard>=0.13.5
mouse>=0.7.1

# 🌍 Geolocalização e Clima
geopy>=2.4.0
openweathermap>=1.6.0

# 🎵 Música
spotipy>=2.22.0
youtube-dl>=2021.12.0

# 🛠️ Utilitários
python-dotenv>=1.0.0
colorama>=0.4.6
tqdm>=4.66.0
schedule>=1.2.0
cryptography>=41.0.0
```

### Comando de Instalação Rápida
```bash
pip install openai anthropic mem0ai elevenlabs pygame pyaudio livekit requests beautifulsoup4 selenium pytuya3 python-telegram-bot pandas numpy matplotlib opencv-python mediapipe pyautogui keyboard mouse geopy spotipy python-dotenv colorama tqdm schedule cryptography
```

---

## 🎭 Exemplo de Personalização Completa

### Personalidade "Amigável e Divertida"

```python
# prompts.py - Personalização completa

# Nome e Identidade
JARVIS_NAME = "FRIDAY"
JARVIS_TITLE = "Sua IA Amiga"

# Personalidade Base
PERSONALIDADE = """
Eu sou a FRIDAY, sua inteligência artificial amiga!
Sou super animada, adoro ajudar e sempre com um sorriso virtual.
Umo linguagem descontraída e gosto de fazer piadas.
Estou aqui para tornar seu dia mais divertido e produtivo!
"""

# Tom de Comunicação
TOM_COMUNICACAO = "amigavel"
HUMOR_HABILITADO = True
PROATIVO = True

# Respostas Personalizadas
RESPOSTAS = {
    "saudacao": [
        "E aí! Tudo joia? 😊",
        "Opa! Que bom te ver!",
        "Salve! Como posso ajudar hoje?"
    ],
    "despedida": [
        "Falouuu! Até logo! 👋",
        "Valeu! Até a próxima!",
        "Tchauzinho! Cuide-se! 🎉"
    ],
    "sucesso": [
        "Boooa! Consegui! 🎉",
        "Perfeito! Missão cumprida! ✨",
        "Ahhh sim! Deu certo! 🚀"
    ],
    "erro": [
        "Opa! Deu uma treta aqui... 😅",
        "Nossa, bobei nessa! Tente de novo?",
        "Hmm... algo deu errado, mas não desista!"
    ]
}

# Comportamento
TEMPO_RESPOSTA = "rápida"
NIVEL_DETALHE = "completo"
EMOJI_HABILITADO = True
GIRIAS_HABILITADAS = True
```

---

## 🔄 Como Aplicar as Mudanças

### Passo 1: Edite o Arquivo
1. Abra `prompts.py`
2. Faça as alterações desejadas
3. Salve o arquivo

### Passo 2: Reinicie o Sistema
```bash
# Pare o JARVIS (Ctrl+C)
# E reinicie:
python agent.py
```

### Passo 3: Teste a Personalização
```bash
# Teste com comandos como:
"Oi, tudo bem?"
"Qual seu nome?"
"Me conta uma piada"
"Ajuda aqui por favor"
```

---

## 🎨 Outros Arquivos que Podem Ser Personalizados

### 1️⃣ `agent.py` - Comportamento Principal
- Configurações de voz
- Tempo de resposta
- Modos de operação

### 2️⃣ `jarvis_modules/comportamento.py` - Comportamento Detalhado
- Reações emocionais
- Adaptação de contexto
- Memória de preferências

### 3️⃣ `data/comportamento.json` - Preferências Salvas
- Histórico de interações
- Preferências do usuário
- Configurações dinâmicas

---

## ⚙️ Configurações Avançadas

### Modos de Operação
```python
# prompts.py
MODO_OPERACAO = {
    "padrao": "normal",
    "noturno": "silencioso", 
    "trabalho": "profissional",
    "lazer": "relaxado"
}
```

### Níveis de Inteligência
```python
NIVEL_INTELIGENCIA = {
    "basico": "respostas simples",
    "intermediario": "contexto básico",
    "avancado": "contexto completo",
    "expert": "previsão de necessidades"
}
```

---

## 🚀 Teste Final

Depois de personalizar:

1. **Teste saudação:** "Oi JARVIS!"
2. **Teste nome:** "Qual seu nome?"
3. **Teste humor:** "Me conta uma piada"
4. **Teste ajuda:** "Ajuda aqui por favor"
5. **Teste despedida:** "Tchau JARVIS!"

---

## 🆘 Dicas Importantes

- **Backup:** Sempre faça backup do `prompts.py` antes de editar
- **Teste:** Teste cada mudança individualmente
- **Consistência:** Mantenha a personalidade consistente
- **Reinicie:** Sempre reinicie após mudanças
- **Logs:** Verifique os logs para erros

---

**Pronto! Seu JARVIS está completamente personalizado! 🎉**

Agora ele tem a personalidade, nome e comportamento que você definiu!
