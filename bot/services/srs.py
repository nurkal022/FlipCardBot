from datetime import datetime, timedelta
from typing import Optional
import aiosqlite
from bot.db.database import get_db


async def create_review(word_id: int, user_id: int):
    """Создать запись о повторении для нового слова"""
    db = await get_db()
    
    # Первое повторение через 1 день
    next_review = datetime.now() + timedelta(days=1)
    
    try:
        await db.execute("""
            INSERT INTO reviews (word_id, user_id, next_review_at, interval_days, ease)
            VALUES (?, ?, ?, ?, ?)
        """, (word_id, user_id, next_review.isoformat(), 1.0, 2.5))
        await db.commit()
    finally:
        await db.close()


async def update_review(word_id: int, user_id: int, result: str):
    """
    Обновить повторение после оценки.
    result: 'know' | 'hard' | 'dontknow'
    """
    db = await get_db()
    
    try:
        # Получаем текущие данные
        cursor = await db.execute("""
            SELECT interval_days, ease FROM reviews
            WHERE word_id = ? AND user_id = ?
        """, (word_id, user_id))
        row = await cursor.fetchone()
        
        if not row:
            # Если записи нет, создаём
            await create_review(word_id, user_id)
            cursor = await db.execute("""
                SELECT interval_days, ease FROM reviews
                WHERE word_id = ? AND user_id = ?
            """, (word_id, user_id))
            row = await cursor.fetchone()
        
        current_interval = row["interval_days"]
        current_ease = row["ease"]
        
        # Обновляем ease и interval в зависимости от результата
        if result == "know":
            new_ease = min(current_ease + 0.15, 2.5)  # Максимум 2.5
            new_interval = current_interval * new_ease
        elif result == "hard":
            new_ease = max(current_ease - 0.15, 1.3)  # Минимум 1.3
            new_interval = current_interval * 1.2
        else:  # dontknow
            new_ease = max(current_ease - 0.2, 1.3)
            new_interval = 1.0  # Повторяем через день
        
        # Округляем до разумных значений
        new_interval = round(new_interval, 1)
        
        # Вычисляем следующее повторение
        next_review = datetime.now() + timedelta(days=new_interval)
        
        # Обновляем запись
        await db.execute("""
            UPDATE reviews
            SET next_review_at = ?, interval_days = ?, ease = ?, last_result = ?
            WHERE word_id = ? AND user_id = ?
        """, (
            next_review.isoformat(),
            new_interval,
            new_ease,
            result,
            word_id,
            user_id
        ))
        await db.commit()
    finally:
        await db.close()


async def get_words_for_review(user_id: int, limit: int = 10) -> list:
    """
    Получить слова, готовые к повторению (next_review_at <= now)
    Возвращает список словарей с word_id и word данными
    """
    db = await get_db()
    
    try:
        cursor = await db.execute("""
            SELECT w.*, r.id as review_id
            FROM words w
            INNER JOIN reviews r ON w.id = r.word_id
            WHERE w.user_id = ? 
            AND (r.next_review_at IS NULL OR r.next_review_at <= ?)
            ORDER BY r.next_review_at ASC NULLS FIRST
            LIMIT ?
        """, (user_id, datetime.now().isoformat(), limit))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_review_stats(user_id: int) -> dict:
    """Получить статистику повторений"""
    db = await get_db()
    
    try:
        # Всего слов
        cursor = await db.execute("SELECT COUNT(*) as count FROM words WHERE user_id = ?", (user_id,))
        total_words = (await cursor.fetchone())["count"]
        
        # Слов на повторение сегодня
        cursor = await db.execute("""
            SELECT COUNT(*) as count
            FROM reviews r
            INNER JOIN words w ON r.word_id = w.id
            WHERE w.user_id = ? 
            AND (r.next_review_at IS NULL OR r.next_review_at <= ?)
        """, (user_id, datetime.now().isoformat()))
        due_today = (await cursor.fetchone())["count"]
        
        # Повторов сегодня (слова, которые были повторены сегодня)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT word_id) as count
            FROM reviews
            WHERE user_id = ?
            AND last_result IS NOT NULL
            AND datetime(next_review_at) >= ?
        """, (user_id, today_start.isoformat()))
        reviewed_today = (await cursor.fetchone())["count"]
        
        return {
            "total_words": total_words,
            "due_today": due_today,
            "reviewed_today": reviewed_today
        }
    finally:
        await db.close()

