import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from bot.db.database import get_db


@dataclass
class Word:
    id: int
    user_id: int
    term: str
    pos: Optional[str]
    ipa: Optional[str]
    reading_ru: Optional[str]
    translations_ru: List[str]
    definition_en: Optional[str]
    examples: List[Dict[str, str]]
    frequency: int = 1
    created_at: datetime = None

    @classmethod
    def from_row(cls, row) -> "Word":
        """Создать Word из строки БД"""
        # sqlite3.Row не имеет метода .get(), используем проверку через in
        frequency = row["frequency"] if "frequency" in row.keys() else 1
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            term=row["term"],
            pos=row["pos"],
            ipa=row["ipa"],
            reading_ru=row["reading_ru"],
            translations_ru=json.loads(row["translations_ru"] or "[]"),
            definition_en=row["definition_en"],
            examples=json.loads(row["examples"] or "[]"),
            frequency=frequency,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
        )


@dataclass
class Review:
    id: int
    word_id: int
    user_id: int
    next_review_at: Optional[datetime]
    interval_days: float
    ease: float
    last_result: Optional[str]

    @classmethod
    def from_row(cls, row) -> "Review":
        """Создать Review из строки БД"""
        return cls(
            id=row["id"],
            word_id=row["word_id"],
            user_id=row["user_id"],
            next_review_at=datetime.fromisoformat(row["next_review_at"]) if row["next_review_at"] else None,
            interval_days=row["interval_days"],
            ease=row["ease"],
            last_result=row["last_result"]
        )


async def add_word(
    user_id: int,
    term: str,
    pos: Optional[str] = None,
    ipa: Optional[str] = None,
    reading_ru: Optional[str] = None,
    translations_ru: Optional[List[str]] = None,
    definition_en: Optional[str] = None,
    examples: Optional[List[Dict[str, str]]] = None
) -> tuple[int, bool]:
    """
    Добавить слово в БД или увеличить счётчик если уже существует.
    Возвращает (word_id, is_new) где is_new=True если слово новое, False если уже было.
    """
    db = await get_db()
    
    try:
        # Пытаемся вставить новое слово
        cursor = await db.execute("""
            INSERT INTO words (user_id, term, pos, ipa, reading_ru, translations_ru, definition_en, examples, frequency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            user_id,
            term,
            pos,
            ipa,
            reading_ru,
            json.dumps(translations_ru or [], ensure_ascii=False),
            definition_en,
            json.dumps(examples or [], ensure_ascii=False)
        ))
        word_id = cursor.lastrowid
        await db.commit()
        return (word_id, True)
    except aiosqlite.IntegrityError:
        # Слово уже существует - увеличиваем счётчик
        cursor = await db.execute("""
            UPDATE words 
            SET frequency = frequency + 1
            WHERE user_id = ? AND term = ?
        """, (user_id, term))
        
        # Получаем ID слова
        cursor = await db.execute("""
            SELECT id FROM words WHERE user_id = ? AND term = ?
        """, (user_id, term))
        row = await cursor.fetchone()
        word_id = row["id"]
        
        await db.commit()
        return (word_id, False)
    finally:
        await db.close()


async def get_word(user_id: int, term: str) -> Optional[Word]:
    """Получить слово по user_id и term"""
    db = await get_db()
    
    try:
        cursor = await db.execute("""
            SELECT * FROM words WHERE user_id = ? AND term = ?
        """, (user_id, term))
        row = await cursor.fetchone()
        
        if row:
            return Word.from_row(row)
        return None
    finally:
        await db.close()


async def word_exists(user_id: int, term: str) -> bool:
    """Проверить, существует ли слово"""
    word = await get_word(user_id, term)
    return word is not None


async def update_word(
    word_id: int,
    pos: Optional[str] = None,
    ipa: Optional[str] = None,
    reading_ru: Optional[str] = None,
    translations_ru: Optional[List[str]] = None,
    definition_en: Optional[str] = None,
    examples: Optional[List[Dict[str, str]]] = None
):
    """Обновить данные слова"""
    db = await get_db()
    
    updates = []
    values = []
    
    if pos is not None:
        updates.append("pos = ?")
        values.append(pos)
    if ipa is not None:
        updates.append("ipa = ?")
        values.append(ipa)
    if reading_ru is not None:
        updates.append("reading_ru = ?")
        values.append(reading_ru)
    if translations_ru is not None:
        updates.append("translations_ru = ?")
        values.append(json.dumps(translations_ru, ensure_ascii=False))
    if definition_en is not None:
        updates.append("definition_en = ?")
        values.append(definition_en)
    if examples is not None:
        updates.append("examples = ?")
        values.append(json.dumps(examples, ensure_ascii=False))
    
    if not updates:
        await db.close()
        return
    
    values.append(word_id)
    query = f"UPDATE words SET {', '.join(updates)} WHERE id = ?"
    
    try:
        await db.execute(query, values)
        await db.commit()
    finally:
        await db.close()


async def get_word_by_id(word_id: int) -> Optional[Word]:
    """Получить слово по ID"""
    db = await get_db()
    
    try:
        cursor = await db.execute("SELECT * FROM words WHERE id = ?", (word_id,))
        row = await cursor.fetchone()
        
        if row:
            return Word.from_row(row)
        return None
    finally:
        await db.close()


async def get_user_words(user_id: int) -> List[Word]:
    """Получить все слова пользователя"""
    db = await get_db()
    
    try:
        cursor = await db.execute("SELECT * FROM words WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = await cursor.fetchall()
        
        return [Word.from_row(row) for row in rows]
    finally:
        await db.close()


async def get_random_user_words(user_id: int, limit: int, exclude_word_id: Optional[int] = None) -> List[Word]:
    """Получить случайные слова пользователя (для Quiz)"""
    db = await get_db()
    
    try:
        if exclude_word_id:
            cursor = await db.execute("""
                SELECT * FROM words 
                WHERE user_id = ? AND id != ?
                ORDER BY RANDOM()
                LIMIT ?
            """, (user_id, exclude_word_id, limit))
        else:
            cursor = await db.execute("""
                SELECT * FROM words 
                WHERE user_id = ?
                ORDER BY RANDOM()
                LIMIT ?
            """, (user_id, limit))
        
        rows = await cursor.fetchall()
        return [Word.from_row(row) for row in rows]
    finally:
        await db.close()


async def delete_word(word_id: int, user_id: int) -> bool:
    """Удалить слово (проверяет, что оно принадлежит пользователю)"""
    db = await get_db()
    
    try:
        cursor = await db.execute("""
            DELETE FROM words 
            WHERE id = ? AND user_id = ?
        """, (word_id, user_id))
        
        deleted = cursor.rowcount > 0
        await db.commit()
        return deleted
    finally:
        await db.close()


async def mark_word_as_learned(word_id: int, user_id: int):
    """Отметить слово как изученное (устанавливает большое время до следующего повторения)"""
    from datetime import datetime, timedelta
    
    db = await get_db()
    
    try:
        # Устанавливаем следующее повторение через 365 дней
        next_review = datetime.now() + timedelta(days=365)
        
        await db.execute("""
            UPDATE reviews
            SET next_review_at = ?, interval_days = 365, ease = 2.5, last_result = 'know'
            WHERE word_id = ? AND user_id = ?
        """, (next_review.isoformat(), word_id, user_id))
        
        await db.commit()
    finally:
        await db.close()

