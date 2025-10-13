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
    
    # Регекс для времени вида 08:30-10:05 (учитываем пробелы)
    time_re = re.compile(r'(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})')
    
    lessons = []
    # бежим по строкам после найденной даты, пока не встретим новую дату/заголовок
    for i in range(found_index + 1, len(schedule_data)):
        row = schedule_data[i]
        if not row:
            continue
        
        # если в первой ячейке что-то похожее на новую дату / день — считаем, что блок закончен
        first_cell = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
        if first_cell:
            low = first_cell.lower()
            # простая эвристика: если в ячейке есть число + слово месяц/день или название дня — новый блок
            if any(d in low for d in ["январ", "феврал", "марта", "апрел", "мая", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]) \
               or any(d in low for d in ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]) \
               or re.search(r'\d{1,2}\s*[\./]\s*\d{1,2}', low) \
               or any(d in low for d in day_variants):
                break  # встретили следующую дату/заголовок -> выходим
    
        # находим время в любой ячейке строки (иногда время может быть в 0-й, 1-й или даже 2-й)
        time_str = ""
        for cell in row[:3]:  # проверяем первые 3 колонки на время — обычно хватает
            if cell is None:
                continue
            m = time_re.search(str(cell))
            if m:
                time_str = f"{m.group(1)}-{m.group(2)}"
                break
        
        # как fallback — попробуем взять то, что у тебя было (вторая колонка)
        if not time_str and len(row) > 1 and row[1]:
            # возможна ситуация, где там уже строка типа "08:30-10:05" без дефиса-минуса стандартизированного
            s = str(row[1]).strip()
            if time_re.search(s):
                m = time_re.search(s)
                time_str = f"{m.group(1)}-{m.group(2)}"
            else:
                # если там просто что-то похожее на время — оставляем как есть
                if re.search(r'\d{1,2}:\d{2}', s):
                    time_str = s
        
        subject_cell = row[group_column] if len(row) > group_column else ""
        if time_str and subject_cell and str(subject_cell).strip():
            # Обрабатываем многострочное содержимое - берем ВСЕ строки
            subject_text = str(subject_cell)
            subject_lines = []
            
            for line in subject_text.split('\n'):
                cleaned_line = line.strip().lstrip('-').strip()
                if cleaned_line:
                    subject_lines.append(cleaned_line)
            
            if subject_lines:
                lessons.append((str(time_str), subject_lines))
    
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

