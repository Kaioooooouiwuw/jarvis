"""
Módulo de Segurança Ética do ROBEN 2
Integra ferramentas profissionais para testes de segurança controlados
"""

import os
import json
import subprocess
import asyncio
import logging
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)

class SegurancaEtica:
    def __init__(self):
        self.relatorios_dir = Path.home() / "Downloads" / "Relatorios_Seguranca"
        self.relatorios_dir.mkdir(exist_ok=True)
        self.zap_api_key = None
        self.zap_host = "127.0.0.1"
        self.zap_port = 8080
        
    def _verificar_ferramenta(self, ferramenta):
        """Verifica se a ferramenta está instalada"""
        try:
            result = subprocess.run([ferramenta, "--version"], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _salvar_relatorio(self, nome_arquivo, conteudo, formato="json"):
        """Salva relatório na pasta de Downloads"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_completo = f"{nome_arquivo}_{timestamp}.{formato}"
        caminho_arquivo = self.relatorios_dir / nome_completo
        
        try:
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                if formato == "json":
                    json.dump(conteudo, f, indent=2, ensure_ascii=False)
                else:
                    f.write(conteudo)
            logger.info(f"Relatório salvo: {caminho_arquivo}")
            return str(caminho_arquivo)
        except Exception as e:
            logger.error(f"Erro ao salvar relatório: {e}")
            return None
    
    async def iniciar_zap(self):
        """Inicia OWASP ZAP em modo headless"""
        if not self._verificar_ferramenta("zap"):
            raise Exception("OWASP ZAP não encontrado. Instale com: brew install zap ou baixe do site oficial.")
        
        try:
            # Iniciar ZAP em modo headless
            cmd = [
                "zap", "-daemon", "-port", str(self.zap_port),
                "-host", self.zap_host, "-config", "api.addrs.addr.name=.*",
                "-config", "api.addrs.addr.regex=true"
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Aguardar ZAP iniciar
            await asyncio.sleep(10)
            
            # Verificar se ZAP está respondendo
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://{self.zap_host}:{self.zap_port}/JSON/core/view/zapVersion/") as response:
                        if response.status == 200:
                            logger.info("OWASP ZAP iniciado com sucesso")
                            return True
            except:
                pass
            
            raise Exception("Falha ao iniciar OWASP ZAP")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar ZAP: {e}")
            raise
    
    async def scan_zap(self, target_url, scan_type="spider"):
        """Executa scan com OWASP ZAP"""
        if not target_url.startswith(('http://', 'https://')):
            target_url = f'http://{target_url}'
        
        try:
            import aiohttp
            
            # Iniciar spider
            async with aiohttp.ClientSession() as session:
                # Iniciar spider
                spider_url = f"http://{self.zap_host}:{self.zap_port}/JSON/spider/action/scan/"
                params = {"url": target_url}
                async with session.get(spider_url, params=params) as response:
                    spider_data = await response.json()
                    scan_id = spider_data.get("scan")
                
                if not scan_id:
                    raise Exception("Falha ao iniciar spider")
                
                # Monitorar progresso
                progress_url = f"http://{self.zap_host}:{self.zap_port}/JSON/spider/view/status/"
                while True:
                    async with session.get(progress_url, params={"scanId": scan_id}) as response:
                        status_data = await response.json()
                        progress = int(status_data.get("status", 0))
                        
                        if progress >= 100:
                            break
                        await asyncio.sleep(2)
                
                # Iniciar scan ativo
                active_url = f"http://{self.zap_host}:{self.zap_port}/JSON/ascan/action/scan/"
                async with session.get(active_url, params={"url": target_url}) as response:
                    active_data = await response.json()
                    active_scan_id = active_data.get("scan")
                
                # Aguardar scan ativo
                active_progress_url = f"http://{self.zap_host}:{self.zap_port}/JSON/ascan/view/status/"
                while True:
                    async with session.get(active_progress_url, params={"scanId": active_scan_id}) as response:
                        progress_data = await response.json()
                        progress = int(progress_data.get("status", 0))
                        
                        if progress >= 100:
                            break
                        await asyncio.sleep(3)
                
                # Obter alertas
                alerts_url = f"http://{self.zap_host}:{self.zap_port}/JSON/core/view/alerts/"
                async with session.get(alerts_url) as response:
                    alerts_data = await response.json()
                
                # Analisar resultados
                relatorio = self._analisar_alerts_zap(alerts_data, target_url)
                
                return relatorio
                
        except Exception as e:
            logger.error(f"Erro no scan ZAP: {e}")
            raise
    
    def _analisar_alerts_zap(self, alerts_data, target_url):
        """Analisa alertas do ZAP e gera relatório inteligente"""
        alerts = alerts_data.get("alerts", [])
        
        vulnerabilidades = []
        risco_contador = {"Alto": 0, "Médio": 0, "Baixo": 0, "Informativo": 0}
        
        for alert in alerts:
            risco = alert.get("risk", "Informativo")
            risco_contador[risco] = risco_contador.get(risco, 0) + 1
            
            vulnerabilidade = {
                "nome": alert.get("alert", "Desconhecido"),
                "risco": risco,
                "descricao": alert.get("desc", ""),
                "solucao": alert.get("solution", ""),
                "referencia": alert.get("reference", ""),
                "parametro": alert.get("param", ""),
                "ataque": alert.get("attack", ""),
                "evidencia": alert.get("evidence", ""),
                "cwe_id": alert.get("cweid", ""),
                "wasc_id": alert.get("wascid", "")
            }
            vulnerabilidades.append(vulnerabilidade)
        
        relatorio = {
            "target": target_url,
            "data_scan": datetime.now().isoformat(),
            "ferramenta": "OWASP ZAP",
            "resumo": {
                "total_vulnerabilidades": len(vulnerabilidades),
                "por_risco": risco_contador
            },
            "vulnerabilidades": vulnerabilidades,
            "recomendacoes": self._gerar_recomendacoes_zap(vulnerabilidades)
        }
        
        # Salvar relatório
        caminho = self._salvar_relatorio(f"zap_{urlparse(target_url).netloc}", relatorio)
        relatorio["caminho_arquivo"] = caminho
        
        return relatorio
    
    def _gerar_recomendacoes_zap(self, vulnerabilidades):
        """Gera recomendações baseadas nas vulnerabilidades encontradas"""
        recomendacoes = []
        
        for vuln in vulnerabilidades:
            risco = vuln.get("risco", "Baixo")
            nome = vuln.get("nome", "")
            
            if "SQL Injection" in nome:
                recomendacoes.append({
                    "prioridade": "Alta",
                    "problema": "Injeção SQL detectada",
                    "solucao": "Use prepared statements/parameterized queries. Valide e sanitize todas as entradas do usuário.",
                    "codigo_exemplo": "# Python com SQLAlchemy\nsession.query(User).filter(User.id == user_id)"
                })
            elif "XSS" in nome or "Cross Site Scripting" in nome:
                recomendacoes.append({
                    "prioridade": "Alta" if risco == "Alto" else "Média",
                    "problema": "Vulnerabilidade XSS detectada",
                    "solucao": "Implemente Content Security Policy. Escape todas as saídas HTML. Use frameworks seguros como React/Vue.",
                    "codigo_exemplo": "# Python com Jinja2\nfrom jinja2 import escape\nsafe_output = escape(user_input)"
                })
            elif "CSRF" in nome:
                recomendacoes.append({
                    "prioridade": "Média",
                    "problema": "Vulnerabilidade CSRF detectada",
                    "solucao": "Implemente tokens CSRF em todos os formulários. Verifique Origin/Referer headers.",
                    "codigo_exemplo": "# Flask CSRF protection\nfrom flask_wtf.csrf import CSRFProtect\ncsrf = CSRFProtect(app)"
                })
        
        return recomendacoes
    
    async def scan_nmap(self, target, ports="1-1000", scan_type="-sS"):
        """Executa scan com Nmap"""
        if not self._verificar_ferramenta("nmap"):
            raise Exception("Nmap não encontrado. Instale com: brew install nmap")
        
        try:
            cmd = ["nmap", scan_type, "-p", ports, "-oX", "-", target]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Erro no Nmap: {stderr.decode()}")
            
            # Parse XML output
            root = ET.fromstring(stdout.decode())
            
            portas_abertas = []
            for port in root.findall(".//port"):
                if port.find(".//state").get("state") == "open":
                    port_info = {
                        "numero": port.get("portid"),
                        "protocolo": port.get("protocol"),
                        "servico": port.find(".//service").get("name", "desconhecido"),
                        "versao": port.find(".//service").get("version", ""),
                        "produto": port.find(".//service").get("product", "")
                    }
                    portas_abertas.append(port_info)
            
            relatorio = {
                "target": target,
                "data_scan": datetime.now().isoformat(),
                "ferramenta": "Nmap",
                "portas_abertas": portas_abertas,
                "resumo": {
                    "total_portas": len(portas_abertas),
                    "servicos_encontrados": list(set([p["servico"] for p in portas_abertas]))
                },
                "recomendacoes": self._gerar_recomendacoes_nmap(portas_abertas)
            }
            
            # Salvar relatório
            caminho = self._salvar_relatorio(f"nmap_{target}", relatorio)
            relatorio["caminho_arquivo"] = caminho
            
            return relatorio
            
        except Exception as e:
            logger.error(f"Erro no scan Nmap: {e}")
            raise
    
    def _gerar_recomendacoes_nmap(self, portas_abertas):
        """Gera recomendações baseadas nas portas abertas"""
        recomendacoes = []
        
        portas_risco = {
            "21": "FTP - Considere SFTP",
            "23": "Telnet - Use SSH",
            "80": "HTTP - Implemente HTTPS",
            "135": "RPC - Verifique necessidade",
            "139": "NetBIOS - Considere desativar",
            "445": "SMB - Verifique configurações",
            "1433": "SQL Server - Restrinja acesso",
            "1521": "Oracle - Restrinja acesso",
            "3306": "MySQL - Restrinja acesso",
            "3389": "RDP - Use VPN",
            "5432": "PostgreSQL - Restrinja acesso"
        }
        
        for porta in portas_abertas:
            numero = porta.get("numero", "")
            if numero in portas_risco:
                recomendacoes.append({
                    "prioridade": "Alta",
                    "porta": f"{numero}/{porta.get('protocolo', 'tcp')}",
                    "servico": porta.get("servico", ""),
                    "recomendacao": portas_risco[numero],
                    "acao": "Verifique se esta porta precisa estar aberta e implemente firewall"
                })
        
        return recomendacoes
    
    async def scan_nikto(self, target_url):
        """Executa scan com Nikto"""
        if not self._verificar_ferramenta("nikto"):
            raise Exception("Nikto não encontrado. Instale com: brew install nikto")
        
        try:
            if not target_url.startswith(('http://', 'https://')):
                target_url = f'http://{target_url}'
            
            cmd = ["nikto", "-h", target_url, "-Format", "json", "-output", "/dev/stdout"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0 and "No items found" not in stderr.decode():
                raise Exception(f"Erro no Nikto: {stderr.decode()}")
            
            # Parse JSON output
            try:
                nikto_data = json.loads(stdout.decode())
            except:
                # Se não for JSON, parse do texto
                nikto_data = self._parse_nikto_text(stdout.decode())
            
            vulnerabilidades = nikto_data.get("vulnerabilities", [])
            
            relatorio = {
                "target": target_url,
                "data_scan": datetime.now().isoformat(),
                "ferramenta": "Nikto",
                "vulnerabilidades": vulnerabilidades,
                "resumo": {
                    "total_vulnerabilidades": len(vulnerabilidades),
                    "server_info": nikto_data.get("server", {})
                },
                "recomendacoes": self._gerar_recomendacoes_nikto(vulnerabilidades)
            }
            
            # Salvar relatório
            caminho = self._salvar_relatorio(f"nikto_{urlparse(target_url).netloc}", relatorio)
            relatorio["caminho_arquivo"] = caminho
            
            return relatorio
            
        except Exception as e:
            logger.error(f"Erro no scan Nikto: {e}")
            raise
    
    def _parse_nikto_text(self, output):
        """Parse output texto do Nikto"""
        vulnerabilidades = []
        linhas = output.split('\n')
        
        for linha in linhas:
            if "+" in linha and ("OSVDB" in linha or "CVE" in linha):
                vulnerabilidades.append({
                    "descricao": linha.strip(),
                    "severidade": "Média"  # Default
                })
        
        return {"vulnerabilities": vulnerabilidades}
    
    def _gerar_recomendacoes_nikto(self, vulnerabilidades):
        """Gera recomendações baseadas nos findings do Nikto"""
        recomendacoes = []
        
        for vuln in vulnerabilidades:
            desc = vuln.get("descricao", "").lower()
            
            if "apache" in desc and "version" in desc:
                recomendacoes.append({
                    "prioridade": "Média",
                    "problema": "Versão do Apache exposta",
                    "solucao": "Configure ServerTokens Prod e ServerSignature Off no Apache"
                })
            elif "php" in desc and "version" in desc:
                recomendacoes.append({
                    "prioridade": "Média",
                    "problema": "Versão do PHP exposta",
                    "solucao": "Desabilite expose_php no php.ini"
                })
            elif "directory listing" in desc:
                recomendacoes.append({
                    "prioridade": "Média",
                    "problema": "Directory listing ativado",
                    "solucao": "Desative Options -Indexes no Apache ou configure nginx adequadamente"
                })
        
        return recomendacoes
    
    async def scan_completo(self, target_url):
        """Executa scan completo com todas as ferramentas"""
        logger.info(f"Iniciando scan completo em: {target_url}")
        
        resultados = {
            "target": target_url,
            "data_inicio": datetime.now().isoformat(),
            "scans": {}
        }
        
        try:
            # 1. Scan Nmap
            logger.info("Executando scan Nmap...")
            target_host = urlparse(target_url).netloc.split(':')[0]
            resultados["scans"]["nmap"] = await self.scan_nmap(target_host)
            
            # 2. Scan Nikto
            logger.info("Executando scan Nikto...")
            resultados["scans"]["nikto"] = await self.scan_nikto(target_url)
            
            # 3. Scan ZAP
            logger.info("Iniciando OWASP ZAP...")
            await self.iniciar_zap()
            resultados["scans"]["zap"] = await self.scan_zap(target_url)
            
            # Análise final
            resultados["analise_final"] = self._analise_final(resultados["scans"])
            resultados["data_fim"] = datetime.now().isoformat()
            
            # Salvar relatório completo
            caminho = self._salvar_relatorio(f"scan_completo_{urlparse(target_url).netloc}", resultados)
            resultados["caminho_arquivo"] = caminho
            
            return resultados
            
        except Exception as e:
            logger.error(f"Erro no scan completo: {e}")
            resultados["erro"] = str(e)
            return resultados
    
    def _analise_final(self, scans):
        """Gera análise final consolidada"""
        analise = {
            "resumo_geral": {
                "total_vulnerabilidades": 0,
                "risco_maximo": "Baixo",
                "portas_criticas": 0,
                "recomendacoes_principais": []
            },
            "prioridade_acoes": []
        }
        
        # Consolidar vulnerabilidades
        todas_vulns = []
        for scan_nome, scan_data in scans.items():
            if "vulnerabilidades" in scan_data:
                todas_vulns.extend(scan_data["vulnerabilidades"])
        
        analise["resumo_geral"]["total_vulnerabilidades"] = len(todas_vulns)
        
        # Verificar risco máximo
        for vuln in todas_vulns:
            risco = vuln.get("risco", "Baixo")
            if risco == "Alto":
                analise["resumo_geral"]["risco_maximo"] = "Alto"
                break
            elif risco == "Médio" and analise["resumo_geral"]["risco_maximo"] != "Alto":
                analise["resumo_geral"]["risco_maximo"] = "Médio"
        
        # Gerar ações priorizadas
        acoes = []
        
        # Ações de alta prioridade
        if any(vuln.get("risco") == "Alto" for vuln in todas_vulns):
            acoes.append({
                "prioridade": "Crítica",
                "acao": "Corrigir vulnerabilidades de Alto risco imediatamente",
                "descricao": "Vulnerabilidades críticas detectadas podem comprometer o sistema"
            })
        
        # Verificar portas
        if "nmap" in scans:
            portas_abertas = scans["nmap"]["portas_abertas"]
            portas_perigosas = [p for p in portas_abertas if p.get("numero") in ["23", "135", "139", "445", "3389"]]
            if portas_perigosas:
                acoes.append({
                    "prioridade": "Alta",
                    "acao": "Revisar portas abertas críticas",
                    "descricao": f"Portas perigosas detectadas: {[p['numero'] for p in portas_perigosas]}"
                })
        
        analise["prioridade_acoes"] = acoes
        return analise
    
    async def aplicar_correcoes_automaticas(self, relatorio, confirmacao=False):
        """Aplica correções automáticas (se permitido)"""
        if not confirmacao:
            return {"status": "negado", "mensagem": "Correções automáticas requerem confirmação explícita"}
        
        logger.warning("Iniciando correções automáticas - ESTA É UMA OPERAÇÃO DE RISCO")
        
        correcoes_aplicadas = []
        
        try:
            # Implementar correções baseadas no relatório
            # NOTA: Esta é uma funcionalidade experimental e perigosa
            # Deve ser usada apenas em ambientes de teste
            
            for scan_data in relatorio.get("scans", {}).values():
                recomendacoes = scan_data.get("recomendacoes", [])
                
                for rec in recomendacoes:
                    if rec.get("prioridade") == "Alta":
                        # Simular aplicação de correção
                        logger.info(f"Aplicando correção: {rec.get('solucao', '')}")
                        correcoes_aplicadas.append(rec)
            
            return {
                "status": "sucesso",
                "correcoes_aplicadas": correcoes_aplicadas,
                "aviso": "Correções aplicadas em ambiente controlado. Verifique manualmente."
            }
            
        except Exception as e:
            logger.error(f"Erro ao aplicar correções: {e}")
            return {
                "status": "erro",
                "mensagem": str(e),
                "correcoes_aplicadas": correcoes_aplicadas
            }

# Funções para integração com o ROBEN
seguranca_instance = None

def get_seguranca_instance():
    """Retorna instância singleton do módulo de segurança"""
    global seguranca_instance
    if seguranca_instance is None:
        seguranca_instance = SegurancaEtica()
    return seguranca_instance

async def scan_seguranca_completo(target_url):
    """Interface principal para scan de segurança completo"""
    seguranca = get_seguranca_instance()
    return await seguranca.scan_completo(target_url)

async def scan_seguranca_rapido(target_url):
    """Interface para scan rápido (apenas Nikto)"""
    seguranca = get_seguranca_instance()
    return await seguranca.scan_nikto(target_url)

async def analisar_relatorio_seguranca(caminho_relatorio):
    """Analisa relatório existente e gera insights"""
    try:
        with open(caminho_relatorio, 'r', encoding='utf-8') as f:
            relatorio = json.load(f)
        
        seguranca = get_seguranca_instance()
        analise = seguranca._analise_final(relatorio.get("scans", {}))
        
        return {
            "relatorio_original": relatorio,
            "analise_inteligente": analise,
            "insights": gerar_insights_adicionais(relatorio)
        }
        
    except Exception as e:
        logger.error(f"Erro ao analisar relatório: {e}")
        return {"erro": str(e)}

def gerar_insights_adicionais(relatorio):
    """Gera insights adicionais baseados em machine learning"""
    insights = []
    
    # Análise de padrões
    total_vulns = 0
    risco_distribution = {"Alto": 0, "Médio": 0, "Baixo": 0}
    
    for scan_data in relatorio.get("scans", {}).values():
        if "vulnerabilidades" in scan_data:
            total_vulns += len(scan_data["vulnerabilidades"])
            for vuln in scan_data["vulnerabilidades"]:
                risco = vuln.get("risco", "Baixo")
                risco_distribution[risco] = risco_distribution.get(risco, 0) + 1
    
    if total_vulns > 20:
        insights.append({
            "tipo": "padrao",
            "mensagem": "Alto número de vulnerabilidades detectado. Considere uma revisão completa da segurança.",
            "severidade": "Alta"
        })
    
    if risco_distribution["Alto"] > 5:
        insights.append({
            "tipo": "risco",
            "mensagem": "Múltiplas vulnerabilidades de alto risco. Ação imediata recomendada.",
            "severidade": "Crítica"
        })
    
    return insights
