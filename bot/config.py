from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    bot_token: str = Field(alias="BOT_TOKEN")
    admin_id: int = Field(alias="ADMIN_ID")
    group_id: int = Field(default=0, alias="GROUP_ID")
    moderation_thread_id: int = Field(default=0, alias="MODERATION_THREAD_ID")

    # thread_id топиков категорий читаются из окружения (<CODE>_THREAD_ID)
    # в bot/categories.py — здесь дублировать не нужно.

    # Реквизиты для оплаты (показываются клиенту)
    payment_details: str = Field(default="", alias="PAYMENT_DETAILS")

    # Reviews
    reviews_channel_id: int = Field(default=0, alias="REVIEWS_CHANNEL_ID")
    reviews_channel_url: str = Field(default="", alias="REVIEWS_CHANNEL_URL")

    # Прокси до Telegram API (если api.telegram.org заблокирован).
    # Форматы: socks5://user:pass@host:port  или  http://host:port. Пусто = напрямую.
    telegram_proxy: str = Field(default="", alias="TELEGRAM_PROXY")

    # Дебаг: бот отвечает chat.id / thread_id на сообщения в группах (для настройки).
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
