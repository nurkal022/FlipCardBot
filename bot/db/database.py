import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from bot.config import settings


async def get_db() -> aiosqlite.Connection:
    """Получить соединение с БД"""
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Инициализация БД: создание таблиц"""
    db = await get_db()
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            term TEXT NOT NULL,
            pos TEXT,
            ipa TEXT,
            reading_ru TEXT,
            translations_ru TEXT,
            definition_en TEXT,
            examples TEXT,
            frequency INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, term)
        )
    """)
    
    # Миграция: добавляем поле frequency если его нет
    try:
        await db.execute("ALTER TABLE words ADD COLUMN frequency INTEGER DEFAULT 1")
        await db.commit()
    except aiosqlite.OperationalError:
        # Поле уже существует, игнорируем
        pass
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            next_review_at TIMESTAMP,
            interval_days REAL DEFAULT 1,
            ease REAL DEFAULT 2.5,
            last_result TEXT,
            FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
        )
    """)
    
    await db.commit()
    await db.close()

