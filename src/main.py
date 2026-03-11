from fastapi import FastAPI
from src.settings import HOST, PORT, RELOAD
import uvicorn

from src.routers import FuncionarioRouter, ClienteRouter

app = FastAPI()


app.include_router(FuncionarioRouter.router)
app.include_router(ClienteRouter.router)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=int(PORT), reload=RELOAD)