from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    writeoff = State()       # ввод суммы списания баланса (creator_id в data)
    add_creator = State()    # ввод @username/id для ручного добавления
    work_value = State()     # правка текстового/числового поля работы (work_id, field в data)
    work_audio = State()     # перезапись аудио работы (work_id в data)
    creator_field = State()  # правка поля профиля исполнителя (creator_id, field в data)
