import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional

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


class UserCredits(Base):
    """Tracks email generation credits for paid AI models.
    Each credit = 1 email generation. Credits are purchased in packs of 25."""
    __tablename__ = "user_credits"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    # Credits for anthropic/claude-sonnet-4.5  (€5 per 25 emails)
    sonnet_credits: Mapped[int] = mapped_column(default=0)
    # Credits for anthropic/claude-haiku-4.5   (€1 per 25 emails)
    haiku_credits: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


# Database engine and session
engine = create_async_engine(
    "sqlite+aiosqlite:///email_bot.db",
    echo=False  # Set True for debug
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Create tables if not exist"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

