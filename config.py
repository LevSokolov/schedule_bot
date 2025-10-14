import os
import json
from datetime import timezone, timedelta
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Безопасно берём токен из окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Укажи его в .env")

# Временная зона
TZ = timezone(timedelta(hours=5))  # Екатеринбург UTC+5

# Базовая директория с расписаниями
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ID группы для уведомлений (можно тоже хранить в .env)
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-4940561857"))

# Файл для хранения данных пользователей
USERS_DATA_FILE = os.path.join(BASE_DIR, 'users_data.json')

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


# ===== Функции работы с данными пользователей =====
def load_users_data():
    """Загружает данные пользователей из файла"""
    if os.path.exists(USERS_DATA_FILE):
        try:
            with open(USERS_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки данных пользователей: {e}")
            return {}
    return {}


def save_users_data(data):
    """Сохраняет данные пользователей в файл"""
    try:
        with open(USERS_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения данных пользователей: {e}")


def update_user_data(user_id, user_info):
    """Обновляет данные пользователя"""
    users_data = load_users_data()
    users_data[str(user_id)] = user_info
    save_users_data(users_data)


def remove_user_data(user_id):
    """Удаляет данные пользователя"""
    users_data = load_users_data()
    user_id_str = str(user_id)
    if user_id_str in users_data:
        del users_data[user_id_str]
        save_users_data(users_data)
        return True
    return False


def get_user_data(user_id):
    """Получает данные пользователя"""
    users_data = load_users_data()
    return users_data.get(str(user_id))
