from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
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


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Основная Reply клавиатура под строкой ввода"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📚 Повторить"),
                KeyboardButton(text="📖 Мои слова")
            ],
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="ℹ️ Помощь")
            ]
        ],
        resize_keyboard=True,
        persistent=True
    )


def get_words_list_keyboard(words: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Клавиатура со списком слов (пагинация)"""
    total_pages = (len(words) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_words = words[start_idx:end_idx]
    
    buttons = []
    for word in page_words:
        # Формируем текст кнопки: слово + краткий перевод
        translations = ", ".join(word.translations_ru[:1]) if word.translations_ru else "—"
        button_text = f"{word.term} — {translations}"
        if len(button_text) > 40:
            button_text = button_text[:37] + "..."
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"word_view_{word.id}"
        )])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"words_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"words_page_{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="words_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_word_detail_keyboard(word_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для детального просмотра слова с действиями"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Изучено", callback_data=f"word_learned_{word_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"word_edit_{word_id}")
        ],
        [
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"word_delete_{word_id}"),
            InlineKeyboardButton(text="🔄 Регенерировать", callback_data=f"word_regen_{word_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 К списку", callback_data="words_list")
        ]
    ])


def get_word_delete_confirm_keyboard(word_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"word_delete_confirm_{word_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"word_view_{word_id}")
        ]
    ])

