import logging
import httpx
import tempfile
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.filters import Command
from bot.services.dictionary import generate_word_card
from bot.services.srs import create_review
from bot.db.models import add_word, word_exists, get_word, update_word
from bot.keyboards.inline import (
    get_word_preview_keyboard,
    get_test_offer_keyboard,
    get_main_reply_keyboard
)

logger = logging.getLogger(__name__)
router = Router()

# Хранилище временных карточек (в продакшене лучше Redis)
_temp_cards = {}


def format_word_card(card_data: dict) -> str:
    """Форматирует карточку для отображения"""
    lines = [
        f"<b>{card_data['term']}</b>",
        ""
    ]
    
    if card_data.get('pos'):
        lines.append(f"<i>{card_data['pos']}</i>")
    
    if card_data.get('ipa') or card_data.get('reading_ru'):
        pronunciation = []
        if card_data.get('ipa'):
            pronunciation.append(card_data['ipa'])
        if card_data.get('reading_ru'):
            pronunciation.append(f"<i>{card_data['reading_ru']}</i>")
        lines.append(" / ".join(pronunciation))
    
    lines.append("")
    
    if card_data.get('translations_ru'):
        translations = ", ".join(card_data['translations_ru'])
        lines.append(f"<b>Перевод:</b> {translations}")
    
    if card_data.get('definition_en'):
        lines.append(f"<b>Определение:</b> {card_data['definition_en']}")
    
    if card_data.get('examples'):
        lines.append("")
        lines.append("<b>Примеры:</b>")
        for i, example in enumerate(card_data['examples'][:2], 1):
            lines.append(f"{i}. {example.get('en', '')}")
            lines.append(f"   {example.get('ru', '')}")
    
    return "\n".join(lines)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_word_input(message: Message):
    """Обработка ввода слова/фразы"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Проверяем, не является ли это кнопкой из Reply Keyboard
    if text in ["📚 Повторить", "📊 Статистика", "ℹ️ Помощь", "📖 Мои слова"]:
        return  # Эти кнопки обрабатываются в других handlers
    
    # Валидация: не слишком длинное
    if len(text) > 100:
        await message.answer(
            "Отправь одно слово или короткую фразу (до 100 символов).",
            reply_markup=get_main_reply_keyboard()
        )
        return
    
    # Показываем загрузку
    loading_msg = await message.answer("Ищу слово в словаре...")
    
    try:
        # Генерируем карточку через Dictionary API
        card_data = await generate_word_card(text)
        
        # Сохраняем во временное хранилище
        _temp_cards[user_id] = card_data
        
        # Форматируем текст карточки
        card_text = format_word_card(card_data)
        
        # Отправляем изображение, если есть
        if card_data.get('image_url'):
            try:
                await message.answer_photo(
                    photo=card_data['image_url'],
                    caption=card_text,
                    reply_markup=get_word_preview_keyboard()
                )
                await loading_msg.delete()
            except Exception as e:
                logger.warning(f"Could not send image: {e}")
                # Если не удалось отправить изображение, отправляем только текст
                await loading_msg.edit_text(
                    card_text,
                    reply_markup=get_word_preview_keyboard()
                )
        else:
            # Если нет изображения, отправляем только текст
            await loading_msg.edit_text(
                card_text,
                reply_markup=get_word_preview_keyboard()
            )
        
        # Отправляем аудио произношение как голосовое сообщение, если есть
        if card_data.get('audio_url'):
            try:
                # Скачиваем аудио файл
                async with httpx.AsyncClient(timeout=10.0) as client:
                    audio_response = await client.get(card_data['audio_url'])
                    audio_response.raise_for_status()
                    
                    # Сохраняем во временный файл
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                        tmp_file.write(audio_response.content)
                        tmp_path = tmp_file.name
                    
                    try:
                        # Отправляем как голосовое сообщение
                        with open(tmp_path, 'rb') as audio_file:
                            await message.answer_voice(
                                voice=InputFile(audio_file, filename="pronunciation.mp3"),
                                caption="🔊 Произношение"
                            )
                    finally:
                        # Удаляем временный файл
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Could not send audio as voice message: {e}")
                # Fallback: пробуем отправить по URL (может не работать для voice)
                try:
                    await message.answer_voice(
                        voice=card_data['audio_url'],
                        caption="🔊 Произношение"
                    )
                except Exception as e2:
                    logger.warning(f"Could not send audio by URL: {e2}")
        
    except ValueError as e:
        logger.error(f"Dictionary API error: {e}")
        await loading_msg.edit_text(
            f"Ошибка при поиске слова: {str(e)}\nПопробуй ещё раз.",
            reply_markup=get_main_reply_keyboard()
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        await loading_msg.edit_text(
            "Произошла ошибка. Попробуй позже.",
            reply_markup=get_main_reply_keyboard()
        )


@router.callback_query(F.data == "word_add")
async def handle_word_add(callback: CallbackQuery):
    """Обработка кнопки 'Добавить'"""
    user_id = callback.from_user.id
    
    if user_id not in _temp_cards:
        await callback.answer("Карточка не найдена. Начни заново.", show_alert=True)
        return
    
    card_data = _temp_cards[user_id]
    
    try:
        # Сохраняем в БД (или увеличиваем счётчик если уже есть)
        word_id, is_new = await add_word(
            user_id=user_id,
            term=card_data['term'],
            pos=card_data.get('pos'),
            ipa=card_data.get('ipa'),
            reading_ru=card_data.get('reading_ru'),
            translations_ru=card_data.get('translations_ru', []),
            definition_en=card_data.get('definition_en'),
            examples=card_data.get('examples', [])
        )
        
        # Получаем текущую частоту
        word = await get_word(user_id, card_data['term'])
        frequency = word.frequency if word else 1
        
        # Создаём запись для повторения только если слово новое
        if is_new:
            await create_review(word_id, user_id)
        
        # Удаляем из временного хранилища
        del _temp_cards[user_id]
        
        # Обновляем сообщение
        if is_new:
            message_text = f"✅ Слово <b>{card_data['term']}</b> добавлено!\n\nПроверим?"
            await callback.message.edit_text(
                message_text,
                reply_markup=get_test_offer_keyboard()
            )
        else:
            message_text = f"✅ Слово <b>{card_data['term']}</b> уже было добавлено.\n📊 Частота: <b>{frequency}</b> раз(а)"
            await callback.message.edit_text(
                message_text,
                reply_markup=get_main_reply_keyboard()
            )
        await callback.answer("Слово добавлено!" if is_new else f"Счётчик увеличен до {frequency}")
        
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error(f"Error adding word: {e}", exc_info=True)
        await callback.answer("Ошибка при сохранении.", show_alert=True)


@router.callback_query(F.data == "word_more_examples")
async def handle_more_examples(callback: CallbackQuery):
    """Обработка кнопки 'Ещё примеры' - регенерируем карточку"""
    user_id = callback.from_user.id
    
    if user_id not in _temp_cards:
        await callback.answer("Карточка не найдена.", show_alert=True)
        return
    
    term = _temp_cards[user_id]['term']
    
    await callback.message.edit_text("Ищу новые данные...")
    
    try:
        card_data = await generate_word_card(term)
        _temp_cards[user_id] = card_data
        
        card_text = format_word_card(card_data)
        
        # Обновляем сообщение с новыми данными
        # Если есть изображение, отправляем новое сообщение с фото
        if card_data.get('image_url'):
            try:
                await callback.message.answer_photo(
                    photo=card_data['image_url'],
                    caption=card_text,
                    reply_markup=get_word_preview_keyboard()
                )
                await callback.message.delete()
            except Exception as e:
                logger.warning(f"Could not send image: {e}")
                await callback.message.edit_text(
                    card_text,
                    reply_markup=get_word_preview_keyboard()
                )
        else:
            await callback.message.edit_text(
                card_text,
                reply_markup=get_word_preview_keyboard()
            )
        
        # Отправляем аудио как голосовое сообщение, если есть
        if card_data.get('audio_url'):
            try:
                # Скачиваем аудио файл
                async with httpx.AsyncClient(timeout=10.0) as client:
                    audio_response = await client.get(card_data['audio_url'])
                    audio_response.raise_for_status()
                    
                    # Сохраняем во временный файл
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                        tmp_file.write(audio_response.content)
                        tmp_path = tmp_file.name
                    
                    try:
                        # Отправляем как голосовое сообщение
                        with open(tmp_path, 'rb') as audio_file:
                            await callback.message.answer_voice(
                                voice=InputFile(audio_file, filename="pronunciation.mp3"),
                                caption="🔊 Произношение"
                            )
                    finally:
                        # Удаляем временный файл
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Could not send audio as voice message: {e}")
                # Fallback: пробуем отправить по URL
                try:
                    await callback.message.answer_voice(
                        voice=card_data['audio_url'],
                        caption="🔊 Произношение"
                    )
                except Exception as e2:
                    logger.warning(f"Could not send audio by URL: {e2}")
        
        await callback.answer("Новые данные готовы!")
        
    except Exception as e:
        logger.error(f"Error regenerating: {e}")
        await callback.message.edit_text("Ошибка при получении данных. Попробуй ещё раз.")


@router.callback_query(F.data == "word_cancel")
async def handle_word_cancel(callback: CallbackQuery):
    """Обработка кнопки 'Отмена'"""
    user_id = callback.from_user.id
    if user_id in _temp_cards:
        del _temp_cards[user_id]
    
    await callback.message.edit_text(
        "Отменено.",
        reply_markup=get_main_reply_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "word_update")
async def handle_word_update(callback: CallbackQuery):
    """Обработка кнопки 'Обновить' при дубликате"""
    user_id = callback.from_user.id
    # Извлекаем слово из сообщения (можно улучшить через FSM)
    text = callback.message.text
    
    # Простая логика: ищем слово в тексте
    # В реальности лучше хранить в callback_data или FSM
    await callback.message.edit_text("Генерирую обновлённую карточку...")
    
    # Здесь нужно извлечь term из сообщения или использовать FSM
    # Для MVP упростим: пользователь должен отправить слово заново
    await callback.message.edit_text(
        "Отправь слово заново, чтобы обновить карточку."
    )
    await callback.answer()


@router.callback_query(F.data.in_(["test_start", "test_later"]))
async def handle_test_offer(callback: CallbackQuery):
    """Обработка предложения теста после добавления"""
    if callback.data == "test_start":
        # Импортируем review handler для прямого вызова
        from bot.handlers.review import cmd_review
        await callback.answer("Начинаем повторение...")
        # Создаём Message объект для передачи в handler
        # В aiogram 3.x можно вызвать handler напрямую через message
        await callback.message.edit_text("Начинаем повторение...")
        # Вызываем review handler
        await cmd_review(callback.message)
    else:
        await callback.message.edit_text(
            "Хорошо, повторим позже.",
            reply_markup=get_main_reply_keyboard()
        )
        await callback.answer()

