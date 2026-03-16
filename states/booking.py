from aiogram.fsm.state import StatesGroup, State


class BookingStates(StatesGroup):
    """FSM для записи клиента."""
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()
    confirm = State()


class AdminStates(StatesGroup):
    """FSM для админ-панели."""
    choosing_action = State()
    add_day_date = State()
    add_slot_date = State()
    add_slot_time = State()
    close_day_date = State()
    view_schedule_date = State()
    cancel_appointment_date = State()
    cancel_appointment_choose = State()