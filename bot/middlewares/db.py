from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy import select

from bot.db.models import User
from bot.db.session import session_factory


class DBMiddleware(BaseMiddleware):
    """Открывает сессию на апдейт и подкладывает объект User из БД (если есть)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with session_factory() as session:
            data["session"] = session
            tg_user: TgUser | None = data.get("event_from_user")
            if tg_user is not None:
                result = await session.execute(
                    select(User).where(User.tg_id == tg_user.id)
                )
                data["user"] = result.scalar_one_or_none()
            return await handler(event, data)
