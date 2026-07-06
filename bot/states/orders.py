from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    filling = State()      # пошаговое заполнение ТЗ


class AdminPayout(StatesGroup):
    amount = State()       # ввод суммы к начислению исполнителю
