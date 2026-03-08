"""
Payment handlers for paid AI model credits.

Flow:
  1. User selects a paid model → sees balance + "Buy" button
  2. User taps "Buy" → bot sends a Telegram invoice (EUR)
  3. Telegram processes payment → pre_checkout_query → successful_payment
  4. Credits are added to user's DB balance
  5. User can now generate emails with the paid model

Commands:
  /credits — show current balance + buy buttons
"""

import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    LabeledPrice, PreCheckoutQuery,
)
from aiogram.enums import ContentType
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from utils.credits import add_credits, get_all_credits

router = Router()
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def _credits_text(all_credits: dict[str, int]) -> str:
    lines = ["💳 <b>موجودی اعتبار شما:</b>\n"]
    for model, balance in all_credits.items():
        info = Config.PAID_MODELS.get(model, {})
        label = info.get("label", model)
        icon = "✅" if balance > 0 else "❌"
        lines.append(f"{icon} {label}: <b>{balance} ایمیل</b>")
    return "\n".join(lines)


def _buy_keyboard(include_back: bool = True):
    builder = InlineKeyboardBuilder()
    for model, info in Config.PAID_MODELS.items():
        builder.button(
            text=(
                f"🛒 {info['label']}  —  "
                f"{info['emails_per_pack']} ایمیل  /  €{info['price_euros']}"
            ),
            callback_data=f"buy_credits:{model}",
        )
    if include_back:
        builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
# /credits command & show_credits callback
# ──────────────────────────────────────────────

@router.message(Command("credits"))
async def cmd_credits(message: Message):
    """Show credit balance and purchase options."""
    all_credits = await get_all_credits(message.chat.id)
    await message.answer(
        _credits_text(all_credits),
        parse_mode="HTML",
        reply_markup=_buy_keyboard(),
    )


@router.callback_query(F.data == "show_credits")
async def show_credits_callback(callback: CallbackQuery):
    all_credits = await get_all_credits(callback.message.chat.id)
    await callback.message.edit_text(
        _credits_text(all_credits),
        parse_mode="HTML",
        reply_markup=_buy_keyboard(),
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Buy credits — send Telegram invoice
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy_credits:"))
async def buy_credits_handler(callback: CallbackQuery):
    model = callback.data.split("buy_credits:", 1)[1]

    if model not in Config.PAID_MODELS:
        await callback.answer("❌ مدل نامعتبر.", show_alert=True)
        return

    if not Config.PAYMENT_PROVIDER_TOKEN:
        await callback.answer(
            "⚠️ درگاه پرداخت هنوز تنظیم نشده.\n"
            "لطفاً با ادمین تماس بگیرید تا PAYMENT_PROVIDER_TOKEN را تنظیم کند.",
            show_alert=True,
        )
        return

    info = Config.PAID_MODELS[model]
    label = info["label"]
    emails = info["emails_per_pack"]
    price_cents = info["price_cents"]
    price_euros = info["price_euros"]

    # payload encodes what to grant on successful payment
    payload = f"credits:{model}:{emails}"

    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"🤖 {label} — {emails} ایمیل",
        description=(
            f"بسته {emails} ایمیل با مدل {label}.\n"
            f"قیمت: €{price_euros} برای {emails} ایمیل."
        ),
        payload=payload,
        provider_token=Config.PAYMENT_PROVIDER_TOKEN,
        currency="EUR",
        prices=[
            LabeledPrice(
                label=f"{emails} ایمیل — {label}",
                amount=price_cents,
            )
        ],
        start_parameter=f"buy_{model.replace('/', '_').replace('-', '_').replace('.', '_')}",
        protect_content=False,
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Pre-checkout — always approve
# ──────────────────────────────────────────────

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


# ──────────────────────────────────────────────
# Successful payment — grant credits
# ──────────────────────────────────────────────

@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: Message):
    payload = message.successful_payment.invoice_payload
    logger.info(f"Successful payment from {message.chat.id}: {payload}")

    try:
        _, model, amount_str = payload.split(":", 2)
        amount = int(amount_str)
    except (ValueError, AttributeError, IndexError) as e:
        logger.error(f"Bad payment payload '{payload}': {e}")
        await message.answer("❌ خطا در پردازش پرداخت. لطفاً با ادمین تماس بگیرید.")
        return

    if model not in Config.PAID_MODELS:
        logger.error(f"Unknown model in payment payload: {model}")
        await message.answer("❌ مدل نامعتبر در پرداخت. لطفاً با ادمین تماس بگیرید.")
        return

    chat_id = message.chat.id
    new_total = await add_credits(chat_id, model, amount)
    model_info = Config.PAID_MODELS[model]

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)

    await message.answer(
        f"✅ <b>پرداخت موفق!</b>\n\n"
        f"🤖 مدل: <code>{model}</code>\n"
        f"📧 <b>{amount} ایمیل</b> به حساب شما اضافه شد\n"
        f"💳 موجودی جدید: <b>{new_total} ایمیل</b>\n\n"
        f"اکنون می‌توانید از پیش‌نویس یا ارسال خودکار با این مدل استفاده کنید.",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
