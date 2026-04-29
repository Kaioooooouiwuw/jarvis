"""
 — Modelos de projetos fullstack para venda, incluindo HTML, CSS e JS avançados.
API gerada pelo Jarvis.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="", description="Modelos de projetos fullstack para venda, incluindo HTML, CSS e JS avançados.")

class Item(BaseModel):
    id: Optional[int] = None
    nome: str
    descricao: str = ""
    ativo: bool = True

db: list[Item] = []
next_id = 1

@app.get("/")
async def root():
    return {"msg": "API  funcionando!", "docs": "/docs"}

@app.get("/items")
async def listar(): return db

@app.post("/items", status_code=201)
async def criar(item: Item):
    global next_id
    item.id = next_id; next_id += 1
    db.append(item); return item

@app.get("/items/{item_id}")
async def obter(item_id: int):
    for i in db:
        if i.id == item_id: return i
    raise HTTPException(404, "Não encontrado")

@app.delete("/items/{item_id}")
async def deletar(item_id: int):
    global db
    db = [i for i in db if i.id != item_id]
    return {"msg": "Deletado"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
