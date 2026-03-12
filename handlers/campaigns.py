"""
handlers/campaigns.py

Preset campaign management:
- /addcampaign command or "📋 مدیریت کمپین‌ها" button → key verification
- After key: add/update a campaign (name, description, target, email list CSV)
- Also: delete a campaign with key auth
- List all campaigns (no auth required — read-only)

Campaign name is the unique slug.  Submitting an existing name → UPDATE.
"""

import io
import os
import tempfile
import logging
import pandas as pd
import aiofiles

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from states.states import PresetCampaignStates
from keyboards.inline import get_start_keyboard, get_campaign_admin_keyboard, get_campaign_delete_keyboard
from database.db import get_all_campaigns, get_campaign_by_name, upsert_campaign, delete_campaign
from utils.csv_validator import validate_and_parse_csv

router = Router()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def _admin_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 بازگشت به مدیریت کمپین‌ها", callback_data="camp_admin:back")
    builder.adjust(1)
    return builder.as_markup()


def _format_campaign_list(campaigns: list) -> str:
    if not campaigns:
        return "📭 هیچ کمپین پیش‌تنظیمی وجود ندارد."
    lines = ["📋 <b>کمپین‌های پیش‌تنظیم:</b>\n"]
    for c in campaigns:
        lines.append(
            f"🔹 <b>{c['name']}</b>\n"
            f"   📝 {c['description']}\n"
            f"   🎯 هدف: <i>{c['target'][:80]}{'...' if len(c['target']) > 80 else ''}</i>\n"
            f"   👥 {len(c['email_list'])} ایمیل   🕒 {c['updated_at']}\n"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Entry: /addcampaign command or manage_campaigns button
# ─────────────────────────────────────────────

@router.message(F.text == "/addcampaign")
async def cmd_addcampaign(message: Message, state: FSMContext):
    await _enter_campaign_key(message, state, via="message")


@router.callback_query(lambda c: c.data == "manage_campaigns")
async def cb_manage_campaigns(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔐 <b>مدیریت کمپین‌های پیش‌تنظیم</b>\n\n"
        "برای ادامه کلید دسترسی را وارد کنید:",
        parse_mode="HTML",
        reply_markup=_back_keyboard()
    )
    await state.set_state(PresetCampaignStates.waiting_key)
    await state.update_data(camp_entry="manage")
    await callback.answer()


async def _enter_campaign_key(message: Message, state: FSMContext, via: str = "message"):
    await message.answer(
        "🔐 <b>مدیریت کمپین‌های پیش‌تنظیم</b>\n\n"
        "برای ادامه کلید دسترسی را وارد کنید:",
        parse_mode="HTML",
        reply_markup=_back_keyboard()
    )
    await state.set_state(PresetCampaignStates.waiting_key)
    await state.update_data(camp_entry="manage")


# ─────────────────────────────────────────────
# Key verification
# ─────────────────────────────────────────────

@router.message(PresetCampaignStates.waiting_key)
async def receive_campaign_key(message: Message, state: FSMContext):
    entered = message.text.strip()
    if entered != Config.CAMPAIGN_ACCESS_KEY:
        await message.answer(
            "❌ کلید نادرست است. دسترسی رد شد.",
            reply_markup=_back_keyboard()
        )
        await state.clear()
        return

    # Key verified — show admin panel
    await message.answer(
        "✅ <b>دسترسی تأیید شد.</b>\n\n"
        "عملیات مورد نظر را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=get_campaign_admin_keyboard()
    )
    await state.set_state(PresetCampaignStates.waiting_action)


# ─────────────────────────────────────────────
# Admin panel actions (after key verified)
# ─────────────────────────────────────────────

@router.callback_query(PresetCampaignStates.waiting_action, lambda c: c.data and c.data.startswith("camp_admin:"))
async def handle_admin_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "add":
        await callback.message.edit_text(
            "➕ <b>افزودن / به‌روزرسانی کمپین</b>\n\n"
            "نام کمپین (slug یکتا) را وارد کنید.\n"
            "اگر این نام از قبل وجود داشته باشد، کمپین <b>به‌روزرسانی</b> می‌شود.\n\n"
            "مثال: <code>eu-meps-2024</code> یا <code>climate-summit</code>\n"
            "• فقط حروف لاتین، اعداد، و خط تیره مجاز است\n"
            "• حداکثر 50 کاراکتر",
            parse_mode="HTML",
            reply_markup=_admin_back_keyboard()
        )
        await state.set_state(PresetCampaignStates.waiting_name)

    elif action == "delete":
        campaigns = await get_all_campaigns()
        if not campaigns:
            await callback.message.edit_text(
                "📭 هیچ کمپینی برای حذف وجود ندارد.",
                reply_markup=get_campaign_admin_keyboard()
            )
        else:
            await callback.message.edit_text(
                "🗑 <b>حذف کمپین</b>\n\nکمپین مورد نظر را انتخاب کنید:",
                parse_mode="HTML",
                reply_markup=get_campaign_delete_keyboard(campaigns)
            )
        await state.set_state(PresetCampaignStates.waiting_action)

    elif action == "list":
        campaigns = await get_all_campaigns()
        text = _format_campaign_list(campaigns)
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_campaign_admin_keyboard()
        )

    elif action == "back":
        await callback.message.edit_text(
            "⚙️ <b>پنل مدیریت کمپین‌ها</b>\n\nعملیات مورد نظر را انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=get_campaign_admin_keyboard()
        )

    await callback.answer()


# Also allow admin panel callbacks even outside waiting_action (e.g. after list)
@router.callback_query(lambda c: c.data and c.data.startswith("camp_admin:"))
async def handle_admin_action_anytime(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "back":
        current_state = await state.get_state()
        # Re-verify key is not needed here since state might still hold camp session
        await callback.message.edit_text(
            "⚙️ <b>پنل مدیریت کمپین‌ها</b>\n\nعملیات مورد نظر را انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=get_campaign_admin_keyboard()
        )
        await state.set_state(PresetCampaignStates.waiting_action)
    elif action == "list":
        campaigns = await get_all_campaigns()
        text = _format_campaign_list(campaigns)
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_campaign_admin_keyboard()
        )
        await state.set_state(PresetCampaignStates.waiting_action)
    elif action == "add":
        await callback.message.edit_text(
            "➕ <b>افزودن / به‌روزرسانی کمپین</b>\n\n"
            "نام کمپین (slug یکتا) را وارد کنید.\n"
            "اگر این نام از قبل وجود داشته باشد، کمپین <b>به‌روزرسانی</b> می‌شود.\n\n"
            "مثال: <code>eu-meps-2024</code> یا <code>climate-summit</code>\n"
            "• فقط حروف لاتین، اعداد، و خط تیره مجاز است\n"
            "• حداکثر 50 کاراکتر",
            parse_mode="HTML",
            reply_markup=_admin_back_keyboard()
        )
        await state.set_state(PresetCampaignStates.waiting_name)
    elif action == "delete":
        campaigns = await get_all_campaigns()
        if not campaigns:
            await callback.message.edit_text(
                "📭 هیچ کمپینی برای حذف وجود ندارد.",
                reply_markup=get_campaign_admin_keyboard()
            )
            await state.set_state(PresetCampaignStates.waiting_action)
        else:
            await callback.message.edit_text(
                "🗑 <b>حذف کمپین</b>\n\nکمپین مورد نظر را انتخاب کنید:",
                parse_mode="HTML",
                reply_markup=get_campaign_delete_keyboard(campaigns)
            )
            await state.set_state(PresetCampaignStates.waiting_action)

    await callback.answer()


# ─────────────────────────────────────────────
# Delete — confirm and execute
# ─────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("camp_delete_confirm:"))
async def confirm_delete_campaign(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split(":", 1)[1]
    campaign = await get_campaign_by_name(name)
    if not campaign:
        await callback.message.edit_text(
            f"⚠️ کمپین <b>{name}</b> یافت نشد.",
            parse_mode="HTML",
            reply_markup=get_campaign_admin_keyboard()
        )
        await state.set_state(PresetCampaignStates.waiting_action)
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ بله، حذف کن «{name}»", callback_data=f"camp_delete_yes:{name}")
    builder.button(text="❌ انصراف", callback_data="camp_admin:delete")
    builder.adjust(1)

    await callback.message.edit_text(
        f"⚠️ <b>آیا مطمئن هستید؟</b>\n\n"
        f"کمپین <b>{name}</b> با <b>{len(campaign['email_list'])}</b> ایمیل حذف خواهد شد.\n"
        f"این عمل قابل بازگشت نیست.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(PresetCampaignStates.waiting_delete_confirm)
    await callback.answer()


@router.callback_query(PresetCampaignStates.waiting_delete_confirm, lambda c: c.data and c.data.startswith("camp_delete_yes:"))
async def execute_delete_campaign(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split(":", 1)[1]
    deleted = await delete_campaign(name)
    if deleted:
        await callback.message.edit_text(
            f"✅ کمپین <b>{name}</b> با موفقیت حذف شد.",
            parse_mode="HTML",
            reply_markup=get_campaign_admin_keyboard()
        )
    else:
        await callback.message.edit_text(
            f"❌ کمپین <b>{name}</b> یافت نشد.",
            parse_mode="HTML",
            reply_markup=get_campaign_admin_keyboard()
        )
    await state.set_state(PresetCampaignStates.waiting_action)
    await callback.answer()


# ─────────────────────────────────────────────
# Add/Update Campaign — Step 1: Name
# ─────────────────────────────────────────────

@router.message(PresetCampaignStates.waiting_name)
async def receive_campaign_name(message: Message, state: FSMContext):
    import re
    name = message.text.strip().lower()

    if not re.match(r'^[a-z0-9\-_]{1,50}$', name):
        await message.answer(
            "❌ نام نامعتبر است.\n"
            "فقط حروف لاتین کوچک، اعداد، خط تیره (-) و زیرخط (_) مجاز است.\n"
            "حداکثر 50 کاراکتر.\n\n"
            "مثال: <code>eu-meps-2024</code>",
            parse_mode="HTML",
            reply_markup=_admin_back_keyboard()
        )
        return

    existing = await get_campaign_by_name(name)
    update_note = ""
    if existing:
        update_note = (
            f"\n\n⚠️ کمپین <b>{name}</b> از قبل وجود دارد.\n"
            f"ادامه دادن باعث <b>به‌روزرسانی</b> آن می‌شود."
        )

    await state.update_data(camp_name=name)
    await state.set_state(PresetCampaignStates.waiting_description)

    await message.answer(
        f"✅ نام: <code>{name}</code>{update_note}\n\n"
        "📝 <b>توضیح کوتاه کمپین را بنویسید:</b>\n"
        "این متن در لیست انتخاب کمپین نمایش داده می‌شود.\n"
        "مثال: <i>نامه‌نگاری به نمایندگان پارلمان اروپا درباره آب‌وهوا</i>",
        parse_mode="HTML",
        reply_markup=_admin_back_keyboard()
    )


# ─────────────────────────────────────────────
# Add/Update Campaign — Step 2: Description
# ─────────────────────────────────────────────

@router.message(PresetCampaignStates.waiting_description)
async def receive_campaign_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if len(description) < 3:
        await message.answer(
            "❌ توضیح خیلی کوتاه است (حداقل 3 کاراکتر).",
            reply_markup=_admin_back_keyboard()
        )
        return

    await state.update_data(camp_description=description)
    await state.set_state(PresetCampaignStates.waiting_target)

    await message.answer(
        "🎯 <b>هدف / زمینه کمپین را بنویسید:</b>\n"
        "این متن به عنوان context کمپین هنگام تولید ایمیل استفاده می‌شود.\n\n"
        "مثال:\n"
        "<i>Request for support on Climate Action Bill X. Formal tone. "
        "Highlight urgency and economic benefits for the constituency.</i>",
        parse_mode="HTML",
        reply_markup=_admin_back_keyboard()
    )


# ─────────────────────────────────────────────
# Add/Update Campaign — Step 3: Target/Context
# ─────────────────────────────────────────────

@router.message(PresetCampaignStates.waiting_target)
async def receive_campaign_target(message: Message, state: FSMContext):
    target = message.text.strip()
    if len(target) < 10:
        await message.answer(
            "❌ هدف کمپین خیلی کوتاه است (حداقل 10 کاراکتر).",
            reply_markup=_admin_back_keyboard()
        )
        return

    await state.update_data(camp_target=target)
    await state.set_state(PresetCampaignStates.waiting_email_list)

    await message.answer(
        "📧 <b>لیست ایمیل کمپین را ارسال کنید:</b>\n\n"
        "فرمت مورد نیاز: <code>name,email,info,language</code>\n\n"
        "✅ <b>روش ۱:</b> فایل CSV با header آپلود کنید:\n"
        "<pre>name,email,info,language\n"
        "John Doe,john@eu.com,MEP,en\n"
        "Jane Smith,jane@bg.com,Bulgaria,bg</pre>\n\n"
        "📋 <b>روش ۲:</b> داده CSV بدون header paste کنید:\n"
        "<pre>John Doe,john@eu.com,MEP,en\n"
        "Jane Smith,jane@bg.com,Bulgaria,bg</pre>\n\n"
        "• <b>language</b>: اختیاری، پیش‌فرض: en\n"
        "• حداکثر 300 رکورد",
        parse_mode="HTML",
        reply_markup=_admin_back_keyboard()
    )


# ─────────────────────────────────────────────
# Add/Update Campaign — Step 4a: Email list via file
# ─────────────────────────────────────────────

@router.message(PresetCampaignStates.waiting_email_list, F.document)
async def receive_campaign_email_list_file(message: Message, state: FSMContext):
    file = message.document
    if not file.file_name.endswith('.csv'):
        await message.answer("❌ فقط فایل‌های CSV مجاز است.", reply_markup=_admin_back_keyboard())
        return

    file_info = await message.bot.get_file(file.file_id)
    temp_path = os.path.join(tempfile.gettempdir(), f"camp_csv_{message.chat.id}_{file.file_unique_id}.csv")
    await message.bot.download_file(file_info.file_path, temp_path)

    is_valid, msg, records = await validate_and_parse_csv(temp_path)
    os.unlink(temp_path)

    if not is_valid:
        await message.answer(f"❌ خطای CSV: {msg}", reply_markup=_admin_back_keyboard())
        return

    await _save_campaign(message, state, records)


# ─────────────────────────────────────────────
# Add/Update Campaign — Step 4b: Email list via text
# ─────────────────────────────────────────────

@router.message(PresetCampaignStates.waiting_email_list, F.text)
async def receive_campaign_email_list_text(message: Message, state: FSMContext):
    try:
        content = message.text.strip()
        if not content:
            await message.answer("❌ داده خالی است.", reply_markup=_admin_back_keyboard())
            return

        df = pd.read_csv(
            io.StringIO(content),
            header=None,
            names=['name', 'email', 'info', 'language'],
            skipinitialspace=True
        )
        for col in ['name', 'email', 'info']:
            df[col] = df[col].astype(str).str.strip()
        df['language'] = df['language'].fillna('en').astype(str).str.strip().str.lower()
        df.loc[~df['language'].isin(['en', 'bg']), 'language'] = 'en'

        temp_path = os.path.join(tempfile.gettempdir(), f"camp_text_{message.chat.id}.csv")
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            buffer = io.StringIO()
            df.to_csv(buffer, index=False)
            await f.write(buffer.getvalue())

        is_valid, msg, records = await validate_and_parse_csv(temp_path)
        os.unlink(temp_path)

        if not is_valid:
            await message.answer(f"❌ خطای CSV: {msg}", reply_markup=_admin_back_keyboard())
            return

        await _save_campaign(message, state, records)

    except Exception as e:
        logger.error(f"Campaign email list parse error: {e}")
        await message.answer(f"❌ خطا در پردازش: {str(e)}", reply_markup=_admin_back_keyboard())


async def _save_campaign(message: Message, state: FSMContext, records: list):
    """Final step: save the campaign to DB."""
    data = await state.get_data()
    name = data.get("camp_name")
    description = data.get("camp_description", "")
    target = data.get("camp_target")

    was_created = await upsert_campaign(name, description, target, records)

    action_word = "✅ ایجاد شد" if was_created else "🔄 به‌روزرسانی شد"

    await message.answer(
        f"{action_word} کمپین <b>{name}</b>\n\n"
        f"📝 توضیح: {description}\n"
        f"🎯 هدف: <i>{target[:100]}{'...' if len(target) > 100 else ''}</i>\n"
        f"👥 تعداد ایمیل: <b>{len(records)}</b>",
        parse_mode="HTML",
        reply_markup=get_campaign_admin_keyboard()
    )
    await state.set_state(PresetCampaignStates.waiting_action)


# ─────────────────────────────────────────────
# Public: View campaign list (no auth)
# ─────────────────────────────────────────────

@router.message(F.text == "/campaigns")
async def cmd_list_campaigns(message: Message):
    campaigns = await get_all_campaigns()
    text = _format_campaign_list(campaigns)
    await message.answer(text, parse_mode="HTML", reply_markup=_back_keyboard())
