"""Register smoking event and update user state."""

from __future__ import annotations

import datetime as dt

from quit_smoke_bot.core.entities.smoking_event import SmokingEvent
from quit_smoke_bot.core.interfaces.repositories.event_repo import AbstractSmokingEventRepository
from quit_smoke_bot.core.interfaces.repositories.user_repo import AbstractUserRepository

# Constants
# (фиксированный рост каждые 2 дня более не используется)
EARLY_THRESHOLD_SECONDS = 10 * 60  # 10 minutes window considered early
MAX_INTERVAL_MINUTES = 12 * 60  # 12 hours
MIN_INTERVAL_MINUTES = 20
EARLY_COUNTER_LIMIT = 3
EARLY_DECREASE_FACTOR = 0.95  # reduce 5%


def execute(
    telegram_id: int,
    user_repo: AbstractUserRepository,
    event_repo: AbstractSmokingEventRepository,
) -> SmokingEvent:
    user = user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise ValueError("User not initialized. Send /start first.")

    now = dt.datetime.utcnow()

    # Determine if early
    was_early = user.next_allowed_time is not None and now < user.next_allowed_time - dt.timedelta(seconds=EARLY_THRESHOLD_SECONDS)
    event = SmokingEvent(
        user_id=user.telegram_id,
        timestamp=now,
        planned_time=user.next_allowed_time or now,
        was_early=was_early,
        interval_before=user.interval_minutes,
    )

    # Finance update
    user.spent += user.cigarette_cost
    # savings: difference between plan vs actual where plan is 1 cigarette count but we can just 0 for now; advanced saving compute elsewhere.

    # Early smoke logic
    if was_early:
        user.early_counter += 1
        if user.early_counter >= EARLY_COUNTER_LIMIT:
            # reduce interval after several early smokes
            new_interval = int(user.interval_minutes * EARLY_DECREASE_FACTOR)
            user.update_interval(max(new_interval, MIN_INTERVAL_MINUTES))
            user.early_counter = 0

        # reset success streak and, starting from the second consecutive early smoke, pause further growth for 2 days
        user.days_success_streak = 0
        if user.early_counter >= 2:
            user.growth_pause_until = (dt.datetime.utcnow().date() + dt.timedelta(days=2))
    else:
        user.early_counter = 0
        # successful cigarette within plan – increase success streak
        user.days_success_streak += 1

    # (old 2-day auto-increase removed; adaptive growth handled by nightly task)

    # Update next allowed time
    user.next_allowed_time = now + dt.timedelta(minutes=user.interval_minutes)

    # Persist changes
    user_repo.update(user)
    event_repo.add(event)

    return event 