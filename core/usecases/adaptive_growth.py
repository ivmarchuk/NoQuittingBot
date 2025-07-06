"""Adaptive daily interval growth logic."""

from __future__ import annotations

import datetime as dt

from no_quitting_bot.core.interfaces.repositories.user_repo import AbstractUserRepository

MAX_INTERVAL_MINUTES = 12 * 60  # 12 hours


def execute(user_repo: AbstractUserRepository) -> None:
    """Adjust users' intervals based on success streaks."""
    today = dt.datetime.utcnow().date()
    users = user_repo.list_all()
    for user in users:
        # Skip if growth pause is active
        if user.growth_pause_until and today < user.growth_pause_until:
            continue

        # Clear pause flag if period ended
        if user.growth_pause_until and today >= user.growth_pause_until:
            user.growth_pause_until = None

        # Apply growth when streak threshold reached
        if user.days_success_streak >= 3:
            new_interval = int(user.interval_minutes * 1.15)
            new_interval = min(new_interval, MAX_INTERVAL_MINUTES)
            user.update_interval(new_interval)
            user.days_success_streak = 0

            # Optionally decrease target cigarettes per day
            if user.target_cigs_per_day and user.target_cigs_per_day > 1:
                threshold_minutes = (24 * 60) // (user.target_cigs_per_day - 1)
                if new_interval >= threshold_minutes:
                    user.target_cigs_per_day -= 1

        # Persist changes
        user_repo.update(user) 