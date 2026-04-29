"""
═══════════════════════════════════════════════════════════════
  JARVIS AUTOMAÇÃO RESIDENCIAL — SmartThings & Home Assistant
═══════════════════════════════════════════════════════════════

Integração completa com:
  • SmartThings API
  • Home Assistant API
  • Sistema de interpretação de comandos via IA
  • Mapeamento de dispositivos para nomes amigáveis
"""

import os
import json
import asyncio
import platform
import requests
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from .core import DataStore, event_bus, agora_iso

# Verificar se estamos no Windows
IS_WINDOWS = platform.system() == "Windows"
USING_REQUESTS = IS_WINDOWS  # Forçar requests no Windows

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()


@dataclass
class ComandoDispositivo:
    """Estrutura de comando para dispositivos"""
    action: str  # turn_on, turn_off, set_temperature, etc.
    device: str  # nome amigável do dispositivo
    value: Optional[Any] = None  # valor para comandos como set_temperature
    capability: Optional[str] = None  # capacidade específica do SmartThings


class SmartThingsManager:
    """Gerenciador de integração com SmartThings API"""
    
    def __init__(self):
        self.token = os.getenv('SMARTTHINGS_TOKEN')
        self.base_url = "https://api.smartthings.com/v1"
        self.devices_cache = {}
        self._last_cache_update = None
        
        if not self.token:
            logger.warning("SMARTTHINGS_TOKEN não encontrado no .env")
    
    async def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Faz requisição HTTP para SmartThings API"""
        if not self.token:
            raise ValueError("Token SmartThings não configurado")
        
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Usar requests no Windows para evitar problemas com aiohttp
            if USING_REQUESTS:
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=10)
                elif method == 'POST':
                    response = requests.post(url, headers=headers, json=data, timeout=10)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"HTTP {response.status_code}: {response.text}"}
            else:
                # Usar aiohttp em outros sistemas
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    if method == 'GET':
                        async with session.get(url, headers=headers) as response:
                            return await response.json()
                    elif method == 'POST':
                        async with session.post(url, headers=headers, json=data) as response:
                            return await response.json()
                    
        except Exception as e:
            logger.error(f"Erro na requisição SmartThings: {e}")
            raise
    
    async def listar_dispositivos(self, force_refresh: bool = False) -> Dict:
        """Lista todos os dispositivos SmartThings"""
        if not force_refresh and self._last_cache_update and \
           (datetime.now() - self._last_cache_update).seconds < 300:  # 5 minutos cache
            return self.devices_cache
        
        try:
            response = await self._request('GET', '/devices')
            self.devices_cache = response
            self._last_cache_update = datetime.now()
            
            # Publicar evento para outros módulos
            event_bus.publish("dispositivos_smartthings_atualizados", response)
            
            return response
        except Exception as e:
            logger.error(f"Erro ao listar dispositivos: {e}")
            return {"error": str(e)}
    
    async def enviar_comando(self, device_id: str, command: Dict) -> Dict:
        """Envia comando para dispositivo específico"""
        try:
            endpoint = f"/devices/{device_id}/commands"
            response = await self._request('POST', endpoint, command)
            
            # Publicar evento de comando executado
            event_bus.publish("comando_smartthings_executado", {
                "device_id": device_id,
                "command": command,
                "response": response,
                "timestamp": agora_iso()
            })
            
            return response
        except Exception as e:
            logger.error(f"Erro ao enviar comando para {device_id}: {e}")
            return {"error": str(e)}
    
    async def status_dispositivo(self, device_id: str) -> Dict:
        """Obtém status atual de um dispositivo"""
        try:
            endpoint = f"/devices/{device_id}/status"
            response = await self._request('GET', endpoint)
            return response
        except Exception as e:
            logger.error(f"Erro ao obter status do dispositivo {device_id}: {e}")
            return {"error": str(e)}


class HomeAssistantManager:
    """Gerenciador de integração com Home Assistant API"""
    
    def __init__(self):
        self.url = os.getenv('HOMEASSISTANT_URL', 'http://localhost:8123')
        self.token = os.getenv('HOMEASSISTANT_TOKEN')
        self.devices_cache = {}
        self._last_cache_update = None
        
        if not self.token:
            logger.warning("HOMEASSISTANT_TOKEN não encontrado no .env")
    
    async def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Faz requisição HTTP para Home Assistant API"""
        if not self.token:
            raise ValueError("Token Home Assistant não configurado")
        
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.url}/api{endpoint}"
        
        try:
            # Usar requests no Windows para evitar problemas com aiohttp
            if USING_REQUESTS:
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=10)
                elif method == 'POST':
                    response = requests.post(url, headers=headers, json=data, timeout=10)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"HTTP {response.status_code}: {response.text}"}
            else:
                # Usar aiohttp em outros sistemas
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    if method == 'GET':
                        async with session.get(url, headers=headers) as response:
                            return await response.json()
                    elif method == 'POST':
                        async with session.post(url, headers=headers, json=data) as response:
                            return await response.json()
                    
        except Exception as e:
            logger.error(f"Erro na requisição Home Assistant: {e}")
            raise
    
    async def listar_dispositivos(self, force_refresh: bool = False) -> Dict:
        """Lista todos os dispositivos Home Assistant"""
        if not force_refresh and self._last_cache_update and \
           (datetime.now() - self._last_cache_update).seconds < 300:
            return self.devices_cache
        
        try:
            response = await self._request('GET', '/states')
            self.devices_cache = response
            self._last_cache_update = datetime.now()
            
            event_bus.publish("dispositivos_homeassistant_atualizados", response)
            return response
        except Exception as e:
            logger.error(f"Erro ao listar dispositivos Home Assistant: {e}")
            return {"error": str(e)}
    
    async def enviar_comando(self, entity_id: str, domain: str, service: str, **kwargs) -> Dict:
        """Envia comando para entidade Home Assistant"""
        try:
            endpoint = f"/services/{domain}/{service}"
            data = {
                "entity_id": entity_id,
                **kwargs
            }
            response = await self._request('POST', endpoint, data)
            
            event_bus.publish("comando_homeassistant_executado", {
                "entity_id": entity_id,
                "domain": domain,
                "service": service,
                "data": data,
                "response": response,
                "timestamp": agora_iso()
            })
            
            return response
        except Exception as e:
            logger.error(f"Erro ao enviar comando para {entity_id}: {e}")
            return {"error": str(e)}


class MapeamentoDispositivos:
    """Gerencia mapeamento entre nomes amigáveis e IDs de dispositivos"""
    
    def __init__(self):
        self.store = DataStore("mapeamento_dispositivos", default={
            "smartthings": {},
            "homeassistant": {}
        })
        self.carregar_mapeamento()
    
    def carregar_mapeamento(self):
        """Carrega mapeamento do armazenamento"""
        self.mapeamento = self.store.load()
    
    def salvar_mapeamento(self):
        """Salva mapeamento no armazenamento"""
        self.store.save(self.mapeamento)
    
    def adicionar_dispositivo(self, plataforma: str, nome_amigavel: str, device_id: str, 
                            tipo: str = None, comodos: List[str] = None):
        """Adiciona ou atualiza mapeamento de dispositivo"""
        if plataforma not in self.mapeamento:
            self.mapeamento[plataforma] = {}
        
        self.mapeamento[plataforma][nome_amigavel.lower()] = {
            "device_id": device_id,
            "tipo": tipo or "desconhecido",
            "comodos": comodos or [],
            "adicionado_em": agora_iso()
        }
        
        self.salvar_mapeamento()
        logger.info(f"Dispositivo mapeado: {nome_amigavel} -> {device_id} ({plataforma})")
    
    def buscar_dispositivo(self, nome: str, plataforma: str = None) -> Dict:
        """Busca dispositivo por nome amigável"""
        nome_lower = nome.lower()
        
        if plataforma:
            return self.mapeamento.get(plataforma, {}).get(nome_lower)
        
        # Buscar em todas as plataformas
        for plat, dispositivos in self.mapeamento.items():
            if nome_lower in dispositivos:
                return dispositivos[nome_lower]
        
        return None
    
    def listar_por_comodo(self, comodo: str) -> Dict:
        """Lista dispositivos por cômodo"""
        resultado = {"smartthings": {}, "homeassistant": {}}
        
        for plataforma, dispositivos in self.mapeamento.items():
            for nome, info in dispositivos.items():
                if comodo.lower() in [c.lower() for c in info.get("comodos", [])]:
                    resultado[plataforma][nome] = info
        
        return resultado
    
    def listar_todos(self) -> Dict:
        """Lista todos os dispositivos mapeados"""
        return self.mapeamento


class InterpretadorComandos:
    """Interpretador de comandos usando IA (Google Gemini)"""
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY não encontrado no .env")
    
    async def interpretar_comando(self, texto: str) -> Optional[ComandoDispositivo]:
        """Interpreta comando do usuário usando IA"""
        if not self.api_key:
            # Fallback para interpretação baseada em regras
            return self._interpretar_regras(texto)
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""
            Analise o comando do usuário e extraia a intenção de automação residencial.
            
            Comando: "{texto}"
            
            Responda APENAS com JSON no seguinte formato:
            {{
                "action": "turn_on|turn_off|set_temperature|set_brightness|toggle",
                "device": "nome do dispositivo",
                "value": número ou null,
                "capability": "capacidade específica ou null"
            }}
            
            Exemplos:
            "Liga a luz da sala" -> {{"action": "turn_on", "device": "luz da sala", "value": null, "capability": null}}
            "Desliga o ar condicionado" -> {{"action": "turn_off", "device": "ar condicionado", "value": null, "capability": null}}
            "Ajusta a temperatura para 22 graus" -> {{"action": "set_temperature", "device": "termostato", "value": 22, "capability": "temperatureMeasurement"}}
            """
            
            response = model.generate_content(prompt)
            resultado = json.loads(response.text.strip())
            
            return ComandoDispositivo(
                action=resultado["action"],
                device=resultado["device"],
                value=resultado.get("value"),
                capability=resultado.get("capability")
            )
            
        except Exception as e:
            logger.error(f"Erro na interpretação via IA: {e}")
            return self._interpretar_regras(texto)
    
    def _interpretar_regras(self, texto: str) -> Optional[ComandoDispositivo]:
        """Interpretação baseada em regras simples (fallback)"""
        texto_lower = texto.lower()
        
        # Palavras-chave para ações
        acoes = {
            "liga": "turn_on",
            "acende": "turn_on",
            "ativa": "turn_on",
            "desliga": "turn_off",
            "apaga": "turn_off",
            "desativa": "turn_off",
            "alterna": "toggle",
            "ajusta": "set_temperature",
            "diminui": "set_brightness",
            "aumenta": "set_brightness"
        }
        
        # Detectar ação
        action = None
        for palavra, acao in acoes.items():
            if palavra in texto_lower:
                action = acao
                break
        
        if not action:
            return None
        
        # Extrair nome do dispositivo (simplificado)
        dispositivos_conhecidos = [
            "luz da sala", "luz do quarto", "luz da cozinha", "luz do banheiro",
            "ar condicionado", "termostato", "tv", "televisão", "ventilador",
            "porta da garagem", "câmera", "trava", "alarme"
        ]
        
        device = None
        for disp in dispositivos_conhecidos:
            if disp in texto_lower:
                device = disp
                break
        
        if not device:
            return None
        
        # Extrair valor (temperatura, brilho, etc.)
        value = None
        if action == "set_temperature":
            import re
            temperaturas = re.findall(r'\d+', texto)
            if temperaturas:
                value = int(temperaturas[0])
        
        return ComandoDispositivo(
            action=action,
            device=device,
            value=value,
            capability=None
        )


class AutomacaoResidencial:
    """Classe principal que orquestra toda a automação residencial"""
    
    def __init__(self):
        self.smartthings = SmartThingsManager()
        self.homeassistant = HomeAssistantManager()
        self.mapeamento = MapeamentoDispositivos()
        self.interpretador = InterpretadorComandos()
        
        # Inscrever eventos
        event_bus.subscribe("comando_voz_recebido", self._processar_comando_voz)
        
        logger.info("Sistema de automação residencial inicializado")
    
    async def inicializar(self):
        """Inicializa o sistema de automação"""
        logger.info("Inicializando sistema de automação residencial...")
        
        # Carregar dispositivos
        await self.smartthings.listar_dispositivos()
        await self.homeassistant.listar_dispositivos()
        
        logger.info("Sistema de automação residencial pronto!")
    
    async def _processar_comando_voz(self, dados: Dict):
        """Processa comando recebido via voz"""
        texto = dados.get("texto", "")
        if not texto:
            return
        
        resultado = await self.executar_comando(texto)
        
        # Publicar resultado para ser falado ao usuário
        event_bus.publish("resposta_comando", {
            "texto": resultado.get("mensagem", ""),
            "sucesso": resultado.get("sucesso", False)
        })
    
    async def executar_comando(self, texto: str) -> Dict:
        """Executa comando baseado no texto do usuário"""
        try:
            # Interpretar comando
            comando = await self.interpretador.interpretar_comando(texto)
            
            if not comando:
                return {
                    "sucesso": False,
                    "mensagem": "Não consegui entender o comando. Tente ser mais específico.",
                    "comando": None
                }
            
            # Buscar dispositivo mapeado
            dispositivo = self.mapeamento.buscar_dispositivo(comando.device)
            
            if not dispositivo:
                return {
                    "sucesso": False,
                    "mensagem": f"Dispositivo '{comando.device}' não encontrado. Verifique o nome ou adicione-o ao sistema.",
                    "comando": comando.__dict__
                }
            
            # Executar comando na plataforma correta
            if dispositivo["device_id"].startswith("smartthings-"):
                resultado = await self._executar_smartthings(comando, dispositivo)
            else:
                resultado = await self._executar_homeassistant(comando, dispositivo)
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao executar comando: {e}")
            return {
                "sucesso": False,
                "mensagem": f"Ocorreu um erro ao executar o comando: {str(e)}",
                "comando": texto
            }
    
    async def _executar_smartthings(self, comando: ComandoDispositivo, dispositivo: Dict) -> Dict:
        """Executa comando no SmartThings"""
        device_id = dispositivo["device_id"].replace("smartthings-", "")
        
        # Mapear ações para comandos SmartThings
        comandos_smartthings = {
            "turn_on": {
                "commands": [{
                    "component": "main",
                    "capability": "switch",
                    "command": "on"
                }]
            },
            "turn_off": {
                "commands": [{
                    "component": "main",
                    "capability": "switch",
                    "command": "off"
                }]
            },
            "set_temperature": {
                "commands": [{
                    "component": "main",
                    "capability": "thermostat",
                    "command": "setTemperature",
                    "arguments": [comando.value]
                }]
            },
            "set_brightness": {
                "commands": [{
                    "component": "main",
                    "capability": "switchLevel",
                    "command": "setLevel",
                    "arguments": [comando.value or 50]
                }]
            }
        }
        
        comando_st = comandos_smartthings.get(comando.action)
        if not comando_st:
            return {
                "sucesso": False,
                "mensagem": f"Ação '{comando.action}' não suportada no SmartThings",
                "comando": comando.__dict__
            }
        
        try:
            response = await self.smartthings.enviar_comando(device_id, comando_st)
            
            return {
                "sucesso": True,
                "mensagem": f"Comando executado com sucesso: {comando.action} em {comando.device}",
                "response": response,
                "comando": comando.__dict__
            }
            
        except Exception as e:
            return {
                "sucesso": False,
                "mensagem": f"Erro ao executar comando no SmartThings: {str(e)}",
                "comando": comando.__dict__
            }
    
    async def _executar_homeassistant(self, comando: ComandoDispositivo, dispositivo: Dict) -> Dict:
        """Executa comando no Home Assistant"""
        entity_id = dispositivo["device_id"]
        logger.info(f"[EXECUTAR_HOMEASSISTANT] Iniciando: entity_id={entity_id}, action={comando.action}, value={comando.value}")
        
        # Mapear ações para serviços Home Assistant
        servicos_ha = {
            "turn_on": ("light", "turn_on"),
            "turn_off": ("light", "turn_off"),
            "toggle": ("light", "toggle"),
            "set_temperature": ("climate", "set_temperature"),
            "set_brightness": ("light", "turn_on")
        }
        
        servico = servicos_ha.get(comando.action)
        if not servico:
            logger.error(f"[EXECUTAR_HOMEASSISTANT] Ação não suportada: {comando.action}")
            return {
                "sucesso": False,
                "mensagem": f"Ação '{comando.action}' não suportada no Home Assistant",
                "comando": comando.__dict__
            }
        
        domain, service = servico
        kwargs = {}
        
        if comando.action == "set_temperature":
            kwargs["temperature"] = comando.value
            logger.info(f"[EXECUTAR_HOMEASSISTANT] Configurando temperatura: {comando.value}")
        elif comando.action == "set_brightness":
            kwargs["brightness_pct"] = comando.value or 50
            logger.info(f"[EXECUTAR_HOMEASSISTANT] Configurando brilho: {kwargs['brightness_pct']}%")
        
        try:
            logger.info(f"[EXECUTAR_HOMEASSISTANT] Enviando requisição: domain={domain}, service={service}, entity_id={entity_id}, kwargs={kwargs}")
            
            response = await self.homeassistant.enviar_comando(entity_id, domain, service, **kwargs)
            
            logger.info(f"[EXECUTAR_HOMEASSISTANT] Resposta recebida: {response}")
            
            return {
                "sucesso": True,
                "mensagem": f"Comando executado com sucesso: {comando.action} em {comando.device}",
                "response": response,
                "comando": comando.__dict__
            }
            
        except Exception as e:
            logger.error(f"[EXECUTAR_HOMEASSISTANT] Erro na execução: {str(e)}")
            return {
                "sucesso": False,
                "mensagem": f"Erro ao executar comando no Home Assistant: {str(e)}",
                "comando": comando.__dict__
            }
    
    async def listar_dispositivos_disponiveis(self) -> Dict:
        """Lista todos os dispositivos disponíveis nas plataformas"""
        st_devices = await self.smartthings.listar_dispositivos()
        ha_devices = await self.homeassistant.listar_dispositivos()
        
        return {
            "smartthings": st_devices,
            "homeassistant": ha_devices,
            "mapeados": self.mapeamento.listar_todos()
        }
    
    def adicionar_mapeamento(self, plataforma: str, nome_amigavel: str, device_id: str, 
                          tipo: str = None, comodos: List[str] = None):
        """Adiciona novo mapeamento de dispositivo"""
        self.mapeamento.adicionar_dispositivo(plataforma, nome_amigavel, device_id, tipo, comodos)
        
        event_bus.publish("dispositivo_mapeado", {
            "plataforma": plataforma,
            "nome_amigavel": nome_amigavel,
            "device_id": device_id
        })
    
    # ═══════════════════════════════════════════
    # CONTROLE DE ILUMINAÇÃO
    # ═══════════════════════════════════════════
    
    async def controle_iluminacao(self, acao: str, dispositivo: str = None, comodo: str = None, 
                                 intensidade: int = None, cena: str = None) -> Dict:
        """Controla iluminação de forma completa"""
        logger.info(f"[CONTROLE_ILUMINACAO] Iniciando: acao={acao}, dispositivo={dispositivo}, comodo={comodo}, intensidade={intensidade}, cena={cena}")
        
        try:
            if acao == "cena" and cena:
                logger.info(f"[CONTROLE_ILUMINACAO] Executando cena: {cena}")
                return await self._executar_cena_iluminacao(cena)
            
            # Determinar dispositivo(s)
            if comodo:
                logger.info(f"[CONTROLE_ILUMINACAO] Buscando dispositivos no cômodo: {comodo}")
                dispositivos = self.mapeamento.listar_por_comodo(comodo)
                logger.info(f"[CONTROLE_ILUMINACAO] Dispositivos encontrados: {dispositivos}")
                
                resultados = []
                for plataforma, disp_dict in dispositivos.items():
                    for nome, info in disp_dict.items():
                        if info.get("tipo") in ["luz", "luz inteligente", "lampada"]:
                            logger.info(f"[CONTROLE_ILUMINACAO] Controlando dispositivo: {nome} ({plataforma})")
                            resultado = await self._executar_acao_iluminacao(
                                acao, nome, info, plataforma, intensidade
                            )
                            resultados.append(resultado)
                
                sucesso = all(r.get("sucesso", False) for r in resultados)
                mensagem = f"Iluminação do {comodo} {acao} com sucesso" if sucesso else "Falha em alguns dispositivos"
                logger.info(f"[CONTROLE_ILUMINACAO] Resultado: {mensagem}")
                return {
                    "sucesso": sucesso,
                    "mensagem": mensagem,
                    "resultados": resultados
                }
            
            elif dispositivo:
                logger.info(f"[CONTROLE_ILUMINACAO] Buscando dispositivo específico: {dispositivo}")
                disp_info = self.mapeamento.buscar_dispositivo(dispositivo)
                if not disp_info:
                    logger.warning(f"[CONTROLE_ILUMINACAO] Dispositivo não encontrado: {dispositivo}")
                    return {"sucesso": False, "mensagem": f"Dispositivo '{dispositivo}' não encontrado"}
                
                plataforma = "smartthings" if disp_info.get("device_id", "").startswith("smartthings-") else "homeassistant"
                logger.info(f"[CONTROLE_ILUMINACAO] Executando ação {acao} no dispositivo {dispositivo} ({plataforma})")
                return await self._executar_acao_iluminacao(acao, dispositivo, disp_info, plataforma, intensidade)
            
            logger.warning(f"[CONTROLE_ILUMINACAO] Parâmetros insuficientes - dispositivo ou cômodo não especificado")
            return {"sucesso": False, "mensagem": "Especifique um dispositivo ou cômodo"}
            
        except Exception as e:
            logger.error(f"[CONTROLE_ILUMINACAO] Erro: {str(e)}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    async def _executar_acao_iluminacao(self, acao: str, nome: str, info: Dict, plataforma: str, intensidade: int = None) -> Dict:
        """Executa ação específica de iluminação"""
        logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] acao={acao}, nome={nome}, plataforma={plataforma}, intensidade={intensidade}")
        
        if acao == "ligar":
            comando = ComandoDispositivo("turn_on", nome)
            logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] Criando comando turn_on para {nome}")
        elif acao == "desligar":
            comando = ComandoDispositivo("turn_off", nome)
            logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] Criando comando turn_off para {nome}")
        elif acao == "dimmer" and intensidade is not None:
            comando = ComandoDispositivo("set_brightness", nome, intensidade)
            logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] Criando comando set_brightness {intensidade}% para {nome}")
        elif acao == "alternar":
            comando = ComandoDispositivo("toggle", nome)
            logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] Criando comando toggle para {nome}")
        else:
            logger.warning(f"[EXECUTAR_ACAO_ILUMINACAO] Ação não reconhecida: {acao}")
            return {"sucesso": False, "mensagem": f"Ação '{acao}' não reconhecida"}
        
        try:
            logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] Enviando comando para plataforma: {plataforma}")
            
            if plataforma == "smartthings":
                logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] Executando via SmartThings")
                resultado = await self._executar_smartthings(comando, info)
            else:
                logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] Executando via Home Assistant")
                resultado = await self._executar_homeassistant(comando, info)
            
            logger.info(f"[EXECUTAR_ACAO_ILUMINACAO] Resultado: {resultado}")
            return resultado
            
        except Exception as e:
            logger.error(f"[EXECUTAR_ACAO_ILUMINACAO] Erro na execução: {str(e)}")
            return {"sucesso": False, "mensagem": f"Erro na execução: {str(e)}"}
    
    async def _executar_cena_iluminacao(self, cena: str) -> Dict:
        """Executa cenas predefinidas de iluminação"""
        cenas = {
            "modo cinema": {
                "luzes": ["luz da sala", "luz principal"],
                "acao": "desligar",
                "intensidade": 10
            },
            "modo leitura": {
                "luzes": ["luz de leitura", "abajur"],
                "acao": "ligar",
                "intensidade": 80
            },
            "modo romântico": {
                "luzes": ["luz ambiente", "luz indireta"],
                "acao": "dimmer",
                "intensidade": 30
            },
            "modo festa": {
                "luzes": ["luz colorida", "fitas de led"],
                "acao": "ligar",
                "intensidade": 100
            }
        }
        
        cena_config = cenas.get(cena.lower())
        if not cena_config:
            return {"sucesso": False, "mensagem": f"Cena '{cena}' não encontrada"}
        
        resultados = []
        for luz in cena_config["luzes"]:
            resultado = await self.controle_iluminacao(
                cena_config["acao"], luz, None, cena_config.get("intensidade")
            )
            resultados.append(resultado)
        
        sucesso = all(r.get("sucesso", False) for r in resultados)
        return {
            "sucesso": sucesso,
            "mensagem": f"Cena '{cena}' ativada com sucesso" if sucesso else "Falha ao ativar cena",
            "resultados": resultados
        }
    
    # ═══════════════════════════════════════════
    # CONTROLE DE TEMPERATURA
    # ═══════════════════════════════════════════
    
    async def controle_temperatura(self, acao: str, dispositivo: str = None, temperatura: int = None, 
                                  modo: str = None) -> Dict:
        """Controla temperatura e climatização"""
        try:
            if dispositivo is None:
                dispositivo = "termostato"  # Padrão
            
            disp_info = self.mapeamento.buscar_dispositivo(dispositivo)
            if not disp_info:
                return {"sucesso": False, "mensagem": f"Dispositivo '{dispositivo}' não encontrado"}
            
            plataforma = "smartthings" if disp_info.get("device_id", "").startswith("smartthings-") else "homeassistant"
            
            if acao == "ajustar" and temperatura is not None:
                comando = ComandoDispositivo("set_temperature", dispositivo, temperatura)
            elif acao == "modo" and modo:
                comando = ComandoDispositivo("set_mode", dispositivo, modo)
            elif acao == "ligar":
                comando = ComandoDispositivo("turn_on", dispositivo)
            elif acao == "desligar":
                comando = ComandoDispositivo("turn_off", dispositivo)
            else:
                return {"sucesso": False, "mensagem": f"Ação '{acao}' não reconhecida"}
            
            if plataforma == "smartthings":
                return await self._executar_smartthings(comando, disp_info)
            else:
                return await self._executar_homeassistant(comando, disp_info)
                
        except Exception as e:
            logger.error(f"Erro no controle de temperatura: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    # ═══════════════════════════════════════════
    # SEGURANÇA
    # ═══════════════════════════════════════════
    
    async def controle_seguranca(self, acao: str, dispositivo: str = None) -> Dict:
        """Controla sistema de segurança"""
        try:
            if acao == "ativar_alarme":
                dispositivos_alarme = ["alarme", "sistema de alarme", "central de alarme"]
                for disp in dispositivos_alarme:
                    info = self.mapeamento.buscar_dispositivo(disp)
                    if info:
                        comando = ComandoDispositivo("turn_on", disp)
                        plataforma = "smartthings" if info.get("device_id", "").startswith("smartthings-") else "homeassistant"
                        await (self._executar_smartthings(comando, info) if plataforma == "smartthings" else self._executar_homeassistant(comando, info))
                return {"sucesso": True, "mensagem": "Sistema de alarme ativado"}
            
            elif acao == "desativar_alarme":
                dispositivos_alarme = ["alarme", "sistema de alarme", "central de alarme"]
                for disp in dispositivos_alarme:
                    info = self.mapeamento.buscar_dispositivo(disp)
                    if info:
                        comando = ComandoDispositivo("turn_off", disp)
                        plataforma = "smartthings" if info.get("device_id", "").startswith("smartthings-") else "homeassistant"
                        await (self._executar_smartthings(comando, info) if plataforma == "smartthings" else self._executar_homeassistant(comando, info))
                return {"sucesso": True, "mensagem": "Sistema de alarme desativado"}
            
            elif dispositivo:
                info = self.mapeamento.buscar_dispositivo(dispositivo)
                if not info:
                    return {"sucesso": False, "mensagem": f"Dispositivo '{dispositivo}' não encontrado"}
                
                plataforma = "smartthings" if info.get("device_id", "").startswith("smartthings-") else "homeassistant"
                
                if acao in ["travar", "fechar"]:
                    comando = ComandoDispositivo("lock", dispositivo)
                elif acao in ["destravar", "abrir"]:
                    comando = ComandoDispositivo("unlock", dispositivo)
                else:
                    comando = ComandoDispositivo(acao, dispositivo)
                
                if plataforma == "smartthings":
                    return await self._executar_smartthings(comando, info)
                else:
                    return await self._executar_homeassistant(comando, info)
            
            return {"sucesso": False, "mensagem": "Dispositivo não especificado"}
            
        except Exception as e:
            logger.error(f"Erro no controle de segurança: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    # ═══════════════════════════════════════════
    # ELETRODOMÉSTICOS
    # ═══════════════════════════════════════════
    
    async def controle_eletrodomesticos(self, acao: str, dispositivo: str, programa: str = None) -> Dict:
        """Controla eletrodomésticos inteligentes"""
        try:
            info = self.mapeamento.buscar_dispositivo(dispositivo)
            if not info:
                return {"sucesso": False, "mensagem": f"Dispositivo '{dispositivo}' não encontrado"}
            
            plataforma = "smartthings" if info.get("device_id", "").startswith("smartthings-") else "homeassistant"
            
            if acao == "iniciar_programa" and programa:
                comando = ComandoDispositivo("start_program", dispositivo, programa)
            elif acao == "ligar":
                comando = ComandoDispositivo("turn_on", dispositivo)
            elif acao == "desligar":
                comando = ComandoDispositivo("turn_off", dispositivo)
            elif acao == "pausar":
                comando = ComandoDispositivo("pause", dispositivo)
            else:
                return {"sucesso": False, "mensagem": f"Ação '{acao}' não reconhecida"}
            
            if plataforma == "smartthings":
                return await self._executar_smartthings(comando, info)
            else:
                return await self._executar_homeassistant(comando, info)
                
        except Exception as e:
            logger.error(f"Erro no controle de eletrodomésticos: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    # ═══════════════════════════════════════════
    # CORTINAS E PERSIANAS
    # ═══════════════════════════════════════════
    
    async def controle_cortinas(self, acao: str, dispositivo: str = None, comodo: str = None, posicao: int = None) -> Dict:
        """Controla cortinas e persianas automáticas"""
        try:
            if comodo:
                dispositivos = self.mapeamento.listar_por_comodo(comodo)
                resultados = []
                for plataforma, disp_dict in dispositivos.items():
                    for nome, info in disp_dict.items():
                        if info.get("tipo") in ["cortina", "persiana", "blackout"]:
                            resultado = await self._executar_acao_cortinas(acao, nome, info, plataforma, posicao)
                            resultados.append(resultado)
                
                sucesso = all(r.get("sucesso", False) for r in resultados)
                return {
                    "sucesso": sucesso,
                    "mensagem": f"Cortinas do {comodo} {acao} com sucesso" if sucesso else "Falha em alguns dispositivos",
                    "resultados": resultados
                }
            
            elif dispositivo:
                info = self.mapeamento.buscar_dispositivo(dispositivo)
                if not info:
                    return {"sucesso": False, "mensagem": f"Dispositivo '{dispositivo}' não encontrado"}
                
                plataforma = "smartthings" if info.get("device_id", "").startswith("smartthings-") else "homeassistant"
                return await self._executar_acao_cortinas(acao, dispositivo, info, plataforma, posicao)
            
            return {"sucesso": False, "mensagem": "Especifique um dispositivo ou cômodo"}
            
        except Exception as e:
            logger.error(f"Erro no controle de cortinas: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    async def _executar_acao_cortinas(self, acao: str, nome: str, info: Dict, plataforma: str, posicao: int = None) -> Dict:
        """Executa ação específica de cortinas"""
        if acao == "abrir":
            comando = ComandoDispositivo("open", nome)
        elif acao == "fechar":
            comando = ComandoDispositivo("close", nome)
        elif acao == "ajustar" and posicao is not None:
            comando = ComandoDispositivo("set_position", nome, posicao)
        elif acao == "parar":
            comando = ComandoDispositivo("stop", nome)
        else:
            return {"sucesso": False, "mensagem": f"Ação '{acao}' não reconhecida"}
        
        if plataforma == "smartthings":
            return await self._executar_smartthings(comando, info)
        else:
            return await self._executar_homeassistant(comando, info)
    
    # ═══════════════════════════════════════════
    # IRRIGAÇÃO E JARDIM
    # ═══════════════════════════════════════════
    
    async def controle_irrigacao(self, acao: str, zona: str = None, duracao_minutos: int = None) -> Dict:
        """Controla sistema de irrigação"""
        try:
            if acao == "iniciar_irrigacao":
                dispositivo = f"irrigação {zona}" if zona else "irrigação"
                info = self.mapeamento.buscar_dispositivo(dispositivo)
                if not info:
                    return {"sucesso": False, "mensagem": f"Sistema de irrigação não encontrado"}
                
                plataforma = "smartthings" if info.get("device_id", "").startswith("smartthings-") else "homeassistant"
                comando = ComandoDispositivo("start", dispositivo, duracao_minutos or 10)
                
                if plataforma == "smartthings":
                    resultado = await self._executar_smartthings(comando, info)
                else:
                    resultado = await self._executar_homeassistant(comando, info)
                
                return resultado
            
            elif acao == "parar_irrigacao":
                dispositivo = "irrigação"
                info = self.mapeamento.buscar_dispositivo(dispositivo)
                if not info:
                    return {"sucesso": False, "mensagem": f"Sistema de irrigação não encontrado"}
                
                plataforma = "smartthings" if info.get("device_id", "").startswith("smartthings-") else "homeassistant"
                comando = ComandoDispositivo("stop", dispositivo)
                
                if plataforma == "smartthings":
                    resultado = await self._executar_smartthings(comando, info)
                else:
                    resultado = await self._executar_homeassistant(comando, info)
                
                return resultado
            
            return {"sucesso": False, "mensagem": f"Ação '{acao}' não reconhecida"}
            
        except Exception as e:
            logger.error(f"Erro no controle de irrigação: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    # ═══════════════════════════════════════════
    # MODOS INTELIGENTES
    # ═══════════════════════════════════════════
    
    async def ativar_modo_inteligente(self, modo: str) -> Dict:
        """Ativa modos inteligentes predefinidos"""
        try:
            modos = {
                "modo cinema": self._executar_modo_cinema,
                "modo sair": self._executar_modo_sair,
                "modo dormir": self._executar_modo_dormir,
                "modo chegar": self._executar_modo_chegar,
                "modo trabalho": self._executar_modo_trabalho,
                "modo festa": self._executar_modo_festa
            }
            
            executor = modos.get(modo.lower())
            if not executor:
                return {"sucesso": False, "mensagem": f"Modo '{modo}' não encontrado"}
            
            return await executor()
            
        except Exception as e:
            logger.error(f"Erro ao ativar modo inteligente: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    async def _executar_modo_cinema(self) -> Dict:
        """Modo Cinema: apaga luzes, baixa persianas, liga TV"""
        resultados = []
        
        # Apagar luzes principais
        resultados.append(await self.controle_iluminacao("desligar", comodo="sala"))
        
        # Fechar persianas
        resultados.append(await self.controle_cortinas("fechar", comodo="sala"))
        
        # Ligar TV e sistema de som
        resultados.append(await self.controle_eletrodomesticos("ligar", "tv sala"))
        resultados.append(await self.controle_eletrodomesticos("ligar", "sistema de som"))
        
        sucesso = all(r.get("sucesso", False) for r in resultados)
        return {
            "sucesso": sucesso,
            "mensagem": "Modo Cinema ativado" if sucesso else "Falha ao ativar Modo Cinema",
            "resultados": resultados
        }
    
    async def _executar_modo_sair(self) -> Dict:
        """Modo Sair: apaga tudo, ativa alarme, ajusta temperatura"""
        resultados = []
        
        # Apagar todas as luzes
        resultados.append(await self.controle_iluminacao("desligar", comodo="toda casa"))
        
        # Ativar alarme
        resultados.append(await self.controle_seguranca("ativar_alarme"))
        
        # Ajustar temperatura para economia
        resultados.append(await self.controle_temperatura("ajustar", "termostato", 25))
        
        # Fechar cortinas
        resultados.append(await self.controle_cortinas("fechar", comodo="toda casa"))
        
        sucesso = all(r.get("sucesso", False) for r in resultados)
        return {
            "sucesso": sucesso,
            "mensagem": "Modo Sair ativado" if sucesso else "Falha ao ativar Modo Sair",
            "resultados": resultados
        }
    
    async def _executar_modo_dormir(self) -> Dict:
        """Modo Dormir: apaga luzes, ajusta temperatura, ativa modo noturno"""
        resultados = []
        
        # Apagar luzes exceto quarto
        resultados.append(await self.controle_iluminacao("desligar", comodo="sala"))
        resultados.append(await self.controle_iluminacao("desligar", comodo="cozinha"))
        
        # Luz do quarto baixa
        resultados.append(await self.controle_iluminacao("dimmer", "luz quarto", None, 20))
        
        # Temperatura confortável para dormir
        resultados.append(await self.controle_temperatura("ajustar", "termostato", 22))
        
        # Ativar modo noturno no alarme
        resultados.append(await self.controle_seguranca("ativar_alarme"))
        
        sucesso = all(r.get("sucesso", False) for r in resultados)
        return {
            "sucesso": sucesso,
            "mensagem": "Modo Dormir ativado" if sucesso else "Falha ao ativar Modo Dormir",
            "resultados": resultados
        }
    
    async def _executar_modo_chegar(self) -> Dict:
        """Modo Chegar: liga luzes, ajusta temperatura, desativa alarme"""
        resultados = []
        
        # Desativar alarme
        resultados.append(await self.controle_seguranca("desativar_alarme"))
        
        # Ligar luzes principais
        resultados.append(await self.controle_iluminacao("ligar", comodo="sala"))
        resultados.append(await self.controle_iluminacao("ligar", comodo="entrada"))
        
        # Temperatura confortável
        resultados.append(await self.controle_temperatura("ajustar", "termostato", 23))
        
        # Abrir cortinas principais
        resultados.append(await self.controle_cortinas("abrir", comodo="sala"))
        
        sucesso = all(r.get("sucesso", False) for r in resultados)
        return {
            "sucesso": sucesso,
            "mensagem": "Modo Chegar ativado" if sucesso else "Falha ao ativar Modo Chegar",
            "resultados": resultados
        }
    
    async def _executar_modo_trabalho(self) -> Dict:
        """Modo Trabalho: iluminação focada, temperatura produtiva"""
        resultados = []
        
        # Iluminação para escritório
        resultados.append(await self.controle_iluminacao("ligar", comodo="escritório"))
        resultados.append(await self.controle_iluminacao("dimmer", "luz escritório", None, 90))
        
        # Temperatura para produtividade
        resultados.append(await self.controle_temperatura("ajustar", "termostato", 21))
        
        # Silenciar notificações não essenciais
        resultados.append(await self.controle_eletrodomesticos("desligar", "tv sala"))
        
        sucesso = all(r.get("sucesso", False) for r in resultados)
        return {
            "sucesso": sucesso,
            "mensagem": "Modo Trabalho ativado" if sucesso else "Falha ao ativar Modo Trabalho",
            "resultados": resultados
        }
    
    async def _executar_modo_festa(self) -> Dict:
        """Modo Festa: luzes coloridas, música ambiente"""
        resultados = []
        
        # Iluminação festiva
        resultados.append(await self.controle_iluminacao("cena", None, None, None, "modo festa"))
        
        # Música ambiente
        resultados.append(await self.controle_eletrodomesticos("ligar", "sistema de som"))
        
        # Abrir áreas sociais
        resultados.append(await self.controle_cortinas("abrir", comodo="sala"))
        
        sucesso = all(r.get("sucesso", False) for r in resultados)
        return {
            "sucesso": sucesso,
            "mensagem": "Modo Festa ativado" if sucesso else "Falha ao ativar Modo Festa",
            "resultados": resultados
        }
    
    # ═══════════════════════════════════════════
    # AUTOMAÇÕES AVANÇADAS
    # ═══════════════════════════════════════════
    
    async def criar_automacao(self, nome: str, gatilho: str, acoes: List[Dict]) -> Dict:
        """Cria automações personalizadas"""
        try:
            automacao = {
                "nome": nome,
                "gatilho": gatilho,
                "acoes": acoes,
                "criada_em": agora_iso(),
                "ativa": True
            }
            
            # Salvar automação no datastore
            store = DataStore("automacoes_personalizadas")
            automacoes = store.load() or {}
            automacoes[nome] = automacao
            store.save(automacoes)
            
            # Publicar evento
            event_bus.publish("automacao_criada", automacao)
            
            return {
                "sucesso": True,
                "mensagem": f"Automação '{nome}' criada com sucesso",
                "automacao": automacao
            }
            
        except Exception as e:
            logger.error(f"Erro ao criar automação: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    async def executar_automacao_evento(self, evento: str) -> Dict:
        """Executa automações baseadas em eventos"""
        try:
            store = DataStore("automacoes_personalizadas")
            automacoes = store.load() or {}
            
            resultados = []
            for nome, automacao in automacoes.items():
                if automacao.get("ativa") and automacao.get("gatilho") == evento:
                    for acao in automacao.get("acoes", []):
                        resultado = await self._executar_acao_automacao(acao)
                        resultados.append(resultado)
            
            return {
                "sucesso": True,
                "mensagem": f"Executadas {len(resultados)} ações para o evento '{evento}'",
                "resultados": resultados
            }
            
        except Exception as e:
            logger.error(f"Erro ao executar automação por evento: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    async def _executar_acao_automacao(self, acao: Dict) -> Dict:
        """Executa uma ação específica de automação"""
        tipo = acao.get("tipo")
        
        if tipo == "iluminacao":
            return await self.controle_iluminacao(
                acao.get("acao"), acao.get("dispositivo"), acao.get("comodo"), acao.get("intensidade")
            )
        elif tipo == "temperatura":
            return await self.controle_temperatura(
                acao.get("acao"), acao.get("dispositivo"), acao.get("temperatura"), acao.get("modo")
            )
        elif tipo == "seguranca":
            return await self.controle_seguranca(acao.get("acao"), acao.get("dispositivo"))
        elif tipo == "eletrodomesticos":
            return await self.controle_eletrodomesticos(
                acao.get("acao"), acao.get("dispositivo"), acao.get("programa")
            )
        elif tipo == "cortinas":
            return await self.controle_cortinas(
                acao.get("acao"), acao.get("dispositivo"), acao.get("comodo"), acao.get("posicao")
            )
        elif tipo == "irrigacao":
            return await self.controle_irrigacao(
                acao.get("acao"), acao.get("zona"), acao.get("duracao_minutos")
            )
        elif tipo == "modo_inteligente":
            return await self.ativar_modo_inteligente(acao.get("modo"))
        else:
            return {"sucesso": False, "mensagem": f"Tipo de ação '{tipo}' não reconhecido"}
    
    # ═══════════════════════════════════════════
    # MONITORAMENTO
    # ═══════════════════════════════════════════
    
    async def monitoramento_consumo(self) -> Dict:
        """Monitora consumo de energia"""
        try:
            # Buscar dispositivos de medição
            dispositivos_medicao = []
            todos_dispositivos = self.mapeamento.listar_todos()
            
            for plataforma, disp_dict in todos_dispositivos.items():
                for nome, info in disp_dict.items():
                    if info.get("tipo") in ["medidor", "sensor energia", "smart plug"]:
                        dispositivos_medicao.append((nome, info, plataforma))
            
            consumos = []
            for nome, info, plataforma in dispositivos_medicao:
                if plataforma == "smartthings":
                    status = await self.smartthings.status_dispositivo(info["device_id"].replace("smartthings-", ""))
                else:
                    status = await self.homeassistant.listar_dispositivos()
                
                consumos.append({
                    "dispositivo": nome,
                    "plataforma": plataforma,
                    "status": status
                })
            
            return {
                "sucesso": True,
                "mensagem": f"Monitoramento de {len(consumos)} dispositivos",
                "consumos": consumos
            }
            
        except Exception as e:
            logger.error(f"Erro no monitoramento de consumo: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    async def status_dispositivos(self) -> Dict:
        """Status completo de todos os dispositivos"""
        try:
            st_devices = await self.smartthings.listar_dispositivos()
            ha_devices = await self.homeassistant.listar_dispositivos()
            mapeados = self.mapeamento.listar_todos()
            
            return {
                "sucesso": True,
                "mensagem": "Status completo dos dispositivos",
                "smartthings": st_devices,
                "homeassistant": ha_devices,
                "mapeados": mapeados,
                "timestamp": agora_iso()
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter status dos dispositivos: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    # ═══════════════════════════════════════════
    # AGENDAMENTO
    # ═══════════════════════════════════════════
    
    async def criar_agendamento(self, nome: str, horario: str, acao: str, dispositivo: str = None, 
                              comodo: str = None, dias: List[str] = None) -> Dict:
        """Cria agendamentos para automações"""
        try:
            agendamento = {
                "nome": nome,
                "horario": horario,
                "acao": acao,
                "dispositivo": dispositivo,
                "comodo": comodo,
                "dias": dias or ["todos"],
                "criado_em": agora_iso(),
                "ativo": True
            }
            
            # Salvar agendamento
            store = DataStore("agendamentos")
            agendamentos = store.load() or {}
            agendamentos[nome] = agendamento
            store.save(agendamentos)
            
            return {
                "sucesso": True,
                "mensagem": f"Agendamento '{nome}' criado para {horario}",
                "agendamento": agendamento
            }
            
        except Exception as e:
            logger.error(f"Erro ao criar agendamento: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}
    
    async def listar_agendamentos(self) -> Dict:
        """Lista todos os agendamentos ativos"""
        try:
            store = DataStore("agendamentos")
            agendamentos = store.load() or {}
            
            ativos = {nome: ag for nome, ag in agendamentos.items() if ag.get("ativo")}
            
            return {
                "sucesso": True,
                "mensagem": f"Encontrados {len(ativos)} agendamentos ativos",
                "agendamentos": ativos
            }
            
        except Exception as e:
            logger.error(f"Erro ao listar agendamentos: {e}")
            return {"sucesso": False, "mensagem": f"Erro: {str(e)}"}


# Instância global para uso no sistema
automacao_residencial = AutomacaoResidencial()
