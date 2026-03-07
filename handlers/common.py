from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.inline import get_start_keyboard, get_gmail_keyboard, get_disconnect_keyboard
from database.db import AsyncSessionLocal, User
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
