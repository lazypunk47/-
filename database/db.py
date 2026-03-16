import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация структуры БД."""
    conn = get_connection()
    cur = conn.cursor()

    # Пользователи
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL,
            name TEXT,
            phone TEXT
        )
        """
    )

    # Рабочие дни
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS work_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,  -- формат YYYY-MM-DD
            is_open INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    # Тайм-слоты
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS time_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,         -- YYYY-MM-DD
            time TEXT NOT NULL,         -- HH:MM
            is_available INTEGER NOT NULL DEFAULT 1,
            UNIQUE(date, time)
        )
        """
    )

    # Записи
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,            -- YYYY-MM-DD
            time TEXT NOT NULL,            -- HH:MM
            status TEXT NOT NULL DEFAULT 'active', -- active / cancelled
            reminder_job_id TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, status)        -- один активный визит на пользователя
        )
        """
    )

    conn.commit()
    conn.close()


# ---------- Пользователи ----------

def get_or_create_user(tg_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    if row:
        user_id = row["id"]
    else:
        cur.execute("INSERT INTO users (tg_id) VALUES (?)", (tg_id,))
        user_id = cur.lastrowid
        conn.commit()
    conn.close()
    return user_id


def update_user_info(tg_id: int, name: str, phone: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET name = ?, phone = ? WHERE tg_id = ?",
        (name, phone, tg_id),
    )
    conn.commit()
    conn.close()


# ---------- Рабочие дни и слоты ----------

def add_work_day(date_str: str):
    """Добавить рабочий день (YYYY-MM-DD)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO work_days (date, is_open) VALUES (?, 1)",
        (date_str,),
    )
    conn.commit()
    conn.close()


def close_work_day(date_str: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE work_days SET is_open = 0 WHERE date = ?",
        (date_str,),
    )
    # Все слоты этого дня делаем недоступными
    cur.execute(
        "UPDATE time_slots SET is_available = 0 WHERE date = ?",
        (date_str,),
    )
    conn.commit()
    conn.close()


def add_time_slot(date_str: str, time_str: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO time_slots (date, time, is_available) VALUES (?, ?, 1)",
        (date_str, time_str),
    )
    conn.commit()
    conn.close()


def delete_time_slot(slot_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM time_slots WHERE id = ?", (slot_id,))
    conn.commit()
    conn.close()


def get_available_dates_for_month(start_date: datetime, months_ahead: int = 1) -> List[str]:
    """Получить даты со свободными слотами в диапазоне 1 месяц."""
    end_date = start_date + timedelta(days=31 * months_ahead)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT date FROM time_slots
        WHERE is_available = 1
          AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
    )
    rows = cur.fetchall()
    conn.close()
    return [r["date"] for r in rows]


def get_available_slots_for_date(date_str: str) -> List[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, time FROM time_slots
        WHERE date = ? AND is_available = 1
        ORDER BY time
        """,
        (date_str,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- Записи ----------

def user_has_active_appointment(user_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM appointments WHERE user_id = ? AND status = 'active'",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def create_appointment(
    user_id: int,
    date_str: str,
    time_str: str,
) -> Optional[int]:
    """Создать запись и пометить слот занятым. Вернуть id записи или None, если не получилось."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Проверка одного активного визита на пользователя
        cur.execute(
            "SELECT id FROM appointments WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        if cur.fetchone():
            conn.close()
            return None

        # Проверка свободного слота
        cur.execute(
            """
            SELECT id FROM time_slots
            WHERE date = ? AND time = ? AND is_available = 1
            """,
            (date_str, time_str),
        )
        slot_row = cur.fetchone()
        if not slot_row:
            conn.close()
            return None

        slot_id = slot_row["id"]

        # Бронируем слот и создаем запись
        cur.execute(
            "UPDATE time_slots SET is_available = 0 WHERE id = ?",
            (slot_id,),
        )
        cur.execute(
            """
            INSERT INTO appointments (user_id, date, time, status, created_at)
            VALUES (?, ?, ?, 'active', ?)
            """,
            (user_id, date_str, time_str, datetime.utcnow().isoformat()),
        )
        appointment_id = cur.lastrowid
        conn.commit()
        return appointment_id
    finally:
        conn.close()


def set_appointment_reminder_job(appointment_id: int, job_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE appointments SET reminder_job_id = ? WHERE id = ?",
        (job_id, appointment_id),
    )
    conn.commit()
    conn.close()


def cancel_appointment(appointment_id: int) -> Optional[Tuple[int, str, str, str]]:
    """
    Отменить запись, освободить слот.
    Возвращает (user_id, date, time, reminder_job_id) или None.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, date, time, reminder_job_id FROM appointments WHERE id = ? AND status = 'active'",
        (appointment_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    user_id, date_str, time_str, job_id = (
        row["user_id"],
        row["date"],
        row["time"],
        row["reminder_job_id"],
    )

    # Удаляем запись полностью, чтобы не нарушать UNIQUE(user_id, status)
    cur.execute(
        "DELETE FROM appointments WHERE id = ?",
        (appointment_id,),
    )
    # Освобождаем слот
    cur.execute(
        """
        UPDATE time_slots
        SET is_available = 1
        WHERE date = ? AND time = ?
        """,
        (date_str, time_str),
    )
    conn.commit()
    conn.close()
    return user_id, date_str, time_str, job_id


def get_active_appointment_for_user(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, date, time FROM appointments
        WHERE user_id = ? AND status = 'active'
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_future_appointments() -> List[sqlite3.Row]:
    """
    Получить все будущие активные записи для восстановления задач напоминаний.
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id, a.user_id, a.date, a.time, a.reminder_job_id
        FROM appointments a
        WHERE a.status = 'active'
        """,
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_appointments_for_date(date_str: str) -> List[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id, a.user_id, a.date, a.time, a.status, u.tg_id, u.name, u.phone
        FROM appointments a
        JOIN users u ON a.user_id = u.id
        WHERE a.date = ?
        ORDER BY a.time
        """,
        (date_str,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows