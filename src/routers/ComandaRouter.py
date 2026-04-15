from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.schemas.AuthSchema import FuncionarioAuth
from domain.schemas.ClienteSchema import ClienteResponse
from domain.schemas.ComandaSchema import (
    ComandaCreate,
    ComandaProdutosCreate,
    ComandaProdutosResponse,
    ComandaProdutosUpdate,
    ComandaResponse,
    ComandaUpdate,
)
from domain.schemas.FuncionarioSchema import FuncionarioResponse
from domain.schemas.ProdutoSchema import ProdutoResponse
from infra.database import get_async_db
from infra.dependencies import get_current_active_user, require_group
from infra.orm.ClienteModel import ClienteDB
from infra.orm.ComandaModel import ComandaDB, ComandaProdutoDB
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.orm.ProdutoModel import ProdutoDB
from infra.rate_limit import get_rate_limit, limiter
from services.AuditoriaService import AuditoriaService

router = APIRouter()


def _build_comanda_response(comanda: ComandaDB, funcionario: Optional[FuncionarioDB], cliente: Optional[ClienteDB]) -> ComandaResponse:
    return ComandaResponse(
        id=comanda.id,
        comanda=comanda.comanda,
        data_hora=comanda.data_hora,
        status=comanda.status,
        cliente_id=comanda.cliente_id,
        funcionario_id=comanda.funcionario_id,
        funcionario=FuncionarioResponse(
            id=funcionario.id,
            nome=funcionario.nome,
            matricula=funcionario.matricula,
            cpf=funcionario.cpf,
            telefone=funcionario.telefone,
            grupo=funcionario.grupo,
        ) if funcionario else None,
        cliente=ClienteResponse(
            id_cliente=cliente.id_cliente,
            nome=cliente.nome,
            cpf=cliente.cpf,
            telefone=cliente.telefone,
        ) if cliente else None,
    )


@router.get("/comanda/{id}", response_model=ComandaResponse, tags=["Comanda"], summary="Buscar comanda por ID")
@limiter.limit(get_rate_limit("moderate"))
async def get_comanda(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user),
):
    result = await db.execute(
        select(ComandaDB, FuncionarioDB, ClienteDB)
        .outerjoin(FuncionarioDB, FuncionarioDB.id == ComandaDB.funcionario_id)
        .outerjoin(ClienteDB, ClienteDB.id_cliente == ComandaDB.cliente_id)
        .where(ComandaDB.id == id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
    return _build_comanda_response(*row)


@router.get("/comanda/", response_model=List[ComandaResponse], tags=["Comanda"], summary="Listar comandas com filtros")
@limiter.limit(get_rate_limit("moderate"))
async def get_comandas(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    id: Optional[int] = Query(None),
    comanda: Optional[str] = Query(None),
    status_filter: Optional[int] = Query(None, alias="status"),
    funcionario_id: Optional[int] = Query(None),
    cliente_id: Optional[int] = Query(None),
    data_inicio: Optional[datetime] = Query(None),
    data_fim: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user),
):
    query = (
        select(ComandaDB, FuncionarioDB, ClienteDB)
        .outerjoin(FuncionarioDB, FuncionarioDB.id == ComandaDB.funcionario_id)
        .outerjoin(ClienteDB, ClienteDB.id_cliente == ComandaDB.cliente_id)
    )
    conditions = []
    if id is not None:
        conditions.append(ComandaDB.id == id)
    if comanda is not None:
        conditions.append(ComandaDB.comanda == comanda)
    if status_filter is not None:
        conditions.append(ComandaDB.status == status_filter)
    if funcionario_id is not None:
        conditions.append(ComandaDB.funcionario_id == funcionario_id)
    if cliente_id is not None:
        conditions.append(ComandaDB.cliente_id == cliente_id)
    if data_inicio is not None:
        conditions.append(ComandaDB.data_hora >= data_inicio)
    if data_fim is not None:
        conditions.append(ComandaDB.data_hora <= data_fim)
    if conditions:
        query = query.where(*conditions)
    result = await db.execute(query.offset(skip).limit(limit))
    return [_build_comanda_response(comanda_row, funcionario_row, cliente_row) for comanda_row, funcionario_row, cliente_row in result.all()]


@router.post("/comanda/", response_model=ComandaResponse, status_code=status.HTTP_201_CREATED, tags=["Comanda"], summary="Criar comanda")
@limiter.limit(get_rate_limit("restrictive"))
async def create_comanda(
    request: Request,
    comanda_data: ComandaCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user),
):
    if comanda_data.status != 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Na abertura o status deve ser 0")
    result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == comanda_data.funcionario_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Funcionário não encontrado")
    if comanda_data.cliente_id:
        result = await db.execute(select(ClienteDB).where(ClienteDB.id_cliente == comanda_data.cliente_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cliente não encontrado")
    result = await db.execute(select(ComandaDB).where(ComandaDB.comanda == comanda_data.comanda, ComandaDB.status == 0))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comanda já está aberta")

    new_comanda = ComandaDB(
        comanda=comanda_data.comanda,
        data_hora=datetime.now(),
        status=0,
        cliente_id=comanda_data.cliente_id,
        funcionario_id=comanda_data.funcionario_id,
    )
    db.add(new_comanda)
    await db.commit()
    await db.refresh(new_comanda)
    await AuditoriaService.registrar_acao_async(db=db, funcionario_id=current_user.id, acao="CREATE", recurso="COMANDA", recurso_id=new_comanda.id, dados_novos=new_comanda, request=request)
    return new_comanda


@router.put("/comanda/{id}", response_model=ComandaResponse, tags=["Comanda"], summary="Atualizar comanda")
@limiter.limit(get_rate_limit("restrictive"))
async def update_comanda(
    request: Request,
    id: int,
    comanda_data: ComandaUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
    comanda = result.scalar_one_or_none()
    if not comanda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")

    dados_antigos = comanda.__dict__.copy()
    update_data = comanda_data.model_dump(exclude_unset=True)
    if "cliente_id" in update_data and update_data["cliente_id"] not in (None, 0):
        result = await db.execute(select(ClienteDB).where(ClienteDB.id_cliente == update_data["cliente_id"]))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cliente não encontrado")
    if "funcionario_id" in update_data and update_data["funcionario_id"] is not None:
        result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == update_data["funcionario_id"]))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Funcionário não encontrado")
    if update_data.get("cliente_id") == 0:
        update_data["cliente_id"] = None

    for field, value in update_data.items():
        setattr(comanda, field, value)
    await db.commit()
    await db.refresh(comanda)
    await AuditoriaService.registrar_acao_async(db=db, funcionario_id=current_user.id, acao="UPDATE", recurso="COMANDA", recurso_id=comanda.id, dados_antigos=dados_antigos, dados_novos=comanda, request=request)
    return comanda


@router.delete("/comanda/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Comanda"], summary="Excluir comanda")
@limiter.limit(get_rate_limit("critical"))
async def delete_comanda(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
    comanda = result.scalar_one_or_none()
    if not comanda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
    result = await db.execute(select(func.count(ComandaProdutoDB.id)).where(ComandaProdutoDB.comanda_id == id))
    if (result.scalar() or 0) > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível excluir comanda com produtos vinculados")
    await db.delete(comanda)
    await db.commit()
    await AuditoriaService.registrar_acao_async(db=db, funcionario_id=current_user.id, acao="DELETE", recurso="COMANDA", recurso_id=id, dados_antigos=comanda, request=request)
    return None


@router.put("/comanda/{id}/cancelar", response_model=ComandaResponse, tags=["Comanda"], summary="Cancelar comanda")
@limiter.limit(get_rate_limit("critical"))
async def cancelar_comanda(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
    comanda = result.scalar_one_or_none()
    if not comanda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
    if comanda.status == 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comanda já está cancelada")
    if comanda.status == 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comanda já está fechada")
    dados_antigos = comanda.__dict__.copy()
    comanda.status = 2
    await db.commit()
    await db.refresh(comanda)
    await AuditoriaService.registrar_acao_async(db=db, funcionario_id=current_user.id, acao="CANCEL", recurso="COMANDA", recurso_id=id, dados_antigos=dados_antigos, dados_novos=comanda, request=request)
    return comanda


@router.post("/comanda/{comanda_id}/produto", response_model=ComandaProdutosResponse, status_code=status.HTTP_201_CREATED, tags=["Comanda"], summary="Adicionar produto na comanda")
@limiter.limit(get_rate_limit("restrictive"))
async def add_produto_to_comanda(
    request: Request,
    comanda_id: int,
    produto_data: ComandaProdutosCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user),
):
    result = await db.execute(select(ComandaDB).where(ComandaDB.id == comanda_id))
    comanda = result.scalar_one_or_none()
    if not comanda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
    if comanda.status != 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comanda precisa estar aberta")
    result = await db.execute(select(ProdutoDB).where(ProdutoDB.id_produto == produto_data.produto_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Produto não encontrado")
    result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == produto_data.funcionario_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Funcionário não encontrado")

    novo_item = ComandaProdutoDB(
        comanda_id=comanda_id,
        produto_id=produto_data.produto_id,
        funcionario_id=produto_data.funcionario_id,
        quantidade=produto_data.quantidade,
        valor_unitario=produto_data.valor_unitario,
    )
    db.add(novo_item)
    await db.commit()
    await db.refresh(novo_item)
    await AuditoriaService.registrar_acao_async(db=db, funcionario_id=current_user.id, acao="CREATE", recurso="COMANDA_PRODUTO", recurso_id=novo_item.id, dados_novos=novo_item, request=request)
    return novo_item


@router.get("/comanda/{id}/produtos", response_model=List[ComandaProdutosResponse], tags=["Comanda"], summary="Listar produtos da comanda")
@limiter.limit(get_rate_limit("moderate"))
async def get_comanda_produtos(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user),
):
    result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
    query = (
        select(ComandaProdutoDB, ProdutoDB, FuncionarioDB)
        .outerjoin(ProdutoDB, ProdutoDB.id_produto == ComandaProdutoDB.produto_id)
        .outerjoin(FuncionarioDB, FuncionarioDB.id == ComandaProdutoDB.funcionario_id)
        .where(ComandaProdutoDB.comanda_id == id)
    )
    result = await db.execute(query)
    rows = result.all()
    output = []
    for item, produto, funcionario in rows:
        output.append(
            ComandaProdutosResponse(
                id=item.id,
                comanda_id=item.comanda_id,
                funcionario_id=item.funcionario_id,
                funcionario=FuncionarioResponse(
                    id=funcionario.id,
                    nome=funcionario.nome,
                    matricula=funcionario.matricula,
                    cpf=funcionario.cpf,
                    telefone=funcionario.telefone,
                    grupo=funcionario.grupo,
                ) if funcionario else None,
                produto_id=item.produto_id,
                produto=ProdutoResponse(
                    id_produto=produto.id_produto,
                    nome=produto.nome,
                    preco=produto.preco,
                    foto=produto.foto,
                    descricao=produto.descricao,
                ) if produto else None,
                quantidade=item.quantidade,
                valor_unitario=float(item.valor_unitario),
            )
        )
    return output


@router.put("/comanda/produto/{id}", response_model=ComandaProdutosResponse, tags=["Comanda"], summary="Atualizar item da comanda")
@limiter.limit(get_rate_limit("restrictive"))
async def update_comanda_produto(
    request: Request,
    id: int,
    produto_data: ComandaProdutosUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.id == id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto da comanda não encontrado")
    if produto_data.quantidade is not None and produto_data.quantidade <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantidade deve ser maior que zero")
    if produto_data.valor_unitario is not None and produto_data.valor_unitario <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valor unitário deve ser maior que zero")

    dados_antigos = item.__dict__.copy()
    update_data = produto_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    await AuditoriaService.registrar_acao_async(db=db, funcionario_id=current_user.id, acao="UPDATE", recurso="COMANDA_PRODUTO", recurso_id=id, dados_antigos=dados_antigos, dados_novos=item, request=request)
    return item


@router.delete("/comanda/produto/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Comanda"], summary="Remover item da comanda")
@limiter.limit(get_rate_limit("critical"))
async def remove_produto_from_comanda(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.id == id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto da comanda não encontrado")
    await db.delete(item)
    await db.commit()
    await AuditoriaService.registrar_acao_async(db=db, funcionario_id=current_user.id, acao="DELETE", recurso="COMANDA_PRODUTO", recurso_id=id, dados_antigos=item, request=request)
    return None
