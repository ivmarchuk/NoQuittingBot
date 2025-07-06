"""Use case for initial user setup."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from no_quitting_bot.core.entities.user import User
from no_quitting_bot.core.interfaces.repositories.user_repo import AbstractUserRepository

# Constants
MIN_INTERVAL_MINUTES = 20  # floor


def calculate_initial_interval(cigs_per_day: int) -> int:
    """Compute initial interval in minutes based on daily amount."""
    minutes_per_day = 24 * 60
    interval = minutes_per_day / max(cigs_per_day, 1)
    return max(int(interval), MIN_INTERVAL_MINUTES)


def execute(
    telegram_id: int,
    cigarettes_per_day: int,
    price_per_pack: float,
    cigarettes_per_pack: int,
    user_repo: AbstractUserRepository,
) -> User:
    """Initialize a user and persist. Returns created or existing User."""
    user = user_repo.get_by_telegram_id(telegram_id)
    if user:
        return user  # already initialized

    interval_minutes = calculate_initial_interval(cigarettes_per_day)
    price_per_cig = price_per_pack / cigarettes_per_pack

    now = datetime.utcnow()
    next_allowed = now  # allow immediately on first run

    user = User(
        telegram_id=telegram_id,
        cigarettes_per_day=cigarettes_per_day,
        cigarette_cost=price_per_cig,
        interval_minutes=interval_minutes,
        last_interval_update=now,
        next_allowed_time=next_allowed,
    )

    user_repo.add(user)
    return user 