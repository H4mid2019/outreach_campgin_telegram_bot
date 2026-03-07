from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_start_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 ساخت پیش‌نویس قابل کپی", callback_data="draft")
    builder.button(text="📁 به‌روزرسانی لیست CSV", callback_data="update_csv")
    builder.button(text=" ارسال خودکار حرفه‌ای از Gmail", callback_data="autosend")
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