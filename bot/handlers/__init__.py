from aiogram import Router

from bot.handlers import start, menu, moderation, beats


def setup_routers() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(moderation.router)
    router.include_router(beats.router)
    router.include_router(menu.router)  # menu — последним: ловит остальной текст
    return router
