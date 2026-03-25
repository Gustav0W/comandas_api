from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.domain.schemas.ProdutoSchema import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse
)
from src.infra.orm.ProdutoModel import ProdutoDB
from src.infra.database import get_db

router = APIRouter()

@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
async def get_produto(db: Session = Depends(get_db)):
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
async def get_produto_id(id_produto: int, db: Session = Depends(get_db)):
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
async def post_produto(produto_data: ProdutoCreate, db: Session = Depends(get_db)):
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
        return novo_produto
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar produto: {str(e)}"
        )

@router.put("/produto/{id_produto}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
async def put_produto(id_produto: int, produto_data: ProdutoUpdate, db: Session = Depends(get_db)):
    """Atualiza um produto existente"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id_produto == id_produto).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        for field, value in produto_data.model_dump(exclude_unset=True).items():
            setattr(produto, field, value)
        db.commit()
        db.refresh(produto)
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
async def delete_produto(id_produto: int, db: Session = Depends(get_db)):
    """Remove um produto pelo ID"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id_produto == id_produto).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
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
