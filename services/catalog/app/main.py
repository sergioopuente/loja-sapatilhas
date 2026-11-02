from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings

SERVICE_NAME = "catalog"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Falha no arranque se faltar alguma variável de ambiente
    get_settings()
    yield


# O gateway publica todas as rotas em /api/catalog/... (--root-path no Dockerfile)
app = FastAPI(
    title="Serviço de Catálogo",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}
