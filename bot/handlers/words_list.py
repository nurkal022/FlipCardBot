import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from bot.db.models import get_user_words, get_word_by_id, delete_word, mark_word_as_learned
from bot.services.ai import generate_word_card
from bot.db.models import update_word
from bot.keyboards.inline import (
    get_main_reply_keyboard,
    get_words_list_keyboard,
    get_word_detail_keyboard,
    get_word_delete_confirm_keyboard
)

logger = logging.getLogger(__name__)
router = Router()

# Хранилище текущих страниц для каждого пользователя
_words_pages = {}


def format_word_detail(word) -> str:
    """Форматирует детальную карточку слова"""
    lines = [
        f"<b>{word.term}</b>",
        ""
    ]
    
    if word.pos:
        lines.append(f"<i>{word.pos}</i>")
    
    if word.ipa or word.reading_ru:
        pronunciation = []
        if word.ipa:
            pronunciation.append(word.ipa)
        if word.reading_ru:
            pronunciation.append(f"<i>{word.reading_ru}</i>")
        lines.append(" / ".join(pronunciation))
    
    lines.append("")
    
    if word.translations_ru:
        translations = ", ".join(word.translations_ru)
        lines.append(f"<b>Перевод:</b> {translations}")
    
    if word.definition_en:
        lines.append(f"<b>Определение:</b> {word.definition_en}")
    
    if word.examples:
        lines.append("")
        lines.append("<b>Примеры:</b>")
        for i, example in enumerate(word.examples[:2], 1):
            lines.append(f"{i}. {example.get('en', '')}")
            lines.append(f"   {example.get('ru', '')}")
    
    if word.frequency > 1:
        lines.append("")
        lines.append(f"📊 Частота: {word.frequency} раз(а)")
    
    return "\n".join(lines)


@router.message(Command("words"))
async def cmd_words(message: Message):
    """Показать все слова пользователя"""
    await show_words_list(message)


@router.message(F.text == "📖 Мои слова")
async def handle_words_button(message: Message):
    """Обработка кнопки Мои слова"""
    await show_words_list(message)


async def show_words_list(message: Message, page: int = 0):
    """Показать список слов с пагинацией"""
    user_id = message.from_user.id
    
    words = await get_user_words(user_id)
    
    if not words:
        await message.answer(
            "У тебя пока нет слов. Отправь слово на английском, чтобы добавить!",
            reply_markup=get_main_reply_keyboard()
        )
        return
    
    # Сохраняем слова для этого пользователя
    _words_pages[user_id] = words
    
    text = f"<b>📖 Мои слова ({len(words)}):</b>\n\nВыбери слово для просмотра:"
    
    await message.answer(
        text,
        reply_markup=get_words_list_keyboard(words, page=page)
    )


@router.callback_query(F.data.startswith("words_page_"))
async def handle_words_page(callback: CallbackQuery):
    """Обработка пагинации списка слов"""
    user_id = callback.from_user.id
    page = int(callback.data.split("_")[-1])
    
    words = _words_pages.get(user_id, [])
    if not words:
        words = await get_user_words(user_id)
        _words_pages[user_id] = words
    
    text = f"<b>📖 Мои слова ({len(words)}):</b>\n\nВыбери слово для просмотра:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_words_list_keyboard(words, page=page)
    )
    await callback.answer()


@router.callback_query(F.data == "words_list")
async def handle_words_list_back(callback: CallbackQuery):
    """Вернуться к списку слов"""
    user_id = callback.from_user.id
    words = _words_pages.get(user_id, [])
    if not words:
        words = await get_user_words(user_id)
        _words_pages[user_id] = words
    
    text = f"<b>📖 Мои слова ({len(words)}):</b>\n\nВыбери слово для просмотра:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_words_list_keyboard(words, page=0)
    )
    await callback.answer()


@router.callback_query(F.data == "words_back")
async def handle_words_back(callback: CallbackQuery):
    """Вернуться в главное меню"""
    await callback.message.delete()
    await callback.message.answer(
        "Главное меню",
        reply_markup=get_main_reply_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("word_view_"))
async def handle_word_view(callback: CallbackQuery):
    """Показать детальную информацию о слове"""
    user_id = callback.from_user.id
    word_id = int(callback.data.split("_")[-1])
    
    word = await get_word_by_id(word_id)
    
    if not word or word.user_id != user_id:
        await callback.answer("Слово не найдено.", show_alert=True)
        return
    
    text = format_word_detail(word)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_word_detail_keyboard(word_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("word_delete_"))
async def handle_word_delete(callback: CallbackQuery):
    """Обработка удаления слова"""
    user_id = callback.from_user.id
    
    if callback.data.startswith("word_delete_confirm_"):
        # Подтверждение удаления
        word_id = int(callback.data.split("_")[-1])
        
        deleted = await delete_word(word_id, user_id)
        
        if deleted:
            await callback.message.edit_text("✅ Слово удалено.")
            await callback.answer("Слово удалено")
            
            # Обновляем кэш
            if user_id in _words_pages:
                _words_pages[user_id] = await get_user_words(user_id)
        else:
            await callback.answer("Ошибка при удалении.", show_alert=True)
    else:
        # Показываем подтверждение
        word_id = int(callback.data.split("_")[-1])
        word = await get_word_by_id(word_id)
        
        if word and word.user_id == user_id:
            await callback.message.edit_text(
                f"⚠️ Удалить слово <b>{word.term}</b>?\n\nЭто действие нельзя отменить.",
                reply_markup=get_word_delete_confirm_keyboard(word_id)
            )
            await callback.answer()
        else:
            await callback.answer("Слово не найдено.", show_alert=True)


@router.callback_query(F.data.startswith("word_learned_"))
async def handle_word_learned(callback: CallbackQuery):
    """Отметить слово как изученное"""
    user_id = callback.from_user.id
    word_id = int(callback.data.split("_")[-1])
    
    word = await get_word_by_id(word_id)
    
    if not word or word.user_id != user_id:
        await callback.answer("Слово не найдено.", show_alert=True)
        return
    
    await mark_word_as_learned(word_id, user_id)
    
    await callback.message.edit_text(
        f"✅ Слово <b>{word.term}</b> отмечено как изученное!\n\nСледующее повторение через год.",
        reply_markup=get_word_detail_keyboard(word_id)
    )
    await callback.answer("Отмечено как изученное!")


@router.callback_query(F.data.startswith("word_regen_"))
async def handle_word_regen(callback: CallbackQuery):
    """Регенерировать карточку слова через ИИ"""
    user_id = callback.from_user.id
    word_id = int(callback.data.split("_")[-1])
    
    word = await get_word_by_id(word_id)
    
    if not word or word.user_id != user_id:
        await callback.answer("Слово не найдено.", show_alert=True)
        return
    
    await callback.message.edit_text("🔄 Регенерирую карточку...")
    
    try:
        # Генерируем новую карточку
        card_data = await generate_word_card(word.term)
        
        # Обновляем слово
        await update_word(
            word_id=word_id,
            pos=card_data.get('pos'),
            ipa=card_data.get('ipa'),
            reading_ru=card_data.get('reading_ru'),
            translations_ru=card_data.get('translations_ru'),
            definition_en=card_data.get('definition_en'),
            examples=card_data.get('examples')
        )
        
        # Получаем обновлённое слово
        updated_word = await get_word_by_id(word_id)
        text = format_word_detail(updated_word)
        
        await callback.message.edit_text(
            text,
            reply_markup=get_word_detail_keyboard(word_id)
        )
        await callback.answer("Карточка обновлена!")
        
    except Exception as e:
        logger.error(f"Error regenerating word: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Ошибка при регенерации. Попробуй позже.",
            reply_markup=get_word_detail_keyboard(word_id)
        )
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("word_edit_"))
async def handle_word_edit(callback: CallbackQuery):
    """Редактирование слова (пока просто сообщение)"""
    await callback.answer("Редактирование будет добавлено в следующей версии. Используй 'Регенерировать' для обновления карточки.", show_alert=True)
