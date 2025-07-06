"""Undo the last smoking event if within allowed window."""

from __future__ import annotations

import datetime as dt

from no_quitting_bot.core.interfaces.repositories.event_repo import AbstractSmokingEventRepository
from no_quitting_bot.core.interfaces.repositories.user_repo import AbstractUserRepository

ALLOWED_MINUTES = 10


class CannotUndo(Exception):
    pass


def execute(telegram_id: int, user_repo: AbstractUserRepository, event_repo: AbstractSmokingEventRepository) -> None:
    user = user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise CannotUndo("Пользователь не найден")

    last_event = event_repo.get_last(telegram_id)
    if not last_event:
        raise CannotUndo("Нет события для отмены")

    now = dt.datetime.utcnow()
    if (now - last_event.timestamp).total_seconds() > ALLOWED_MINUTES * 60:
        raise CannotUndo("Слишком поздно отменять")

    # revert spent
    user.spent -= user.cigarette_cost
    user.spent = max(user.spent, 0)

    # restore next_allowed_time
    user.next_allowed_time = last_event.planned_time

    # persist changes to user before deleting event
    user_repo.update(user)

    if last_event.id is not None:
        event_repo.delete(last_event.id)
    else:
        raise CannotUndo("Невозможно отменить — не найден идентификатор события")
    # note: id not stored earlier; extend model? We'll not use id for now 