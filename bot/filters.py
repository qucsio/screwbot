from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings


class IsAdmin(BaseFilter):
    """Пропускает только главного админа (ADMIN_ID)."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return user is not None and user.id == get_settings().admin_id
