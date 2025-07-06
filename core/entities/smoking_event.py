"""Domain event representing a single smoked cigarette."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(slots=True)
class SmokingEvent:
    user_id: int
    timestamp: dt.datetime
    planned_time: dt.datetime
    was_early: bool
    interval_before: int  # minutes
    via_bonus_token: bool = False
    alternative_done: bool = False
    id: int | None = None 