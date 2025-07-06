"""Repository interface for SmokingEvent entity."""

from __future__ import annotations

import abc
from typing import List, Protocol

from no_quitting_bot.core.entities.smoking_event import SmokingEvent


class AbstractSmokingEventRepository(Protocol):
    """Contract for persisting smoking events."""

    @abc.abstractmethod
    def add(self, event: SmokingEvent) -> None: ...

    @abc.abstractmethod
    def list_by_user(self, user_id: int, limit: int | None = None) -> List[SmokingEvent]: ...

    @abc.abstractmethod
    def delete(self, event_id: int) -> None: ...

    @abc.abstractmethod
    def get_last(self, user_id: int) -> SmokingEvent | None: ... 