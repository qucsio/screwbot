from aiogram import Router

from bot.config import get_settings
from bot.handlers import start, menu, moderation, beats, orders, profile, admin, debug


def setup_routers() -> Router:
    router = Router()
    if get_settings().debug_ids:
        router.include_router(debug.router)  # первым: перехватывает сообщения в группах
    router.include_router(admin.router)     # админ — раньше клиентских, ловит /admin и свои FSM
    router.include_router(start.router)
    router.include_router(moderation.router)
    router.include_router(beats.router)
    router.include_router(orders.router)
    router.include_router(profile.router)
    router.include_router(menu.router)  # menu — последним: ловит остальной текст
    return router
