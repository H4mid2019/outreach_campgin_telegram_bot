from aiogram.fsm.state import State, StatesGroup

class DraftStates(StatesGroup):
    waiting_csv = State()
    waiting_templates = State()
    waiting_context = State()
    waiting_sender_name = State()

class AutosendStates(StatesGroup):
    waiting_csv = State()
    waiting_context = State()
    waiting_sender_name = State()

class GmailStates(StatesGroup):
    waiting_email = State()
    waiting_password = State()

class UpdateCsvStates(StatesGroup):
    waiting_input = State()
