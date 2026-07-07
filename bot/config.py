"""Секреты и инфраструктура — читаются из .env (не коммитятся).

Здесь ТОЛЬКО то, что секретно или зависит от хоста: токен бота, креды БД,
адрес Redis, прокси. Стабильные не-секретные id — в bot/app_config.py.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Секрет
    bot_token: str = Field(alias="BOT_TOKEN")

    # Инфраструктура / хост-специфично
    telegram_proxy: str = Field(default="", alias="TELEGRAM_PROXY")
    debug_ids: bool = Field(default=False, alias="DEBUG_IDS")

    # Postgres
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="screw", alias="POSTGRES_DB")
    postgres_user: str = Field(default="screw", alias="POSTGRES_USER")
    postgres_password: str = Field(default="screw", alias="POSTGRES_PASSWORD")

    # Redis
    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
