from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    lang = State()
    nickname = State()


class CreatorApplication(StatesGroup):
    """Заявка на одно направление; код направления — в данных состояния."""

    about = State()
    links = State()
    portfolio_media = State()   # необязательный цикл добавления медиа в портфолио
