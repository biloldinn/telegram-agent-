from aiogram.fsm.state import State, StatesGroup

class LoginState(StatesGroup):
    waiting_for_admin_broadcast = State()
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()
    waiting_for_business_info = State()
    waiting_for_channel_link = State()
    waiting_for_broadcast = State()
    waiting_for_client_broadcast = State()
