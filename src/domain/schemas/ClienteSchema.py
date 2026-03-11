from pydantic import BaseModel, ConfigDict
from typing import Optional
class ClienteCreate(BaseModel):
    nome: str
    cpf: str
    telefone: str

class ClienteUpdate(BaseModel):
    id_cliente: int = None
    nome: Optional[str] = None
    cpf: Optional[str] = None
    telefone: Optional[str] = None

class ClienteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_cliente: int
    nome: str
    cpf: str
    telefone: str
#Gustavo Vieira Walter