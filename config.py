import os
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
# Храним данные тут, чтобы бот работал мгновенно и не дергал базу лишний раз
USER_CACHE = {}

async def init_db_pool():
    """Инициализация пула соединений при старте бота"""
    global db_pool
    if db_pool is None:
        print("⏳ Подключение к Neon DB...")
        try:
            # Настройки для Neon.tech
            # Neon отлично работает со стандартным ssl='require'
            db_pool = await asyncpg.create_pool(
                DATABASE_URL, 
                min_size=1, 
                max_size=5,              # Для бесплатного тарифа Render 5 соединений достаточно
                command_timeout=60,      # Время на выполнение запроса
                statement_cache_size=0,  # Для облачных баз лучше отключать кэш выражений
                ssl='require',           # Стандартный SSL для Neon
                timeout=30               # 30 секунд хватит с головой
            )
            print("✅ УСПЕХ! База Neon подключена")
        except Exception as e:
            print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ К БД: {e}")
            raise e

async def close_db_pool():
    """Закрытие пула при остановке"""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("🛑 Пул соединений закрыт")

# Структура факультетов
FACULTIES = {
    "Механический факультет": "МФ",
    "Строительный факультет": "СФ",
    "Факультет управления процессами перевозок": "ФУПП",
    "Факультет экономики и управления": "ФЭУ",
    "Электромеханический факультет": "ЭМФ",
    "Электротехнический факультет": "ЭТФ",
    "ДиА": "ДиА"
}

# ===== ССЫЛКИ НА РАСПИСАНИЯ =====
SCHEDULE_URLS = {
    "Нечетная неделя": {
        "ДиА": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25309681_1",
        },
        "Механический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25234801_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25238173_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25240072_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25234816_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863375_1", #его в бб нет
        },
        "Строительный факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25309913_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25309914_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25309915_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25310877_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863376_1", #его в бб нет
        },
        "Факультет управления процессами перевозок": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25238175_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25238174_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25240073_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25155451_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23864226_1", #его в бб нет
        },
        "Факультет экономики и управления": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25234802_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25238179_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25240074_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23863121_1", #его в бб нет
        },
        "Электромеханический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25309925_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25309926_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25309927_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25310882_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863378_1", #его в бб нет
        },
        "Электротехнический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25234803_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25309928_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25240075_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25238198_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863379_1", #его в бб нет
        }
    },
    "Четная неделя": {
        "ДиА": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25276496_1",
        },
        "Механический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25449277_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25449278_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25449279_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25449280_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23882477_1", #его в бб нет
        },
        "Строительный факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25449281_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25449282_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25449283_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25449284_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23883756_1", #его в бб нет
        },
        "Факультет управления процессами перевозок": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25449295_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25449296_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25449297_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25449298_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23886773_1", #его в бб нет
        },
        "Факультет экономики и управления": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25449703_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25449704_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25449705_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23879497_1", #его в бб нет
        },
        "Электромеханический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25449706_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25449707_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25449708_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25449709_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23882478_1", #его в бб нет
        },
        "Электротехнический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25449710_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25449711_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25449712_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25449713_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23883107_1", #его в бб нет
        }
    }
}

# ===== Функции работы с базой данных (ЧЕРЕЗ ПУЛ + КЭШ) =====

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
    """Обновляет или создает данные пользователя (БД + КЭШ)"""
    
    # 1. Сначала обновляем кэш (это моментально)
    USER_CACHE[user_id] = {
        'faculty': user_info['faculty'],
        'course': user_info['course'],
        'group': user_info['group'],
        'username': user_info['username'],
        'full_name': user_info['full_name']
    }

    # 2. Потом обновляем базу данных
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
                user_info['group'], user_info['username'], user_info['full_name'])
    except Exception as e:
        print(f"❌ Ошибка обновления данных пользователя в БД: {e}")

async def remove_user_data(user_id):
    """Удаляет данные пользователя (БД + КЭШ)"""
    
    # 1. Удаляем из кэша
    if user_id in USER_CACHE:
        del USER_CACHE[user_id]

    # 2. Удаляем из БД
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute('DELETE FROM users WHERE user_id = $1', user_id)
            return "DELETE 1" in result
    except Exception as e:
        print(f"❌ Ошибка удаления пользователя из БД: {e}")
        return False

async def get_user_data(user_id):
    """Получает данные пользователя (Сначала КЭШ, потом БД)"""
    
    # 1. ПРОВЕРЯЕМ КЭШ
    if user_id in USER_CACHE:
        return USER_CACHE[user_id]

    # 2. Если в кэше пусто, идем в базу
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



