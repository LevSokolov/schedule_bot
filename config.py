import os
import ssl  # 👈 ВАЖНО: Добавили этот импорт
import asyncpg
from datetime import timezone, timedelta
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Безопасно берём токен из окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Укажи его в .env")

# URL базы данных
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL не найден! Укажи его в .env")

# Временная зона
TZ = timezone(timedelta(hours=5))  # Екатеринбург UTC+5

# ID группы для уведомлений
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-4805485452"))

# ГЛОБАЛЬНЫЙ ПУЛ СОЕДИНЕНИЙ
db_pool = None

# 🔥 КЭШ ПОЛЬЗОВАТЕЛЕЙ В ПАМЯТИ
USER_CACHE = {}

async def init_db_pool():
    """Инициализация пула соединений при старте бота"""
    global db_pool
    if db_pool is None:
        # 👇 СОЗДАЕМ СПЕЦИАЛЬНЫЙ SSL КОНТЕКСТ
        # Это решает проблему зависания при подключении к Pooler
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        db_pool = await asyncpg.create_pool(
            DATABASE_URL, 
            min_size=1, 
            max_size=5,
            command_timeout=60,
            statement_cache_size=0, 
            ssl=ssl_context,  # 👈 Передаем наш контекст вместо строки 'require'
            timeout=30 
        )
        print("✅ Пул соединений с БД успешно создан")

async def close_db_pool():
    """Закрытие пула при остановке"""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("🛑 Пул соединений закрыт")

# Структура факультетов (без изменений)
FACULTIES = {
    "Механический факультет": "МФ",
    "Строительный факультет": "СФ",
    "Факультет управления процессами перевозок": "ФУПП",
    "Факультет экономики и управления": "ФЭУ",
    "Электромеханический факультет": "ЭМФ",
    "Электротехнический факультет": "ЭТФ",
    "ДиА": "ДиА"
}

# ===== ССЫЛКИ НА РАСПИСАНИЯ (Тут твой словарь SCHEDULE_URLS, оставь как был) =====
SCHEDULE_URLS = {
    # ... Вставь сюда свой полный словарь ссылок ...
    "Нечетная неделя": {
        "ДиА": { 1: "https://bb.usurt.ru/bbcswebdav/xid-21084187_1" },
        # ... остальные ссылки ...
    },
    "Четная неделя": {
        # ... остальные ссылки ...
    }
}

# ===== Функции работы с базой данных (С КЭШИРОВАНИЕМ) =====

async def create_tables():
    """Создает таблицы в базе данных если они не существуют"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    faculty TEXT NOT NULL,
                    course TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("✅ Таблицы в базе данных созданы/проверены")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")

async def update_user_data(user_id, user_info):
    """Обновляет данные в БД и сразу в КЭШЕ"""
    
    # 1. Обновляем локальный кэш
    USER_CACHE[user_id] = {
        'faculty': user_info['faculty'],
        'course': user_info['course'],
        'group': user_info['group_name'] if 'group_name' in user_info else user_info['group'],
        'username': user_info['username'],
        'full_name': user_info['full_name']
    }

    # 2. Обновляем базу данных
    try:
        async with db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, faculty, course, group_name, username, full_name)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    faculty = $2,
                    course = $3,
                    group_name = $4,
                    username = $5,
                    full_name = $6,
                    registered_at = CURRENT_TIMESTAMP
            ''', user_id, user_info['faculty'], user_info['course'], 
                user_info.get('group', user_info.get('group_name')), 
                user_info['username'], user_info['full_name'])
    except Exception as e:
        print(f"❌ Ошибка обновления данных пользователя в БД: {e}")

async def remove_user_data(user_id):
    """Удаляет данные из БД и кэша"""
    if user_id in USER_CACHE:
        del USER_CACHE[user_id]

    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute('DELETE FROM users WHERE user_id = $1', user_id)
            return "DELETE 1" in result
    except Exception as e:
        print(f"❌ Ошибка удаления пользователя: {e}")
        return False

async def get_user_data(user_id):
    """Получает данные пользователя (сначала из КЭША, потом из БД)"""
    if user_id in USER_CACHE:
        return USER_CACHE[user_id]

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT faculty, course, group_name, username, full_name FROM users WHERE user_id = $1', 
                user_id
            )
            if row:
                data = {
                    'faculty': row['faculty'],
                    'course': row['course'],
                    'group': row['group_name'],
                    'username': row['username'],
                    'full_name': row['full_name']
                }
                USER_CACHE[user_id] = data
                return data
            return None
    except Exception as e:
        print(f"❌ Ошибка получения данных пользователя: {e}")
        return None
