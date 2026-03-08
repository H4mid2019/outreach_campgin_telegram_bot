from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import F
from states.states import AutosendStates
from keyboards.inline import get_start_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.csv_validator import validate_and_parse_csv
from services.email_generator import EmailGenerator
from services.gmail_service import GmailService
from database.db import AsyncSessionLocal, User, UserCsvRecord
from services.search_service import SearchService
from sqlalchemy import select
import aiofiles
import os
import tempfile
import asyncio
import random
import logging
from typing import List, Dict, Tuple

router = Router()
logger = logging.getLogger(__name__)

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


@router.callback_query(lambda c: c.data == "autosend")
async def start_autosend(callback: CallbackQuery, state: FSMContext):
    chat_id = callback.message.chat.id

    # Check Gmail connection
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)

    if not user or not user.gmail_tokens:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            "❌ <b>Gmail متصل نیست.</b>\n"
            "ابتدا /status → اتصال Gmail (ایمیل + App Password)",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    gmail_email = user.gmail_email

    # Load records: user-specific first, then fall back to sample_draft.csv
    is_valid, source_label, records = await _load_records_for_user(chat_id)
    if not is_valid:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            f"✅ متصل به: {gmail_email}\n\n❌ خطای CSV\nبه‌روزرسانی کنید.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    await state.update_data(records=records, gmail_email=gmail_email)
    await callback.message.edit_text(
        f"✅ متصل به: {gmail_email}\n"
        f"{source_label} — {len(records)} رکورد\n\n"
        f"💬 <b>زمینه کمپین را بنویسید (فارسی):</b>\n"
        f"مثال: درخواست حمایت برای طرح X، لحن رسمی",
        parse_mode="HTML"
    )
    await state.set_state(AutosendStates.waiting_context)
    await callback.answer()


@router.message(AutosendStates.waiting_context)
async def process_autosend_context(message: Message, state: FSMContext):
    context = message.text.strip()
    await state.update_data(context=context)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    await message.answer(
        "👤 <b>نام فرستنده را وارد کنید:</b>\n"
        "این نام در انتهای ایمیل‌ها قرار می‌گیرد\n"
        "مثال: علی احمدی یا John Doe",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AutosendStates.waiting_sender_name)


@router.message(AutosendStates.waiting_sender_name)
async def process_sender_name(message: Message, state: FSMContext):
    sender_name = message.text.strip()
    if len(sender_name) < 2:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
        builder.adjust(1)
        await message.answer("❌ نام معتبر وارد کنید (حداقل 2 حرف).", reply_markup=builder.as_markup())
        return
    
    data = await state.get_data()
    records: List[Dict] = data['records']
    context: str = data['context']
    
    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)
        if not user or not user.gmail_tokens:
            builder = InlineKeyboardBuilder()
            builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
            builder.adjust(1)
            await message.answer("❌ Gmail متصل نیست.", reply_markup=builder.as_markup())
            await state.clear()
            return
        
        gmail_email = user.gmail_email
        tokens_encrypted = user.gmail_tokens
    
    email_gen = EmailGenerator()
    gmail_svc = GmailService()
    search_service = SearchService()
    
    await message.answer("🚀 <b>شروع ارسال...</b>\n⏳ لطفاً صبر کنید (تأخیر بین ایمیل‌ها + research).", parse_mode="HTML")

    results = []
    success_count = 0
    
    for i, rec in enumerate(records):
        name = rec['name']
        info = rec['info']
        email_to = rec['email']
        lang = rec['language']
        
        try:
            async with AsyncSessionLocal() as db_session:
                profile = await search_service.get_recipient_profile(db_session, rec)
            
            # Generate with sender_name, profile, and per-user model
            email_data = await email_gen.generate_personalized_email(context, name, info, lang, sender_name, profile, chat_id=chat_id)
            subject = email_data['subject']
            body = email_data['body']
            
            # Send with delay
            success, err_msg = await gmail_svc.send_email(chat_id, tokens_encrypted, gmail_email, email_to, subject, body)
            if success:
                success_count += 1
                results.append(f"✅ {email_to}")
            else:
                results.append(f"❌ {email_to}: {err_msg}")
            
            # Delay 8-12s + jitter
            delay = random.uniform(8, 12) + random.uniform(1, 3)
            await asyncio.sleep(delay)
            
            # Progress update every 5
            if (i + 1) % 5 == 0:
                await message.answer(f"📊 پیشرفت: {i+1}/{len(records)}")
                
        except Exception as e:
            logger.error(f"Error for {email_to}: {e}")
            results.append(f"❌ {email_to}: خطای تولید")
    
    # Final report
    report = (
        f"📊 <b>گزارش نهایی ({len(records)} ایمیل)</b>\n\n"
        f"✅ <b>موفق:</b> {success_count}\n"
        f"❌ <b>ناموفق:</b> {len(records) - success_count}\n\n"
        "<b>جزئیات:</b>\n"
    )
    for res in results:
        report += f"• {res}\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    await message.answer(report, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.clear()
