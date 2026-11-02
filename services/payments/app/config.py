from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente; sem valores por omissão."""

    database_url: str
    jwt_secret: str
    jwt_algorithm: str
    nats_url: str
    orders_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
