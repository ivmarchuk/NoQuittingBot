"""Abstract repository interface for User entity."""

from __future__ import annotations

import abc
from typing import Protocol, List

from no_quitting_bot.core.entities.user import User


class AbstractUserRepository(Protocol):
    """User repository contract."""

    @abc.abstractmethod
    def get_by_telegram_id(self, telegram_id: int) -> User | None: ...

    @abc.abstractmethod
    def add(self, user: User) -> None: ...

    @abc.abstractmethod
    def update(self, user: User) -> None: ...

    @abc.abstractmethod
    def list_all(self) -> List[User]: ... 