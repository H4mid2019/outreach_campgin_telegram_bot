from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import Config
from typing import List, Dict


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 ساخت پیش‌نویس قابل کپی", callback_data="draft")
    builder.button(text="📁 لیست ایمیل شخصی", callback_data="update_csv")
    builder.button(text=" ارسال خودکار حرفه‌ای از Gmail", callback_data="autosend")
    builder.button(text="🤖 تغییر مدل AI", callback_data="change_model")
    builder.button(text="📋 مدیریت کمپین‌ها", callback_data="manage_campaigns")
    builder.button(text="ℹ️ راهنما", callback_data="help")
    builder.button(text="📊 وضعیت/اتصال به gmail", callback_data="status")
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


def get_model_keyboard(current_model: str) -> InlineKeyboardMarkup:
    """Model selection keyboard — marks the currently active model with ✅"""
    builder = InlineKeyboardBuilder()
    for model in Config.AVAILABLE_MODELS:
        label = f"✅ {model}" if model == current_model else model
        builder.button(text=label, callback_data=f"set_model:{model}")
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_preset_campaigns_keyboard(campaigns: List[Dict], mode: str) -> InlineKeyboardMarkup:
    """
    Shows a list of preset campaigns for selection during draft/autosend.
    mode = 'draft' or 'autosend'
    Also includes a "manual" option to skip preset and enter manually.
    """
    builder = InlineKeyboardBuilder()
    for campaign in campaigns:
        name = campaign["name"]
        desc = campaign["description"]
        count = len(campaign["email_list"])
        label = f"📌 {name} — {desc} ({count} emails)"
        builder.button(
            text=label,
            callback_data=f"select_campaign:{mode}:{name}"
        )
    builder.button(text="✏️ ورود دستی (بدون پیش‌تنظیم)", callback_data=f"campaign_manual:{mode}")
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_campaign_admin_keyboard() -> InlineKeyboardMarkup:
    """Admin keyboard for managing preset campaigns (after key verification)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ افزودن / به‌روزرسانی کمپین", callback_data="camp_admin:add")
    builder.button(text="🗑 حذف کمپین", callback_data="camp_admin:delete")
    builder.button(text="📋 لیست کمپین‌ها", callback_data="camp_admin:list")
    builder.button(text="🔙 بازگشت به منو", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_campaign_delete_keyboard(campaigns: List[Dict]) -> InlineKeyboardMarkup:
    """Shows campaigns with delete buttons."""
    builder = InlineKeyboardBuilder()
    for campaign in campaigns:
        name = campaign["name"]
        label = f"🗑 {name}"
        builder.button(text=label, callback_data=f"camp_delete_confirm:{name}")
    builder.button(text="🔙 بازگشت", callback_data="camp_admin:back")
    builder.adjust(1)
    return builder.as_markup()
