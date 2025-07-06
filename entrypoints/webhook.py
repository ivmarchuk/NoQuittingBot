"""Webhook entrypoint for QuitSmokeBot (Render Free Web Service).

Render expects a web process that listens on PORT env var. We launch aiohttp web server that handles Telegram webhooks via aiogram 3 dispatcher.
"""
from __future__ import annotations

import os
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from no_quitting_bot.entrypoints import bot_main  # re-use configured dispatcher & scheduler

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env variable not set")

BASE_URL = os.getenv("BASE_URL")  # e.g. https://my-bot.onrender.com
if not BASE_URL:
    raise RuntimeError("BASE_URL env variable not set (Render -> Environment)" )

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "qsbotsecret")

bot: Bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp: Dispatcher = bot_main.dp  # same dispatcher with all handlers & scheduler

app = web.Application()

async def on_startup(app: web.Application):
    # Use render external URL
    await bot.set_webhook(f"{BASE_URL}/webhook", secret_token=WEBHOOK_SECRET)
    # start scheduled jobs (weekly report, adaptive growth, inactivity pings)
    if not bot_main.scheduler.running:
        bot_main.scheduler.start()
    logger.info("Webhook set and scheduler started")

async def on_cleanup(app: web.Application):
    await bot.delete_webhook()

# Register aiogram request handler
SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path="/webhook")

# Apply aiogram middlewares to aiohttp app
setup_application(app, dp, bot=bot)

app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port) 