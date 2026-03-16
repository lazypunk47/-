from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from aiogram import Bot

from database.db import get_future_appointments, set_appointment_reminder_job
from config import ADMIN_ID


scheduler: Optional[AsyncIOScheduler] = None


def setup_scheduler() -> AsyncIOScheduler:
    """Создать и вернуть планировщик."""
    global scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    return scheduler


async def send_reminder(bot: Bot, user_tg_id: int, date_str: str, time_str: str):
    """Текст напоминания клиенту."""
    # Можно адаптировать под маникюр/ресницы
    text = (
        f"Напоминаем, что вы записаны на наращивание ресниц завтра в {time_str}.\n"
        f"Ждём вас ❤️"
    )
    await bot.send_message(user_tg_id, text)
    # Можно уведомить администратора при желании
    # await bot.send_message(ADMIN_ID, f"Отправлено напоминание {user_tg_id} на {date_str} {time_str}")


def schedule_appointment_reminder(
    bot: Bot,
    appointment_id: int,
    user_tg_id: int,
    date_str: str,
    time_str: str,
):
    """
    Запланировать напоминание за 24 часа.
    Возвращает job_id или None, если напоминание не нужно.
    """
    global scheduler
    if scheduler is None:
        return None

    visit_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    reminder_dt = visit_dt - timedelta(hours=24)
    now = datetime.utcnow()

    if reminder_dt <= now:
        # Визит менее чем через 24 часа – не создаём напоминание
        return None

    job_id = f"reminder_{appointment_id}"

    scheduler.add_job(
        send_reminder,
        trigger=DateTrigger(run_date=reminder_dt),
        args=(bot, user_tg_id, date_str, time_str),
        id=job_id,
        replace_existing=True,
    )
    return job_id


def remove_reminder_job(job_id: str):
    global scheduler
    if scheduler is None:
        return
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass


async def restore_reminders(bot: Bot):
    """
    Восстановление задач при старте бота.
    Стратегия: очищаем все задачи и пересоздаём по актуальным записям.
    """
    global scheduler
    if scheduler is None:
        return

    scheduler.remove_all_jobs()

    now = datetime.utcnow()
    rows = get_future_appointments()
    for a in rows:
        visit_dt = datetime.strptime(
            f"{a['date']} {a['time']}", "%Y-%m-%d %H:%M"
        )
        reminder_dt = visit_dt - timedelta(hours=24)
        if reminder_dt <= now:
            continue

        job_id = f"reminder_{a['id']}"
        scheduler.add_job(
            send_reminder,
            trigger=DateTrigger(run_date=reminder_dt),
            args=(bot, a["user_id"], a["date"], a["time"]),
            id=job_id,
            replace_existing=True,
        )
        # Обновляем job_id в БД
        set_appointment_reminder_job(a["id"], job_id)