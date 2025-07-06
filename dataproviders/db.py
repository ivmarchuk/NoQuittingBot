"""Database configuration and session management for QuitSmokeBot."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, DeclarativeBase
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Constants & Helpers
# ---------------------------------------------------------------------------
DB_FILENAME = os.getenv("QS_DB_FILENAME", "quit_smoke_bot.db")
DB_PATH = Path(DB_FILENAME).expanduser().absolute()

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# SQLite specific pragmas for better performance / safety
_engine_kwargs = {
    "connect_args": {"check_same_thread": False},  # needed for SQLite + threads
}

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False, future=True, **_engine_kwargs)

# Configure Session class
SessionLocal = scoped_session(sessionmaker(bind=engine, autocommit=False, autoflush=False))


class Base(DeclarativeBase):
    """Base class for declarative models."""


@contextmanager
def session_scope() -> Iterator[scoped_session]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# ---------------------------------------------------------------------------
# Simple migration helper (SQLite only)
# ---------------------------------------------------------------------------


def _add_column_if_missing(table: str, column_name: str, column_def: str) -> None:
    """Add column to SQLite table if it doesn't exist."""
    with engine.connect() as conn:
        cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        if column_name not in [c[1] for c in cols]:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_def}"))


def run_migrations() -> None:
    """Run simple migrations to add new columns if needed."""
    # Add water tracking columns
    _add_column_if_missing("users", "last_delay_offer", "DATETIME")
    _add_column_if_missing("users", "growth_pause_until", "DATETIME")
    _add_column_if_missing("users", "target_cigs_per_day", "INTEGER")
    _add_column_if_missing("users", "days_success_streak", "INTEGER DEFAULT 0")

    # Smoking events additions
    _add_column_if_missing("smoking_events", "via_bonus_token", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("smoking_events", "alternative_done", "BOOLEAN DEFAULT 0") 