from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings

SERVICE_NAME = "orders"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Falha no arranque se faltar alguma variável de ambiente
    get_settings()
    yield


# O gateway publica /orders... em /api/orders... e os endpoints técnicos em /api/orders/...
# --root-path (Dockerfile) faz o Swagger encontrar o openapi.json; servers acerta o "Try it out".
app = FastAPI(
    title="Serviço de Encomendas",
    lifespan=lifespan,
    servers=[{"url": "/api"}],
    root_path_in_servers=False,
)


@app.get("/health", openapi_extra={"servers": [{"url": "/api/orders"}]})
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}
