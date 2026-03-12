from fastapi import APIRouter
from src.domain.schemas.ProdutoSchema import ProdutoCreate, ProdutoUpdate, ProdutoResponse

router = APIRouter()

@router.get("/produto/", tags=["Produto"], status_code=200)
def get_produto():
    return {"msg": "produto get todos executado"}

@router.get("/produto/{id}", tags=["Produto"], status_code=200)
def get_produto_id(id: int):
    return {"msg": "produto get um executado"}

@router.post("/produto/", tags=["Produto"], status_code=200)
def post_produto(corpo: Produto):
    return {"msg": "produto post executado", "nome": corpo.nome, "preco": corpo.preco, "descricao": corpo.descricao}

@router.put("/produto/{id}", tags=["Produto"], status_code=200)
def put_produto(id: int, corpo: Produto):
    return {"msg": "produto put executado", "id": id, "nome": corpo.nome, "preco": corpo.preco, "descricao": corpo.descricao}

@router.delete("/produto/{id}", tags=["Produto"], status_code=200)
def delete_produto(id: int):
    return {"msg": "produto delete executado", "id": id}
#Gustavo Vieira Walter
