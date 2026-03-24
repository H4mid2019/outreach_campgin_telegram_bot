from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, select, delete, text
from typing import Optional, List, Dict


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    gmail_tokens: Mapped[Optional[str]] = mapped_column(nullable=True)
    gmail_email: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class RecipientInfo(Base):
    __tablename__ = "recipient_info"

    email: Mapped[str] = mapped_column(primary_key=True)
    profile_json: Mapped[Optional[str]] = mapped_column(nullable=True)
    language: Mapped[str] = mapped_column(default="en")
    last_searched: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserCsvRecord(Base):
    """Stores per-user CSV records uploaded via 'Update CSV'.
    Each user has their own set of records; sample_draft.csv is never modified."""

    __tablename__ = "user_csv_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column()
    email: Mapped[str] = mapped_column()
    info: Mapped[str] = mapped_column()
    language: Mapped[str] = mapped_column(default="en")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class PresetCampaign(Base):
    """Global preset campaigns accessible by all users.
    Each campaign has a name (unique slug), description, target text, JSON email list, and optional attachments."""

    __tablename__ = "preset_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    target: Mapped[str] = mapped_column(Text)
    email_list_json: Mapped[str] = mapped_column(
        Text
    )  # JSON list of {name,email,info,language}
    attachments_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON list of attachment metadata {filename, relative_path, size, mime_type}
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )


# Database engine and session
engine = create_async_engine(
    "sqlite+aiosqlite:///email_bot.db",
    echo=False,  # Set True for debug
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create tables if not exist, migrate schema if needed"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Ensure attachments_json column exists (migration for existing DBs)
        result = await conn.execute(text("PRAGMA table_info(preset_campaigns)"))
        columns = [row[1] for row in result.fetchall()]
        if "attachments_json" not in columns:
            await conn.execute(
                text("ALTER TABLE preset_campaigns ADD COLUMN attachments_json TEXT")
            )
            await conn.commit()


# ─────────────────────────────────────────────
# Preset Campaign CRUD helpers
# ─────────────────────────────────────────────

import json


async def get_all_campaigns() -> List[Dict]:
    """Return all preset campaigns as a list of dicts."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PresetCampaign).order_by(PresetCampaign.name)
        )
        rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "target": r.target,
            "email_list": json.loads(r.email_list_json),
            "attachments": json.loads(r.attachments_json) if r.attachments_json else [],
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": r.updated_at.strftime("%Y-%m-%d %H:%M")
            if r.updated_at
            else "",
        }
        for r in rows
    ]


async def get_campaign_by_name(name: str) -> Optional[Dict]:
    """Return a single campaign dict by name, or None."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PresetCampaign).where(PresetCampaign.name == name)
        )
        row = result.scalar_one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "target": row.target,
        "email_list": json.loads(row.email_list_json),
        "attachments": json.loads(row.attachments_json) if row.attachments_json else [],
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M")
        if row.updated_at
        else "",
    }


async def upsert_campaign(
    name: str,
    description: str,
    target: str,
    email_list: List[Dict],
    attachments: Optional[List[Dict]] = None,
) -> bool:
    """Create or update a preset campaign. Returns True if created, False if updated."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PresetCampaign).where(PresetCampaign.name == name)
        )
        existing = result.scalar_one_or_none()
        att_json = (
            json.dumps(attachments or [], ensure_ascii=False)
            if attachments is not None
            else None
        )
        if existing:
            existing.description = description
            existing.target = target
            existing.email_list_json = json.dumps(email_list, ensure_ascii=False)
            if att_json is not None:
                existing.attachments_json = att_json
            existing.updated_at = datetime.utcnow()
            await session.commit()
            return False  # updated
        else:
            session.add(
                PresetCampaign(
                    name=name,
                    description=description,
                    target=target,
                    email_list_json=json.dumps(email_list, ensure_ascii=False),
                    attachments_json=att_json or json.dumps([], ensure_ascii=False),
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()
            return True  # created


async def delete_campaign(name: str) -> bool:
    """Delete a preset campaign by name. Returns True if deleted."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(PresetCampaign).where(PresetCampaign.name == name)
        )
        await session.commit()
        return result.rowcount > 0


# ─────────────────────────────────────────────
# Retry-campaign helpers
# ─────────────────────────────────────────────

RETRY_CAMPAIGN_PREFIX = "_retry_"


def make_retry_campaign_name(chat_id: int, timestamp: int) -> str:
    """Build the DB name for a per-user retry campaign."""
    return f"{RETRY_CAMPAIGN_PREFIX}{chat_id}_{timestamp}"


def is_retry_campaign(name: str, chat_id: int) -> bool:
    """Return True if this campaign name is a retry campaign owned by chat_id."""
    return name.startswith(f"{RETRY_CAMPAIGN_PREFIX}{chat_id}_")


async def get_retry_campaigns_for_user(chat_id: int) -> List[Dict]:
    """Return all retry campaigns that belong to this user, newest first."""
    prefix = f"{RETRY_CAMPAIGN_PREFIX}{chat_id}_"
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PresetCampaign)
            .where(PresetCampaign.name.startswith(prefix))
            .order_by(PresetCampaign.created_at.desc())
        )
        rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "target": r.target,
            "email_list": json.loads(r.email_list_json),
            "attachments": json.loads(r.attachments_json) if r.attachments_json else [],
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": r.updated_at.strftime("%Y-%m-%d %H:%M")
            if r.updated_at
            else "",
        }
        for r in rows
    ]
