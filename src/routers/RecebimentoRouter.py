import base64
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.schemas.AuthSchema import FuncionarioAuth
from domain.schemas.RecebimentoSchema import (
    ComandaDetalheProdutoItem,
    ComandaDetalheResponse,
    ComprovanteResponse,
    DashboardComandaItem,
    RecebimentoCompletoCreate,
    RecebimentoResponse,
    RecebimentoUpdate,
)
from infra.database import get_async_db
from infra.dependencies import get_current_active_user, require_group
from infra.orm.ClienteModel import ClienteDB
from infra.orm.ComandaModel import ComandaDB, ComandaProdutoDB
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.orm.ProdutoModel import ProdutoDB
from infra.orm.RecebimentoModel import RecebimentoComandaDB, RecebimentoDB
from infra.rate_limit import get_rate_limit, limiter
from services.AuditoriaService import AuditoriaService

router = APIRouter()


def _foto_to_base64(foto) -> Optional[str]:
    if foto is None:
        return None
    if isinstance(foto, str):
        return foto
    if isinstance(foto, memoryview):
        foto = foto.tobytes()
    try:
        return base64.b64encode(foto).decode("utf-8")
    except Exception:
        return None


async def _calcular_total_comanda(db: AsyncSession, comanda_id: int) -> float:
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(ComandaProdutoDB.quantidade * ComandaProdutoDB.valor_unitario),
                0,
            )
        ).where(ComandaProdutoDB.comanda_id == comanda_id)
    )
    return float(result.scalar() or 0)


async def _contar_itens_comanda(db: AsyncSession, comanda_id: int) -> int:
    result = await db.execute(
        select(func.count(ComandaProdutoDB.id)).where(
            ComandaProdutoDB.comanda_id == comanda_id
        )
    )
    return int(result.scalar() or 0)


async def _build_comanda_detalhe(
    db: AsyncSession, comanda: ComandaDB, cliente: Optional[ClienteDB]
) -> ComandaDetalheResponse:
    query = (
        select(ComandaProdutoDB, ProdutoDB)
        .outerjoin(ProdutoDB, ProdutoDB.id_produto == ComandaProdutoDB.produto_id)
        .where(ComandaProdutoDB.comanda_id == comanda.id)
    )
    result = await db.execute(query)
    itens = []
    for item, produto in result.all():
        valor_unitario = float(item.valor_unitario)
        quantidade = item.quantidade
        itens.append(
            ComandaDetalheProdutoItem(
                id=item.id,
                produto_id=item.produto_id,
                produto_nome=produto.nome if produto else f"Produto #{item.produto_id}",
                produto_foto=_foto_to_base64(produto.foto) if produto else None,
                quantidade=quantidade,
                valor_unitario=valor_unitario,
                valor_total=round(valor_unitario * quantidade, 2),
            )
        )
    valor_total = round(sum(i.valor_total for i in itens), 2)
    return ComandaDetalheResponse(
        id=comanda.id,
        comanda=comanda.comanda,
        cliente_id=comanda.cliente_id,
        cliente_nome=cliente.nome if cliente else None,
        itens=itens,
        valor_total=valor_total,
    )


async def _get_comanda_ids_recebimento(db: AsyncSession, recebimento_id: int) -> List[int]:
    result = await db.execute(
        select(RecebimentoComandaDB.comanda_id).where(
            RecebimentoComandaDB.recebimento_id == recebimento_id
        )
    )
    return [row[0] for row in result.all()]


async def _build_recebimento_response(
    db: AsyncSession, recebimento: RecebimentoDB
) -> RecebimentoResponse:
    result = await db.execute(
        select(FuncionarioDB).where(FuncionarioDB.id == recebimento.funcionario_id)
    )
    funcionario = result.scalar_one_or_none()
    comanda_ids = await _get_comanda_ids_recebimento(db, recebimento.id)
    return RecebimentoResponse(
        id=recebimento.id,
        data_hora=recebimento.data_hora,
        funcionario_id=recebimento.funcionario_id,
        funcionario_nome=funcionario.nome if funcionario else None,
        desconto=float(recebimento.desconto),
        acrescimo=float(recebimento.acrescimo),
        valor_subtotal=float(recebimento.valor_subtotal),
        valor_total=float(recebimento.valor_total),
        cliente_id=recebimento.cliente_id,
        comanda_ids=comanda_ids,
    )


@router.get(
    "/recebimento/dashboard",
    response_model=List[DashboardComandaItem],
    tags=["Recebimento"],
    summary="Dashboard de comandas abertas",
)
@limiter.limit(get_rate_limit("moderate"))
async def dashboard_comandas(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    query = (
        select(ComandaDB, ClienteDB)
        .outerjoin(ClienteDB, ClienteDB.id_cliente == ComandaDB.cliente_id)
        .where(ComandaDB.status == 0)
        .order_by(ComandaDB.comanda)
    )
    result = await db.execute(query)
    dashboard = []
    for comanda, cliente in result.all():
        dashboard.append(
            DashboardComandaItem(
                id=comanda.id,
                comanda=comanda.comanda,
                data_hora=comanda.data_hora,
                cliente_id=comanda.cliente_id,
                cliente_nome=cliente.nome if cliente else None,
                quantidade_itens=await _contar_itens_comanda(db, comanda.id),
                valor_total=await _calcular_total_comanda(db, comanda.id),
            )
        )
    return dashboard


@router.get(
    "/recebimento/comandas/detalhe/{ids}",
    response_model=List[ComandaDetalheResponse],
    tags=["Recebimento"],
    summary="Detalhar comandas para conferência no caixa",
)
@limiter.limit(get_rate_limit("moderate"))
async def detalhar_comandas(
    request: Request,
    ids: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    try:
        comanda_ids = [int(part.strip()) for part in ids.split(",") if part.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IDs de comanda inválidos",
        ) from exc

    if not comanda_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe ao menos uma comanda",
        )

    detalhes = []
    for comanda_id in comanda_ids:
        result = await db.execute(
            select(ComandaDB, ClienteDB)
            .outerjoin(ClienteDB, ClienteDB.id_cliente == ComandaDB.cliente_id)
            .where(ComandaDB.id == comanda_id)
        )
        row = result.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comanda {comanda_id} não encontrada",
            )
        comanda, cliente = row
        if comanda.status != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Comanda {comanda.comanda} não está aberta",
            )
        detalhes.append(await _build_comanda_detalhe(db, comanda, cliente))
    return detalhes


@router.post(
    "/recebimento/completo",
    response_model=RecebimentoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Recebimento"],
    summary="Processar recebimento completo",
)
@limiter.limit(get_rate_limit("critical"))
async def processar_recebimento(
    request: Request,
    payload: RecebimentoCompletoCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    comanda_ids = list(dict.fromkeys(payload.comanda_ids))
    subtotal = Decimal("0")

    if payload.cliente_id is not None:
        result = await db.execute(
            select(ClienteDB).where(ClienteDB.id_cliente == payload.cliente_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cliente não encontrado",
            )

    comandas = []
    for comanda_id in comanda_ids:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == comanda_id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comanda {comanda_id} não encontrada",
            )
        if comanda.status != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Comanda {comanda.comanda} não está aberta",
            )
        item_count = await _contar_itens_comanda(db, comanda_id)
        if item_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Comanda {comanda.comanda} não possui itens",
            )
        total = Decimal(str(await _calcular_total_comanda(db, comanda_id)))
        subtotal += total
        comandas.append(comanda)

    desconto = Decimal(str(payload.desconto))
    acrescimo = Decimal(str(payload.acrescimo))
    if desconto > subtotal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Desconto não pode ser maior que o subtotal",
        )

    valor_total = subtotal - desconto + acrescimo
    if valor_total < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valor total final inválido",
        )

    recebimento = RecebimentoDB(
        data_hora=datetime.now(),
        funcionario_id=current_user.id,
        desconto=desconto,
        acrescimo=acrescimo,
        valor_subtotal=subtotal,
        valor_total=valor_total,
        cliente_id=payload.cliente_id,
    )
    db.add(recebimento)
    await db.flush()

    for comanda in comandas:
        db.add(
            RecebimentoComandaDB(
                recebimento_id=recebimento.id,
                comanda_id=comanda.id,
            )
        )
        comanda.status = 1
        comanda.funcionario_id = current_user.id
        if payload.cliente_id is not None:
            comanda.cliente_id = payload.cliente_id

    await db.commit()
    await db.refresh(recebimento)
    await AuditoriaService.registrar_acao_async(
        db=db,
        funcionario_id=current_user.id,
        acao="CREATE",
        recurso="RECEBIMENTO",
        recurso_id=recebimento.id,
        dados_novos=recebimento,
        request=request,
    )
    return await _build_recebimento_response(db, recebimento)


@router.get(
    "/recebimento/comprovante/{id}",
    response_model=ComprovanteResponse,
    tags=["Recebimento"],
    summary="Gerar comprovante de recebimento",
)
@limiter.limit(get_rate_limit("moderate"))
async def comprovante_recebimento(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
    recebimento = result.scalar_one_or_none()
    if not recebimento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recebimento não encontrado",
        )

    result = await db.execute(
        select(FuncionarioDB).where(FuncionarioDB.id == recebimento.funcionario_id)
    )
    funcionario = result.scalar_one_or_none()

    cliente_nome = None
    if recebimento.cliente_id:
        result = await db.execute(
            select(ClienteDB).where(ClienteDB.id_cliente == recebimento.cliente_id)
        )
        cliente = result.scalar_one_or_none()
        cliente_nome = cliente.nome if cliente else None

    comanda_ids = await _get_comanda_ids_recebimento(db, recebimento.id)
    comandas_detalhe = []
    for comanda_id in comanda_ids:
        result = await db.execute(
            select(ComandaDB, ClienteDB)
            .outerjoin(ClienteDB, ClienteDB.id_cliente == ComandaDB.cliente_id)
            .where(ComandaDB.id == comanda_id)
        )
        row = result.first()
        if row:
            comanda, cliente = row
            comandas_detalhe.append(await _build_comanda_detalhe(db, comanda, cliente))

    return ComprovanteResponse(
        id=recebimento.id,
        data_hora=recebimento.data_hora,
        funcionario_id=recebimento.funcionario_id,
        funcionario_nome=funcionario.nome if funcionario else "—",
        desconto=float(recebimento.desconto),
        acrescimo=float(recebimento.acrescimo),
        valor_subtotal=float(recebimento.valor_subtotal),
        valor_total=float(recebimento.valor_total),
        cliente_id=recebimento.cliente_id,
        cliente_nome=cliente_nome,
        comandas=comandas_detalhe,
    )


@router.get(
    "/recebimento/",
    response_model=List[RecebimentoResponse],
    tags=["Recebimento"],
    summary="Listar recebimentos",
)
@limiter.limit(get_rate_limit("moderate"))
async def listar_recebimentos(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    result = await db.execute(
        select(RecebimentoDB).order_by(RecebimentoDB.data_hora.desc())
    )
    recebimentos = result.scalars().all()
    return [await _build_recebimento_response(db, r) for r in recebimentos]


@router.get(
    "/recebimento/{id}",
    response_model=RecebimentoResponse,
    tags=["Recebimento"],
    summary="Buscar recebimento por ID",
)
@limiter.limit(get_rate_limit("moderate"))
async def buscar_recebimento(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
    recebimento = result.scalar_one_or_none()
    if not recebimento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recebimento não encontrado",
        )
    return await _build_recebimento_response(db, recebimento)


@router.put(
    "/recebimento/{id}",
    response_model=RecebimentoResponse,
    tags=["Recebimento"],
    summary="Atualizar recebimento (desconto/acréscimo)",
)
@limiter.limit(get_rate_limit("restrictive"))
async def atualizar_recebimento(
    request: Request,
    id: int,
    payload: RecebimentoUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
    recebimento = result.scalar_one_or_none()
    if not recebimento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recebimento não encontrado",
        )

    dados_antigos = recebimento.__dict__.copy()
    update_data = payload.model_dump(exclude_unset=True)
    desconto = Decimal(str(update_data.get("desconto", recebimento.desconto)))
    acrescimo = Decimal(str(update_data.get("acrescimo", recebimento.acrescimo)))
    subtotal = Decimal(str(recebimento.valor_subtotal))

    if desconto > subtotal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Desconto não pode ser maior que o subtotal",
        )

    valor_total = subtotal - desconto + acrescimo
    if valor_total < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valor total final inválido",
        )

    recebimento.desconto = desconto
    recebimento.acrescimo = acrescimo
    recebimento.valor_total = valor_total
    await db.commit()
    await db.refresh(recebimento)
    await AuditoriaService.registrar_acao_async(
        db=db,
        funcionario_id=current_user.id,
        acao="UPDATE",
        recurso="RECEBIMENTO",
        recurso_id=id,
        dados_antigos=dados_antigos,
        dados_novos=recebimento,
        request=request,
    )
    return await _build_recebimento_response(db, recebimento)


@router.delete(
    "/recebimento/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Recebimento"],
    summary="Excluir recebimento e reabrir comandas",
)
@limiter.limit(get_rate_limit("critical"))
async def excluir_recebimento(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
    recebimento = result.scalar_one_or_none()
    if not recebimento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recebimento não encontrado",
        )

    dados_antigos = recebimento.__dict__.copy()
    comanda_ids = await _get_comanda_ids_recebimento(db, recebimento.id)

    for comanda_id in comanda_ids:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == comanda_id))
        comanda = result.scalar_one_or_none()
        if comanda:
            comanda.status = 0

    result = await db.execute(
        select(RecebimentoComandaDB).where(RecebimentoComandaDB.recebimento_id == id)
    )
    for link in result.scalars().all():
        await db.delete(link)

    await db.delete(recebimento)
    await db.commit()
    await AuditoriaService.registrar_acao_async(
        db=db,
        funcionario_id=current_user.id,
        acao="DELETE",
        recurso="RECEBIMENTO",
        recurso_id=id,
        dados_antigos=dados_antigos,
        request=request,
    )
    return None
