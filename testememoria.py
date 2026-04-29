from dotenv import load_dotenv
from mem0 import AsyncMemoryClient
import logging
import json
import asyncio
import os

# Configuração básica
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JarvisMemory:
    def __init__(self, user_name="Senhor"):
        self.user_name = user_name
        self.client = AsyncMemoryClient()

    async def salvar_conversa(self):
        """Simula o envio de mensagens para a memória do Mem0"""
        print(f"\n🚀 Enviando novas memórias para: {self.user_name}...")

        messages = [
            {"role": "user", "content": "[PREENCHER]"},
            {"role": "assistant", "content": "[PREENCHER]"},
            {"role": "user", "content": "[PREENCHER]"},
        ]

        await self.client.add(messages, user_id=self.user_name)
        print("✅ Informações processadas e salvas com sucesso!")

    async def buscar_memorias(self):
        """Recupera as informações que o jarvis aprendeu"""
        print(f"\n🧠 jarvis, o que você lembra sobre {self.user_name}?")

        query = f"Quais são as preferências e gostos de {self.user_name}?"

        response = await self.client.search(query, filters={"user_id": self.user_name})

        results = response["results"] if isinstance(response, dict) and "results" in response else response

        memories_list = []
        for item in results:
            if isinstance(item, dict):
                memories_list.append({
                    "fato": item.get("memory"),
                    "data": item.get("updated_at")
                })

        return memories_list


# --- EXECUÇÃO ---
async def main():
    brain = JarvisMemory("Senhor")

    await brain.salvar_conversa()

    historico = await brain.buscar_memorias()

    if historico:
        print(json.dumps(historico, indent=2, ensure_ascii=False))
    else:
        print("❌ Nenhuma memória encontrada para este usuário.")


if __name__ == "__main__":
    asyncio.run(main())