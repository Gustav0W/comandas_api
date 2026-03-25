from pydantic import BaseModel, ConfigDict
from typing import Optional

class ProdutoCreate(BaseModel):
    nome: str
    preco: float
    foto: bytes
    descricao: str = None

class ProdutoUpdate(BaseModel):
    id_produto: int = None
    nome: Optional[str] = None
    preco: Optional[float] = None
    foto: Optional[bytes] = None
    descricao: Optional[str] = None

class ProdutoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_produto: int
    nome: str
    preco: float
    foto: bytes
    descricao: str = None
#Gustavo Vieira Walter
