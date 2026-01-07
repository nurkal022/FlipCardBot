import logging
import random
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from bot.services.srs import get_words_for_review, update_review, create_review
from bot.db.models import get_word_by_id, get_user_words, get_random_user_words
from bot.keyboards.inline import (
    get_review_rating_keyboard,
    get_review_reveal_keyboard,
    get_quiz_keyboard,
    get_main_reply_keyboard
)

logger = logging.getLogger(__name__)
router = Router()

# Временное хранилище текущих тестов (word_id -> test_type)
_active_tests = {}


def format_review_card(word_data: dict, show_answer: bool = False) -> str:
    """Форматирует карточку для повторения"""
    lines = []
    
    if show_answer:
        lines.append(f"<b>{word_data['term']}</b>")
        if word_data.get('pos'):
            lines.append(f"<i>{word_data['pos']}</i>")
        if word_data.get('ipa') or word_data.get('reading_ru'):
            pronunciation = []
            if word_data.get('ipa'):
                pronunciation.append(word_data['ipa'])
            if word_data.get('reading_ru'):
                pronunciation.append(f"<i>{word_data['reading_ru']}</i>")
            lines.append(" / ".join(pronunciation))
        lines.append("")
    
    # Обработка translations_ru (может быть список или JSON строка)
    translations_ru = word_data.get('translations_ru')
    if translations_ru:
        if isinstance(translations_ru, str):
            translations = json.loads(translations_ru or "[]")
        else:
            translations = translations_ru
        if translations:
            lines.append(f"<b>Перевод:</b> {', '.join(translations)}")
    
    if word_data.get('definition_en'):
        lines.append(f"<b>Определение:</b> {word_data['definition_en']}")
    
    if show_answer and word_data.get('examples'):
        lines.append("")
        lines.append("<b>Примеры:</b>")
        examples_data = word_data.get('examples')
        if isinstance(examples_data, str):
            examples = json.loads(examples_data or "[]")
        else:
            examples = examples_data or []
        for i, example in enumerate(examples[:2], 1):
            if isinstance(example, dict):
                lines.append(f"{i}. {example.get('en', '')}")
                lines.append(f"   {example.get('ru', '')}")
    
    return "\n".join(lines) if lines else "Нет данных"


@router.message(Command("review"))
async def cmd_review(message: Message):
    """Обработка команды /review"""
    user_id = message.from_user.id
    
    words = await get_words_for_review(user_id, limit=10)
    
    if not words:
        await message.answer(
            "Нет слов для повторения. Добавь слова, чтобы начать изучение!",
            reply_markup=get_main_reply_keyboard()
        )
        return
    
    # Берём первое слово
    word_row = words[0]
    word_id = word_row['id']
    
    # Преобразуем row в word_data (JSON строки -> списки)
    word_data = {
        "id": word_id,
        "term": word_row['term'],
        "pos": word_row.get('pos'),
        "ipa": word_row.get('ipa'),
        "reading_ru": word_row.get('reading_ru'),
        "translations_ru": json.loads(word_row.get('translations_ru') or "[]"),
        "definition_en": word_row.get('definition_en'),
        "examples": json.loads(word_row.get('examples') or "[]")
    }
    
    # Определяем тип теста
    all_words = await get_user_words(user_id)
    test_type = None
    
    if len(all_words) >= 4:
        # 50/50 между Recall и Quiz
        test_type = random.choice(["recall", "quiz"])
    else:
        # Только Recall
        test_type = "recall"
    
    _active_tests[user_id] = {
        "word_id": word_id,
        "test_type": test_type,
        "words_queue": [w['id'] for w in words[1:]],  # Очередь остальных слов
        "correct_translation": None  # Для Quiz режима
    }
    
    await show_review_test(message, word_data, test_type)


async def show_review_test(message: Message, word_data: dict, test_type: str):
    """Показать тест (Recall или Quiz)"""
    user_id = message.from_user.id
    
    if test_type == "recall":
        # Recall: показываем перевод + определение, скрываем слово
        translations_ru = word_data.get('translations_ru')
        if isinstance(translations_ru, str):
            translations = json.loads(translations_ru or "[]")
        else:
            translations = translations_ru or []
        definition = word_data.get('definition_en', "")
        
        text = f"<b>Вспомни слово:</b>\n\n"
        if translations:
            text += f"<b>Перевод:</b> {', '.join(translations)}\n"
        if definition:
            text += f"<b>Определение:</b> {definition}"
        
        await message.answer(
            text,
            reply_markup=get_review_reveal_keyboard()
        )
    
    else:  # quiz
        # Quiz: показываем слово, предлагаем 4 варианта перевода
        word_id = word_data['id']
        translations_ru = word_data.get('translations_ru')
        if isinstance(translations_ru, str):
            translations = json.loads(translations_ru or "[]")
        else:
            translations = translations_ru or []
        correct_translation = translations[0] if translations else "Нет перевода"
        
        # Сохраняем правильный перевод в активном тесте
        if user_id in _active_tests:
            _active_tests[user_id]["correct_translation"] = correct_translation
        
        # Получаем 3 случайных перевода из других слов
        other_words = await get_random_user_words(user_id, limit=3, exclude_word_id=word_id)
        wrong_translations = []
        for other_word in other_words:
            if other_word.translations_ru:
                wrong_translations.append(other_word.translations_ru[0])
        
        # Если не хватило, добавляем заглушки
        while len(wrong_translations) < 3:
            wrong_translations.append("...")
        
        text = f"<b>Выбери правильный перевод:</b>\n\n<b>{word_data['term']}</b>"
        
        await message.answer(
            text,
            reply_markup=get_quiz_keyboard(word_id, correct_translation, wrong_translations[:3])
        )


@router.callback_query(F.data == "review_reveal")
async def handle_review_reveal(callback: CallbackQuery):
    """Показать ответ в Recall режиме"""
    user_id = callback.from_user.id
    
    if user_id not in _active_tests:
        await callback.answer("Тест не найден.", show_alert=True)
        return
    
    test_data = _active_tests[user_id]
    word_id = test_data["word_id"]
    
    word = await get_word_by_id(word_id)
    if not word:
        await callback.answer("Слово не найдено.", show_alert=True)
        return
    
    # Форматируем полную карточку (используем списки напрямую)
    word_dict = {
        "term": word.term,
        "pos": word.pos,
        "ipa": word.ipa,
        "reading_ru": word.reading_ru,
        "translations_ru": word.translations_ru,
        "definition_en": word.definition_en,
        "examples": word.examples
    }
    
    card_text = format_review_card(word_dict, show_answer=True)
    
    await callback.message.edit_text(
        card_text,
        reply_markup=get_review_rating_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.in_(["review_know", "review_hard", "review_dontknow"]))
async def handle_review_rating(callback: CallbackQuery):
    """Обработка оценки (Знаю/Сложно/Не знаю)"""
    user_id = callback.from_user.id
    
    if user_id not in _active_tests:
        await callback.answer("Тест не найден.", show_alert=True)
        return
    
    test_data = _active_tests[user_id]
    word_id = test_data["word_id"]
    result = callback.data.split("_")[1]  # know, hard, dontknow
    
    # Обновляем повторение
    await update_review(word_id, user_id, result)
    
    # Показываем следующее слово или завершаем
    words_queue = test_data.get("words_queue", [])
    
    if words_queue:
        # Берём следующее слово
        next_word_id = words_queue.pop(0)
        test_data["word_id"] = next_word_id
        test_data["words_queue"] = words_queue
        
        # Определяем тип теста для следующего слова
        all_words = await get_user_words(user_id)
        if len(all_words) >= 4:
            test_type = random.choice(["recall", "quiz"])
        else:
            test_type = "recall"
        
        test_data["test_type"] = test_type
        
        next_word = await get_word_by_id(next_word_id)
        if next_word:
            word_dict = {
                "id": next_word.id,
                "term": next_word.term,
                "pos": next_word.pos,
                "ipa": next_word.ipa,
                "reading_ru": next_word.reading_ru,
                "translations_ru": next_word.translations_ru,
                "definition_en": next_word.definition_en,
                "examples": next_word.examples
            }
            
            await callback.message.edit_text("Следующее слово...")
            await show_review_test(callback.message, word_dict, test_type)
        else:
            await callback.message.edit_text("✅ Повторение завершено!", reply_markup=None)
            await callback.message.answer(
                "Используй кнопки ниже для навигации 👇",
                reply_markup=get_main_reply_keyboard()
            )
            del _active_tests[user_id]
    else:
        await callback.message.edit_text("✅ Повторение завершено! Отлично поработал! 🎉", reply_markup=None)
        await callback.message.answer(
            "Используй кнопки ниже для навигации 👇",
            reply_markup=get_main_reply_keyboard()
        )
        del _active_tests[user_id]
    
    await callback.answer()


@router.callback_query(F.data.startswith("quiz_"))
async def handle_quiz_answer(callback: CallbackQuery):
    """Обработка ответа в Quiz режиме"""
    user_id = callback.from_user.id
    
    if user_id not in _active_tests:
        await callback.answer("Тест не найден.", show_alert=True)
        return
    
    # Парсим callback_data: quiz_{word_id}_{correct/wrong}
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    
    callback_word_id = int(parts[1])
    is_correct = parts[2] == "correct"
    
    test_data = _active_tests[user_id]
    word_id = test_data["word_id"]
    
    # Проверяем, что word_id совпадает
    if callback_word_id != word_id:
        await callback.answer("Неверный ответ.", show_alert=True)
        return
    
    result = "know" if is_correct else "dontknow"
    
    # Обновляем повторение
    await update_review(word_id, user_id, result)
    
    # Показываем результат
    word = await get_word_by_id(word_id)
    if word:
        translations = ", ".join(word.translations_ru) if word.translations_ru else "Нет перевода"
        
        if is_correct:
            feedback = "✅ Правильно!"
        else:
            feedback = "❌ Неправильно"
        
        text = f"{feedback}\n\n<b>{word.term}</b>\n<b>Перевод:</b> {translations}"
        
        # Показываем следующее слово или завершаем
        words_queue = test_data.get("words_queue", [])
        
        if words_queue:
            next_word_id = words_queue.pop(0)
            test_data["word_id"] = next_word_id
            test_data["words_queue"] = words_queue
            
            all_words = await get_user_words(user_id)
            if len(all_words) >= 4:
                test_type = random.choice(["recall", "quiz"])
            else:
                test_type = "recall"
            
            test_data["test_type"] = test_type
            
            next_word = await get_word_by_id(next_word_id)
            if next_word:
                word_dict = {
                    "id": next_word.id,
                    "term": next_word.term,
                    "pos": next_word.pos,
                    "ipa": next_word.ipa,
                    "reading_ru": next_word.reading_ru,
                    "translations_ru": next_word.translations_ru,
                    "definition_en": next_word.definition_en,
                    "examples": next_word.examples
                }
                
                await callback.message.edit_text(f"{text}\n\nСледующее слово...")
                await show_review_test(callback.message, word_dict, test_type)
            else:
                await callback.message.edit_text(f"{text}\n\n✅ Повторение завершено!", reply_markup=None)
                await callback.message.answer(
                    "Используй кнопки ниже для навигации 👇",
                    reply_markup=get_main_reply_keyboard()
                )
                del _active_tests[user_id]
        else:
            await callback.message.edit_text(f"{text}\n\n✅ Повторение завершено! Отлично поработал! 🎉", reply_markup=None)
            await callback.message.answer(
                "Используй кнопки ниже для навигации 👇",
                reply_markup=get_main_reply_keyboard()
            )
            del _active_tests[user_id]
    
    await callback.answer()


@router.message(F.text == "📚 Повторить")
async def handle_review_button(message: Message):
    """Обработка кнопки Повторить"""
    await cmd_review(message)

