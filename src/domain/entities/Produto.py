from pydantic import BaseModel

class Produto(BaseModel):
    id_produto: int = None
    nome: str
    preco: float
    foto: bytes
    descricao: str = None
