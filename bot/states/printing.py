from aiogram.fsm.state import State, StatesGroup


class PrintingStates(StatesGroup):
    waiting_for_screenshot = State()
    waiting_for_order_numbers = State()
