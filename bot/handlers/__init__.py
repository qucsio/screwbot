from aiogram import F, Router
from aiogram.enums import ChatType

from bot.config import get_settings
from bot.handlers import (
    start, menu, moderation, beats, orders, order_flow, portfolio, profile,
    admin, reviews, debug, errors,
)
from bot.services import forms


def setup_routers() -> Router:
    router = Router()
    router.include_router(errors.router)        # ответ пользователю при необработанной ошибке
    if get_settings().debug_ids:
        router.include_router(debug.router)  # первым: перехватывает сообщения в группах

    # Сообщения обрабатываем только в личке: в группе тендеров бот не должен
    # регистрировать и показывать меню. Кнопки (callback) работают везде —
    # «Взять заказ» нажимают именно в группе.
    private = Router()
    private.message.filter(F.chat.type == ChatType.PRIVATE)
    private.include_router(menu.nav_router)    # кнопки меню прерывают любую форму
    private.include_router(forms.router)       # /cancel и «Отмена» — раньше форм и админки
    private.include_router(admin.router)       # админ — раньше клиентских, ловит /admin и свои FSM
    private.include_router(start.router)
    private.include_router(moderation.router)
    private.include_router(beats.router)
    private.include_router(orders.router)
    private.include_router(order_flow.router)
    private.include_router(portfolio.router)
    private.include_router(profile.router)
    private.include_router(reviews.router)
    private.include_router(menu.router)  # последним: остальной текст и устаревшие кнопки
    router.include_router(private)
    return router
