from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import F
from states.states import DraftStates, UpdateCsvStates
from keyboards.inline import get_start_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.csv_validator import validate_and_parse_csv
import logging
import pandas as pd
import aiofiles
import os
import tempfile
import io
from typing import Dict, List, Optional

from services.openrouter_service import OpenRouterService
from services.search_service import SearchService
from database.db import AsyncSessionLocal, UserCsvRecord
from sqlalchemy import select, delete
from config import Config
from utils.user_settings import get_user_model
from utils.credits import is_paid_model, get_credits, deduct_credit

router = Router()
logger = logging.getLogger(__name__)

EMAILS_PER_PAGE = 2

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


async def get_user_records(chat_id: int) -> List[Dict]:
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


async def save_user_records(chat_id: int, records: List[Dict]) -> None:
    """Replace all CSV records for a user with the new list."""
    async with AsyncSessionLocal() as session:
        # Delete existing records for this user
        await session.execute(
            delete(UserCsvRecord).where(UserCsvRecord.chat_id == chat_id)
        )
        # Insert new records
        for rec in records:
            session.add(UserCsvRecord(
                chat_id=chat_id,
                name=rec['name'],
                email=rec['email'],
                info=rec['info'],
                language=rec.get('language', 'en'),
            ))
        await session.commit()


async def load_records_for_user(chat_id: int) -> tuple[bool, str, List[Dict]]:
    """
    Load records for a user:
    - If the user has uploaded their own CSV, use those records.
    - Otherwise fall back to sample_draft.csv (read-only).
    Returns (is_valid, message, records).
    """
    user_records = await get_user_records(chat_id)
    if user_records:
        return True, f"✅ {len(user_records)} رکورد شخصی بارگذاری شد", user_records

    # Fall back to sample_draft.csv
    return await validate_and_parse_csv('sample_draft.csv')


async def generate_emails_for_records(
    records: List[Dict],
    context: str,
    sender_name: str,
    chat_id: int = None,
) -> List[Dict]:
    """Generate email drafts for a list of records using campaign context and sender name.

    For paid models, 1 credit is deducted per successfully generated email.
    If the user runs out of credits mid-batch, remaining emails get an error entry.
    """
    ors = OpenRouterService()
    search_service = SearchService()
    generated = []

    # Resolve the user's chosen model once for the whole batch
    user_model = get_user_model(chat_id) if chat_id is not None else None
    paid = chat_id is not None and user_model and is_paid_model(user_model)

    for rec in records:
        name = rec['name']
        info = rec['info']
        lang = rec['language']
        email_addr = rec['email']

        # ── Credit gate for paid models ──────────────────────────────────
        if paid:
            deducted = await deduct_credit(chat_id, user_model)
            if not deducted:
                generated.append({
                    'email_addr': email_addr,
                    'subject': "❌ اعتبار ناکافی",
                    'body': (
                        "اعتبار شما برای این مدل تمام شده است.\n"
                        "برای خرید بسته جدید /credits را بزنید."
                    ),
                })
                continue
        # ─────────────────────────────────────────────────────────────────

        async with AsyncSessionLocal() as session:
            profile = await search_service.get_recipient_profile(session, rec)

        system_prompt = Config.get_system_prompt(lang)

        user_prompt = f"""Campaign context/goal: {context}

Recipient details:
- Full name: {name}
- Position/Party/Info: {info}
- Language: {lang}
- Sender name (use EXACTLY in closing): {sender_name}"""

        if profile:
            user_prompt += f"""

Recipient profile from research:
Bio: {profile.get('bio', '')}
Gender: {profile.get('gender', 'unknown')}
Targets: {', '.join(profile.get('targets', []))}
Mottos: {', '.join(profile.get('mottos', []))}
Values: {', '.join(profile.get('values', []))}
Keywords: {', '.join(profile.get('keywords', []))}
Subjects: {', '.join(profile.get('subjects', []))}

Use profile for hyper-personalization. Match language/style. Official clickbait subjects using keywords/mottos."""

        user_prompt += """

Generate a personalized email using the exact structure from system prompt. Use the sender name exactly in the closing signature, no placeholders."""

        try:
            email_data = await ors.generate_email(system_prompt, user_prompt, model=user_model)
            subject = email_data.get('subject', 'Subject Missing')
            body = email_data.get('body', 'Body Missing')
        except Exception as e:
            subject = "Error generating"
            body = f"Failed: {str(e)}"

        generated.append({
            'email_addr': email_addr,
            'subject': subject,
            'body': body,
        })

    return generated


def build_draft_page_text(cached_emails: Dict[int, List[Dict]], page: int, total_records: int) -> str:
    """Build the message text for a given page of draft emails."""
    total_pages = (total_records + EMAILS_PER_PAGE - 1) // EMAILS_PER_PAGE
    page_emails = cached_emails.get(page, [])

    text = f"📋 <b>Political Email Drafts — Page {page + 1}/{total_pages}</b>\n\n"

    start_index = page * EMAILS_PER_PAGE
    for i, email_item in enumerate(page_emails, start=start_index + 1):
        text += f"<b>{i}. To: <code>{email_item['email_addr']}</code></b>\n"
        text += f"<b>Subject:</b> <code>{email_item['subject']}</code>\n\n"
        text += f"<b>Body:</b>\n"
        text += f"<pre>{email_item['body']}</pre>\n\n"
        text += f"{'─' * 50}\n\n"

    return text


def build_draft_page_keyboard(page: int, total_records: int):
    """Build navigation keyboard for draft pagination."""
    total_pages = (total_records + EMAILS_PER_PAGE - 1) // EMAILS_PER_PAGE
    builder = InlineKeyboardBuilder()

    if page > 0:
        builder.button(text="⬅️ Previous", callback_data=f"draft_page:{page - 1}")
    if page < total_pages - 1:
        builder.button(text="Next ➡️", callback_data=f"draft_page:{page + 1}")

    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(2, 1)
    return builder.as_markup()


# ─────────────────────────────────────────────
# Step 1 — Entry: ask for campaign context
# ─────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "draft")
async def start_draft(callback: CallbackQuery, state: FSMContext):
    """Entry point: load records (user-specific or sample), then ask for campaign context."""
    chat_id = callback.message.chat.id
    is_valid, msg, records = await load_records_for_user(chat_id)

    if not is_valid:
        await callback.message.edit_text(
            f"❌ CSV Error: {msg}",
            parse_mode="HTML",
            reply_markup=_back_keyboard()
        )
        await callback.answer()
        return

    # Determine source label for the user
    user_records = await get_user_records(chat_id)
    source_label = "📂 لیست شخصی شما" if user_records else "📋 لیست پیش‌فرض (sample)"

    # Store records in state and move to context step
    await state.update_data(draft_records=records, draft_total=len(records))
    await state.set_state(DraftStates.waiting_context)

    await callback.message.edit_text(
        f"📝 <b>ساخت پیش‌نویس ایمیل</b>\n\n"
        f"{source_label} — {len(records)} رکورد بارگذاری شد.\n\n"
        f"💬 <b>زمینه / هدف کمپین را بنویسید:</b>\n"
        f"مثال: درخواست حمایت برای طرح X، لحن رسمی\n"
        f"Example: Invite to political summit, formal tone",
        parse_mode="HTML",
        reply_markup=_back_keyboard()
    )
    await callback.answer()


# ─────────────────────────────────────────────
# Step 2 — Receive campaign context, ask sender name
# ─────────────────────────────────────────────

@router.message(DraftStates.waiting_context)
async def draft_receive_context(message: Message, state: FSMContext):
    context = message.text.strip()
    if not context:
        await message.answer("❌ لطفاً زمینه کمپین را وارد کنید.", reply_markup=_back_keyboard())
        return

    await state.update_data(draft_context=context)
    await state.set_state(DraftStates.waiting_sender_name)

    await message.answer(
        "👤 <b>نام فرستنده را وارد کنید:</b>\n"
        "این نام در انتهای ایمیل‌ها قرار می‌گیرد.\n"
        "مثال: علی احمدی یا John Doe",
        parse_mode="HTML",
        reply_markup=_back_keyboard()
    )


# ─────────────────────────────────────────────
# Step 3 — Receive sender name, generate first page
# ─────────────────────────────────────────────

@router.message(DraftStates.waiting_sender_name)
async def draft_receive_sender_name(message: Message, state: FSMContext):
    sender_name = message.text.strip()
    if len(sender_name) < 2:
        await message.answer(
            "❌ نام معتبر وارد کنید (حداقل 2 حرف).",
            reply_markup=_back_keyboard()
        )
        return

    chat_id = message.chat.id

    # ── Credit pre-check for paid models ─────────────────────────────────
    user_model = get_user_model(chat_id)
    if is_paid_model(user_model):
        balance = await get_credits(chat_id, user_model)
        if balance == 0:
            model_info = Config.PAID_MODELS[user_model]
            builder = InlineKeyboardBuilder()
            builder.button(
                text=f"🛒 خرید {model_info['emails_per_pack']} ایمیل — €{model_info['price_euros']}",
                callback_data=f"buy_credits:{user_model}",
            )
            builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
            builder.adjust(1)
            await message.answer(
                f"💳 <b>اعتبار ناکافی</b>\n\n"
                f"مدل انتخابی: <code>{user_model}</code>\n"
                f"موجودی: <b>0 ایمیل</b>\n\n"
                f"برای استفاده از این مدل، یک بسته "
                f"{model_info['emails_per_pack']} ایمیل به قیمت "
                f"€{model_info['price_euros']} بخرید.",
                parse_mode="HTML",
                reply_markup=builder.as_markup(),
            )
            await state.clear()
            return
    # ─────────────────────────────────────────────────────────────────────

    data = await state.get_data()
    records: List[Dict] = data['draft_records']
    context: str = data['draft_context']
    total_records: int = data['draft_total']

    await state.update_data(draft_sender_name=sender_name, draft_cached_emails={})

    # Show loading message
    loading_msg = await message.answer(
        f"⏳ <b>در حال تولید پیش‌نویس‌های صفحه ۱...</b>\n"
        f"لطفاً صبر کنید.",
        parse_mode="HTML"
    )

    # Generate first page only
    first_page_records = records[:EMAILS_PER_PAGE]
    first_page_emails = await generate_emails_for_records(first_page_records, context, sender_name, chat_id=message.chat.id)

    cached_emails = {0: first_page_emails}
    await state.update_data(draft_cached_emails=cached_emails)

    page_text = build_draft_page_text(cached_emails, 0, total_records)
    keyboard = build_draft_page_keyboard(0, total_records)

    if len(page_text) > 4000:
        page_text = page_text[:4000] + "\n\n... (truncated)"

    await loading_msg.edit_text(page_text, parse_mode="HTML", reply_markup=keyboard)


# ─────────────────────────────────────────────
# Pagination — navigate between pages (lazy generation)
# ─────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("draft_page:"))
async def navigate_draft_page(callback: CallbackQuery, state: FSMContext):
    """Handle pagination navigation — generates next page on demand."""
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid page.")
        return

    data = await state.get_data()
    records: Optional[List[Dict]] = data.get("draft_records")
    cached_emails: Optional[Dict] = data.get("draft_cached_emails")
    total_records: Optional[int] = data.get("draft_total")
    context: Optional[str] = data.get("draft_context")
    sender_name: Optional[str] = data.get("draft_sender_name")

    if not records or cached_emails is None or total_records is None:
        await callback.answer("Session expired. Please restart draft generation.")
        await callback.message.edit_text(
            "⚠️ Session expired. Please go back and start again.",
            parse_mode="HTML",
            reply_markup=_back_keyboard()
        )
        return

    total_pages = (total_records + EMAILS_PER_PAGE - 1) // EMAILS_PER_PAGE

    if page < 0 or page >= total_pages:
        await callback.answer("No more pages.")
        return

    # Generate this page if not cached yet
    if page not in cached_emails:
        await callback.message.edit_text(
            f"⏳ <b>در حال تولید پیش‌نویس‌های صفحه {page + 1}/{total_pages}...</b>\n"
            f"لطفاً صبر کنید.",
            parse_mode="HTML"
        )
        await callback.answer("Generating...")

        start = page * EMAILS_PER_PAGE
        end = start + EMAILS_PER_PAGE
        page_records = records[start:end]

        page_emails = await generate_emails_for_records(page_records, context, sender_name, chat_id=callback.message.chat.id)

        cached_emails[page] = page_emails
        await state.update_data(draft_cached_emails=cached_emails)
    else:
        await callback.answer()

    page_text = build_draft_page_text(cached_emails, page, total_records)
    keyboard = build_draft_page_keyboard(page, total_records)

    if len(page_text) > 4000:
        page_text = page_text[:4000] + "\n\n... (truncated)"

    await callback.message.edit_text(page_text, parse_mode="HTML", reply_markup=keyboard)


# ─────────────────────────────────────────────
# Update CSV — saves records per-user in DB
# sample_draft.csv is NEVER modified
# ─────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "update_csv")
async def start_update_csv(callback: CallbackQuery, state: FSMContext):
    chat_id = callback.message.chat.id
    user_records = await get_user_records(chat_id)
    current_info = (
        f"📂 شما در حال حاضر <b>{len(user_records)} رکورد شخصی</b> دارید."
        if user_records
        else "📋 در حال حاضر از <b>لیست پیش‌فرض</b> استفاده می‌شود."
    )

    await callback.message.edit_text(
        f"📁 <b>به‌روزرسانی لیست CSV:</b>\n\n"
        f"{current_info}\n\n"
        "فرمت مورد نیاز: <code>name,email,info,language</code>\n\n"
        "✅ <b>روش ۱:</b> فایل CSV با header آپلود کنید:\n"
        "<pre>name,email,info,language\n"
        "John Doe,john@eu.com,MEP,en\n"
        "Jane Smith,jane@bg.com,Bulgaria,bg</pre>\n\n"
        "📋 <b>روش ۲:</b> داده CSV بدون header paste کنید:\n"
        "<pre>John Doe,john@eu.com,MEP,en\n"
        "Jane Smith,jane@bg.com,Bulgaria,bg</pre>\n\n"
        "• <b>name</b>: نام کامل\n"
        "• <b>email</b>: آدرس ایمیل\n"
        "• <b>info</b>: موقعیت / حزب / توضیح (مثال: MEP, Bulgaria, Media)\n"
        "• <b>language</b>: زبان ایمیل — <code>en</code> یا <code>bg</code> (اختیاری، پیش‌فرض: en)\n\n"
        "حداکثر 300 رکورد.\n\n"
        "⚠️ <i>رکوردهای جدید فقط برای شما ذخیره می‌شوند.</i>",
        parse_mode="HTML"
    )
    await state.set_state(UpdateCsvStates.waiting_input)
    await callback.answer()


@router.message(UpdateCsvStates.waiting_input, F.document)
async def process_update_csv_upload(message: Message, state: FSMContext):
    file = message.document
    if not file.file_name.endswith('.csv'):
        await message.answer("❌ فقط فایل‌های CSV مجاز است.")
        return

    file_info = await message.bot.get_file(file.file_id)
    temp_path = os.path.join(tempfile.gettempdir(), f"update_csv_{message.chat.id}_{file.file_unique_id}.csv")

    await message.bot.download_file(file_info.file_path, temp_path)

    is_valid, msg, records = await validate_and_parse_csv(temp_path)
    os.unlink(temp_path)

    if not is_valid:
        await message.answer(f"❌ خطا: {msg}")
        return

    # Save records to DB for this user only — sample_draft.csv is untouched
    await save_user_records(message.chat.id, records)

    await message.answer(
        f"✅ لیست شخصی شما به‌روزرسانی شد! {len(records)} رکورد ذخیره شد.\n"
        f"از این پس Draft و Autosend از لیست شخصی شما استفاده می‌کنند.",
        reply_markup=get_start_keyboard()
    )
    await state.clear()


@router.message(UpdateCsvStates.waiting_input, F.text)
async def process_update_csv_text(message: Message, state: FSMContext):
    try:
        content = message.text.strip()
        if not content:
            await message.answer("❌ داده خالی است.")
            await state.clear()
            return

        # Parse as CSV without header — columns must match: name, email, info, language
        df = pd.read_csv(io.StringIO(content), header=None, names=['name', 'email', 'info', 'language'],
                         skipinitialspace=True)
        # Strip whitespace from all string columns to handle "name, email, info, lang" spacing
        for col in ['name', 'email', 'info']:
            df[col] = df[col].astype(str).str.strip()
        df['language'] = df['language'].fillna('en').astype(str).str.strip().str.lower()
        df.loc[~df['language'].isin(['en', 'bg']), 'language'] = 'en'

        # Create temp file for validation
        temp_buffer = io.StringIO()
        df.to_csv(temp_buffer, index=False)
        temp_buffer.seek(0)

        temp_path = os.path.join(tempfile.gettempdir(), f"text_csv_{message.chat.id}.csv")
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            await f.write(temp_buffer.getvalue())

        is_valid, msg, records = await validate_and_parse_csv(temp_path)
        os.unlink(temp_path)

        if not is_valid:
            await message.answer(f"❌ خطا: {msg}")
            return

        # Save records to DB for this user only — sample_draft.csv is untouched
        await save_user_records(message.chat.id, records)

        await message.answer(
            f"✅ لیست شخصی شما از متن به‌روزرسانی شد! {len(records)} رکورد ذخیره شد.\n"
            f"از این پس Draft و Autosend از لیست شخصی شما استفاده می‌کنند.",
            reply_markup=get_start_keyboard()
        )
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ خطا در پردازش: {str(e)}")
        await state.clear()
