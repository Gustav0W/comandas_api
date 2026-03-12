from fastapi import APIRouter
from src.domain.schemas.ClienteSchema import ClienteCreate, ClienteUpdate, ClienteResponse
router = APIRouter()

@router.get("/cliente/", tags=["Cliente"], status_code=200)
def get_cliente():
    return {"msg": "cliente get todos executado"}

@router.get("/cliente/{id}", tags=["Cliente"], status_code=200)
def get_cliente(id: int):
    return {"msg": "cliente get um executado"}

@router.post("/cliente/", tags=["Cliente"], status_code=200)
def post_cliente(corpo: Cliente):
    return {"msg": "cliente post executado", "nome": corpo.nome, "cpf": corpo.cpf, "telefone": corpo.telefone}

@router.put("/cliente/{id}", tags=["Cliente"], status_code=200)
def put_cliente(id: int, corpo: Cliente):
    return {"msg": "cliente put executado", "id":id, "nome": corpo.nome, "cpf": corpo.cpf, "telefone": corpo.telefone}

@router.delete("/cliente/{id}", tags=["Cliente"], status_code=200)
def delete_cliente(id: int):
    return {"msg": "cliente delete executado", "id":id}
#Gustavo Vieira Walter