from datetime import datetime, timedelta
import calendar

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import CHANNEL_LINK


def prices_message_html() -> str:
    """HTML для прайса."""
    return (
        "💰<b>Прайс на услуги:</b>\n\n"
        "✨Френч — <b>1000₽</b>\n"
        "⬛Квадрат — <b>500₽</b>\n"
    )


def portfolio_kb() -> InlineKeyboardMarkup:
    """Кнопка на портфолио."""
    kb = [
        [
            InlineKeyboardButton(
                text="Смотреть портфолио",
                url="https://ru.pinterest.com/crystalwithluv/_created/",
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def subscription_kb() -> InlineKeyboardMarkup:
    """Кнопки проверки подписки на канал."""
    kb = [
        [
            InlineKeyboardButton(text="Подписаться", url=CHANNEL_LINK),
        ],
        [
            InlineKeyboardButton(text="Проверить подписку", callback_data="check_sub"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ----- Админ-панель -----

def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="Добавить рабочий день", callback_data="admin_add_day"),
        ],
        [
            InlineKeyboardButton(text="Добавить слот", callback_data="admin_add_slot"),
            InlineKeyboardButton(text="Удалить слот", callback_data="admin_delete_slot"),
        ],
        [
            InlineKeyboardButton(text="Отменить запись клиента", callback_data="admin_cancel_appointment"),
        ],
        [
            InlineKeyboardButton(text="Закрыть день", callback_data="admin_close_day"),
        ],
        [
            InlineKeyboardButton(text="Расписание на дату", callback_data="admin_view_schedule"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


########################
# Календарь (клиент)
########################

def build_calendar(year: int, month: int, available_dates: list[str]) -> InlineKeyboardMarkup:
    """
    Инлайн-календарь с подсветкой доступных дат для клиентов.
    available_dates: список строк 'YYYY-MM-DD'
    """
    kb: list[list[InlineKeyboardButton]] = []

    # Заголовок месяца
    kb.append(
        [
            InlineKeyboardButton(
                text=f"{calendar.month_name[month]} {year}",
                callback_data="ignore",
            )
        ]
    )

    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append([InlineKeyboardButton(text=d, callback_data="ignore") for d in week_days])

    cal = calendar.Calendar(firstweekday=0)
    date_set = set(available_dates)

    for week in cal.monthdatescalendar(year, month):
        row = []
        for day in week:
            if day.month != month:
                # Пустая кнопка
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_str = day.strftime("%Y-%m-%d")
                # Доступные даты отмечаем кружком
                if date_str in date_set:
                    text = f"{day.day}✅"
                    cb = f"date_{date_str}"
                else:
                    text = f"{day.day}"
                    cb = "ignore"
                row.append(InlineKeyboardButton(text=text, callback_data=cb))
        kb.append(row)

    # Навигация по месяцам
    prev_month = (datetime(year, month, 15) - timedelta(days=31))
    next_month = (datetime(year, month, 15) + timedelta(days=31))

    kb.append(
        [
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"cal_prev_{prev_month.year}_{prev_month.month}",
            ),
            InlineKeyboardButton(text="Закрыть", callback_data="cal_close"),
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"cal_next_{next_month.year}_{next_month.month}",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


########################
# Календарь (админ)
########################

def build_admin_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    """
    Календарь для админа: кликабельны все дни месяца.
    Используется для выбора даты, к которой нужно добавить слот.
    """
    kb: list[list[InlineKeyboardButton]] = []

    # Заголовок месяца
    kb.append(
        [
            InlineKeyboardButton(
                text=f"{calendar.month_name[month]} {year}",
                callback_data="ignore",
            )
        ]
    )

    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append([InlineKeyboardButton(text=d, callback_data="ignore") for d in week_days])

    cal = calendar.Calendar(firstweekday=0)

    for week in cal.monthdatescalendar(year, month):
        row = []
        for day in week:
            if day.month != month:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_str = day.strftime("%Y-%m-%d")
                text = f"{day.day}"
                cb = f"date_{date_str}"
                row.append(InlineKeyboardButton(text=text, callback_data=cb))
        kb.append(row)

    prev_month = (datetime(year, month, 15) - timedelta(days=31))
    next_month = (datetime(year, month, 15) + timedelta(days=31))

    kb.append(
        [
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"cal_prev_{prev_month.year}_{prev_month.month}",
            ),
            InlineKeyboardButton(text="Закрыть", callback_data="cal_close"),
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"cal_next_{next_month.year}_{next_month.month}",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_time_slots_kb(slots: list) -> InlineKeyboardMarkup:
    """Кнопки для выбора времени."""
    rows: list[list[InlineKeyboardButton]] = []
    for slot in slots:
        rows.append(
            [
                InlineKeyboardButton(
                    text=slot["time"],
                    callback_data=f"time_{slot['id']}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_booking")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_slots_kb(slots: list) -> InlineKeyboardMarkup:
    """Кнопки для админа (удаление слотов по id)."""
    rows = []
    for slot in slots:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{slot['time']}",
                    callback_data=f"admin_slot_{slot['id']}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="Назад", callback_data="admin_back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_appointments_kb(appointments: list) -> InlineKeyboardMarkup:
    rows = []
    for a in appointments:
        label = f"{a['time']} - {a['name'] or a['phone'] or a['tg_id']}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"admin_cancel_{a['id']}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="Назад", callback_data="admin_back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)