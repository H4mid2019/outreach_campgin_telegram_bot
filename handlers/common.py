from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.inline import (
    get_start_keyboard, get_gmail_keyboard, get_disconnect_keyboard,
    get_model_keyboard, get_buy_credits_keyboard,
)
from database.db import AsyncSessionLocal, User
from utils.user_settings import get_user_model, set_user_model
from utils.credits import get_all_credits, get_credits
from config import Config
import logging

router = Router()
logger = logging.getLogger(__name__)

PERSIAN_WELCOME = """🤖 <b>به ربات ارسال ایمیل سیاسی هوشمند خوش آمدید!</b>

این ربات ایمیل‌های رسمی و شخصی‌سازی‌شده برای سیاستمداران (MPs بلغارستان) تولید و ارسال می‌کند.

📋 <b>گزینه‌ها:</b>
• 📝 <b>پیش‌نویس</b>: CSV آپلود → قالب → متن آماده کپی
• 🚀 <b>ارسال خودکار</b>: اتصال Gmail → CSV → زمینه → ارسال AI
• 💳 <b>اعتبار و خرید</b>: خرید بسته ایمیل برای مدل‌های پولی

⚠️ <b>نکات مهم:</b>
• CSV: name, email, company (party/position), language (en/bg)
• حداکثر 300 ردیف
• ایمیل‌ها: فقط en/bg، لحن بسیار رسمی
• 💰 مدل‌های <b>Claude Sonnet 4.5</b> و <b>Claude Haiku 4.5</b> نیاز به خرید اعتبار دارند

/start برای منو | /help راهنما | /status وضعیت | /credits موجودی"""

@router.message(Command("start"))
async def cmd_start(message: Message):
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

<b>مدل‌های پولی:</b>
• Claude Sonnet 4.5 — €5 برای 25 ایمیل
• Claude Haiku 4.5 — €1 برای 25 ایمیل
→ /credits برای خرید و مشاهده موجودی

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
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(PERSIAN_WELCOME, parse_mode="HTML", reply_markup=get_start_keyboard())
    await callback.answer()


@router.callback_query(F.data == "change_model")
async def show_model_selection(callback: CallbackQuery):
    """Show the list of available AI models — paid ones display balance."""
    chat_id = callback.message.chat.id
    current_model = get_user_model(chat_id)
    credits_dict = await get_all_credits(chat_id)

    await callback.message.edit_text(
        "🤖 <b>انتخاب مدل هوش مصنوعی</b>\n\n"
        f"مدل فعلی: <code>{current_model}</code>\n\n"
        "💰 مدل‌های دارای علامت 💰 نیاز به اعتبار دارند.\n"
        "   قیمت: €5/25 ایمیل (Sonnet) | €1/25 ایمیل (Haiku)\n\n"
        "یکی از مدل‌های زیر را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=get_model_keyboard(current_model, credits_dict),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_model:"))
async def handle_set_model(callback: CallbackQuery):
    """Save the user's chosen AI model and handle paid-model credit check."""
    chat_id = callback.message.chat.id
    chosen_model = callback.data.split("set_model:", 1)[1]

    if chosen_model not in Config.AVAILABLE_MODELS:
        await callback.answer("❌ مدل نامعتبر است.", show_alert=True)
        return

    set_user_model(chat_id, chosen_model)
    credits_dict = await get_all_credits(chat_id)

    is_paid = chosen_model in Config.PAID_MODELS

    if is_paid:
        model_info = Config.PAID_MODELS[chosen_model]
        balance = credits_dict.get(chosen_model, 0)

        if balance == 0:
            status_line = (
                "⚠️ <b>اعتبار ندارید!</b> برای استفاده از این مدل اعتبار بخرید."
            )
        else:
            status_line = f"✅ <b>{balance} ایمیل</b> موجودی دارید."

        await callback.message.edit_text(
            f"✅ <b>مدل انتخاب شد:</b> <code>{chosen_model}</code>\n\n"
            f"💰 قیمت: €{model_info['price_euros']} برای {model_info['emails_per_pack']} ایمیل\n"
            f"💳 موجودی: <b>{balance} ایمیل</b>\n\n"
            f"{status_line}",
            parse_mode="HTML",
            reply_markup=get_buy_credits_keyboard(chosen_model),
        )
    else:
        await callback.message.edit_text(
            f"✅ <b>مدل انتخاب شد:</b> <code>{chosen_model}</code>\n\n"
            "از این مدل برای تولید ایمیل‌های بعدی استفاده خواهد شد.",
            parse_mode="HTML",
            reply_markup=get_model_keyboard(chosen_model, credits_dict),
        )

    await callback.answer(f"✅ مدل تغییر یافت: {chosen_model}")
