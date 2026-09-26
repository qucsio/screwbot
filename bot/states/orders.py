from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    filling = State()      # пошаговое заполнение ТЗ
    attachments = State()  # необязательные вложения (изображения/файлы) к ТЗ
    choosing = State()     # выбор исполнителя по профилям направления


class AdminPayout(StatesGroup):
    amount = State()       # ввод суммы к начислению исполнителю
