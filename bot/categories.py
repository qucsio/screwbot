"""Единый реестр категорий/услуг — ЕДИНСТВЕННЫЙ источник правды.

Чтобы добавить новую услугу:
  1. добавь один CategoryDef в CATEGORIES ниже;
  2. если это услуга «на заказ» (kind="custom") — перечисли поля формы ТЗ;
  3. если нужен топик-тендер — заведи топик и пропиши <CODE>_THREAD_ID в .env.
Больше ничего править не нужно: меню, сид, формы и роутинг строятся отсюда.
"""
import os
from dataclasses import dataclass, field

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
    fields: tuple[Field, ...] = ()  # шаги ТЗ для kind="custom"

    def title(self, lang: Lang) -> str:
        return self.en if lang == Lang.en else self.ru

    @property
    def env_thread_key(self) -> str:
        return f"{self.code.upper()}_THREAD_ID"

    @property
    def thread_id(self) -> int:
        """thread_id топика из окружения (0 = не задан)."""
        try:
            return int(os.getenv(self.env_thread_key, "0") or "0")
        except ValueError:
            return 0


# Порядок в списке = порядок кнопок в главном меню.
CATEGORIES: list[CategoryDef] = [
    CategoryDef("ready_beats", "🎧 Готовые аранжировки и биты", "🎧 Ready arrangements & beats", "catalog"),
    CategoryDef(
        "custom_beats", "🎶 Аранжировки и биты на заказ", "🎶 Custom arrangements & beats", "custom",
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
