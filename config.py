import os
import asyncpg
from datetime import timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent / "sheets"

# ===== Настройки токена =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Добавь его в настройки Render → Environment Variables")

# ===== Временная зона =====
TZ = timezone(timedelta(hours=5))  # Екатеринбург UTC+5

# ===== База данных =====
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL не найден! Добавь переменную окружения в Render")

# ===== ID группы =====
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-4940561857"))

# ===== Факультеты =====
FACULTIES = {
    "Механический факультет": "МФ",
    "Строительный факультет": "СФ",
    "Факультет управления процессами перевозок": "ФУПП",
    "Факультет экономики и управления": "ФЭУ",
    "Электромеханический факультет": "ЭМФ",
    "Электротехнический факультет": "ЭТФ",
    "ДиА": "ДиА"
}

# ===== Работа с БД =====
async def create_db_pool():
    """Создает пул соединений с PostgreSQL"""
    return await asyncpg.create_pool(DATABASE_URL)

async def init_db(pool):
    """Создает таблицу, если её нет"""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                faculty TEXT,
                course INTEGER,
                user_group TEXT
            );
        """)

async def add_or_update_user(pool, user_id, full_name, username, faculty, course, group):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, full_name, username, faculty, course, user_group)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id) DO UPDATE
            SET full_name=$2, username=$3, faculty=$4, course=$5, user_group=$6;
        """, user_id, full_name, username, faculty, course, group)

async def get_user(pool, user_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None

async def remove_user(pool, user_id):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)

async def get_all_users(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users")
        return [dict(r) for r in rows]


