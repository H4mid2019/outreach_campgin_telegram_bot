from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from keyboards.inline import get_start_keyboard
from states.states import GmailStates
from database.db import AsyncSessionLocal, User
from utils.crypto import CryptoManager
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data == "connect_gmail")
async def connect_gmail(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔗 <b>اتصال به Gmail:</b>\n\n"
        "1️⃣ ایمیل Gmail خود را ارسال کنید (مثال: user@gmail.com)\n"
        "2️⃣ رمز اپلیکیشن (App Password) 16 کاراکتری را وارد کنید\n\n"
        "<b>نکته مهم:</b>\n"
        "• 2FA را در حساب Google فعال کنید\n"
        "• به https://myaccount.google.com/apppasswords بروید\n"
        "• App Password جدید بسازید (Mail → Other)\n"
        "• فقط 16 کاراکتر را کپی کنید (بدون فاصله)",
        parse_mode="HTML",
    )
    await state.set_state(GmailStates.waiting_email)
    await callback.answer()


@router.callback_query(lambda c: c.data == "status")
async def status_callback(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)
        if user and user.gmail_email:
            try:
                await callback.message.edit_text(
                    f"✅ <b>متصل به:</b> <code>{user.gmail_email}</code>\n\n"
                    "برای قطع: /disconnect_gmail",
                    parse_mode="HTML",
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise
        else:
            try:
                from keyboards.inline import get_gmail_keyboard

                await callback.message.edit_text(
                    "❌ <b>Gmail متصل نیست.</b>",
                    parse_mode="HTML",
                    reply_markup=get_gmail_keyboard(),
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(lambda c: c.data == "disconnect_gmail")
async def disconnect_callback(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)
        if user:
            user.gmail_tokens = None
            user.gmail_email = None
            await session.commit()
            await callback.message.edit_text(
                "✅ اتصال قطع شد.", reply_markup=get_start_keyboard()
            )
        else:
            await callback.message.edit_text(
                "❌ خطا.", reply_markup=get_start_keyboard()
            )
    await callback.answer()


@router.callback_query(lambda c: c.data == "help")
async def help_callback(callback: CallbackQuery):
    from handlers.common import PERSIAN_WELCOME

    await callback.message.edit_text(PERSIAN_WELCOME, parse_mode="HTML")
    await callback.answer()


@router.message(GmailStates.waiting_email)
async def gmail_email_input(message: Message, state: FSMContext):
    email = message.text.strip().lower()
    if "@gmail.com" not in email or len(email) < 10:
        await message.answer("❌ ایمیل Gmail معتبر وارد کنید (مثال: user@gmail.com)")
        return

    await state.update_data(gmail_email=email)
    await message.answer(
        "🔑 <b>رمز اپلیکیشن را وارد کنید:</b>\nفقط 16 کاراکتر (بدون فاصله یا توضیح)",
        parse_mode="HTML",
    )
    await state.set_state(GmailStates.waiting_password)


@router.message(GmailStates.waiting_password)
async def gmail_password_input(message: Message, state: FSMContext):
    app_password = message.text.strip()
    if len(app_password) != 16 or not app_password.isalnum():
        await message.answer("❌ رمز اپلیکیشن 16 کاراکتر الفانومریک است.")
        return

    data = await state.get_data()
    gmail_email = data["gmail_email"]

    crypto = CryptoManager()
    encrypted_password = crypto.encrypt(app_password)

    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, chat_id)
        if not user:
            user = User(chat_id=chat_id)
            session.add(user)
        user.gmail_tokens = encrypted_password
        user.gmail_email = gmail_email
        await session.commit()

    await message.answer(
        f"✅ <b>اتصال Gmail موفق!</b>\n\n"
        f"📧 <code>{gmail_email}</code>\n"
        f"🔒 رمز اپلیکیشن ذخیره شد (رمز نگاری شده)\n\n"
        f"حالا می‌توانید ایمیل ارسال کنید! /status",
        parse_mode="HTML",
        reply_markup=get_start_keyboard(),
    )
    await state.clear()
