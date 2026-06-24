from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DashboardComandaItem(BaseModel):
    id: int
    comanda: str
    data_hora: datetime
    cliente_id: Optional[int] = None
    cliente_nome: Optional[str] = None
    quantidade_itens: int
    valor_total: float


class ComandaDetalheProdutoItem(BaseModel):
    id: int
    produto_id: int
    produto_nome: str
    produto_foto: Optional[str] = None
    quantidade: int
    valor_unitario: float
    valor_total: float


class ComandaDetalheResponse(BaseModel):
    id: int
    comanda: str
    cliente_id: Optional[int] = None
    cliente_nome: Optional[str] = None
    itens: List[ComandaDetalheProdutoItem]
    valor_total: float


class RecebimentoCompletoCreate(BaseModel):
    comanda_ids: List[int] = Field(..., min_length=1)
    desconto: float = Field(default=0, ge=0)
    acrescimo: float = Field(default=0, ge=0)
    cliente_id: Optional[int] = None


class RecebimentoUpdate(BaseModel):
    desconto: Optional[float] = Field(default=None, ge=0)
    acrescimo: Optional[float] = Field(default=None, ge=0)


class RecebimentoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    data_hora: datetime
    funcionario_id: int
    funcionario_nome: Optional[str] = None
    desconto: float
    acrescimo: float
    valor_subtotal: float
    valor_total: float
    cliente_id: Optional[int] = None
    comanda_ids: List[int] = []


class ComprovanteResponse(BaseModel):
    id: int
    data_hora: datetime
    funcionario_id: int
    funcionario_nome: str
    desconto: float
    acrescimo: float
    valor_subtotal: float
    valor_total: float
    cliente_id: Optional[int] = None
    cliente_nome: Optional[str] = None
    comandas: List[ComandaDetalheResponse]
