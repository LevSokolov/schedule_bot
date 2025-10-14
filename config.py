import os
from datetime import timezone, timedelta
from dotenv import load_dotenv
import asyncpg
import asyncio

# Загружаем переменные окружения
load_dotenv()

# ===== Настройки токена =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Укажи его в .env")

# ===== Временная зона =====
TZ = timezone(timedelta(hours=5))  # Екатеринбург UTC+5

# ===== База данных =====
DATABASE_URL = os.getenv("DATABASE_URL")  # строка подключения к PostgreSQL (Render / Supabase и т.п.)

# ===== ID группы =====
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-4940561857"))

# ===== Список факультетов =====
FACULTIES = {
    "Механический факультет": "МФ",
    "Строительный факультет": "СФ",
    "Факультет управления процессами перевозок": "ФУПП",
    "Факультет экономики и управления": "ФЭУ",
    "Электромеханический факультет": "ЭМФ",
    "Электротехнический факультет": "ЭТФ",
    "ДиА": "ДиА"
}

# ===== Подключение к базе =====
async def create_db_pool():
    """Создает пул соединений с базой данных"""
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL не найден! Укажи его в .env")
    return await asyncpg.create_pool(DATABASE_URL)

# ===== Инициализация таблицы =====
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

# ===== CRUD (работа с пользователями) =====

async def add_or_update_user(pool, user_id, full_name, username, faculty, course, group):
    """Добавляет или обновляет пользователя"""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, full_name, username, faculty, course, user_group)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id)
            DO UPDATE SET
                full_name = EXCLUDED.full_name,
                username = EXCLUDED.username,
                faculty = EXCLUDED.faculty,
                course = EXCLUDED.course,
                user_group = EXCLUDED.user_group;
        """, user_id, full_name, username, faculty, course, group)

async def get_user(pool, user_id):
    """Получает данные пользователя"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None

async def remove_user(pool, user_id):
    """Удаляет пользователя"""
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)
        return "DELETE" in result

async def get_all_users(pool):
    """Возвращает всех пользователей"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users")
        return [dict(r) for r in rows]
