import os
from pathlib import Path
from dotenv import load_dotenv

# Путь к .env в папке проекта (рядом с config.py)
_env_path = Path(__file__).resolve().parent / ".env"
if not _env_path.exists():
    raise FileNotFoundError(f"Файл .env не найден: {_env_path}")
load_dotenv(dotenv_path=_env_path, override=True)

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")

# ID администратора (целое число)
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# Путь к базе данных
DB_PATH = os.getenv("DB_PATH", "database/bot.db")

# Настройки канала для проверки подписки
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1001234567890")  # например, -100xxxx
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/your_channel_link")