from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional


def get_word_preview_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для предпросмотра карточки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Добавить", callback_data="word_add"),
            InlineKeyboardButton(text="🔁 Ещё примеры", callback_data="word_more_examples")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="word_cancel")
        ]
    ])


def get_word_duplicate_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура при обнаружении дубликата"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Обновить", callback_data="word_update"),
            InlineKeyboardButton(text="❌ Нет", callback_data="word_cancel")
        ]
    ])


def get_review_rating_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оценки при повторении"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Знаю", callback_data="review_know"),
            InlineKeyboardButton(text="⚠️ Сложно", callback_data="review_hard")
        ],
        [
            InlineKeyboardButton(text="❌ Не знаю", callback_data="review_dontknow")
        ]
    ])


def get_review_reveal_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для Recall режима: показать ответ"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁️ Показать ответ", callback_data="review_reveal")
        ]
    ])


def get_quiz_keyboard(word_id: int, correct_translation: str, wrong_translations: List[str]) -> InlineKeyboardMarkup:
    """Клавиатура для Quiz режима: 4 варианта перевода"""
    import random
    
    # Смешиваем правильный и неправильные варианты
    options = [correct_translation] + wrong_translations
    random.shuffle(options)
    
    buttons = []
    for option in options:
        # Используем первые 50 символов для кнопки
        button_text = option[:50] + ("..." if len(option) > 50 else "")
        is_correct = option == correct_translation
        callback_data = f"quiz_{word_id}_{'correct' if is_correct else 'wrong'}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_test_offer_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после добавления слова: предложение теста"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="test_start"),
            InlineKeyboardButton(text="⏭️ Позже", callback_data="test_later")
        ]
    ])

