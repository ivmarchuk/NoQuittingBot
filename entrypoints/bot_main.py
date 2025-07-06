"""Entry point for QuitSmokeBot Telegram bot.

Usage:
    export BOT_TOKEN="<your_token>"
    python -m quit_smoke_bot.entrypoints.bot_main
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta
import datetime as dt
import random

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from quit_smoke_bot.core.interfaces.repositories.user_repo import AbstractUserRepository
from quit_smoke_bot.core.interfaces.repositories.event_repo import AbstractSmokingEventRepository
from quit_smoke_bot.dataproviders.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from quit_smoke_bot.dataproviders.repositories.event_repository import (
    SqlAlchemySmokingEventRepository,
)
from quit_smoke_bot.dataproviders.db import engine, Base
from quit_smoke_bot.core.usecases import (
    init_user as init_user_uc,
    can_smoke_now as can_smoke_now_uc,
    register_smoking_event as register_smoke_uc,
)

from quit_smoke_bot.core.entities.user import User
from quit_smoke_bot.utils import hub

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ---------------------------------------------------------------------------
# Configure logging & DB
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# Create DB tables
Base.metadata.create_all(bind=engine)

# Run simple migrations for new columns
from quit_smoke_bot.dataproviders.db import run_migrations

run_migrations()

# Repositories
user_repo: AbstractUserRepository = SqlAlchemyUserRepository()
event_repo: AbstractSmokingEventRepository = SqlAlchemySmokingEventRepository()

# Scheduler setup
scheduler = AsyncIOScheduler(timezone="UTC")

# ---------------------------------------------------------------------------
# Alternative task system (in-memory)
# ---------------------------------------------------------------------------
ALTERNATIVE_TASKS: list[str] = [
    "10 отжиманий",
    "2 мин дыхания по схеме 4-7-8",
]

# user_id → {"expires_at": datetime, "task": str}
PENDING_ALTERNATIVES: dict[int, dict[str, dt.datetime | str]] = {}

# Inactivity ping tracking (in-memory)
LAST_PING: dict[int, dt.datetime] = {}
INACTIVITY_HOURS = 12  # n часов молчания

# ---------------------------------------------------------------------------
# Weekly report job
# ---------------------------------------------------------------------------


async def send_weekly_reports() -> None:
    now = dt.datetime.utcnow()
    week_start = now - dt.timedelta(days=7)
    users = user_repo.list_all()
    for user in users:
        events = event_repo.list_by_user(user.telegram_id)
        events_last_week = [e for e in events if e.timestamp >= week_start]
        smoked = len(events_last_week)
        planned = user.cigarettes_per_day * 7
        not_smoked = max(planned - smoked, 0)
        cost_per_cig = user.cigarette_cost
        spent = smoked * cost_per_cig
        saved = not_smoked * cost_per_cig

        report_text = (
            "📅 Итоги недели:\n"
            f"Выкурено: {smoked} шт (−{not_smoked} от плана)\n"
            f"Потрачено: {spent:.2f} zł\n"
            f"Сэкономлено: {saved:.2f} zł"
        )

        try:
            await bot.send_message(chat_id=user.telegram_id, text=report_text)
        except Exception as e:
            logger.warning("Failed to send weekly report to %s: %s", user.telegram_id, e)


# ---------------------------------------------------------------------------
# Inactivity ping job
# ---------------------------------------------------------------------------

async def send_inactivity_pings() -> None:
    now = dt.datetime.utcnow()
    threshold = dt.timedelta(hours=INACTIVITY_HOURS)
    users = user_repo.list_all()
    for user in users:
        last_event = event_repo.get_last(user.telegram_id)
        if last_event:
            inactivity = now - last_event.timestamp
        else:
            inactivity = threshold + dt.timedelta(seconds=1)  # ensure ping if never smoked

        if inactivity < threshold:
            continue  # active recently

        # avoid duplicate pings within same threshold
        last_ping = LAST_PING.get(user.telegram_id)
        if last_ping and (now - last_ping) < threshold:
            continue

        avoided_cigs = int(inactivity.total_seconds() / 60 / max(user.interval_minutes, 1))
        saved = avoided_cigs * user.cigarette_cost

        text = (
            "👋 Маленький чек-ин!\n"
            f"Ты не заходил {INACTIVITY_HOURS}+ часов и уже сэкономил примерно {saved:.2f} zł. Продолжай в том же духе!"
        )
        try:
            await bot.send_message(chat_id=user.telegram_id, text=text)
            LAST_PING[user.telegram_id] = now
        except Exception as e:
            logger.warning("Failed to send inactivity ping to %s: %s", user.telegram_id, e)


# ---------------------------------------------------------------------------
# Adaptive growth daily job
# ---------------------------------------------------------------------------

async def run_adaptive_growth() -> None:
    from quit_smoke_bot.core.usecases import adaptive_growth as adaptive_growth_uc
    adaptive_growth_uc.execute(user_repo)


# ---------------------------------------------------------------------------
# Bot & Dispatcher
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env variable not set.")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ---------------------------------------------------------------------------
# FSM States
# ---------------------------------------------------------------------------


class SetupState(StatesGroup):
    cigarettes_per_day = State()
    price_per_pack = State()
    cigs_per_pack = State()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_timedelta(seconds: int) -> str:
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}ч {minutes:02d}мин"


# ---------------------------------------------------------------------------
# Hub refresh function
# ---------------------------------------------------------------------------


async def refresh_hub(user: User) -> None:
    """Create or update the single hub message for the user."""

    # Check for active alternative task
    alt = PENDING_ALTERNATIVES.get(user.telegram_id)
    now_dt = dt.datetime.utcnow()
    if alt and now_dt > alt["expires_at"]:
        # expired – remove
        PENDING_ALTERNATIVES.pop(user.telegram_id, None)
        alt = None

    if alt:
        text = (
            "💡 <b>Альтернатива:</b>\n"
            f"Сделай {alt['task']} за 2 мин"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Сделал", callback_data="ALT_DONE")],
                [InlineKeyboardButton(text="🚬 Курю сейчас", callback_data="SMOKE_NOW")],
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="REFRESH")],
            ]
        )
        try:
            if user.hub_message_id:
                await bot.edit_message_text(
                    chat_id=user.telegram_id,
                    message_id=user.hub_message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                )
            else:
                raise ValueError
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return
            sent = await bot.send_message(user.telegram_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            user.hub_message_id = sent.message_id
            user_repo.update(user)
        except Exception:
            sent = await bot.send_message(user.telegram_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            user.hub_message_id = sent.message_id
            user_repo.update(user)
        return

    # Compute whether user can smoke and seconds left
    can_smoke, seconds_left = can_smoke_now_uc.execute(user.telegram_id, user_repo)

    # Cigarette stats today
    today = dt.datetime.utcnow().date()
    events_today = [e for e in event_repo.list_by_user(user.telegram_id) if e.timestamp.date() == today]
    smoked_today = len(events_today)
    plan_today = user.cigarettes_per_day

    # Build message
    text = hub.build_hub_text(
        user=user,
        smoked_today=smoked_today,
        plan_today=plan_today,
        can_smoke=can_smoke,
        seconds_left=seconds_left,
    )

    last_event = event_repo.get_last(user.telegram_id)
    allow_undo = False
    if last_event and last_event.id is not None:
        if (dt.datetime.utcnow() - last_event.timestamp).total_seconds() <= 10*60:
            allow_undo = True

    # Клавиатура без функции задержки (+5 минут)
    keyboard = hub.build_hub_keyboard(can_smoke, allow_undo)

    # Редкое предложение подождать ещё 5-30 минут —
    # только когда до разрешённой сигареты осталось ≤ 10 мин.
    if (not can_smoke) and seconds_left is not None and 0 < seconds_left <= 300:
        if random.random() < 0.05:  # ~5 % шанс
            extra = random.choice([5, 10, 15, 20, 25, 30])
            last_offer = user.last_delay_offer or dt.datetime.min
            if (dt.datetime.utcnow() - last_offer).total_seconds() > 3 * 3600:  # не чаще раза в 3 ч
                await bot.send_message(
                    user.telegram_id,
                    f"🤔 Осталось всего {seconds_left // 60} мин. Может подождёшь ещё {extra} минут?"
                )
                user.last_delay_offer = dt.datetime.utcnow()
                user_repo.update(user)

    try:
        if user.hub_message_id:
            await bot.edit_message_text(
                chat_id=user.telegram_id,
                message_id=user.hub_message_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        else:
            raise ValueError
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return  # nothing to update
        # other bad request -> send new
        sent = await bot.send_message(user.telegram_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        user.hub_message_id = sent.message_id
        user_repo.update(user)
    except Exception:
        sent = await bot.send_message(user.telegram_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        user.hub_message_id = sent.message_id
        user_repo.update(user)


# ---------------------------------------------------------------------------
# In-memory helpers to track last message IDs (simple, per session)
# ---------------------------------------------------------------------------

LAST_CAN_MSG: dict[int, int] = {}
LAST_STATS_MSG: dict[int, int] = {}

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Greet new users and start onboarding if not configured."""
    user = user_repo.get_by_telegram_id(message.from_user.id)
    if user:
        await refresh_hub(user)
        return

    await state.set_state(SetupState.cigarettes_per_day)
    await message.answer("👋 Привет! Сколько сигарет в день ты обычно выкуриваешь?")


# ---------------------------------------------------------------------------
# Onboarding handlers
# ---------------------------------------------------------------------------


@dp.message(SetupState.cigarettes_per_day)
async def setup_cigs_per_day(message: Message, state: FSMContext) -> None:
    try:
        cigs_per_day = int(message.text)
        if cigs_per_day <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Пожалуйста, введи положительное целое число сигарет в день.")
        return

    await state.update_data(cigs_per_day=cigs_per_day)
    await state.set_state(SetupState.price_per_pack)
    await message.answer("Сколько стоит пачка сигарет (в zł)?")


@dp.message(SetupState.price_per_pack)
async def setup_price_per_pack(message: Message, state: FSMContext) -> None:
    try:
        price_per_pack = float(message.text.replace(",", "."))
        if price_per_pack <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Введи положительное число — цену пачки в злотых.")
        return

    await state.update_data(price_per_pack=price_per_pack)
    await state.set_state(SetupState.cigs_per_pack)
    await message.answer("Сколько сигарет в одной пачке?")


@dp.message(SetupState.cigs_per_pack)
async def setup_cigs_per_pack(message: Message, state: FSMContext) -> None:
    try:
        cigs_per_pack = int(message.text)
        if cigs_per_pack <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Введи положительное целое число сигарет в пачке.")
        return

    data = await state.get_data()
    user = init_user_uc.execute(
        telegram_id=message.from_user.id,
        cigarettes_per_day=data["cigs_per_day"],
        price_per_pack=data["price_per_pack"],
        cigarettes_per_pack=cigs_per_pack,
        user_repo=user_repo,
    )

    await state.clear()

    await message.answer("✅ Настройка завершена! Формирую твой личный хаб...")
    await refresh_hub(user)


@dp.message(Command("setup"))
async def cmd_setup(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 4:
        await message.reply("Неверный формат. Пример: /setup 20 180 20")
        return

    try:
        cigs_per_day = int(parts[1])
        price_per_pack = float(parts[2])
        cigs_per_pack = int(parts[3])
    except ValueError:
        await message.reply("Не получилось распознать числа. Попробуй ещё раз.")
        return

    user = init_user_uc.execute(
        telegram_id=message.from_user.id,
        cigarettes_per_day=cigs_per_day,
        price_per_pack=price_per_pack,
        cigarettes_per_pack=cigs_per_pack,
        user_repo=user_repo,
    )

    await message.reply(
        (
            "Настройка завершена ✅\n"
            f"Начальный интервал между сигаретами: {user.interval_minutes} минут.\n"
            "Чтобы узнать, можно ли курить — нажми /can"
        )
    )


@dp.message(F.text == "🚬 Можно курить?")
async def handle_can_button(message: Message) -> None:
    try:
        can_smoke, seconds_left = can_smoke_now_uc.execute(message.from_user.id, user_repo)
    except ValueError as exc:
        await message.reply(str(exc))
        return

    if can_smoke:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Курю сейчас", callback_data="SMOKE_NOW")]]
        )
        if mid := LAST_CAN_MSG.get(message.from_user.id):
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=mid,
                    text="✅ Можно курить!",
                    reply_markup=keyboard,
                )
            except Exception:
                mid = None  # fallthrough to send new

        if mid is None:
            sent = await message.reply("✅ Можно курить!", reply_markup=keyboard)
            LAST_CAN_MSG[message.from_user.id] = sent.message_id
    else:
        text = f"🚫 Рано. До следующей сигареты: {_format_timedelta(seconds_left)}"

        if mid := LAST_CAN_MSG.get(message.from_user.id):
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=mid,
                    text=text,
                )
            except Exception:
                mid = None
        if mid is None:
            sent = await message.reply(text)
            LAST_CAN_MSG[message.from_user.id] = sent.message_id


@dp.message(F.text == "📊 Статистика")
async def handle_stats_button(message: Message) -> None:
    user = user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.reply("Сначала настрой бота командой /start!")
        return

    initial_interval = int((24*60)/ max(user.cigarettes_per_day,1))
    progress_ratio = 1 - (user.interval_minutes / initial_interval)
    progress_ratio = max(0, min(progress_ratio, 1))
    total_blocks = 10
    filled = int(progress_ratio * total_blocks)
    bar = "🟩" * filled + "⬜" * (total_blocks - filled)

    text = (
        f"💵 Потрачено: {user.spent:.2f} zł\n"
        f"💰 Сэкономлено: {user.savings:.2f} zł\n"
        f"Текущий интервал: {user.interval_minutes} мин\n"
        f"Прогресс: {bar}"
    )

    if mid := LAST_STATS_MSG.get(message.from_user.id):
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=mid,
                text=text,
            )
            return
        except Exception:
            pass

    sent = await message.reply(text)
    LAST_STATS_MSG[message.from_user.id] = sent.message_id


@dp.callback_query(F.data == "SMOKE_NOW")
async def handle_smoke_now(callback: CallbackQuery) -> None:
    user = user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return

    now_dt = dt.datetime.utcnow()

    # If alternative pending
    alt = PENDING_ALTERNATIVES.get(user.telegram_id)
    if alt:
        if now_dt <= alt["expires_at"]:
            # relapse – early smoke
            register_smoke_uc.execute(
                telegram_id=user.telegram_id,
                user_repo=user_repo,
                event_repo=event_repo,
            )
            user_repo.update(user)
            PENDING_ALTERNATIVES.pop(user.telegram_id, None)
            await callback.answer("Срыв зафиксирован")
            await refresh_hub(user)
            return
        else:
            PENDING_ALTERNATIVES.pop(user.telegram_id, None)

    # Allowed?
    can_smoke, _ = can_smoke_now_uc.execute(user.telegram_id, user_repo)
    if can_smoke:
        register_smoke_uc.execute(
            telegram_id=user.telegram_id,
            user_repo=user_repo,
            event_repo=event_repo,
        )
        await callback.answer("Сигарета зафиксирована")
        await refresh_hub(user)
        return

    # Early attempt – propose alternative (токены/воля исключены)
    task_text = random.choice(ALTERNATIVE_TASKS)
    PENDING_ALTERNATIVES[user.telegram_id] = {
        "expires_at": now_dt + dt.timedelta(minutes=2),
        "task": task_text,
    }
    await callback.answer("Попробуй альтернативу 💪")
    await refresh_hub(user)


@dp.callback_query(F.data == "ALT_DONE")
async def handle_alt_done(callback: CallbackQuery) -> None:
    user = user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    alt = PENDING_ALTERNATIVES.get(user.telegram_id)
    now_dt = dt.datetime.utcnow()
    if not alt or now_dt > alt["expires_at"]:
        PENDING_ALTERNATIVES.pop(user.telegram_id, None)
        await callback.answer("Время вышло", show_alert=True)
        await refresh_hub(user)
        return

    # Success – просто сдвигаем разрешённое время на 3 минуты
    user.next_allowed_time = (user.next_allowed_time or now_dt) + dt.timedelta(minutes=3)
    user_repo.update(user)

    PENDING_ALTERNATIVES.pop(user.telegram_id, None)

    await callback.answer("Отлично!")
    await refresh_hub(user)


@dp.callback_query(F.data == "UNDO")
async def handle_undo(callback: CallbackQuery) -> None:
    from quit_smoke_bot.core.usecases import undo_last_event as undo_uc

    try:
        undo_uc.execute(callback.from_user.id, user_repo, event_repo)
        await callback.answer("Отменено")
    except Exception as exc:
        await callback.answer(str(exc), show_alert=True)

    user = user_repo.get_by_telegram_id(callback.from_user.id)
    if user:
        await refresh_hub(user)


# TOKEN_SMOKE и DELAY функциональности удалены


@dp.callback_query(F.data == "REFRESH")
async def handle_refresh(callback: CallbackQuery) -> None:
    user = user_repo.get_by_telegram_id(callback.from_user.id)
    if user:
        await refresh_hub(user)
    await callback.answer("Обновлено")


@dp.callback_query(F.data == "FAQ")
async def handle_faq(callback: CallbackQuery) -> None:
    text = (
        "ℹ️ <b>FAQ / Команды</b>\n"
        "• /start — запустить бота и показать хаб\n"
        "• /reset — сбросить все настройки\n\n"
        "В хабе доступны: \n"
        "🚬 Курю сейчас — фиксирует сигарету (если разрешено) \n"
        "🔄 Обновить — вручную обновить данные."
    )
    await callback.answer()
    await bot.send_message(callback.from_user.id, text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Reset command
# ---------------------------------------------------------------------------


@dp.message(Command("reset"))
@dp.message(F.text == "⚙️ Сброс")
async def cmd_reset(message: Message, state: FSMContext) -> None:
    """Delete user and restart onboarding."""
    existing = user_repo.get_by_telegram_id(message.from_user.id)
    if existing:
        # naive delete via direct session (simple for now)
        from quit_smoke_bot.dataproviders.db import session_scope
        from quit_smoke_bot.dataproviders.repositories._models import UserModel, SmokingEventModel
        from sqlalchemy import delete

        with session_scope() as session:
            session.execute(delete(SmokingEventModel).where(SmokingEventModel.user_id == existing.telegram_id))
            session.execute(delete(UserModel).where(UserModel.telegram_id == existing.telegram_id))

    await state.clear()
    await message.answer("⚠️ Настройки сброшены. Давай начнём заново! Сколько сигарет в день ты обычно выкуриваешь?")
    await state.set_state(SetupState.cigarettes_per_day)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _runner() -> None:
    """Async runner: start scheduler and polling concurrently."""
    # Scheduler must be started inside running loop
    scheduler.start()
    await dp.start_polling(bot)


def main() -> None:
    logger.info("Starting QuitSmokeBot...")

    # Schedule weekly reports: every Monday 09:00 UTC
    scheduler.add_job(send_weekly_reports, "cron", day_of_week="mon", hour=9, minute=0)
    # Daily adaptive growth task at 02:00 UTC
    scheduler.add_job(run_adaptive_growth, "cron", hour=2, minute=0)
    # Inactivity ping every hour
    scheduler.add_job(send_inactivity_pings, "cron", minute=0)

    asyncio.run(_runner())


if __name__ == "__main__":
    main() 