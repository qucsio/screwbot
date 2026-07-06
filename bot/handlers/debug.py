from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

router = Router()

# Работает только в группах/супергруппах, чтобы не мешать личным чатам.
router.message.filter(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})
)


@router.message()
async def show_ids(message: Message):
    await message.reply(
        f"chat.id = <code>{message.chat.id}</code>\n"
        f"thread_id = <code>{message.message_thread_id}</code>\n"
        f"type = {message.chat.type}\n"
        f"is_topic_message = {message.is_topic_message}"
    )
