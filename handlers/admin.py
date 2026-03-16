from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID
from database.db import (
    add_work_day,
    add_time_slot,
    close_work_day,
    get_available_slots_for_date,
    delete_time_slot,
    get_appointments_for_date,
    cancel_appointment,
)
from keyboards.inline import (
    admin_menu_kb,
    build_calendar,
    build_admin_calendar,
    build_admin_slots_kb,
    build_admin_appointments_kb,
)
from states.booking import AdminStates

router = Router()


def is_admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID


@router.message(F.text == "/admin")
async def admin_panel(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    await state.clear()
    await message.answer(
        "<b>Админ-панель</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.choosing_action)


# ---------- Обработка кнопок админ-панели ----------

@router.callback_query(AdminStates.choosing_action, F.data == "admin_add_day")
async def admin_add_day(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    await callback.message.edit_text(
        "Введите дату нового рабочего дня в формате <b>ДД.ММ.ГГГГ</b>:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.add_day_date)
    await callback.answer()


@router.message(AdminStates.add_day_date)
async def admin_add_day_date(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуйте ещё раз (ДД.ММ.ГГГГ).")
        return

    add_work_day(d.strftime("%Y-%m-%d"))
    await message.answer(
        "Рабочий день добавлен.",
        reply_markup=admin_menu_kb(),
    )
    await state.set_state(AdminStates.choosing_action)


@router.callback_query(AdminStates.choosing_action, F.data == "admin_add_slot")
async def admin_add_slot(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    today = datetime.today()
    # Для админа: можно выбрать ЛЮБУЮ дату месяца
    kb = build_admin_calendar(today.year, today.month)
    await callback.message.edit_text(
        "Выберите дату, для которой хотите добавить слот (или уже существующую рабочую дату):",
        reply_markup=kb,
    )
    await state.set_state(AdminStates.add_slot_date)
    await callback.answer()


@router.callback_query(AdminStates.add_slot_date, F.data.startswith("date_"))
async def admin_add_slot_date_chosen(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_", 1)[1]
    await state.update_data(add_slot_date=date_str)
    await callback.message.edit_text(
        f"Выбрана дата: <b>{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
        f"Введите время слота в формате <b>ЧЧ:ММ</b> (например, 10:00):",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.add_slot_time)
    await callback.answer()


@router.callback_query(
    AdminStates.add_slot_date,
    F.data.startswith("cal_") | (F.data == "cal_close") | (F.data == "ignore"),
)
async def admin_add_slot_calendar_navigation(callback: CallbackQuery, state: FSMContext):
    """
    Обработка навигации календаря при добавлении слота админом:
    стрелки месяцев, кнопка закрытия и "пустые" ячейки.
    """
    from database.db import get_available_dates_for_month

    data = callback.data

    # Закрыть календарь и вернуться в админ-меню
    if data == "cal_close":
        await callback.message.edit_text(
            "<b>Админ-панель</b>",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML",
        )
        await state.set_state(AdminStates.choosing_action)
        await callback.answer()
        return

    # Игнорируем клики по пустым ячейкам / заголовкам
    if data == "ignore":
        await callback.answer()
        return

    # Переключение месяца
    if data.startswith("cal_prev_") or data.startswith("cal_next_"):
        _, direction, year, month = data.split("_")
        year = int(year)
        month = int(month)

        from datetime import datetime as dt

        current_date = dt(year=year, month=month, day=1)
        available_dates = get_available_dates_for_month(current_date)
        kb = build_calendar(year, month, available_dates)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
        return


@router.message(AdminStates.add_slot_time)
async def admin_add_slot_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ.")
        return

    data = await state.get_data()
    date_str = data["add_slot_date"]

    # Добавляем рабочий день на всякий случай
    add_work_day(date_str)
    add_time_slot(date_str, time_str)

    await message.answer(
        "Слот добавлен.",
        reply_markup=admin_menu_kb(),
    )
    await state.set_state(AdminStates.choosing_action)


@router.callback_query(AdminStates.choosing_action, F.data == "admin_delete_slot")
async def admin_delete_slot(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    await callback.message.edit_text(
        "Введите дату, для которой хотите удалить слот, в формате <b>ДД.ММ.ГГГГ</b>:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.add_slot_date)  # переиспользуем состояние
    await callback.answer()


@router.message(AdminStates.add_slot_date)
async def admin_delete_slot_choose_date(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуйте ещё раз (ДД.ММ.ГГГГ).")
        return
    date_str = d.strftime("%Y-%m-%d")
    await state.update_data(delete_slot_date=date_str)

    slots = get_available_slots_for_date(date_str)
    if not slots:
        await message.answer(
            "На эту дату нет доступных слотов.",
            reply_markup=admin_menu_kb(),
        )
        await state.set_state(AdminStates.choosing_action)
        return

    kb = build_admin_slots_kb(slots)
    await message.answer(
        "Выберите слот для удаления:",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("admin_slot_"))
async def admin_delete_slot_confirm(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    slot_id = int(callback.data.split("_")[2])
    delete_time_slot(slot_id)
    await callback.message.edit_text(
        "Слот удалён.",
        reply_markup=admin_menu_kb(),
    )
    await state.set_state(AdminStates.choosing_action)
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back_handler(callback: CallbackQuery, state: FSMContext):
    """
    Общая кнопка 'Назад' из инлайн-меню (слоты, записи и т.п.)
    Возвращает в главное меню админа.
    """
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return

    await state.set_state(AdminStates.choosing_action)
    await callback.message.edit_text(
        "<b>Админ-панель</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_action, F.data == "admin_close_day")
async def admin_close_day(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    await callback.message.edit_text(
        "Введите дату, которую нужно полностью закрыть, в формате <b>ДД.ММ.ГГГГ</b>:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.close_day_date)
    await callback.answer()


@router.message(AdminStates.close_day_date)
async def admin_close_day_date(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуйте ещё раз (ДД.ММ.ГГГГ).")
        return
    date_str = d.strftime("%Y-%m-%d")

    from database.db import get_appointments_for_date
    from utils.scheduler import remove_reminder_job

    # Отмена всех записей на эту дату
    appointments = get_appointments_for_date(date_str)
    for a in appointments:
        if a["status"] == "active":
            res = cancel_appointment(a["id"])
            if res:
                _user_id, _d, _t, job_id = res
                if job_id:
                    remove_reminder_job(job_id)

    close_work_day(date_str)

    await message.answer(
        "День закрыт, все записи отменены.",
        reply_markup=admin_menu_kb(),
    )
    await state.set_state(AdminStates.choosing_action)


@router.callback_query(AdminStates.choosing_action, F.data == "admin_view_schedule")
async def admin_view_schedule(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    await callback.message.edit_text(
        "Введите дату для просмотра расписания в формате <b>ДД.ММ.ГГГГ</b>:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.view_schedule_date)
    await callback.answer()


@router.message(AdminStates.view_schedule_date)
async def admin_view_schedule_date(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуйте ещё раз (ДД.ММ.ГГГГ).")
        return
    date_str = d.strftime("%Y-%m-%d")

    appointments = get_appointments_for_date(date_str)
    if not appointments:
        await message.answer(
            "На эту дату записей нет.",
            reply_markup=admin_menu_kb(),
        )
        await state.set_state(AdminStates.choosing_action)
        return

    text_lines = [
        f"Расписание на {d.strftime('%d.%m.%Y')}:",
        "",
    ]
    for a in appointments:
        status = "✅" if a["status"] == "active" else "❌"
        text_lines.append(
            f"{status} {a['time']} — {a['name'] or a['phone'] or a['tg_id']}"
        )

    await message.answer(
        "\n".join(text_lines),
        reply_markup=admin_menu_kb(),
    )
    await state.set_state(AdminStates.choosing_action)


@router.callback_query(AdminStates.choosing_action, F.data == "admin_cancel_appointment")
async def admin_cancel_appointment(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    await callback.message.edit_text(
        "Введите дату, на которую нужно отменить запись клиента, в формате <b>ДД.ММ.ГГГГ</b>:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.cancel_appointment_date)
    await callback.answer()


@router.message(AdminStates.cancel_appointment_date)
async def admin_cancel_appointment_date(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуйте ещё раз (ДД.ММ.ГГГГ).")
        return
    date_str = d.strftime("%Y-%m-%d")
    await state.update_data(cancel_date=date_str)

    appointments = get_appointments_for_date(date_str)
    active = [a for a in appointments if a["status"] == "active"]
    if not active:
        await message.answer(
            "На эту дату нет активных записей.",
            reply_markup=admin_menu_kb(),
        )
        await state.set_state(AdminStates.choosing_action)
        return

    kb = build_admin_appointments_kb(active)
    await message.answer(
        "Выберите запись для отмены:",
        reply_markup=kb,
    )
    await state.set_state(AdminStates.cancel_appointment_choose)


@router.callback_query(AdminStates.cancel_appointment_choose, F.data.startswith("admin_cancel_"))
async def admin_cancel_appointment_choose(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    appointment_id = int(callback.data.split("_")[2])

    from utils.scheduler import remove_reminder_job

    res = cancel_appointment(appointment_id)
    if not res:
        await callback.answer("Не удалось отменить запись.", show_alert=True)
        return
    _user_id, date_str, time_str, job_id = res
    if job_id:
        remove_reminder_job(job_id)

    await callback.message.edit_text(
        f"Запись на {datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')} {time_str} отменена.",
        reply_markup=admin_menu_kb(),
    )
    await state.set_state(AdminStates.choosing_action)
    await callback.answer()