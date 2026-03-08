from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import Config


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 ساخت پیش‌نویس قابل کپی", callback_data="draft")
    builder.button(text="📁 به‌روزرسانی لیست CSV", callback_data="update_csv")
    builder.button(text=" ارسال خودکار حرفه‌ای از Gmail", callback_data="autosend")
    builder.button(text="🤖 تغییر مدل AI", callback_data="change_model")
    builder.button(text="💳 اعتبار و خرید", callback_data="show_credits")
    builder.button(text="ℹ️ راهنما", callback_data="help")
    builder.button(text="📊 وضعیت", callback_data="status")
    builder.adjust(1)
    return builder.as_markup()


def get_gmail_keyboard() -> InlineKeyboardMarkup:
    """Connect Gmail button"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 اتصال به Gmail", callback_data="connect_gmail")
    builder.adjust(1)
    return builder.as_markup()


def get_disconnect_keyboard() -> InlineKeyboardMarkup:
    """Disconnect Gmail"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ قطع اتصال Gmail", callback_data="disconnect_gmail")
    builder.button(text="🔙 بازگشت", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_model_keyboard(current_model: str, credits_dict: dict = None) -> InlineKeyboardMarkup:
    """
    Model selection keyboard.
    - Marks the active model with ✅
    - Marks paid models with 💰 and shows the user's balance
    credits_dict: {model_str: int}  — pass result of get_all_credits()
    """
    builder = InlineKeyboardBuilder()
    for model in Config.AVAILABLE_MODELS:
        is_current = model == current_model
        is_paid = model in Config.PAID_MODELS

        if is_paid:
            info = Config.PAID_MODELS[model]
            balance = (credits_dict or {}).get(model, 0)
            active = "✅ " if is_current else ""
            label = (
                f"{active}💰 {model}  |  "
                f"€{info['price_euros']}/25  |  "
                f"💳 {balance} ایمیل"
            )
        else:
            label = f"✅ {model}" if is_current else model

        builder.button(text=label, callback_data=f"set_model:{model}")

    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_buy_credits_keyboard(model: str) -> InlineKeyboardMarkup:
    """Keyboard shown when user selects a paid model with 0 credits."""
    info = Config.PAID_MODELS.get(model, {})
    builder = InlineKeyboardBuilder()
    builder.button(
        text=(
            f"🛒 خرید {info.get('emails_per_pack', 25)} ایمیل  —  "
            f"€{info.get('price_euros', '?')}"
        ),
        callback_data=f"buy_credits:{model}",
    )
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()
