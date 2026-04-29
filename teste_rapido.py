#!/usr/bin/env python3
"""
Teste rápido da automação residencial com logs detalhados
"""

import asyncio
import sys
import os

# Adicionar o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jarvis_modules.automacao_residencial import automacao_residencial

async def teste_rapido():
    """Teste rápido com logs detalhados"""
    print("🧪 Teste rápido da automação residencial...")
    
    try:
        # Inicializar sistema
        await automacao_residencial.inicializar()
        print("✅ Sistema inicializado")
        
        # Adicionar dispositivo de teste (se já não existir)
        automacao_residencial.adicionar_mapeamento(
            "homeassistant", 
            "LED BULB W5K", 
            "light.led_bulb_w5k", 
            "luz", 
            ["quarto"]
        )
        print("✅ Dispositivo mapeado")
        
        # Testar comando específico
        print("\n🎮 Testando comando desligar...")
        resultado = await automacao_residencial.controle_iluminacao(
            "desligar", 
            dispositivo="LED BULB W5K"
        )
        
        print(f"📊 Resultado: {resultado}")
        
        # Aguardar 2 segundos
        await asyncio.sleep(2)
        
        # Testar comando ligar
        print("\n🎮 Testando comando ligar...")
        resultado = await automacao_residencial.controle_iluminacao(
            "ligar", 
            dispositivo="LED BULB W5K"
        )
        
        print(f"📊 Resultado: {resultado}")
        
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(teste_rapido())
