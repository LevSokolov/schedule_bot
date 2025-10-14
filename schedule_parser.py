import os
from datetime import datetime, timedelta, date
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

def is_even_week(target_date: datetime) -> bool:
    """Определяет четность недели (учебный семестр обычно начинается с нечетной)"""
    # Преобразуем в наивный datetime для вычислений
    if target_date.tzinfo is not None:
        naive_date = target_date.replace(tzinfo=None)
    else:
        naive_date = target_date
    
    # Учебный год обычно начинается с нечетной недели в сентябре
    if naive_date.month >= 9:  # С сентября по декабрь
        start_year = naive_date.year
        start_date = datetime(start_year, 9, 1)
    else:  # С января по август
        start_year = naive_date.year - 1
        start_date = datetime(start_year, 9, 1)
    
    # Находим первый понедельник сентября
    while start_date.weekday() != 0:  # 0 = понедельник
        start_date += timedelta(days=1)
    
    # Вычисляем разницу в неделях
    delta = naive_date - start_date
    weeks_passed = delta.days // 7
    
    # Нечетная неделя = нечетное количество прошедших недель
    return weeks_passed % 2 == 1

def get_schedule_file_path(faculty: str, course: int, is_even: bool) -> str:
    """Получает путь к файлу расписания"""
    week_folder = "Четная неделя" if is_even else "Нечетная неделя"
    faculty_abbr = FACULTIES[faculty]
    
    # Формируем базовый путь
    base_path = os.path.join(BASE_DIR, week_folder, faculty)
    
    print(f"🔍 Ищем файл расписания по пути: {base_path}")
    print(f"📁 Факультет: {faculty}, курс: {course}, неделя: {'четная' if is_even else 'нечетная'}")
    
    if not os.path.exists(base_path):
        print(f"❌ Путь не существует: {base_path}")
        return None
    
    # Ищем подходящий файл
    files_found = []
    for file in os.listdir(base_path):
        if file.endswith(('.xls', '.xlsx')):
            files_found.append(file)
            # Проверяем, что файл подходит по курсу
            if f"{course} курс" in file:
                file_path = os.path.join(base_path, file)
                print(f"✅ Найден подходящий файл: {file_path}")
                return file_path
    
    print(f"❌ Файл для курса {course} не найден. Найдены файлы: {files_found}")
    return None

def load_schedule(file_path: str):
    """Загружает данные из файла расписания"""
    if not file_path or not os.path.exists(file_path):
        print(f"❌ Файл не существует: {file_path}")
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
        print(f"✅ Успешно загружено {len(data)} строк из файла")
    except Exception as e:
        print(f"❌ Ошибка загрузки файла {file_path}: {e}")
        return None
        
    return data

def get_available_groups(faculty: str, course: int) -> list:
    """Получает список доступных групп для факультета и курса"""
    print(f"🔍 Получаем доступные группы для {faculty}, курс {course}")
    
    # Пробуем сначала нечетную неделю, потом четную
    for is_even in [False, True]:
        file_path = get_schedule_file_path(faculty, course, is_even)
        if not file_path:
            continue
            
        schedule_data = load_schedule(file_path)
        if not schedule_data:
            continue
            
        # Ищем строку с заголовками групп (где есть "День" и "Часы")
        for row_idx, row in enumerate(schedule_data):
            if len(row) > 2:
                first_cell = str(row[0]).lower() if row[0] else ""
                second_cell = str(row[1]).lower() if row[1] else ""
                
                if "день" in first_cell and "часы" in second_cell:
                    # Нашли заголовок, собираем группы
                    groups = []
                    for col_idx, cell in enumerate(row[2:], start=2):
                        cell_str = str(cell).strip()
                        if cell_str and cell_str not in ["День", "Часы"] and not cell_str.isspace():
                            groups.append(cell_str)
                    print(f"✅ Найдены группы: {groups}")
                    return groups if groups else []
    
    print("❌ Группы не найдены ни в одном файле расписания")
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
                for col_idx, cell in enumerate(row[2:], start=2):
                    if str(cell).strip() == group_name:
                        print(f"✅ Найден столбец для группы {group_name}: {col_idx}")
                        return col_idx
                break
                
    print(f"❌ Столбец для группы {group_name} не найден")
    return -1

def find_schedule_for_group(schedule_data: list, group_column: int, target_date: datetime):
    """Находит расписание для группы на указанную дату"""
    if not schedule_data or group_column < 0:
        return []
    
    # Преобразуем в наивный datetime для поиска
    if target_date.tzinfo is not None:
        search_date = target_date.replace(tzinfo=None)
    else:
        search_date = target_date
    
    day_rus = {
        "monday": "понедельник",
        "tuesday": "вторник", 
        "wednesday": "среда",
        "thursday": "четверг",
        "friday": "пятница",
        "saturday": "суббота",
        "sunday": "воскресенье"
    }[search_date.strftime("%A").lower()]
    
    day_variants = [
        str(search_date.day),
        f"{search_date.day}.{search_date.month}",
        f"{search_date.day}/{search_date.month}",
        search_date.strftime("%d.%m"),
        search_date.strftime("%d/%m"),
        day_rus
    ]
    
    print(f"🔍 Ищем расписание на дату: {search_date.strftime('%d.%m.%Y')}")
    print(f"🔍 Варианты поиска: {day_variants}")
    
    # Ищем строку с нужной датой
    found_index = -1
    for i, row in enumerate(schedule_data):
        if row and row[0]:
            cell = str(row[0]).lower()
            if any(d in cell for d in day_variants):
                found_index = i
                print(f"✅ Найдена строка с датой: строка {i}, содержимое: '{row[0]}'")
                break
    
    if found_index == -1:
        print(f"❌ Дата {search_date.strftime('%d.%m.%Y')} не найдена в расписании")
        return []
    
    # Собираем пары
    lessons = []
    current_time = None
    
    # Проходим по всем строкам начиная со строки с датой
    i = found_index
    while i < len(schedule_data):
        row = schedule_data[i]
        
        # Проверяем, есть ли время в этой строке
        time = row[1] if len(row) > 1 else ""
        subject_cell = row[group_column] if len(row) > group_column else ""
        
        # Если есть время - обновляем current_time
        if time and str(time).strip():
            current_time = str(time).strip()
        
        # Если есть данные о паре - добавляем
        if current_time and subject_cell and str(subject_cell).strip():
            subject_text = str(subject_cell)
            subject_lines = []
            
            for line in subject_text.split('\n'):
                cleaned_line = line.strip().lstrip('-').strip()
                if cleaned_line:
                    subject_lines.append(cleaned_line)
            
            if subject_lines:
                lessons.append((current_time, subject_lines))
                print(f"✅ Добавлена пара: {current_time} - {subject_lines}")
        
        # Переходим к следующей строке
        i += 1
        
        # Прерываем цикл если нашли следующую дату
        if i < len(schedule_data) and schedule_data[i] and schedule_data[i][0]:
            next_cell = str(schedule_data[i][0]).lower()
            if any(d in next_cell for d in day_variants) or any(day in next_cell for day in DAY_MAP.keys()):
                break
    
    print(f"✅ Найдено {len(lessons)} пар для даты {search_date.strftime('%d.%m.%Y')}")
    return lessons

def get_day_schedule(faculty: str, course: int, group: str, command: str):
    """Основная функция для получения расписания"""
    now = datetime.now(TZ)
    print(f"🎯 Запрос расписания: {faculty}, курс {course}, группа {group}, команда '{command}'")
    
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
    
    print(f"📅 Целевая дата: {target_date.strftime('%d.%m.%Y')}")
    print(f"📊 Определена неделя: {'четная' if is_even else 'нечетная'}")
    
    # Получаем файл расписания
    file_path = get_schedule_file_path(faculty, course, is_even)
    if not file_path:
        # Пробуем противоположную неделю
        is_even = not is_even
        print(f"🔄 Пробуем противоположную неделю: {'четная' if is_even else 'нечетная'}")
        file_path = get_schedule_file_path(faculty, course, is_even)
        if not file_path:
            error_msg = "❌ Файл расписания не найден"
            print(error_msg)
            return error_msg
    
    # Загружаем данные
    schedule_data = load_schedule(file_path)
    if not schedule_data:
        error_msg = "❌ Не удалось загрузить расписание"
        print(error_msg)
        return error_msg
    
    # Находим столбец группы
    group_column = find_group_column(schedule_data, group)
    if group_column == -1:
        error_msg = f"❌ Группа {group} не найдена в расписании"
        print(error_msg)
        return error_msg
    
    # Получаем расписание
    lessons = find_schedule_for_group(schedule_data, group_column, target_date)
    
    # Форматируем результат
    return format_schedule(lessons, is_even, target_date, group)

def format_schedule(lessons, is_even, date, group):
    """Форматирует расписание в красивый текст"""
    # Преобразуем в наивный datetime для форматирования
    if date.tzinfo is not None:
        format_date = date.replace(tzinfo=None)
    else:
        format_date = date
        
    week_str = "Четная" if is_even else "Нечетная"
    day_short = RUS_DAYS_SHORT[format_date.weekday()]
    month_rus = RUS_MONTHS[format_date.month]
    month_rus = month_rus[0].upper() + month_rus[1:]
    date_str = f"{day_short} {format_date.day} {month_rus}"
    
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
