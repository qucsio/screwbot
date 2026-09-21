"""Приём файлов от пользователя и отправка их обратно правильным методом.

Telegram различает тип файла по file_id: голосовое или документ нельзя отправить
через send_audio, картинку-файл — через send_photo. Поэтому тип определяем при
приёме, храним рядом с file_id и отправляем тем же методом.
"""
from aiogram import Bot
from aiogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    ReplyParameters,
)

from bot.db.models import MediaType, Work
from bot.services.notify import safe_send

# Вложений к одному ТЗ: больше — это флуд в топике и упор в лимит Telegram
# (~20 сообщений в минуту на группу).
MAX_ATTACHMENTS = 10


def detect_media(message: Message) -> tuple[MediaType, str] | None:
    """Элемент портфолио: фото, видео, аудиофайл или документ.

    Голосовые и кружки не подходят: их нельзя показать в карусели портфолио.
    """
    if message.photo:
        return MediaType.photo, message.photo[-1].file_id
    if message.video:
        return MediaType.video, message.video.file_id
    if message.audio:
        return MediaType.audio, message.audio.file_id
    if message.document:
        return MediaType.document, message.document.file_id
    return None


def detect_attachment(message: Message) -> dict | None:
    """Вложение к ТЗ — всё, что можно переслать исполнителю, включая голосовые и кружки."""
    if message.photo:
        kind, file_id = "photo", message.photo[-1].file_id
    elif message.video:
        kind, file_id = "video", message.video.file_id
    elif message.audio:
        kind, file_id = "audio", message.audio.file_id
    elif message.voice:
        kind, file_id = "voice", message.voice.file_id
    elif message.video_note:
        kind, file_id = "video_note", message.video_note.file_id
    elif message.document:
        kind, file_id = "document", message.document.file_id
    else:
        return None
    return {"type": kind, "file_id": file_id}


def detect_audio(message: Message) -> tuple[str, str] | None:
    """Сниппет бита: аудиофайл или аудио, присланное документом (так обычно приходит WAV).

    Возвращает (вид, file_id); вид нужен, чтобы потом отправить файл тем же методом.
    Голосовые и не-аудио документы — None.
    """
    if message.audio:
        return "audio", message.audio.file_id
    doc = message.document
    if doc and (doc.mime_type or "").startswith("audio/"):
        return "document", doc.file_id
    return None


async def send_work_audio(message: Message, work: Work) -> None:
    """«Слушать»: аудио, присланное документом, уходит документом (send_audio его не примет)."""
    if work.audio_kind == "document":
        await message.answer_document(work.audio_file_id)
    else:
        await message.answer_audio(work.audio_file_id, title=work.title)


async def send_attachments(
    bot: Bot,
    chat_id: int,
    attachments: list[dict],
    thread_id: int | None = None,
    reply_to: int | None = None,
) -> None:
    """Вложения ТЗ альбомами, а не десятком отдельных сообщений.

    Правила Telegram: фото и видео можно смешивать в одном альбоме, документы и
    аудио — только с однотипными; голосовые и кружки альбомом не отправить.
    reply_to привязывает вложения к посту-тендеру, чтобы в топике они не
    перемешивались с чужими заказами. Ошибки не роняют обработчик.
    """
    common: dict = {}
    if thread_id:
        common["message_thread_id"] = thread_id
    if reply_to:
        common["reply_parameters"] = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True)

    albums: dict[str, list] = {"visual": [], "document": [], "audio": []}
    singles: list[tuple[str, str]] = []
    for att in attachments:
        kind, file_id = att.get("type"), att.get("file_id")
        if kind == "photo":
            albums["visual"].append(InputMediaPhoto(media=file_id))
        elif kind == "video":
            albums["visual"].append(InputMediaVideo(media=file_id))
        elif kind == "audio":
            albums["audio"].append(InputMediaAudio(media=file_id))
        elif kind in ("voice", "video_note"):
            singles.append((kind, file_id))
        else:
            albums["document"].append(InputMediaDocument(media=file_id))

    for media in albums.values():
        for i in range(0, len(media), 10):
            chunk = media[i:i + 10]
            if len(chunk) > 1:
                await safe_send(bot.send_media_group(chat_id, chunk, **common))
            else:
                await _send_one(bot, chat_id, chunk[0], common)
    for kind, file_id in singles:
        if kind == "voice":
            await safe_send(bot.send_voice(chat_id, file_id, **common))
        else:
            await safe_send(bot.send_video_note(chat_id, file_id, **common))


async def _send_one(bot: Bot, chat_id: int, media, common: dict) -> None:
    """Альбом из одного элемента Telegram не принимает — шлём обычным сообщением."""
    if isinstance(media, InputMediaPhoto):
        await safe_send(bot.send_photo(chat_id, media.media, **common))
    elif isinstance(media, InputMediaVideo):
        await safe_send(bot.send_video(chat_id, media.media, **common))
    elif isinstance(media, InputMediaAudio):
        await safe_send(bot.send_audio(chat_id, media.media, **common))
    else:
        await safe_send(bot.send_document(chat_id, media.media, **common))
