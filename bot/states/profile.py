from aiogram.fsm.state import State, StatesGroup


class ProfileEdit(StatesGroup):
    socials = State()      # общие контакты человека
    about = State()        # описание профиля направления (profile_id в data)
    links = State()        # ссылки на работы этого направления
    price = State()        # правка цены работы; work_id и вид цены — в data
