#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════
  JARVIS Casa Inteligente — Diagnóstico (Versão Windows)
═════════════════════════════════════════════════════════════
"""

import requests
import json
import os
import sys
from dotenv import load_dotenv

# Adicionar o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def carregar_configuracao():
    """Carrega e exibe configuração atual"""
    print("🔍 Verificando configuração atual...")
    
    load_dotenv()
    
    ha_url = os.getenv('HOMEASSISTANT_URL')
    ha_token = os.getenv('HOMEASSISTANT_TOKEN')
    st_token = os.getenv('SMARTTHINGS_TOKEN')
    
    print(f"Home Assistant URL: {ha_url}")
    print(f"Home Assistant Token: {'✅ Configurado' if ha_token else '❌ Não configurado'}")
    print(f"SmartThings Token: {'✅ Configurado' if st_token else '❌ Não configurado'}")
    
    return ha_url, ha_token, st_token

def testar_conexao_homeassistant(url, token):
    """Testa conexão com Home Assistant usando requests"""
    print(f"\n🏠 Testando conexão com Home Assistant em {url}")
    
    if not token:
        print("❌ Token não configurado - não é possível testar")
        return False
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Testar conexão básica
        response = requests.get(f"{url}/api/", headers=headers, timeout=10)
        if response.status_code == 200:
            print("✅ Conexão básica com Home Assistant OK")
        else:
            print(f"❌ Erro na conexão básica: {response.status_code}")
            return False
        
        # Listar entidades (dispositivos)
        response = requests.get(f"{url}/api/states", headers=headers, timeout=10)
        if response.status_code == 200:
            states = response.json()
            print(f"✅ Encontradas {len(states)} entidades no Home Assistant")
            
            # Procurar por luzes específicas
            luzes = [s for s in states if s.get('entity_id', '').startswith('light.')]
            print(f"💡 Encontradas {len(luzes)} luzes:")
            
            for luz in luzes[:5]:  # Mostrar apenas as 5 primeiras
                entity_id = luz.get('entity_id')
                friendly_name = luz.get('attributes', {}).get('friendly_name', 'Sem nome')
                state = luz.get('state', 'unknown')
                print(f"   • {entity_id} - {friendly_name} - Estado: {state}")
            
            if len(luzes) > 5:
                print(f"   ... e mais {len(luzes) - 5} luzes")
            
            return luzes
        else:
            print(f"❌ Erro ao listar entidades: {response.status_code}")
            print(f"   Detalhes: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def testar_controle_luz(url, token, entity_id):
    """Testa controle de uma luz específica"""
    print(f"\n💡 Testando controle da luz: {entity_id}")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Verificar estado atual
        response = requests.get(f"{url}/api/states/{entity_id}", headers=headers, timeout=10)
        if response.status_code == 200:
            state_data = response.json()
            current_state = state_data.get('state', 'unknown')
            print(f"   Estado atual: {current_state}")
            
            # Determinar próxima ação
            next_action = "turn_on" if current_state == "off" else "turn_off"
            print(f"   Testando ação: {next_action}")
            
            # Enviar comando
            service_data = {"entity_id": entity_id}
            response = requests.post(
                f"{url}/api/services/light/{next_action}", 
                headers=headers, 
                json=service_data,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"   ✅ Comando {next_action} enviado com sucesso")
                
                # Aguardar um momento e verificar resultado
                import time
                time.sleep(2)
                
                response = requests.get(f"{url}/api/states/{entity_id}", headers=headers, timeout=10)
                if response.status_code == 200:
                    new_state = response.json()
                    new_state_value = new_state.get('state', 'unknown')
                    print(f"   Novo estado: {new_state_value}")
                    
                    if new_state_value != current_state:
                        print(f"   ✅ Luz respondeu ao comando! {current_state} → {new_state_value}")
                        return True
                    else:
                        print(f"   ⚠️ Luz não mudou de estado - pode estar offline ou com problema")
                        return False
                else:
                    print(f"   ❌ Erro ao verificar resultado: {response.status_code}")
                    return False
            else:
                print(f"   ❌ Erro ao enviar comando: {response.status_code}")
                print(f"   Detalhes: {response.text}")
                return False
        else:
            print(f"   ❌ Luz não encontrada: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro no teste: {e}")
        return False

def diagnosticar_completo():
    """Diagnóstico completo do sistema"""
    print("═════════════════════════════════════════════════════════════")
    print("  JARVIS Casa Inteligente — Diagnóstico Completo (Windows)")
    print("═════════════════════════════════════════════════════════════")
    
    # Carregar configuração
    ha_url, ha_token, st_token = carregar_configuracao()
    
    if not ha_url or not ha_token:
        print("\n❌ Home Assistant não configurado corretamente!")
        print("Verifique seu arquivo .env:")
        print("HOMEASSISTANT_URL=http://seu-home-assistant:8123/")
        print("HOMEASSISTANT_TOKEN=seu_token_de_acesso_longo")
        return
    
    # Testar conexão
    luzes = testar_conexao_homeassistant(ha_url, ha_token)
    
    if not luzes:
        print("\n❌ Não foi possível encontrar dispositivos no Home Assistant")
        print("Verifique:")
        print("1. Se o Home Assistant está online")
        print("2. Se o token tem permissões suficientes")
        print("3. Se a URL está correta")
        return
    
    # Testar controle de algumas luzes
    print(f"\n🎮 Testando controle das luzes encontradas...")
    
    luzes_testadas = 0
    luzes_funcionando = 0
    
    for luz in luzes[:3]:  # Testar apenas 3 luzes
        entity_id = luz.get('entity_id')
        if testar_controle_luz(ha_url, ha_token, entity_id):
            luzes_funcionando += 1
        luzes_testadas += 1
        print()  # Espaçamento
    
    # Resumo final
    print("═════════════════════════════════════════════════════════════")
    print("  RESUMO DO DIAGNÓSTICO")
    print("═════════════════════════════════════════════════════════════")
    print(f"📊 Dispositivos encontrados: {len(luzes)} luzes")
    print(f"🧪 Dispositivos testados: {luzes_testadas}")
    print(f"✅ Dispositivos funcionando: {luzes_funcionando}")
    print(f"❌ Dispositivos com problema: {luzes_testadas - luzes_funcionando}")
    
    if luzes_funcionando > 0:
        print(f"\n🎉 Sua configuração está funcionando!")
        print(f"💡 {luzes_funcionando} luz(es) responderam aos comandos")
        print(f"\nSe algumas luzes não funcionam, pode ser:")
        print(f"• Luz offline ou sem energia")
        print(f"• Problema na integração com o Home Assistant")
        print(f"• Permissões insuficientes no token")
    else:
        print(f"\n❌ Nenhuma luz respondeu aos comandos!")
        print(f"\nPossíveis causas:")
        print(f"• Token sem permissões de controle")
        print(f"• Dispositivos offline")
        print(f"• Problema na configuração do Home Assistant")
        print(f"• Firewall bloqueando a conexão")
    
    print(f"\n🔧 Soluções recomendadas:")
    print(f"1. Verifique se as luzes funcionam diretamente no Home Assistant")
    print(f"2. Crie um token de acesso com permissões totais")
    print(f"3. Teste a conexão da rede onde o JARVIS está rodando")
    print(f"4. Verifique o log do Home Assistant para erros")

if __name__ == "__main__":
    diagnosticar_completo()
