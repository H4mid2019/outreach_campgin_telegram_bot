from typing import Dict, Set
from config import Config

# In-memory store for per-user AI model selection
# Keys: chat_id (int), Values: model string
_user_models: Dict[int, str] = {}

# Set of chat_ids authorized to change models
_authorized_users: Set[int] = set()


def get_user_model(chat_id: int) -> str:
    """Return the selected model for a user, falling back to the default."""
    return _user_models.get(chat_id, Config.OPENROUTER_MODEL)


def set_user_model(chat_id: int, model: str) -> None:
    """Persist a user's model choice in memory."""
    _user_models[chat_id] = model


def is_authorized_for_model_selection(chat_id: int) -> bool:
    """Check if user is authorized to change models."""
    return chat_id in _authorized_users


def authorize_user(chat_id: int) -> None:
    """Authorize a user to change models."""
    _authorized_users.add(chat_id)


def deauthorize_user(chat_id: int) -> None:
    """Remove a user's authorization to change models."""
    _authorized_users.discard(chat_id)


def validate_access_key(key: str) -> bool:
    """Validate if the provided key matches the configured access key."""
    return key == Config.MODEL_ACCESS_KEY
