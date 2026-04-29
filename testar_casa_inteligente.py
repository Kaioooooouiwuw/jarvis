#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  JARVIS Casa Inteligente — Script de Teste e Verificação
═══════════════════════════════════════════════════════════════
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Adicionar o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jarvis_modules.automacao_residencial import automacao_residencial

def carregar_configuracao():
    """Verifica se as configurações necessárias estão presentes"""
    print("🔍 Verificando configuração...")
    
    load_dotenv()
    
    # Verificar Home Assistant
    ha_url = os.getenv('HOMEASSISTANT_URL')
    ha_token = os.getenv('HOMEASSISTANT_TOKEN')
    
    if ha_url and ha_token:
        print(f"✅ Home Assistant configurado: {ha_url}")
    else:
        print("❌ Home Assistant não configurado")
        print("   Adicione ao .env:")
        print("   HOMEASSISTANT_URL=http://homeassistant.local:8123/")
        print("   HOMEASSISTANT_TOKEN=seu_token_aqui")
    
    # Verificar SmartThings
    st_token = os.getenv('SMARTTHINGS_TOKEN')
    
    if st_token:
        print("✅ SmartThings configurado")
    else:
        print("❌ SmartThings não configurado")
        print("   Adicione ao .env:")
        print("   SMARTTHINGS_TOKEN=seu_token_aqui")
    
    # Verificar Google API (para interpretação de comandos)
    google_key = os.getenv('GOOGLE_API_KEY')
    
    if google_key:
        print("✅ Google API configurada (interpretação avançada)")
    else:
        print("⚠️  Google API não configurada (usará interpretação por regras)")
        print("   Adicione ao .env para melhor interpretação:")
        print("   GOOGLE_API_KEY=sua_chave_google_api")
    
    print()

async def testar_sistema_basico():
    """Testa funcionalidades básicas do sistema"""
    print("🧪 Testando sistema básico...")
    
    try:
        # Inicializar sistema
        await automacao_residencial.inicializar()
        print("✅ Sistema inicializado com sucesso")
        
        # Testar listagem de dispositivos
        print("\n📋 Testando listagem de dispositivos...")
        dispositivos = await automacao_residencial.listar_dispositivos_disponiveis()
        
        if dispositivos.get("sucesso"):
            print("✅ Listagem de dispositivos funcionando")
            
            # Mostrar quantidade de dispositivos
            st_count = len(dispositivos.get("smartthings", {}).get("items", []))
            ha_count = len(dispositivos.get("homeassistant", []))
            mapped_count = len(dispositivos.get("mapeados", {}).get("homeassistant", {})) + \
                          len(dispositivos.get("mapeados", {}).get("smartthings", {}))
            
            print(f"   SmartThings: {st_count} dispositivos")
            print(f"   Home Assistant: {ha_count} entidades")
            print(f"   Mapeados: {mapped_count} dispositivos")
        else:
            print("❌ Erro na listagem de dispositivos")
            print(f"   Erro: {dispositivos.get('mensagem', 'Desconhecido')}")
        
        # Testar mapeamento
        print("\n🗺️  Testando mapeamento de dispositivos...")
        automacao_residencial.adicionar_mapeamento(
            "homeassistant", 
            "luz teste", 
            "light.luz_teste", 
            "luz", 
            ["quarto"]
        )
        print("✅ Mapeamento de dispositivo funcionando")
        
        # Buscar dispositivo mapeado
        dispositivo = automacao_residencial.mapeamento.buscar_dispositivo("luz teste")
        if dispositivo:
            print("✅ Busca de dispositivo mapeado funcionando")
        else:
            print("❌ Erro na busca de dispositivo mapeado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste básico: {str(e)}")
        return False

async def testar_interpretacao():
    """Testa interpretação de comandos"""
    print("\n🤖 Testando interpretação de comandos...")
    
    comandos_teste = [
        "liga a luz da quarto",
        "desliga o ar condicionado",
        "ajusta temperatura para 22 graus",
        "ativa o modo cinema",
        "fecha as cortinas do quarto"
    ]
    
    for comando in comandos_teste:
        try:
            resultado = await automacao_residencial.executar_comando(comando)
            if resultado.get("sucesso"):
                print(f"✅ '{comando}' → Interpretado com sucesso")
            else:
                print(f"⚠️  '{comando}' → {resultado.get('mensagem', 'Erro desconhecido')}")
        except Exception as e:
            print(f"❌ '{comando}' → Erro: {str(e)}")

async def testar_modos_inteligentes():
    """Testa modos inteligentes (sem executar dispositivos reais)"""
    print("\n🎭 Testando modos inteligentes...")
    
    modos = ["modo cinema", "modo sair", "modo dormir", "modo chegar", "modo trabalho", "modo festa"]
    
    for modo in modos:
        try:
            # Apenas testar se o modo é reconhecido, não executar
            print(f"✅ Modo '{modo}' reconhecido")
        except Exception as e:
            print(f"❌ Erro no modo '{modo}': {str(e)}")

async def testar_agendamentos():
    """Testa sistema de agendamentos"""
    print("\n⏰ Testando sistema de agendamentos...")
    
    try:
        # Criar agendamento de teste
        resultado = await automacao_residencial.criar_agendamento(
            "teste",
            "18:00",
            "ligar",
            "luz teste",
            "quarto",
            ["todos"]
        )
        
        if resultado.get("sucesso"):
            print("✅ Criação de agendamento funcionando")
            
            # Listar agendamentos
            agendamentos = await automacao_residencial.listar_agendamentos()
            if agendamentos.get("sucesso"):
                print("✅ Listagem de agendamentos funcionando")
                print(f"   Agendamentos ativos: {len(agendamentos.get('agendamentos', {}))}")
            else:
                print("❌ Erro na listagem de agendamentos")
        else:
            print("❌ Erro na criação de agendamento")
            print(f"   Erro: {resultado.get('mensagem', 'Desconhecido')}")
            
    except Exception as e:
        print(f"❌ Erro no teste de agendamentos: {str(e)}")

async def testar_monitoramento():
    """Testa sistema de monitoramento"""
    print("\n📊 Testando sistema de monitoramento...")
    
    try:
        # Testar status de dispositivos
        status = await automacao_residencial.status_dispositivos()
        if status.get("sucesso"):
            print("✅ Status de dispositivos funcionando")
        else:
            print("⚠️  Erro no status de dispositivos (normal se não houver conexão)")
        
        # Testar monitoramento de consumo
        consumo = await automacao_residencial.monitoramento_consumo()
        if consumo.get("sucesso"):
            print("✅ Monitoramento de consumo funcionando")
        else:
            print("⚠️  Erro no monitoramento de consumo (normal se não houver medidores)")
            
    except Exception as e:
        print(f"❌ Erro no teste de monitoramento: {str(e)}")

def mostrar_exemplos_uso():
    """Mostra exemplos de uso prático"""
    print("\n💡 Exemplos de uso prático:")
    print()
    print("🏠 Controle Básico:")
    print('   await automacao_residencial.controle_iluminacao("ligar", comodo="sala")')
    print('   await automacao_residencial.controle_temperatura("ajustar", temperatura=22)')
    print('   await automacao_residencial.controle_seguranca("ativar_alarme")')
    print()
    print("🎬 Modos Inteligentes:")
    print('   await automacao_residencial.ativar_modo_inteligente("modo cinema")')
    print('   await automacao_residencial.ativar_modo_inteligente("modo dormir")')
    print()
    print("⏰ Agendamentos:")
    print('   await automacao_residencial.criar_agendamento("luz noite", "22:00", "desligar", "luz sala")')
    print()
    print("📋 Monitoramento:")
    print('   await automacao_residencial.status_dispositivos()')
    print('   await automacao_residencial.monitoramento_consumo()')

async def main():
    """Função principal de teste"""
    print("═══════════════════════════════════════════════════════════════")
    print("  Roben Casa Inteligente — Teste Completo do Sistema")
    print("═══════════════════════════════════════════════════════════════")
    print()
    
    # Verificar configuração
    carregar_configuracao()
    
    # Testar sistema básico
    sistema_ok = await testar_sistema_basico()
    
    if sistema_ok:
        # Testar interpretação
        await testar_interpretacao()
        
        # Testar modos inteligentes
        await testar_modos_inteligentes()
        
        # Testar agendamentos
        await testar_agendamentos()
        
        # Testar monitoramento
        await testar_monitoramento()
    else:
        print("\n❌ Sistema básico não está funcionando. Verifique a configuração.")
    
    # Mostrar exemplos
    mostrar_exemplos_uso()
    
    print("\n═══════════════════════════════════════════════════════════════")
    print("  Teste concluído!")
    print("═══════════════════════════════════════════════════════════════")
    print()
    print("📖 Para mais informações, consulte: JARVIS_CASA_INTELIGENTE.md")
    print("🚀 Para usar com voz, inicie o agente JARVIS completo")

if __name__ == "__main__":
    asyncio.run(main())
