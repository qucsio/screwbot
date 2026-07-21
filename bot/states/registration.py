from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    lang = State()
    nickname = State()


class CreatorApplication(StatesGroup):
    service = State()
    experience = State()
    portfolio = State()
    portfolio_media = State()   # необязательный цикл добавления медиа в портфолио
