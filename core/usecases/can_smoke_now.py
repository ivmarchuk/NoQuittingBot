"""Use case to check if user can smoke now and seconds left."""

from __future__ import annotations

from datetime import datetime

from no_quitting_bot.core.interfaces.repositories.user_repo import AbstractUserRepository


def execute(telegram_id: int, user_repo: AbstractUserRepository) -> tuple[bool, int]:
    """Return (can_smoke, seconds_left)."""
    user = user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise ValueError("User not initialized. Send /start first.")

    now = datetime.utcnow()
    if user.next_allowed_time is None or now >= user.next_allowed_time:
        return True, 0

    seconds_left = int((user.next_allowed_time - now).total_seconds())
    return False, max(seconds_left, 0) 