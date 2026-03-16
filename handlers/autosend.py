from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import F
from states.states import AutosendStates
from keyboards.inline import get_start_keyboard, get_preset_campaigns_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.csv_validator import validate_and_parse_csv
from services.email_generator import EmailGenerator
from services.gmail_service import GmailService
from database.db import AsyncSessionLocal, User, UserCsvRecord, get_all_campaigns, get_campaign_by_name
from services.search_service import SearchService
from sqlalchemy import select
import aiofiles
import os
import tempfile
import asyncio
import random
import logging
from typing import List, Dict, Tuple, Optional

router = Router()
logger = logging.getLogger(__name__)

TELEGRAM_MAX_LENGTH = 4096


async def _send_long_message(message: Message, text: str, **kwargs):
    """Send a message, splitting into chunks if it exceeds Telegram's limit."""
    if len(text) <= TELEGRAM_MAX_LENGTH:
        await message.answer(text, **kwargs)
        return
    # Split on newlines to avoid cutting mid-line
    lines = text.split("\n")
    chunk = ""
    for line in lines:
        candidate = chunk + line + "\n"
        if len(candidate) > TELEGRAM_MAX_LENGTH:
            if chunk:
                await message.answer(chunk.rstrip("\n"), **kwargs)
            chunk = line + "\n"
        else:
            chunk = candidate
    if chunk.strip():
        await message.answer(chunk.rstrip("\n"), **kwargs)


# Concurrency limits
_PROFILE_SEMAPHORE = asyncio.Semaphore(5)   # max 5 concurrent web searches
_GENERATE_SEMAPHORE = asyncio.Semaphore(5)  # max 5 concurrent LLM calls


def _back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


async def _get_user_records(chat_id: int) -> List[Dict]:
    """Return the user's custom CSV records from DB, or empty list if none."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserCsvRecord).where(UserCsvRecord.chat_id == chat_id)
        )
        rows = result.scalars().all()
    return [
        {'name': r.name, 'email': r.email, 'info': r.info, 'language': r.language}
        for r in rows
    ]


async def _load_records_for_user(chat_id: int):
    """
    Load records for a user:
    - If the user has uploaded their own CSV, use those records.
    - Otherwise fall back to sample_draft.csv (read-only).
    Returns (is_valid, source_label, records).
    """
    user_records = await _get_user_records(chat_id)
    if user_records:
        return True, "📂 لیست شخصی شما", user_records

    is_valid, msg, records = await validate_and_parse_csv('sample_draft.csv')
    return is_valid, "📋 لیست پیش‌فرض (sample)", records


# ─────────────────────────────────────────────
# Step 0 — Entry: Gmail check, then show presets
# ─────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "autosend")
async def start_autosend(callback: CallbackQuery, state: FSMContext):
    chat_id = callback.message.chat.id

    # Check Gmail connection first
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)

    if not user or not user.gmail_tokens:
        await callback.message.edit_text(
            "❌ <b>Gmail متصل نیست.</b>\n"
            "ابتدا /status → اتصال Gmail (ایمیل + App Password)",
            parse_mode="HTML",
            reply_markup=_back_keyboard()
        )
        await callback.answer()
        return

    # Store Gmail info in state
    await state.update_data(gmail_email=user.gmail_email)

    # Check for preset campaigns
    campaigns = await get_all_campaigns()

    if campaigns:
        await state.set_state(AutosendStates.waiting_preset_selection)
        await callback.message.edit_text(
            f"✅ متصل به: <b>{user.gmail_email}</b>\n\n"
            "📤 <b>ارسال خودکار ایمیل</b>\n\n"
            "یک کمپین پیش‌تنظیم انتخاب کنید یا به صورت دستی ادامه دهید:",
            parse_mode="HTML",
            reply_markup=get_preset_campaigns_keyboard(campaigns, mode="autosend")
        )
    else:
        # No presets — go straight to manual flow
        await _start_autosend_manual(callback.message, state, chat_id=chat_id, gmail_email=user.gmail_email, edit=True)

    await callback.answer()


# ─────────────────────────────────────────────
# Step 0a — User selects a preset campaign
# ─────────────────────────────────────────────

@router.callback_query(AutosendStates.waiting_preset_selection, lambda c: c.data and c.data.startswith("select_campaign:autosend:"))
async def autosend_select_preset_campaign(callback: CallbackQuery, state: FSMContext):
    """User picked a preset campaign — load its email list and target."""
    campaign_name = callback.data.split(":", 2)[2]
    campaign = await get_campaign_by_name(campaign_name)

    if not campaign:
        await callback.message.edit_text(
            "❌ این کمپین دیگر موجود نیست. لطفاً دوباره امتحان کنید.",
            reply_markup=_back_keyboard()
        )
        await state.clear()
        await callback.answer()
        return

    records = campaign["email_list"]
    context = campaign["target"]
    data = await state.get_data()
    gmail_email = data.get("gmail_email", "")

    await state.update_data(
        records=records,
        context=context,
        campaign_name=campaign_name,
    )
    await state.set_state(AutosendStates.waiting_sender_name)

    await callback.message.edit_text(
        f"✅ متصل به: <b>{gmail_email}</b>\n\n"
        f"📌 <b>کمپین انتخاب شد: {campaign_name}</b>\n"
        f"📝 {campaign['description']}\n"
        f"🎯 هدف: <i>{context[:100]}{'...' if len(context) > 100 else ''}</i>\n"
        f"👥 {len(records)} ایمیل آماده\n\n"
        "👤 <b>نام فرستنده را وارد کنید:</b>\n"
        "این نام در انتهای ایمیل‌ها قرار می‌گیرد.\n"
        "مثال: علی احمدی یا John Doe",
        parse_mode="HTML",
        reply_markup=_back_keyboard()
    )
    await callback.answer()


# ─────────────────────────────────────────────
# Step 0b — User chooses manual entry (no preset)
# ─────────────────────────────────────────────

@router.callback_query(AutosendStates.waiting_preset_selection, lambda c: c.data == "campaign_manual:autosend")
async def autosend_choose_manual(callback: CallbackQuery, state: FSMContext):
    """User chose manual — load their CSV and ask for context."""
    data = await state.get_data()
    gmail_email = data.get("gmail_email", "")
    await _start_autosend_manual(callback.message, state, chat_id=callback.message.chat.id, gmail_email=gmail_email, edit=True)
    await callback.answer()


@router.callback_query(lambda c: c.data == "campaign_manual:autosend")
async def autosend_choose_manual_fallback(callback: CallbackQuery, state: FSMContext):
    """Fallback for manual entry outside preset selection state."""
    data = await state.get_data()
    gmail_email = data.get("gmail_email", "")
    await _start_autosend_manual(callback.message, state, chat_id=callback.message.chat.id, gmail_email=gmail_email, edit=True)
    await callback.answer()


async def _start_autosend_manual(message, state: FSMContext, chat_id: int, gmail_email: str, edit: bool = False):
    """Load user's CSV (or sample) and prompt for campaign context."""
    is_valid, source_label, records = await _load_records_for_user(chat_id)
    if not is_valid:
        text = f"✅ متصل به: {gmail_email}\n\n❌ خطای CSV\nبه‌روزرسانی کنید."
        if edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=_back_keyboard())
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=_back_keyboard())
        return

    await state.update_data(records=records)
    await state.set_state(AutosendStates.waiting_context)

    text = (
        f"✅ متصل به: {gmail_email}\n"
        f"{source_label} — {len(records)} رکورد\n\n"
        f"💬 <b>زمینه کمپین را بنویسید:</b>\n"
        f"مثال: درخواست حمایت برای طرح X، لحن رسمی"
    )
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=_back_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=_back_keyboard())


# ─────────────────────────────────────────────
# Step 1 — Receive context (manual only)
# ─────────────────────────────────────────────

@router.message(AutosendStates.waiting_context)
async def process_autosend_context(message: Message, state: FSMContext):
    context = message.text.strip()
    await state.update_data(context=context)
    await message.answer(
        "👤 <b>نام فرستنده را وارد کنید:</b>\n"
        "این نام در انتهای ایمیل‌ها قرار می‌گیرد\n"
        "مثال: علی احمدی یا John Doe",
        parse_mode="HTML",
        reply_markup=_back_keyboard()
    )
    await state.set_state(AutosendStates.waiting_sender_name)


# ─────────────────────────────────────────────
# Step 2 — Receive sender name & launch campaign
# ─────────────────────────────────────────────

@router.message(AutosendStates.waiting_sender_name)
async def process_sender_name(message: Message, state: FSMContext):
    sender_name = message.text.strip()
    if len(sender_name) < 2:
        await message.answer("❌ نام معتبر وارد کنید (حداقل 2 حرف).", reply_markup=_back_keyboard())
        return

    data = await state.get_data()
    records: List[Dict] = data['records']
    context: str = data['context']

    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)
        if not user or not user.gmail_tokens:
            await message.answer("❌ Gmail متصل نیست.", reply_markup=_back_keyboard())
            await state.clear()
            return

        gmail_email = user.gmail_email
        tokens_encrypted = user.gmail_tokens

    campaign_label = data.get("campaign_name", "دستی")

    # ── Acknowledge immediately so the handler returns and other users are served ──
    await message.answer(
        f"🚀 <b>کمپین در حال اجرا در پس‌زمینه است...</b>\n"
        f"📌 کمپین: <b>{campaign_label}</b>\n"
        f"👥 تعداد: <b>{len(records)}</b> ایمیل\n\n"
        f"⚡ پروفایل‌ها و ایمیل‌ها به‌صورت موازی آماده می‌شوند.\n"
        f"📊 گزارش نهایی بعد از اتمام، ارسال می شود.",
        parse_mode="HTML"
    )
    await state.clear()  # free the FSM immediately

    # ── Launch the campaign as a background task ──
    asyncio.create_task(
        _run_campaign(
            message=message,
            records=records,
            context=context,
            sender_name=sender_name,
            chat_id=chat_id,
            tokens_encrypted=tokens_encrypted,
            gmail_email=gmail_email,
            campaign_label=campaign_label,
        )
    )


# ─────────────────────────────────────────────
# Background campaign runner (non-blocking)
# ─────────────────────────────────────────────

async def _fetch_profile_for_rec(search_service: SearchService, rec: Dict) -> Dict:
    """Fetch one recipient profile with semaphore limiting."""
    async with _PROFILE_SEMAPHORE:
        try:
            async with AsyncSessionLocal() as db_session:
                return await search_service.get_recipient_profile(db_session, rec)
        except Exception as e:
            logger.error(f"Profile fetch failed for {rec.get('email', '?')}: {e}")
            return {}


async def _generate_email_for_rec(
    email_gen: EmailGenerator,
    context: str,
    rec: Dict,
    sender_name: str,
    profile: Dict,
    chat_id: int,
) -> Optional[Dict]:
    """Generate one email with semaphore limiting."""
    async with _GENERATE_SEMAPHORE:
        try:
            return await email_gen.generate_personalized_email(
                context,
                rec['name'],
                rec['info'],
                rec['language'],
                sender_name,
                profile,
                chat_id=chat_id,
            )
        except Exception as e:
            logger.error(f"Email generation failed for {rec.get('email', '?')}: {e}")
            return None


async def _run_campaign(
    message: Message,
    records: List[Dict],
    context: str,
    sender_name: str,
    chat_id: int,
    tokens_encrypted: str,
    gmail_email: str,
    campaign_label: str,
):
    """
    Runs the full campaign in the background:
      Phase 1 — Fetch all profiles concurrently (semaphore=5)
      Phase 2 — Generate all emails concurrently (semaphore=5)
      Phase 3 — Send emails sequentially with delays (Gmail limits)
    """
    email_gen = EmailGenerator()
    gmail_svc = GmailService()
    search_service = SearchService()
    total = len(records)

    # ── Phase 1: Concurrent profile fetching ──────────────────────────
    await message.answer(f"🔍 <b>فاز ۱:</b> دریافت پروفایل‌های {total} گیرنده به‌صورت موازی...", parse_mode="HTML")

    profile_tasks = [_fetch_profile_for_rec(search_service, rec) for rec in records]
    profiles = await asyncio.gather(*profile_tasks)

    await message.answer(f"✅ <b>فاز ۱ تمام شد.</b> {total} پروفایل دریافت شد.\n⚙️ <b>فاز ۲:</b> تولید ایمیل‌ها به‌صورت موازی...", parse_mode="HTML")

    # ── Phase 2: Concurrent email generation ──────────────────────────
    gen_tasks = [
        _generate_email_for_rec(email_gen, context, rec, sender_name, profile, chat_id)
        for rec, profile in zip(records, profiles)
    ]
    email_data_list = await asyncio.gather(*gen_tasks)

    await message.answer(f"✅ <b>فاز ۲ تمام شد.</b> ایمیل‌ها آماده‌اند.\n📤 <b>فاز ۳:</b> ارسال ایمیل‌ها با تأخیر (جلوگیری از block شدن Gmail)...", parse_mode="HTML")

    # ── Phase 3: Sequential sending with delays ────────────────────────
    results = []
    success_count = 0

    for i, (rec, email_data) in enumerate(zip(records, email_data_list)):
        email_to = rec['email']

        if email_data is None:
            results.append(f"❌ {email_to}: خطای تولید ایمیل")
            continue

        subject = email_data['subject']
        body = email_data['body']

        try:
            success, err_msg = await gmail_svc.send_email(
                chat_id, tokens_encrypted, gmail_email, email_to, subject, body
            )
            if success:
                success_count += 1
                results.append(f"✅ {email_to}")
            else:
                results.append(f"❌ {email_to}: {err_msg}")
        except Exception as e:
            logger.error(f"Send error for {email_to}: {e}")
            results.append(f"❌ {email_to}: خطای ارسال")

        # Delay between sends: 8-12s + jitter to avoid Gmail rate limits
        if i < total - 1:  # no delay after the last email
            delay = random.uniform(8, 12) + random.uniform(1, 3)
            await asyncio.sleep(delay)

        # Progress update every 5 emails
        if (i + 1) % 5 == 0:
            await message.answer(f"📊 ارسال: {i+1}/{total} — ✅ {success_count} موفق")

    # ── Final report ─────────────────────────────────────────────────
    report = (
        f"📊 <b>گزارش نهایی</b>\n"
        f"📌 کمپین: <b>{campaign_label}</b>\n"
        f"📧 تعداد کل: <b>{total}</b>\n\n"
        f"✅ <b>موفق:</b> {success_count}\n"
        f"❌ <b>ناموفق:</b> {total - success_count}\n\n"
        "<b>جزئیات:</b>\n"
    )
    for res in results:
        report += f"• {res}\n"

    await _send_long_message(message, report, parse_mode="HTML", reply_markup=get_start_keyboard())
