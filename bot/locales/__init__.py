from bot.db.models import Lang
from bot.locales import en, ru

_TABLES = {Lang.ru: ru.TEXTS, Lang.en: en.TEXTS}


def t(msg_key: str, lang: Lang = Lang.ru, **kwargs) -> str:
    # msg_key (не key!), чтобы не конфликтовать с шаблонами, где есть {key}
    table = _TABLES.get(lang, ru.TEXTS)
    text = table.get(msg_key) or ru.TEXTS.get(msg_key, msg_key)
    return text.format(**kwargs) if kwargs else text
