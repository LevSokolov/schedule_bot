import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import router
from aiohttp import web

async def handle(request):
    return web.Response(text="✅ Bot is alive!", content_type="text/plain")

async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    # aiohttp сервер
    app = web.Application()
    app.router.add_get("/", handle)

    # Запуск Telegram бота и веб-сервера параллельно
    async def run_bot():
        await dp.start_polling(bot)

    async def run_web():
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 10000)
        await site.start()
        print("🌐 Web server запущен на порту 10000")

    await asyncio.gather(run_bot(), run_web())

if __name__ == "__main__":
    asyncio.run(main())

schedule_parser.py
import os
from datetime import datetime, timedelta
from config import FACULTIES, TZ, BASE_DIR
import openpyxl
import xlrd
import re

BASE_DIR = os.path.join(os.path.dirname(__file__), "sheets")
print("BASE_DIR =", BASE_DIR)
print("Содержимое BASE_DIR:", os.listdir(BASE_DIR))

DAY_MAP = {
    "понедельник": 0,
    "вторник": 1,
    "среда": 2,
    "четверг": 3,
    "пятница": 4,
    "суббота": 5,
    "воскресенье": 6
}

RUS_DAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RUS_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

def escape_markdown(text: str) -> str:
    """Экранирование специальных символов для MarkdownV2"""
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def is_even_week(date: datetime) -> bool:
    return date.isocalendar().week % 2 != 0

def get_schedule_file_path(faculty: str, course: int, is_even: bool) -> str:
    """Получает путь к файлу расписания"""
    week_folder = "Четная неделя" if is_even else "Нечетная неделя"
    faculty_abbr = FACULTIES[faculty]
    
    # Формируем базовый путь
    base_path = os.path.join(BASE_DIR, week_folder, faculty)
    
    if not os.path.exists(base_path):
        return None
    
    # Ищем подходящий файл
    for file in os.listdir(base_path):
        if file.endswith(('.xls', '.xlsx')):
            # Проверяем, что файл подходит по курсу
            if f"{course} курс" in file:
                return os.path.join(base_path, file)
    
    return None

def load_schedule(file_path: str):
    """Загружает данные из файла расписания"""
    if not file_path or not os.path.exists(file_path):
        return None
        
    ext = os.path.splitext(file_path)[1].lower()
    data = []

    try:
        if ext == ".xlsx":
            wb = openpyxl.load_workbook(file_path)
            sheet = wb.active
            for row in sheet.iter_rows(values_only=True):
                data.append([cell if cell is not None else "" for cell in row])
        elif ext == ".xls":
            wb = xlrd.open_workbook(file_path)
            sheet = wb.sheet_by_index(0)
            for r in range(sheet.nrows):
                data.append([sheet.cell_value(r, c) if sheet.cell_value(r, c) else "" for c in range(sheet.ncols)])
    except Exception as e:
        print(f"Ошибка загрузки файла {file_path}: {e}")
        return None
        
    return data

def get_available_groups(faculty: str, course: int) -> list:
    """Получает список доступных групп для факультета и курса"""
    # Пробуем сначала нечетную неделю, потом четную
    for is_even in [False, True]:
        file_path = get_schedule_file_path(faculty, course, is_even)
        if not file_path:
            continue
            
        schedule_data = load_schedule(file_path)
        if not schedule_data:
            continue
            
        # Ищем строку с заголовками групп (где есть "День" и "Часы")
        for row in schedule_data:
            if len(row) > 2:
                first_cell = str(row[0]).lower() if row[0] else ""
                second_cell = str(row[1]).lower() if row[1] else ""
                
                if "день" in first_cell and "часы" in second_cell:
                    # Нашли заголовок, собираем группы
                    groups = []
                    for cell in row[2:]:  # Начиная с третьего столбца
                        cell_str = str(cell).strip()
                        if cell_str and cell_str not in ["День", "Часы"] and not cell_str.isspace():
                            groups.append(cell_str)
                    return groups if groups else []
    
    return []

def find_group_column(schedule_data: list, group_name: str) -> int:
    """Находит номер столбца для указанной группы"""
    if not schedule_data:
        return -1
        
    # Ищем строку с заголовками групп
    for row in schedule_data:
        if len(row) > 2:
            first_cell = str(row[0]).lower() if row[0] else ""
            second_cell = str(row[1]).lower() if row[1] else ""
            
            if "день" in first_cell and "часы" in second_cell:
                # Нашли заголовок, ищем нашу группу
                for col_idx, cell in enumerate(row[2:], start=2):  # Начиная с 3 столбца
                    if str(cell).strip() == group_name:
                        return col_idx
                break
                
    return -1

def find_schedule_for_group(schedule_data: list, group_column: int, date: datetime):
    """Находит расписание для группы на указанную дату"""
    if not schedule_data or group_column < 0:
        return []
    
    day_rus = {
        "monday": "понедельник",
        "tuesday": "вторник", 
        "wednesday": "среда",
        "thursday": "четверг",
        "friday": "пятница",
        "saturday": "суббота",
        "sunday": "воскресенье"
    }[date.strftime("%A").lower()]
    
    day_variants = [
        str(date.day),
        f"{date.day}.{date.month}",
        f"{date.day}/{date.month}",
        date.strftime("%d.%m"),
        date.strftime("%d/%m")
    ]
    
    # Ищем строку с нужной датой
    found_index = -1
    for i, row in enumerate(schedule_data):
        if row and row[0]:
            cell = str(row[0]).lower()
            if any(d in cell for d in day_variants) or day_rus in cell:
                found_index = i
                break
    
    if found_index == -1:
        return []
    
    # Собираем пары
    lessons = []
    current_time = None  # Храним текущее время для объединенных ячеек
    
    # Проходим по всем строкам начиная со строки с датой
    i = found_index
    while i < len(schedule_data):
        row = schedule_data[i]
        
        # Проверяем, есть ли время в этой строке
        time = row[1] if len(row) > 1 else ""
        subject_cell = row[group_column] if len(row) > group_column else ""
        
        # Если есть время - обновляем current_time (даже если ячейка группы пустая)
        if time and str(time).strip():
            current_time = str(time).strip()
        
        # Если есть данные о паре - добавляем (используя current_time)
        # ВАЖНОЕ ИЗМЕНЕНИЕ: убираем проверку на дублирование времени, чтобы разрешить несколько пар в одно время
        if current_time and subject_cell and str(subject_cell).strip():
            # Обрабатываем многострочное содержимое - берем ВСЕ строки
            subject_text = str(subject_cell)
            subject_lines = []
            
            for line in subject_text.split('\n'):
                cleaned_line = line.strip().lstrip('-').strip()
                if cleaned_line:
                    subject_lines.append(cleaned_line)
            
            if subject_lines:
                # УБИРАЕМ ПРОВЕРКУ НА ДУБЛИРОВАНИЕ ВРЕМЕНИ - разрешаем несколько пар в одно время
                lessons.append((current_time, subject_lines))
        
        # Переходим к следующей строке
        i += 1
        
        # Прерываем цикл если нашли следующую дату
        if i < len(schedule_data) and schedule_data[i] and schedule_data[i][0]:
            next_cell = str(schedule_data[i][0]).lower()
            if any(d in next_cell for d in day_variants) or any(day in next_cell for day in DAY_MAP.keys()):
                break
    
    return lessons

def get_day_schedule(faculty: str, course: int, group: str, command: str):
    """Основная функция для получения расписания"""
    now = datetime.now(TZ)
    
    # Определяем смещение дней
    if command == "сегодня":
        shift = 0
    elif command == "завтра":
        shift = 1
    else:
        days_map = {"пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6}
        today = now.weekday()
        shift = (days_map.get(command, 0) - today) % 7
        if shift < 0:
            shift += 7
    
    target_date = now + timedelta(days=shift)
    is_even = is_even_week(target_date)
    
    # Получаем файл расписания
    file_path = get_schedule_file_path(faculty, course, is_even)
    if not file_path:
        return "❌ Файл расписания не найден"
    
    # Загружаем данные
    schedule_data = load_schedule(file_path)
    if not schedule_data:
        return "❌ Не удалось загрузить расписание"
    
    # Находим столбец группы
    group_column = find_group_column(schedule_data, group)
    if group_column == -1:
        return f"❌ Группа {group} не найдена в расписании"
    
    # Получаем расписание
    lessons = find_schedule_for_group(schedule_data, group_column, target_date)
    
    # Форматируем результат
    return format_schedule(lessons, is_even, target_date, group)

def format_schedule(lessons, is_even, date, group):
    """Форматирует расписание в красивый текст"""
    week_str = "Четная" if is_even else "Нечетная"
    day_short = RUS_DAYS_SHORT[date.weekday()]
    month_rus = RUS_MONTHS[date.month]
    # Делаем первую букву месяца заглавной
    month_rus = month_rus[0].upper() + month_rus[1:]
    date_str = f"{day_short} {date.day} {month_rus}"
    
    # Экранируем все данные
    escaped_week = escape_markdown(week_str)
    escaped_group = escape_markdown(group)
    escaped_date = escape_markdown(date_str)
    
    result = [
        f"*📅 {escaped_week} неделя*",
        f"*👥 {escaped_group}*",
        "",
        f"🟢__*{escaped_date}*__",
        "",
    ]
    
    if not lessons:
        result.append("❌ *Пар нет*")
    else:
        for time, subject_lines in lessons:
            escaped_time = escape_markdown(time)
            result.append(f"*⏰ {escaped_time}*")
            
            for line in subject_lines:
                escaped_line = escape_markdown(line)
                result.append(f"\\- {escaped_line}")
            result.append("")
    

    return "\n".join(result)
