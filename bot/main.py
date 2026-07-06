import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.config import get_settings
from bot.handlers import setup_routers
from bot.middlewares.db import DBMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def main() -> None:
    settings = get_settings()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    redis = Redis(host=settings.redis_host, port=settings.redis_port)
    storage = RedisStorage(redis)
    dp = Dispatcher(storage=storage)

    db_mw = DBMiddleware()
    dp.message.middleware(db_mw)
    dp.callback_query.middleware(db_mw)

    dp.include_router(setup_routers())

    logging.info("Bot started")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
