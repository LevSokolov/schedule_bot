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
            1: "https://bb.usurt.ru/bbcswebdav/xid-26543310_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-26543673_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26543832_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26544710_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-26544114_1", #его в бб нет
        },
        "Строительный факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-26543311_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-26543587_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26543833_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26544349_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-26544192_1", #его в бб нет
        },
        "Факультет управления процессами перевозок": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-26543312_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-26543326_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26544851_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-25155451_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-26544198_1", #его в бб нет
        },
        "Факультет экономики и управления": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-26543315_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-26543699_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26543837_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26545167_1", #его в бб нет
        },
        "Электромеханический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-26543316_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-26543668_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26543835_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26544778_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-26544157_1", #его в бб нет
        },
        "Электротехнический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-26543317_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-26543656_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26543836_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26544358_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23863379_1", #его в бб нет
        }
    },
    "Четная неделя": {
        "ДиА": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25276496_1",
        },
        "Механический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25518354_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-26544886_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26544887_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26547254_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-26545480_1", #его в бб нет
        },
        "Строительный факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25518361_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25518362_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26544888_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26547255_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-26545481_1", #его в бб нет
        },
        "Факультет управления процессами перевозок": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25518366_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25518367_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25518368_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26547256_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-23886773_1", #его в бб нет
        },
        "Факультет экономики и управления": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25518370_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-26544890_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25518372_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26547257_1", #его в бб нет
        },
        "Электромеханический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25518373_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25518374_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-26544891_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26547258_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-26545483_1", #его в бб нет
        },
        "Электротехнический факультет": {
            1: "https://bb.usurt.ru/bbcswebdav/xid-25518379_1",
            2: "https://bb.usurt.ru/bbcswebdav/xid-25518380_1",
            3: "https://bb.usurt.ru/bbcswebdav/xid-25518381_1",
            4: "https://bb.usurt.ru/bbcswebdav/xid-26547259_1",
            5: "https://bb.usurt.ru/bbcswebdav/xid-26545484_1", #его в бб нет
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
            # Список групп, которые бот когда-либо видел в расписании.
            # Нужен, чтобы летом (когда файлов расписания нет) кнопки выбора
            # группы всё равно были и регистрация не вставала колом.
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS known_groups (
                    faculty TEXT NOT NULL,
                    course TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (faculty, course, group_name)
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




# ===== ЗАПОМИНАНИЕ СПИСКА ГРУПП =====
# Летом файлов расписания на сайте нет, и раньше бот из-за этого не мог
# показать кнопки с группами — регистрация застревала на выборе курса.
# Теперь список групп сохраняется в базе и переживает каникулы.

async def save_known_groups(faculty: str, course, groups: list):
    """Запоминает список групп курса."""
    if not groups:
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.executemany('''
                INSERT INTO known_groups (faculty, course, group_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (faculty, course, group_name)
                DO UPDATE SET seen_at = CURRENT_TIMESTAMP
            ''', [(faculty, str(course), g) for g in groups])
    except Exception as e:
        print(f"❌ Не удалось сохранить список групп: {e}")


async def load_known_groups(faculty: str, course) -> list:
    """Достаёт запомненный список групп курса."""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT group_name FROM known_groups
                WHERE faculty = $1 AND course = $2
                ORDER BY group_name
            ''', faculty, str(course))
            return [r['group_name'] for r in rows]
    except Exception as e:
        print(f"❌ Не удалось прочитать список групп: {e}")
        return []
