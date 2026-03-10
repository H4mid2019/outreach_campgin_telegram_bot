from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.inline import get_start_keyboard, get_gmail_keyboard, get_disconnect_keyboard, get_model_keyboard
from database.db import AsyncSessionLocal, User
from utils.user_settings import (
    get_user_model, set_user_model, is_authorized_for_model_selection,
    authorize_user, validate_access_key
)
from states.states import AccessKeyStates
from config import Config
import logging

router = Router()
logger = logging.getLogger(__name__)

PERSIAN_WELCOME = """🤖 <b>به ربات ارسال ایمیل سیاسی هوشمند خوش آمدید!</b>

این ربات ایمیل‌های رسمی و شخصی‌سازی‌شده برای سیاستمداران (MPs بلغارستان) تولید و ارسال می‌کند.

📋 <b>گزینه‌ها:</b>
• 📝 <b>پیش‌نویس</b>: CSV آپلود → قالب → متن آماده کپی
• 🚀 <b>ارسال خودکار</b>: اتصال Gmail → CSV → زمینه → ارسال AI

⚠️ <b>نکات مهم:</b>
• CSV: name, email, company (party/position), language (en/bg)
• حداکثر 300 ردیف
• ایمیل‌ها: فقط en/bg، لحن بسیار رسمی

/start برای منو | /help راهنما | /status وضعیت | /disconnect_gmail قطع Gmail"""

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Clear any lingering state (e.g. access key flow) when user hits /start
    await state.clear()
    await message.answer(PERSIAN_WELCOME, parse_mode="HTML", reply_markup=get_start_keyboard())

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """ℹ️ <b>راهنما</b>

<b>CSV فرمت:</b>
<pre>name,email,company,language
John Doe,john@parliament.bg,MP GERB,en
Иван Иванов,ivan@parliament.bg,Minister BG,bg</pre>

<b>زمینه کمپین (فارسی):</b> "درخواست حمایت از طرح قانون محیط زیست، لحن رسمی"

<b>Gmail OAuth:</b>
1. /status چک کنید
2. "اتصال به Gmail" کلیک
3. لینک → اجازه → callback خودکار

<b>گزارش:</b> موفق/ناموفق + خطاها"""
    await message.answer(help_text, parse_mode="HTML")

@router.message(Command("status"))
async def cmd_status(message: Message):
    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)
        if user and user.gmail_email:
            status = f"✅ <b>متصل به Gmail:</b> <code>{user.gmail_email}</code>"
            markup = get_disconnect_keyboard()
        else:
            status = "❌ <b>Gmail متصل نیست.</b> اتصال کنید."
            markup = get_gmail_keyboard()
        await message.answer(status, parse_mode="HTML", reply_markup=markup)

@router.message(Command("disconnect_gmail"))
async def cmd_disconnect(message: Message):
    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)
        if user:
            user.gmail_tokens = None
            user.gmail_email = None
            await session.commit()
            await message.answer("✅ اتصال Gmail قطع شد.", reply_markup=get_start_keyboard())
        else:
            await message.answer("❌ کاربری یافت نشد.", reply_markup=get_start_keyboard())

@router.callback_query(F.data == "main_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    # Also clear any lingering state when returning to main menu
    await state.clear()
    await callback.message.edit_text(PERSIAN_WELCOME, parse_mode="HTML", reply_markup=get_start_keyboard())
    await callback.answer()


@router.callback_query(F.data == "change_model")
async def show_model_selection(callback: CallbackQuery, state: FSMContext):
    """Show the list of available AI models for the user to choose from."""
    chat_id = callback.message.chat.id
    current_model = get_user_model(chat_id)

    # Check if user is authorized to change models
    if not is_authorized_for_model_selection(chat_id):
        # Use FSM state to track "waiting for access key" — prevents catch-all interference
        await state.set_state(AccessKeyStates.waiting_key)
        await callback.message.edit_text(
            "🔐 <b>دسترسی محدود</b>\n\n"
            "برای تغییر مدل AI نیاز به کلید دسترسی دارید.\n"
            "لطفاً کلید دسترسی خود را وارد کنید:\n\n"
            "<i>برای لغو، /start را بزنید</i>",
            parse_mode="HTML"
        )
        await callback.answer("🔐 نیاز به کلید دسترسی", show_alert=True)
        return

    await callback.message.edit_text(
        "🤖 <b>انتخاب مدل هوش مصنوعی</b>\n\n"
        f"مدل فعلی: <code>{current_model}</code>\n\n"
        "یکی از مدل‌های زیر را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=get_model_keyboard(current_model)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_model:"))
async def handle_set_model(callback: CallbackQuery):
    """Save the user's chosen AI model."""
    chat_id = callback.message.chat.id
    chosen_model = callback.data.split("set_model:", 1)[1]

    # Check if user is authorized
    if not is_authorized_for_model_selection(chat_id):
        await callback.answer("🔐 شما مجاز به تغییر مدل نیستید.", show_alert=True)
        return

    if chosen_model not in Config.AVAILABLE_MODELS:
        await callback.answer("❌ مدل نامعتبر است.", show_alert=True)
        return

    set_user_model(chat_id, chosen_model)
    await callback.message.edit_text(
        f"✅ <b>مدل انتخاب شد:</b> <code>{chosen_model}</code>\n\n"
        "از این مدل برای تولید ایمیل‌های بعدی استفاده خواهد شد.",
        parse_mode="HTML",
        reply_markup=get_model_keyboard(chosen_model)
    )
    await callback.answer(f"✅ مدل تغییر یافت: {chosen_model}")


@router.message(AccessKeyStates.waiting_key)
async def handle_access_key_input(message: Message, state: FSMContext):
    """Handle access key input — only fires when user is in AccessKeyStates.waiting_key state."""
    chat_id = message.chat.id
    entered_key = message.text.strip()

    if validate_access_key(entered_key):
        # Authorize the user and clear the FSM state
        authorize_user(chat_id)
        await state.clear()

        current_model = get_user_model(chat_id)
        await message.answer(
            "✅ <b>کلید دسترسی تایید شد!</b>\n\n"
            "شما اکنون می‌توانید مدل AI را تغییر دهید.",
            parse_mode="HTML"
        )
        # Show model selection immediately
        await message.answer(
            "🤖 <b>انتخاب مدل هوش مصنوعی</b>\n\n"
            f"مدل فعلی: <code>{current_model}</code>\n\n"
            "یکی از مدل‌های زیر را انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=get_model_keyboard(current_model)
        )
    else:
        await state.clear()
        await message.answer(
            "❌ <b>کلید دسترسی نامعتبر است.</b>\n\n"
            "دسترسی شما رد شد. برای تلاش مجدد روی 'تغییر مدل AI' کلیک کنید.",
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
