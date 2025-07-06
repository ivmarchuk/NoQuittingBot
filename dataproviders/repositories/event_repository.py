"""SQLAlchemy implementation of SmokingEvent repository."""

from __future__ import annotations

from typing import List

from sqlalchemy import select, delete

from quit_smoke_bot.core.entities.smoking_event import SmokingEvent
from quit_smoke_bot.core.interfaces.repositories.event_repo import (
    AbstractSmokingEventRepository,
)
from quit_smoke_bot.dataproviders.db import session_scope
from quit_smoke_bot.dataproviders.repositories._models import SmokingEventModel


class SqlAlchemySmokingEventRepository(AbstractSmokingEventRepository):
    """SQLAlchemy implementation for SmokingEvent repository."""

    def _to_entity(self, model: SmokingEventModel) -> SmokingEvent:
        return SmokingEvent(
            id=model.id,
            user_id=model.user_id,
            timestamp=model.timestamp,
            planned_time=model.planned_time,
            was_early=model.was_early,
            interval_before=model.interval_before,
            via_bonus_token=model.via_bonus_token,
            alternative_done=model.alternative_done,
        )

    def add(self, event: SmokingEvent) -> None:
        with session_scope() as session:
            model = SmokingEventModel(
                user_id=event.user_id,
                timestamp=event.timestamp,
                planned_time=event.planned_time,
                was_early=event.was_early,
                interval_before=event.interval_before,
                via_bonus_token=event.via_bonus_token,
                alternative_done=event.alternative_done,
            )
            session.add(model)
            session.flush()
            event.id = model.id

    def list_by_user(self, user_id: int, limit: int | None = None) -> List[SmokingEvent]:
        with session_scope() as session:
            stmt = select(SmokingEventModel).where(SmokingEventModel.user_id == user_id).order_by(
                SmokingEventModel.timestamp.desc()
            )
            if limit:
                stmt = stmt.limit(limit)
            models = session.scalars(stmt).all()
            return [self._to_entity(m) for m in models]

    def delete(self, event_id: int) -> None:
        with session_scope() as session:
            session.execute(delete(SmokingEventModel).where(SmokingEventModel.id == event_id))

    def get_last(self, user_id: int) -> SmokingEvent | None:
        with session_scope() as session:
            model = session.scalar(
                select(SmokingEventModel)
                .where(SmokingEventModel.user_id == user_id)
                .order_by(SmokingEventModel.timestamp.desc())
            )
            return self._to_entity(model) if model else None 