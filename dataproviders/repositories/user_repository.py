"""SQLAlchemy implementation of AbstractUserRepository."""

from __future__ import annotations

import datetime as dt
from typing import List

from sqlalchemy import select

from no_quitting_bot.core.entities.user import User
from no_quitting_bot.core.interfaces.repositories.user_repo import AbstractUserRepository
from no_quitting_bot.dataproviders.db import session_scope
from no_quitting_bot.dataproviders.repositories._models import UserModel


class SqlAlchemyUserRepository(AbstractUserRepository):
    """SQLAlchemy-based user repository implementation."""

    def _to_entity(self, model: UserModel) -> User:
        return User(
            telegram_id=model.telegram_id,
            cigarettes_per_day=model.cigarettes_per_day,
            cigarette_cost=model.cigarette_cost,
            interval_minutes=model.interval_minutes,
            last_interval_update=model.last_interval_update,
            next_allowed_time=model.next_allowed_time,
            early_counter=model.early_counter,
            spent=model.spent,
            savings=model.savings,
            hub_message_id=model.hub_message_id,
            last_delay_offer=model.last_delay_offer,
            growth_pause_until=model.growth_pause_until.date() if model.growth_pause_until else None,
            target_cigs_per_day=model.target_cigs_per_day,
            days_success_streak=model.days_success_streak,
        )

    def _update_model(self, model: UserModel, entity: User) -> None:
        model.cigarettes_per_day = entity.cigarettes_per_day
        model.cigarette_cost = entity.cigarette_cost
        model.interval_minutes = entity.interval_minutes
        model.last_interval_update = entity.last_interval_update
        model.next_allowed_time = entity.next_allowed_time
        model.early_counter = entity.early_counter
        model.spent = entity.spent
        model.savings = entity.savings
        model.hub_message_id = entity.hub_message_id
        model.last_delay_offer = entity.last_delay_offer
        model.growth_pause_until = dt.datetime.combine(entity.growth_pause_until, dt.time()) if entity.growth_pause_until else None
        model.target_cigs_per_day = entity.target_cigs_per_day
        model.days_success_streak = entity.days_success_streak

    # ---------------------------------------------------------------------
    # Public methods
    # ---------------------------------------------------------------------

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        with session_scope() as session:
            model: UserModel | None = session.scalar(
                select(UserModel).where(UserModel.telegram_id == telegram_id)
            )
            if model:
                return self._to_entity(model)
            return None

    def add(self, user: User) -> None:
        with session_scope() as session:
            model = UserModel(
                telegram_id=user.telegram_id,
                cigarettes_per_day=user.cigarettes_per_day,
                cigarette_cost=user.cigarette_cost,
                interval_minutes=user.interval_minutes,
                last_interval_update=user.last_interval_update,
                next_allowed_time=user.next_allowed_time,
                early_counter=user.early_counter,
                spent=user.spent,
                savings=user.savings,
                hub_message_id=user.hub_message_id,
                last_delay_offer=user.last_delay_offer,
                growth_pause_until=dt.datetime.combine(user.growth_pause_until, dt.time()) if user.growth_pause_until else None,
                target_cigs_per_day=user.target_cigs_per_day,
                days_success_streak=user.days_success_streak,
            )
            session.add(model)

    def update(self, user: User) -> None:
        with session_scope() as session:
            model: UserModel | None = session.scalar(
                select(UserModel).where(UserModel.telegram_id == user.telegram_id)
            )
            if not model:
                raise ValueError("User not found")
            self._update_model(model, user)
            session.add(model)

    def list_all(self) -> List[User]:
        with session_scope() as session:
            models = session.scalars(select(UserModel)).all()
            return [self._to_entity(m) for m in models] 