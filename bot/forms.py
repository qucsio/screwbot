"""Декларативные формы ТЗ для услуг «на заказ».

Все поля — свободный текст (по ТЗ). Обход шагов — генерический FSM,
хранит ответы в Order.brief (JSONB): {field_key: value}.
"""
from dataclasses import dataclass

from bot.db.models import Lang


@dataclass(frozen=True)
class Field:
    key: str
    ru: str          # промпт (вопрос) на русском
    en: str          # промпт на английском
    label: str       # короткая подпись для карточки заказа

    def prompt(self, lang: Lang) -> str:
        return self.en if lang == Lang.en else self.ru


FORMS: dict[str, list[Field]] = {
    "custom_beats": [
        Field("genre_style", "Жанр/стиль:", "Genre/style:", "Жанр/стиль"),
        Field("bpm", "BPM:", "BPM:", "BPM"),
        Field("mood", "Настроение/вайб:", "Mood/vibe:", "Настроение"),
        Field("references", "Референсы (ссылки):", "References (links):", "Референсы"),
        Field("format", "Формат (WAV, MP3, STEMS):", "Format (WAV, MP3, STEMS):", "Формат"),
        Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
    ],
    "mixing": [
        Field("tracks_count", "Количество дорожек:", "Number of tracks:", "Дорожек"),
        Field("ref_sound", "Референс звучания:", "Reference sound:", "Референс"),
        Field("special", "Особые пожелания:", "Special requests:", "Пожелания"),
        Field("mastering", "Нужен мастеринг (Да/Нет):", "Mastering needed (Yes/No):", "Мастеринг"),
        Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
    ],
    "ghostwriting": [
        Field("genre_style", "Жанр/стиль:", "Genre/style:", "Жанр/стиль"),
        Field("verses", "Кол-во куплетов/припевов:", "Verses/choruses count:", "Куплеты"),
        Field("theme", "Тематика/концепт:", "Theme/concept:", "Тема"),
        Field("artist_example", "Пример исполнителя:", "Artist example:", "Пример"),
        Field("lang", "Язык текста:", "Lyrics language:", "Язык"),
        Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
    ],
    "visual": [
        Field("type", "Тип (обложка, баннер, арт, 3D):", "Type (cover, banner, art, 3D):", "Тип"),
        Field("palette", "Цветовая палитра/стиль:", "Color palette/style:", "Палитра"),
        Field("elements", "Описание элементов:", "Elements description:", "Элементы"),
        Field("references", "Референсы (ссылки):", "References (links):", "Референсы"),
        Field("format", "Формат (1:1, 16:9):", "Format (1:1, 16:9):", "Формат"),
        Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
    ],
    "videographer": [
        Field("video_type", "Тип видео:", "Video type:", "Тип видео"),
        Field("idea", "Идея/сценарий:", "Idea/script:", "Идея"),
        Field("location", "Локация:", "Location:", "Локация"),
        Field("dates", "Сроки съёмки:", "Shooting dates:", "Сроки"),
        Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
    ],
    "editing": [
        Field("video_type", "Тип видео:", "Video type:", "Тип видео"),
        Field("duration", "Хронометраж:", "Duration:", "Хронометраж"),
        Field("sources", "Ссылка на исходники:", "Source files link:", "Исходники"),
        Field("style_example", "Пример стиля:", "Style example:", "Стиль"),
        Field("format", "Формат видео:", "Video format:", "Формат"),
        Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
    ],
    "photo": [
        Field("city", "Город (строго Москва):", "City (Moscow only):", "Город"),
        Field("style", "Стиль съёмки:", "Shooting style:", "Стиль"),
        Field("looks", "Количество образов:", "Number of looks:", "Образы"),
        Field("dates", "Сроки:", "Dates:", "Сроки"),
        Field("examples", "Примеры:", "Examples:", "Примеры"),
        Field("budget_term", "Бюджет и срок:", "Budget and deadline:", "Бюджет/срок"),
    ],
}

# Соответствие ключа кнопки меню коду категории.
MENU_TO_CODE = {
    "menu_custom_beats": "custom_beats",
    "menu_mixing": "mixing",
    "menu_ghostwriting": "ghostwriting",
    "menu_visual": "visual",
    "menu_videographer": "videographer",
    "menu_editing": "editing",
    "menu_photo": "photo",
}
