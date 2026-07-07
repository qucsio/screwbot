"""Единый реестр категорий/услуг — ЕДИНСТВЕННЫЙ источник правды.

Чтобы добавить новую услугу:
  1. добавь один CategoryDef в CATEGORIES ниже;
  2. если это услуга «на заказ» (kind="custom") — перечисли поля формы ТЗ;
  3. если нужен топик-тендер — заведи топик и впиши его id в thread_id.
Больше ничего править не нужно: меню, сид, формы и роутинг строятся отсюда.

thread_id — id топика в супергруппе (bot/app_config.GROUP_ID). Не секрет,
стабилен между запусками, поэтому хранится прямо здесь.
"""
from dataclasses import dataclass

from bot.db.models import Lang


@dataclass(frozen=True)
class Field:
    """Шаг формы ТЗ (свободный текст)."""
    key: str
    ru: str          # вопрос на русском
    en: str          # вопрос на английском
    label: str       # короткая подпись в карточке заказа

    def prompt(self, lang: Lang) -> str:
        return self.en if lang == Lang.en else self.ru


@dataclass(frozen=True)
class CategoryDef:
    code: str
    ru: str                       # название кнопки/категории (RU)
    en: str                       # (EN)
    kind: str                     # "catalog" (готовые работы) | "custom" (заказ) | "static"
    thread_id: int = 0            # id топика-тендера в супергруппе (0 = не задан)
    fields: tuple[Field, ...] = ()  # шаги ТЗ для kind="custom"

    def title(self, lang: Lang) -> str:
        return self.en if lang == Lang.en else self.ru


# Порядок в списке = порядок кнопок в главном меню.
CATEGORIES: list[CategoryDef] = [
    CategoryDef("ready_beats", "🎧 Готовые аранжировки и биты", "🎧 Ready arrangements & beats", "catalog"),
    CategoryDef(
        "custom_beats", "🎶 Аранжировки и биты на заказ", "🎶 Custom arrangements & beats", "custom",
        thread_id=0,  # ← id топика-тендера в супергруппе
        fields=(
            Field("genre_style", "Жанр/стиль:", "Genre/style:", "Жанр/стиль"),
            Field("bpm", "BPM:", "BPM:", "BPM"),
            Field("mood", "Настроение/вайб:", "Mood/vibe:", "Настроение"),
            Field("references", "Референсы (ссылки):", "References (links):", "Референсы"),
            Field("format", "Формат (WAV, MP3, STEMS):", "Format (WAV, MP3, STEMS):", "Формат"),
            Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
        ),
    ),
    CategoryDef(
        "mixing", "🎚️ Mixing", "🎚️ Mixing", "custom",
        thread_id=0,  # ← id топика-тендера в супергруппе
        fields=(
            Field("tracks_count", "Количество дорожек:", "Number of tracks:", "Дорожек"),
            Field("ref_sound", "Референс звучания:", "Reference sound:", "Референс"),
            Field("special", "Особые пожелания:", "Special requests:", "Пожелания"),
            Field("mastering", "Нужен мастеринг (Да/Нет):", "Mastering needed (Yes/No):", "Мастеринг"),
            Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
        ),
    ),
    CategoryDef(
        "ghostwriting", "✍️ Текст (призрак-писатель)", "✍️ Lyrics (ghostwriter)", "custom",
        thread_id=0,  # ← id топика-тендера в супергруппе
        fields=(
            Field("genre_style", "Жанр/стиль:", "Genre/style:", "Жанр/стиль"),
            Field("verses", "Кол-во куплетов/припевов:", "Verses/choruses count:", "Куплеты"),
            Field("theme", "Тематика/концепт:", "Theme/concept:", "Тема"),
            Field("artist_example", "Пример исполнителя:", "Artist example:", "Пример"),
            Field("lang", "Язык текста:", "Lyrics language:", "Язык"),
            Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
        ),
    ),
    CategoryDef(
        "visual", "🖼️ Визуал", "🖼️ Visuals", "custom",
        thread_id=0,  # ← id топика-тендера в супергруппе
        fields=(
            Field("type", "Тип (обложка, баннер, арт, 3D):", "Type (cover, banner, art, 3D):", "Тип"),
            Field("palette", "Цветовая палитра/стиль:", "Color palette/style:", "Палитра"),
            Field("elements", "Описание элементов:", "Elements description:", "Элементы"),
            Field("references", "Референсы (ссылки):", "References (links):", "Референсы"),
            Field("format", "Формат (1:1, 16:9):", "Format (1:1, 16:9):", "Формат"),
            Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
        ),
    ),
    CategoryDef(
        "videographer", "🎥 Видеограф", "🎥 Videographer", "custom",
        thread_id=0,  # ← id топика-тендера в супергруппе
        fields=(
            Field("video_type", "Тип видео:", "Video type:", "Тип видео"),
            Field("idea", "Идея/сценарий:", "Idea/script:", "Идея"),
            Field("location", "Локация:", "Location:", "Локация"),
            Field("dates", "Сроки съёмки:", "Shooting dates:", "Сроки"),
            Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
        ),
    ),
    CategoryDef(
        "editing", "🎬 Монтаж", "🎬 Video editing", "custom",
        thread_id=0,  # ← id топика-тендера в супергруппе
        fields=(
            Field("video_type", "Тип видео:", "Video type:", "Тип видео"),
            Field("duration", "Хронометраж:", "Duration:", "Хронометраж"),
            Field("sources", "Ссылка на исходники:", "Source files link:", "Исходники"),
            Field("style_example", "Пример стиля:", "Style example:", "Стиль"),
            Field("format", "Формат видео:", "Video format:", "Формат"),
            Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
        ),
    ),
    CategoryDef(
        "photo", "📸 Фото-сессия (Москва)", "📸 Photoshoot (Moscow)", "custom",
        thread_id=0,  # ← id топика-тендера в супергруппе
        fields=(
            Field("city", "Город (строго Москва):", "City (Moscow only):", "Город"),
            Field("style", "Стиль съёмки:", "Shooting style:", "Стиль"),
            Field("looks", "Количество образов:", "Number of looks:", "Образы"),
            Field("dates", "Сроки:", "Dates:", "Сроки"),
            Field("examples", "Примеры:", "Examples:", "Примеры"),
            Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
        ),
    ),
]

_BY_CODE = {c.code: c for c in CATEGORIES}


def by_code(code: str) -> CategoryDef | None:
    return _BY_CODE.get(code)


def custom_categories() -> list[CategoryDef]:
    return [c for c in CATEGORIES if c.kind == "custom"]
