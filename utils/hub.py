"""Utilities to generate and update the single hub message."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from quit_smoke_bot.core.entities.user import User


def progress_bar(current: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return ""  # avoid div/zero
    filled = int((current / total) * length)
    filled = min(max(filled, 0), length)
    return "🟥" * filled + "⬜" * (length - filled)


def build_hub_text(
    user: User,
    smoked_today: int,
    plan_today: int,
    can_smoke: bool,
    seconds_left: Optional[int],
) -> str:
    lines: list[str] = ["🚭 <b>хаб</b>"]

    # Cigarettes progress
    bar = progress_bar(smoked_today, plan_today)
    lines.append(f"Сигареты сегодня: {smoked_today}/{plan_today}  {bar}")

    # Next cigarette info
    if can_smoke:
        lines.append("<b>Ну покури</b>")
    else:
        minutes = seconds_left // 60 if seconds_left else 0
        lines.append(f"🚫 До следующей сигареты: {minutes} мин")

    # Финансы, интервал и прогресс теперь основные метрики (токены/воля убраны)
    # lines.append(f"⏱️ Интервал: {user.interval_minutes} мин")
    # streak_target = 3
    # lines.append(f"Без срывов: {user.days_success_streak}/{streak_target} дней")

    # Finances
    lines.append(f"Потрачено: {user.spent:.2f} zł")
    lines.append(f"Сэкономлено: {user.savings:.2f} zł")

    return "\n".join(lines)


def build_hub_keyboard(can_smoke: bool, allow_undo: bool) -> InlineKeyboardMarkup:
    """Собираем клавиатуру без функции задержки (+5 минут)."""
    smoke_btn = InlineKeyboardButton(text="🚬 Курю сейчас", callback_data="SMOKE_NOW")

    row1 = [smoke_btn]
    if allow_undo:
        row1.append(InlineKeyboardButton(text="↩️ Отменить", callback_data="UNDO"))

    row2 = [
        InlineKeyboardButton(text="ℹ️ FAQ", callback_data="FAQ"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="REFRESH"),
    ]

    return InlineKeyboardMarkup(inline_keyboard=[row1, row2]) 