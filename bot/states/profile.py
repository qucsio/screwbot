from aiogram.fsm.state import State, StatesGroup


class ProfileEdit(StatesGroup):
    socials = State()
    description = State()
    price = State()      # правка цены работы; work_id и вид цены — в data
