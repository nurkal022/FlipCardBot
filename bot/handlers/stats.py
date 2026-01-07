from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from bot.services.srs import get_review_stats

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Обработка команды /stats"""
    user_id = message.from_user.id
    
    stats = await get_review_stats(user_id)
    
    text = f"""<b>📊 Статистика</b>

<b>Всего слов:</b> {stats['total_words']}
<b>На повторение сегодня:</b> {stats['due_today']}
<b>Повторено сегодня:</b> {stats['reviewed_today']}

Используй /review для повторения слов."""
    
    await message.answer(text)

