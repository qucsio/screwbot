from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Creator, CreatorStatus, Lang, User
from bot.filters import IsAdmin
from bot.keyboards.common import main_menu
from bot.locales import t

router = Router()
# Кнопки модерации видит только админ, но callback_data можно подделать
# (userbot шлёт любые данные) — поэтому проверяем, кто нажал.
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data.startswith("modcreator:"))
async def moderate_creator(call: CallbackQuery, session: AsyncSession, bot: Bot):
    _, action, creator_id_raw = call.data.split(":")
    creator = await session.get(Creator, int(creator_id_raw))
    if creator is None:
        await call.answer("not found", show_alert=True)
        return

    creator_user = await session.get(User, creator.user_id)

    if action == "approve":
        creator.status = CreatorStatus.approved
        admin_msg = t("mod_approved_admin", Lang.ru)
        notify = t("creator_approved_notify", creator_user.lang)
    else:
        creator.status = CreatorStatus.blocked
        admin_msg = t("mod_rejected_admin", Lang.ru)
        notify = t("creator_rejected_notify", creator_user.lang)

    await session.commit()

    try:
        markup = main_menu(creator_user.lang, CreatorStatus.approved) if action == "approve" else None
        await bot.send_message(creator_user.tg_id, notify, reply_markup=markup)
    except Exception:
        pass

    # html_text, а не text: иначе «<» из заявки ломает правку, а жирный шрифт пропадает.
    await call.message.edit_text(f"{call.message.html_text}\n\n— {admin_msg}")
    await call.answer(admin_msg)
