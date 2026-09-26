from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import CreatorStatus, Lang
from bot.db.repositories import profiles as profiles_repo
from bot.filters import IsAdmin
from bot.keyboards.common import main_menu
from bot.locales import t
from bot.services.moderation import direction_title
from bot.services.notify import safe_send

router = Router()
# Кнопки модерации видит только админ, но callback_data можно подделать
# (userbot шлёт любые данные) — поэтому проверяем, кто нажал.
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data.startswith("modprofile:"))
async def moderate_profile(call: CallbackQuery, session: AsyncSession, bot: Bot):
    """Решение по одному направлению: остальные профили человека не трогаем."""
    _, action, profile_id_raw = call.data.split(":")
    bundle = await profiles_repo.profile_with_owner(session, int(profile_id_raw))
    if bundle is None:
        await call.answer("not found", show_alert=True)
        return
    profile, creator, creator_user = bundle

    if action == "approve":
        profile.status = CreatorStatus.approved
        admin_msg = t("mod_approved_admin", Lang.ru)
        notify_key = "profile_approved_notify"
    else:
        profile.status = CreatorStatus.blocked
        admin_msg = t("mod_rejected_admin", Lang.ru)
        notify_key = "profile_rejected_notify"
    await session.commit()

    lang = creator_user.lang
    status = await profiles_repo.menu_status(session, creator_user.id)
    await safe_send(bot.send_message(
        creator_user.tg_id,
        t(notify_key, lang, direction=direction_title(profile.direction, lang)),
        reply_markup=main_menu(lang, status),
    ))

    # html_text, а не text: иначе «<» из заявки ломает правку, а жирный шрифт пропадает.
    await call.message.edit_text(f"{call.message.html_text}\n\n— {admin_msg}")
    await call.answer(admin_msg)
