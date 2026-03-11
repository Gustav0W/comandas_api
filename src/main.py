from fastapi import FastAPI
from src.settings import HOST, PORT, RELOAD
import uvicorn

from src.routers import FuncionarioRouter, ClienteRouter, ProdutoRouter

app = FastAPI()

# rota padrão
@app.get("/", tags=["Root"], status_code=200)
def root():
    return {"detail":"API Pastelaria", "Swagger UI": "http://127.0.0.1:8000/docs", "ReDoc": "http://127.0.0.1:8000/redoc" }

app.include_router(FuncionarioRouter.router)
app.include_router(ClienteRouter.router)
app.include_router(ProdutoRouter.router)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=int(PORT), reload=RELOAD)