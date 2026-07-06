from bot.db.models import Lang
from bot.locales import en, ru

_TABLES = {Lang.ru: ru.TEXTS, Lang.en: en.TEXTS}


def t(key: str, lang: Lang = Lang.ru, **kwargs) -> str:
    table = _TABLES.get(lang, ru.TEXTS)
    text = table.get(key) or ru.TEXTS.get(key, key)
    return text.format(**kwargs) if kwargs else text
