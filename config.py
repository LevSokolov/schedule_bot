import os
import ssl
import asyncpg
from datetime import timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL не найден!")

TZ = timezone(timedelta(hours=5))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-4805485452"))

db_pool = None
USER_CACHE = {}

async def init_db_pool():
    global db_pool
    if db_pool is None:
        # СОЗДАЕМ КОНТЕКСТ БЕЗ ПРОВЕРКИ (Для скорости)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        print("⏳ Подключаемся к базе данных (Порт 5432 + Fast SSL)...")
        try:
            db_pool = await asyncpg.create_pool(
                DATABASE_URL, 
                min_size=1, 
                max_size=5,
                command_timeout=60,
                statement_cache_size=0,
                ssl=ssl_ctx,     # Игнорируем проверку сертификата
                timeout=20       # 20 секунд - золотая середина
            )
            print("✅ УСПЕХ! База подключена.")
        except Exception as e:
            print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
            raise e

async def close_db_pool():
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
        "ДиА": { 1: "https://bb.usurt.ru/bbcswebdav/xid-21084187_1" },
        "Механический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-20933625_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23861424_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23862319_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23863115_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863375_1",
        },
        "Строительный факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-20933630_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23861425_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23862320_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23863116_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863376_1",
        },
        "Факультет управления процессами перевозок": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-20933635_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23861426_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23862321_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23863377_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23864226_1",
        },
        "Факультет экономики и управления": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-20933640_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23861427_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23862322_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23863121_1",
        },
        "Электромеханический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-20933644_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23861428_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23862323_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23863126_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863378_1",
        },
        "Электротехнический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-20933649_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23861429_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23862324_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23863127_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863379_1",
        }
    },
    "Четная неделя": {
        "ДиА": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-23870736_1",
        },
        "Механический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-23870737_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23870789_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23872118_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23879494_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23882477_1",
        },
        "Строительный факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-23872117_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23870790_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23872119_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23879495_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23883756_1",
        },
        "Факультет управления процессами перевозок": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-23870739_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23870791_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23872120_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23879496_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23886773_1",
        },
        "Факультет экономики и управления": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-23873014_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23870793_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23872121_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23879497_1",
        },
        "Электромеханический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-23870741_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23870794_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23872122_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23879498_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23882478_1",
        },
        "Электротехнический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-23870742_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-23870795_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-23872123_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-23879499_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23883107_1",
        }
    }
}

# ===== Функции работы с базой данных (ЧЕРЕЗ ПУЛ + КЭШ) =====

async def create_tables():
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
    USER_CACHE[user_id] = {
        'faculty': user_info['faculty'],
        'course': user_info['course'],
        'group': user_info['group'],
        'username': user_info['username'],
        'full_name': user_info['full_name']
    }
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
    if user_id in USER_CACHE:
        del USER_CACHE[user_id]
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute('DELETE FROM users WHERE user_id = $1', user_id)
            return "DELETE 1" in result
    except Exception as e:
        print(f"❌ Ошибка удаления пользователя из БД: {e}")
        return False

async def get_user_data(user_id):
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
