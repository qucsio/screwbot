from aiogram.fsm.state import State, StatesGroup


class ReviewUpload(StatesGroup):
    photo = State()
