from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное меню пользователя."""
    kb = [
        [
            KeyboardButton(text="📅 Записаться"),
            KeyboardButton(text="❌ Отменить запись"),
        ],
        [
            KeyboardButton(text="💰 Прайсы"),
            KeyboardButton(text="📸 Портфолио"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True
    )