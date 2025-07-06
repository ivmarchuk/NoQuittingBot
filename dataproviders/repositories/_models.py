"""SQLAlchemy ORM models."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, Integer, Float, DateTime, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from no_quitting_bot.dataproviders.db import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    cigarettes_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    cigarette_cost: Mapped[float] = mapped_column(Float, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    last_interval_update: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    next_allowed_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    early_counter: Mapped[int] = mapped_column(Integer, default=0)
    spent: Mapped[float] = mapped_column(Float, default=0.0)
    savings: Mapped[float] = mapped_column(Float, default=0.0)
    hub_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_delay_offer: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    growth_pause_until: Mapped[dt.date | None] = mapped_column(DateTime, nullable=True)
    target_cigs_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_success_streak: Mapped[int] = mapped_column(Integer, default=0)


class SmokingEventModel(Base):
    __tablename__ = "smoking_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    planned_time: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    was_early: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_before: Mapped[int] = mapped_column(Integer, nullable=False)
    via_bonus_token: Mapped[bool] = mapped_column(Boolean, default=False)
    alternative_done: Mapped[bool] = mapped_column(Boolean, default=False) 