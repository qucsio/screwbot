from aiogram.fsm.state import State, StatesGroup


class AddPortfolio(StatesGroup):
    media = State()
    caption = State()   # media_type/file_id — во временных данных состояния
