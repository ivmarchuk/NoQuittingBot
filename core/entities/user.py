"""User entity representing a single Telegram user of QuitSmokeBot."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(slots=True)
class User:
    telegram_id: int  # Telegram user id
    cigarettes_per_day: int
    cigarette_cost: float  # cost per single cigarette
    interval_minutes: int  # current interval between cigarettes
    last_interval_update: dt.datetime = field(default_factory=dt.datetime.utcnow)
    next_allowed_time: dt.datetime | None = None
    early_counter: int = 0  # number of consecutive early smokes
    spent: float = 0.0
    savings: float = 0.0
    hub_message_id: int | None = None

    # Delay suggestion tracking
    last_delay_offer: dt.datetime | None = None
    growth_pause_until: dt.date | None = None
    target_cigs_per_day: int | None = None
    days_success_streak: int = 0

    def update_interval(self, new_interval: int) -> None:
        self.interval_minutes = new_interval
        self.last_interval_update = dt.datetime.utcnow()

    @property
    def interval_timedelta(self) -> dt.timedelta:
        return dt.timedelta(minutes=self.interval_minutes) 