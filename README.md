# QuitSmokeBot

A Telegram bot that helps users gradually quit smoking by managing smoking intervals and tracking progress.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set your bot token:**
   ```bash
   export BOT_TOKEN="your_telegram_bot_token"
   ```

3. **Run the bot:**
   ```bash
   python -m no_quitting_bot
   ```

4. **Start using:**
   - Open Telegram and find your bot
   - Send `/start` to begin setup
   - Follow the interactive configuration

## Features

- **Smart intervals:** Gradually increases time between cigarettes
- **Progress tracking:** Monitor spending and savings in PLN
- **Weekly reports:** Automatic reports every Monday at 09:00 UTC
- **Alternative tasks:** Suggests activities when trying to smoke early

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot and setup |
| `/reset` | Reset all settings |

## Database

Data is stored in `no_quitting_bot.db` by default. Set `QS_DB_FILENAME` environment variable to change the path.

## Docker

```bash
docker build -t quitbot .
docker run -e BOT_TOKEN="your_token" quitbot
``` 