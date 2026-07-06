from aiogram.fsm.state import State, StatesGroup


class AddBeat(StatesGroup):
    title = State()
    genre = State()
    key = State()
    bpm = State()
    cover = State()
    audio = State()
    price_rent = State()
    price_buy = State()


class BeatFilter(StatesGroup):
    genre = State()
    key = State()
    bpm = State()
