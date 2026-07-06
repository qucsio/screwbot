from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    lang = State()
    role = State()
    nickname = State()


class CreatorApplication(StatesGroup):
    service = State()
    experience = State()
    portfolio = State()
