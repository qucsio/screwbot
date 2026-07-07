from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot import app_config


class IsAdmin(BaseFilter):
    """Пропускает только главного админа (ADMIN_ID)."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return user is not None and user.id == app_config.ADMIN_ID
