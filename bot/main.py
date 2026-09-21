import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats
from redis.asyncio import Redis

from bot.config import get_settings
from bot.handlers import setup_routers
from bot.middlewares.db import DBMiddleware
from bot.services.notify import safe_send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def _validate_config() -> None:
    """Предупреждает о незаполненном прикладном конфиге (не падает)."""
    from bot import app_config
    from bot.categories import custom_categories

    if not app_config.ADMIN_ID:
        logging.warning("app_config.ADMIN_ID не задан — админ-панель недоступна")
    if not app_config.GROUP_ID:
        logging.warning("app_config.GROUP_ID не задан — тендеры/модерация уйдут в личку админу")
    missing = [c.code for c in custom_categories() if not c.thread_id]
    if missing:
        logging.warning("Категории без thread_id (заказы недоступны): %s", ", ".join(missing))


async def _set_commands(bot: Bot) -> None:
    """Меню команд (кнопка «/» в личке с ботом)."""
    scope = BotCommandScopeAllPrivateChats()
    await safe_send(bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ], scope=scope))
    await safe_send(bot.set_my_commands([
        BotCommand(command="start", description="Main menu"),
        BotCommand(command="cancel", description="Cancel the current action"),
    ], scope=scope, language_code="en"))


async def main() -> None:
    settings = get_settings()
    _validate_config()

    session = None
    if settings.telegram_proxy:
        logging.info("Using proxy for Telegram API")
        session = AiohttpSession(proxy=settings.telegram_proxy)

    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    redis = Redis(host=settings.redis_host, port=settings.redis_port)
    storage = RedisStorage(redis)
    # Апдейты одного пользователя — строго по очереди. Без этого aiogram обрабатывает
    # их параллельно: из альбома фото во вложениях сохранялось одно (гонка за данные
    # формы), а двойное нажатие «Готово» создавало два заказа.
    dp = Dispatcher(storage=storage, events_isolation=storage.create_isolation())

    db_mw = DBMiddleware()
    dp.message.middleware(db_mw)
    dp.callback_query.middleware(db_mw)

    dp.include_router(setup_routers())

    logging.info("Bot started")
    await _set_commands(bot)
    # Не сбрасываем накопившиеся апдейты: сообщения, присланные, пока бот был
    # недоступен (перезапуск, падение), обрабатываются после старта, а не теряются.
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
