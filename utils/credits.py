"""
Credit management utilities for paid AI models.

Pricing:
  - anthropic/claude-sonnet-4.5 : €5  per pack of 25 emails
  - anthropic/claude-haiku-4.5  : €1  per pack of 25 emails

Each credit = 1 email generation.
"""

from database.db import AsyncSessionLocal, UserCredits
from datetime import datetime

# Maps model identifier → UserCredits column name
CREDIT_FIELD_MAP: dict[str, str] = {
    "anthropic/claude-sonnet-4.5": "sonnet_credits",
    "anthropic/claude-haiku-4.5":  "haiku_credits",
}


def is_paid_model(model: str) -> bool:
    """Return True if the model requires credits to use."""
    return model in CREDIT_FIELD_MAP


async def get_credits(chat_id: int, model: str) -> int:
    """Return the user's current credit balance for the given paid model."""
    field = CREDIT_FIELD_MAP.get(model)
    if not field:
        return 0
    async with AsyncSessionLocal() as session:
        uc = await session.get(UserCredits, chat_id)
        if uc is None:
            return 0
        return getattr(uc, field, 0)


async def get_all_credits(chat_id: int) -> dict[str, int]:
    """Return {model: credits} for every paid model."""
    async with AsyncSessionLocal() as session:
        uc = await session.get(UserCredits, chat_id)
        if uc is None:
            return {model: 0 for model in CREDIT_FIELD_MAP}
        return {
            model: getattr(uc, field, 0)
            for model, field in CREDIT_FIELD_MAP.items()
        }


async def add_credits(chat_id: int, model: str, amount: int) -> int:
    """
    Add *amount* credits for *model* to the user's balance.
    Returns the new total.
    """
    field = CREDIT_FIELD_MAP.get(model)
    if not field:
        return 0
    async with AsyncSessionLocal() as session:
        uc = await session.get(UserCredits, chat_id)
        if uc is None:
            uc = UserCredits(chat_id=chat_id)
            session.add(uc)
        current = getattr(uc, field, 0)
        new_val = current + amount
        setattr(uc, field, new_val)
        uc.updated_at = datetime.utcnow()
        await session.commit()
        return new_val


async def deduct_credit(chat_id: int, model: str) -> bool:
    """
    Deduct 1 credit from the user's balance for *model*.
    Returns True on success, False if the user has no credits.
    """
    field = CREDIT_FIELD_MAP.get(model)
    if not field:
        return False
    async with AsyncSessionLocal() as session:
        uc = await session.get(UserCredits, chat_id)
        if uc is None or getattr(uc, field, 0) <= 0:
            return False
        current = getattr(uc, field, 0)
        setattr(uc, field, current - 1)
        uc.updated_at = datetime.utcnow()
        await session.commit()
        return True
