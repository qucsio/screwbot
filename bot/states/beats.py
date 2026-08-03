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


class AddVisual(StatesGroup):
    title = State()
    vtype = State()      # тип: обложка/баннер/арт/лого (хранится в Work.genre)
    cover = State()
    price_buy = State()


class AddVideo(StatesGroup):
    title = State()
    vtype = State()      # тип видео: клип/лирик/реклама/motion (хранится в Work.genre)
    video = State()      # сам видеофайл (file_id хранится в Work.cover_file_id)
    price_buy = State()


class BeatFilter(StatesGroup):
    genre = State()
    key = State()
    bpm = State()
