from typing import Dict
from config import Config

# In-memory store for per-user AI model selection
# Keys: chat_id (int), Values: model string
_user_models: Dict[int, str] = {}


def get_user_model(chat_id: int) -> str:
    """Return the selected model for a user, falling back to the default."""
    return _user_models.get(chat_id, Config.OPENROUTER_MODEL)


def set_user_model(chat_id: int, model: str) -> None:
    """Persist a user's model choice in memory."""
    _user_models[chat_id] = model
