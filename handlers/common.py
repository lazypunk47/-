from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID, CHANNEL_ID
from database.db import (
    get_or_create_user,
    update_user_info,
    get_available_dates_for_month,
    get_available_slots_for_date,
    create_appointment,
    get_active_appointment_for_user,
    cancel_appointment,
)
from keyboards.main_menu import main_menu_kb
from keyboards.inline import (
    prices_message_html,
    portfolio_kb,
    subscription_kb,
    build_calendar,
    build_time_slots_kb,
)
from states.booking import BookingStates
from utils.scheduler import schedule_appointment_reminder, remove_reminder_job

router = Router()


# ---------- Вспомогательные функции ----------

async def check_subscription(bot: Bot, user_id: int) -> bool:
    """Проверка подписки через getChatMember."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ("member", "administrator", "creator"):
            return True
        return False
    except Exception:
        # Если произошла ошибка, считаем, что нет доступа
        return False


# ---------- Общие хендлеры ----------

@router.message(F.text == "/start")
async def cmd_start(message: Message, bot: Bot):
    user_name = message.from_user.first_name or message.from_user.username or "гость"
    await message.answer(
        f"💅<b>Здравствуйте, {user_name}!</b>\n\n"
        "Я бот-записи к мастеру по маникюру!\n"
        "Выберите нужный раздел в меню ниже.👇",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.message(F.text.contains("Прайсы"))
async def show_prices(message: Message):
    """Отправка прайса без FSM."""
    await message.answer(
        prices_message_html(),
        parse_mode="HTML",
    )


@router.message(F.text.contains("Портфолио"))
async def show_portfolio(message: Message):
    """Отправка кнопки с ссылкой на портфолио."""
    await message.answer(
        "📸<b>Портфолио работ:</b>",
        reply_markup=portfolio_kb(),
        parse_mode="HTML",
    )


# ---------- Запись клиента (FSM) ----------

@router.message(F.text.contains("Записаться"))
async def start_booking(message: Message, state: FSMContext, bot: Bot):
    """Старт записи: сначала проверка подписки."""
    is_sub = await check_subscription(bot, message.from_user.id)
    if not is_sub:
        await message.answer(
            "Для записи необходимо подписаться на канал",
            reply_markup=subscription_kb(),
        )
        return

    user_id = get_or_create_user(message.from_user.id)

    # Проверка, что нет активной записи
    from database.db import user_has_active_appointment
    if user_has_active_appointment(user_id):
        await message.answer(
            "У вас уже есть активная запись.\n"
            "Сначала отмените её, чтобы записаться на другую дату.",
            reply_markup=main_menu_kb(),
        )
        return

    today = datetime.today()
    available_dates = get_available_dates_for_month(today)

    if not available_dates:
        await message.answer(
            "К сожалению, на ближайший месяц свободных дат нет.\n"
            "Попробуйте позже.",
            reply_markup=main_menu_kb(),
        )
        return

    kb = build_calendar(today.year, today.month, available_dates)
    await message.answer(
        "Выберите дату для записи:",
        reply_markup=kb,
    )
    await state.set_state(BookingStates.choosing_date)


@router.callback_query(
    BookingStates.choosing_date,
    F.data.startswith("cal_") | (F.data == "cal_close") | (F.data == "ignore"),
)
async def ignore_calendar_navigation(callback: CallbackQuery, state: FSMContext):
    """Обработка навигации календаря и игнорируемых кнопок."""
    from database.db import get_available_dates_for_month

    data = callback.data
    if data == "cal_close":
        await callback.message.delete()
        await state.clear()
        await callback.answer()
        return

    if data.startswith("cal_prev_") or data.startswith("cal_next_"):
        _, direction, year, month = data.split("_")
        year = int(year)
        month = int(month)
        # Берём доступные даты снова
        from datetime import datetime as dt

        current_date = dt(year=year, month=month, day=1)
        available_dates = get_available_dates_for_month(current_date)
        kb = build_calendar(year, month, available_dates)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
        return

    if data == "ignore":
        await callback.answer()
        return


@router.callback_query(BookingStates.choosing_date, F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    """Пользователь выбрал дату."""
    date_str = callback.data.split("_", maxsplit=1)[1]

    slots = get_available_slots_for_date(date_str)
    if not slots:
        await callback.answer("На эту дату нет свободных слотов", show_alert=True)
        return

    await state.update_data(chosen_date=date_str)
    kb = build_time_slots_kb(slots)

    await callback.message.edit_text(
        f"Вы выбрали дату <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>.\n"
        "Теперь выберите время:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await state.set_state(BookingStates.choosing_time)
    await callback.answer()


@router.callback_query(BookingStates.choosing_time, F.data == "cancel_booking")
async def cancel_booking_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.answer()


@router.callback_query(BookingStates.choosing_time, F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    """Пользователь выбрал время слота."""
    slot_id = int(callback.data.split("_")[1])

    from database.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT date, time FROM time_slots WHERE id = ? AND is_available = 1",
        (slot_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        await callback.answer("Этот слот уже занят.", show_alert=True)
        return

    date_str = row["date"]
    time_str = row["time"]
    await state.update_data(slot_id=slot_id, chosen_time=time_str, chosen_date=date_str)

    await callback.message.edit_text(
        f"Вы выбрали:\n"
        f"Дата: <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
        f"Время: <b>{time_str}</b>\n\n"
        f"Теперь введите ваше <b>имя</b>:",
        parse_mode="HTML",
    )
    await state.set_state(BookingStates.entering_name)
    await callback.answer()


@router.message(BookingStates.entering_name)
async def enter_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer(
        "Введите ваш <b>номер телефона</b> (например, +79998887766):",
        parse_mode="HTML",
    )
    await state.set_state(BookingStates.entering_phone)


@router.message(BookingStates.entering_phone)
async def enter_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    data = await state.get_data()
    await state.update_data(phone=phone)

    date_str = data["chosen_date"]
    time_str = data["chosen_time"]
    name = data["name"]

    text = (
        "<b>Проверьте данные записи:</b>\n\n"
        f"Имя: <b>{name}</b>\n"
        f"Телефон: <b>{phone}</b>\n"
        f"Дата: <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
        f"Время: <b>{time_str}</b>\n\n"
        "Если всё верно, напишите <b>Да</b>.\n"
        "Чтобы отменить, напишите <b>Нет</b>."
    )

    await message.answer(text, parse_mode="HTML")
    await state.set_state(BookingStates.confirm)


@router.message(BookingStates.confirm, F.text.casefold() == "нет")
async def booking_confirm_no(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Запись отменена. Вы можете начать заново.",
        reply_markup=main_menu_kb(),
    )


@router.message(BookingStates.confirm)
async def booking_confirm_yes(message: Message, state: FSMContext, bot: Bot):
    if message.text.strip().lower() != "да":
        await message.answer("Напишите <b>Да</b> или <b>Нет</b>.", parse_mode="HTML")
        return

    data = await state.get_data()
    date_str = data["chosen_date"]
    time_str = data["chosen_time"]
    name = data["name"]
    phone = data["phone"]

    user_id = get_or_create_user(message.from_user.id)
    update_user_info(message.from_user.id, name, phone)

    appointment_id = create_appointment(user_id, date_str, time_str)
    if not appointment_id:
        await message.answer(
            "К сожалению, этот слот уже занят или у вас есть активная запись.\n"
            "Попробуйте выбрать другое время.",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return

    # Планируем напоминание
    from database.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT tg_id FROM users WHERE id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        user_tg_id = row["tg_id"]
        job_id = schedule_appointment_reminder(
            bot, appointment_id, user_tg_id, date_str, time_str
        )
        if job_id:
            from database.db import set_appointment_reminder_job
            set_appointment_reminder_job(appointment_id, job_id)

    # Сообщение клиенту
    await message.answer(
        "<b>Запись успешно создана!</b>\n\n"
        f"Дата: <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
        f"Время: <b>{time_str}</b>\n"
        f"Имя: <b>{name}</b>\n"
        f"Телефон: <b>{phone}</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )

    # Уведомление администратору
    await bot.send_message(
        ADMIN_ID,
        "<b>Новая запись!</b>\n\n"
        f"@{message.from_user.username or message.from_user.id}\n"
        f"Имя: <b>{name}</b>\n"
        f"Телефон: <b>{phone}</b>\n"
        f"Дата: <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
        f"Время: <b>{time_str}</b>",
        parse_mode="HTML",
    )

    await state.clear()


# ---------- Проверка подписки (кнопка) ----------

@router.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: CallbackQuery, bot: Bot):
    is_sub = await check_subscription(bot, callback.from_user.id)
    if is_sub:
        await callback.message.edit_text(
            "Спасибо за подписку! Теперь вы можете записаться через кнопку <b>Записаться</b> в главном меню.",
            parse_mode="HTML",
        )
    else:
        await callback.answer(
            "Подписка не обнаружена. Пожалуйста, подпишитесь и попробуйте снова.",
            show_alert=True,
        )


# ---------- Отмена записи пользователем ----------

@router.message(F.text.contains("Отменить запись"))
async def user_cancel_appointment(message: Message):
    user_id = get_or_create_user(message.from_user.id)
    appt = get_active_appointment_for_user(user_id)
    if not appt:
        await message.answer(
            "У вас нет активных записей.",
            reply_markup=main_menu_kb(),
        )
        return

    appointment_id = appt["id"]
    result = cancel_appointment(appointment_id)
    if not result:
        await message.answer(
            "Не удалось отменить запись. Попробуйте позже.",
            reply_markup=main_menu_kb(),
        )
        return

    _user_id, date_str, time_str, job_id = result
    if job_id:
        remove_reminder_job(job_id)

    await message.answer(
        "Ваша запись отменена.\n"
        f"Дата: <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
        f"Время: <b>{time_str}</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )