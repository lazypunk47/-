import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID
from database.db import init_db
from handlers.common import router as common_router
from handlers.admin import router as admin_router
from utils.scheduler import setup_scheduler, restore_reminders


async def main():
    # Проверка: в консоли видны ID из .env (если совпадают с вашими — всё подставилось верно)
    print(f"Config: ADMIN_ID={ADMIN_ID}, CHANNEL_ID={CHANNEL_ID}")

    # Инициализация БД
    init_db()

    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Роутеры
    dp.include_router(common_router)
    dp.include_router(admin_router)

    # Планировщик
    scheduler = setup_scheduler()
    scheduler.start()
    await restore_reminders(bot)

    # Запуск бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен.")