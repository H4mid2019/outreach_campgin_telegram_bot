from aiogram.fsm.state import State, StatesGroup

class DraftStates(StatesGroup):
    waiting_csv = State()
    waiting_templates = State()
    waiting_preset_selection = State()   # NEW: choosing a preset campaign
    waiting_context = State()
    waiting_sender_name = State()

class AutosendStates(StatesGroup):
    waiting_csv = State()
    waiting_preset_selection = State()   # NEW: choosing a preset campaign
    waiting_context = State()
    waiting_sender_name = State()

class GmailStates(StatesGroup):
    waiting_email = State()
    waiting_password = State()

class UpdateCsvStates(StatesGroup):
    waiting_input = State()

class AccessKeyStates(StatesGroup):
    waiting_key = State()

# ── Preset Campaign Management (requires CAMPAIGN_ACCESS_KEY) ──────────────────
class PresetCampaignStates(StatesGroup):
    waiting_key = State()           # key verification
    waiting_action = State()        # add / delete (after key verified)
    waiting_name = State()          # campaign unique slug/name
    waiting_description = State()   # short description
    waiting_target = State()        # campaign target text (pre-fill context)
    waiting_email_list = State()    # CSV email list (file or text)
    waiting_delete_confirm = State()  # confirm deletion
