import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1001234567890"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Добавь его в переменные окружения Railway.")
