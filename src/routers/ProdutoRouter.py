
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from domain.schemas.ProdutoSchema import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse
)
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_db
from infra.dependencies import get_current_active_user, require_group
from infra.rate_limit import limiter, get_rate_limit
from services.AuditoriaService import AuditoriaService
from domain.schemas.AuthSchema import FuncionarioAuth

router = APIRouter()

# Schema público para produto (sem id e preco)
class ProdutoPublico(BaseModel):
    nome: str
    foto: str
    descricao: str

@router.get("/produto-publico/", response_model=List[ProdutoPublico], tags=["Produto"])
async def get_produto_publico(db: Session = Depends(get_db)):
    """Retorna todos os produtos (rota pública, sem id e valor)"""
    produtos = db.query(ProdutoDB).all()
    produtos_publicos = [
        ProdutoPublico(
            nome=produto.nome,
            foto=produto.foto,
            descricao=produto.descricao
        ) for produto in produtos
    ]
    return produtos_publicos

@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
async def get_produto(
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    """Retorna todos os produtos"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )

@router.get("/produto/{id_produto}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
async def get_produto_id(
    id_produto: int,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    """Retorna um produto específico pelo ID"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id_produto == id_produto).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        return produto
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produto: {str(e)}"
        )

@router.post("/produto/", response_model=ProdutoResponse, status_code=status.HTTP_201_CREATED, tags=["Produto"])
@limiter.limit(get_rate_limit("restrictive"))
async def post_produto(
    request: Request,
    produto_data: ProdutoCreate,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    """Cria um novo produto"""
    try:
        novo_produto = ProdutoDB(
            id_produto=None,
            nome=produto_data.nome,
            preco=produto_data.preco,
            foto=produto_data.foto,
            descricao=produto_data.descricao
        )
        db.add(novo_produto)
        db.commit()
        db.refresh(novo_produto)
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="PRODUTO",
            recurso_id=novo_produto.id_produto,
            dados_novos=novo_produto,
            request=request
        )
        return novo_produto
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar produto: {str(e)}"
        )

@router.put("/produto/{id_produto}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("restrictive"))
async def put_produto(
    request: Request,
    id_produto: int,
    produto_data: ProdutoUpdate,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    """Atualiza um produto existente"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id_produto == id_produto).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        dados_antigos = produto.__class__(**produto.__dict__)
        for field, value in produto_data.model_dump(exclude_unset=True).items():
            setattr(produto, field, value)
        db.commit()
        db.refresh(produto)
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="PRODUTO",
            recurso_id=produto.id_produto,
            dados_antigos=dados_antigos,
            dados_novos=produto,
            request=request
        )
        return produto
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar produto: {str(e)}"
        )

@router.delete("/produto/{id_produto}", tags=["Produto"], status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(get_rate_limit("critical"))
async def delete_produto(
    request: Request,
    id_produto: int,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    """Remove um produto pelo ID"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id_produto == id_produto).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="PRODUTO",
            recurso_id=produto.id_produto,
            dados_antigos=produto,
            request=request
        )
        db.delete(produto)
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao remover produto: {str(e)}"
        )
