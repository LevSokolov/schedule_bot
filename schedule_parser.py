"""
Парсер расписания УрГУПС.

Главные отличия от старой версии:
  * год у даты берётся из шапки файла ("1 семестр 2026/2027"), а не угадывается
    по текущему месяцу (из-за этого все прошедшие дни месяца улетали в +1 год);
  * "Пн".."Сб" = дни ТЕКУЩЕЙ недели, а не "следующее такое-то число";
  * чётность недели берётся из шапки файла, а не из номера ISO-недели;
  * различаются три ситуации: "пар нет", "группы нет в файле",
    "расписание на эту неделю ещё не выложено";
  * тип файла определяется по содержимому (xls/xlsx), а не по расширению в URL;
  * если сайт вуза лежит — отдаём последние удачные данные из кэша,
    а не пустоту.
"""

import asyncio
import io
import re
import time
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import aiohttp
import openpyxl
import xlrd

from config import SCHEDULE_URLS

try:
    from config import TZ
except ImportError:  # на всякий случай
    from datetime import timezone
    TZ = timezone(timedelta(hours=5))

# ===== КЭШ =====
CACHE_TTL_SECONDS = 1800          # 30 минут — свежие данные
STALE_TTL_SECONDS = 60 * 60 * 24  # сутки — аварийный запас, если сайт недоступен
_RAW_CACHE: Dict[str, Tuple[float, list]] = {}
_PARSED_CACHE: Dict[str, Tuple[float, "ParsedSchedule"]] = {}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=25)

# ===== КОНСТАНТЫ =====
RUS_DAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RUS_DAYS_FULL = ["понедельник", "вторник", "среда", "четверг",
                 "пятница", "суббота", "воскресенье"]
RUS_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября",
    12: "декабря",
}
# по трём первым буквам ловим и "сентября", и "сентябрь"
MONTH_PREFIXES = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "мая": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}
WEEKDAY_COMMANDS = {"пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6}


def escape_markdown(text) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if text is None:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))


def _norm(value) -> str:
    """Ячейка -> строка без лишних пробелов."""
    if value is None:
        return ""
    return str(value).strip()


# ===================== ЗАГРУЗКА ФАЙЛОВ =====================

def _rows_from_bytes(content: bytes) -> Optional[list]:
    """Определяем формат по сигнатуре файла, а не по URL."""
    rows = []
    try:
        if content[:2] == b"PK":                      # zip => xlsx
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            sheet = wb.active
            for row in sheet.iter_rows(values_only=True):
                rows.append(["" if c is None else c for c in row])
        else:                                         # старый BIFF => xls
            wb = xlrd.open_workbook(file_contents=content)
            sheet = wb.sheet_by_index(0)
            for r in range(sheet.nrows):
                rows.append([sheet.cell_value(r, c) or "" for c in range(sheet.ncols)])
        return rows
    except Exception as e:
        print(f"❌ Не смог разобрать файл: {e}")
        return None


async def _download(url: str) -> Optional[list]:
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ {url}: HTTP {response.status}")
                    return None
                return _rows_from_bytes(await response.read())
    except Exception as e:
        print(f"❌ Ошибка загрузки {url}: {e}")
        return None


async def get_rows(url: str) -> Optional[list]:
    """Строки файла с кэшем. Если скачать не вышло — отдаём протухший кэш."""
    now = time.time()
    cached = _RAW_CACHE.get(url)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    rows = await _download(url)
    if rows:
        _RAW_CACHE[url] = (now, rows)
        _PARSED_CACHE.pop(url, None)
        return rows

    if cached and now - cached[0] < STALE_TTL_SECONDS:
        print(f"⚠️ Отдаю устаревший кэш для {url}")
        return cached[1]
    return None


# ===================== РАЗБОР ТАБЛИЦЫ =====================

@dataclass
class DayBlock:
    day: date_cls
    start: int          # индекс первой строки дня
    end: int            # индекс строки СЛЕДУЮЩЕГО дня (не включительно)


@dataclass
class ParsedSchedule:
    rows: list
    parity_even: Optional[bool] = None      # True = чётная неделя
    groups: Dict[int, str] = field(default_factory=dict)   # колонка -> группа
    days: List[DayBlock] = field(default_factory=list)

    def group_column(self, group_name: str) -> int:
        target = group_name.strip().lower()
        for col, name in self.groups.items():
            if name.strip().lower() == target:
                return col
        return -1

    def has_day(self, day: date_cls) -> bool:
        return any(b.day == day for b in self.days)

    @property
    def first_day(self) -> Optional[date_cls]:
        return min((b.day for b in self.days), default=None)

    @property
    def last_day(self) -> Optional[date_cls]:
        return max((b.day for b in self.days), default=None)

    @property
    def week_monday(self) -> Optional[date_cls]:
        """Понедельник недели, которую описывает файл."""
        first = self.first_day
        if first is None:
            return None
        return first - timedelta(days=first.weekday())

    def covers_week_of(self, day: date_cls) -> bool:
        """Файл описывает ту же учебную неделю, что и переданная дата.

        Нужно, чтобы отличать «в этот день пар нет» (день внутри недели файла,
        но строки для него в таблице просто не завели) от «файл на эту неделю
        ещё не выложили».
        """
        monday = self.week_monday
        return monday is not None and monday == day - timedelta(days=day.weekday())

    def lessons(self, day: date_cls, col: int) -> Optional[List[Tuple[str, List[str]]]]:
        """Пары группы за день. None = такого дня в файле нет."""
        block = next((b for b in self.days if b.day == day), None)
        if block is None:
            return None

        lessons: List[Tuple[str, List[str]]] = []
        current_time = ""
        for i in range(block.start, block.end):
            row = self.rows[i]
            time_cell = _norm(row[1]) if len(row) > 1 else ""
            if time_cell:
                current_time = time_cell

            cell = _norm(row[col]) if len(row) > col else ""
            if not cell or not current_time:
                continue

            lines = [ln.strip().lstrip("-").strip()
                     for ln in cell.split("\n") if ln.strip().lstrip("-").strip()]
            if lines:
                item = (current_time, lines)
                if item not in lessons:
                    lessons.append(item)

        lessons.sort(key=_time_key)
        return lessons


def _time_key(lesson) -> Tuple[int, int]:
    try:
        hh, mm = lesson[0].split("-")[0].strip().split(":")
        return int(hh), int(mm)
    except Exception:
        return (99, 99)


def _parse_years(rows: list) -> Optional[Tuple[int, int]]:
    """Ищем '2026/2027' в первых строках файла."""
    for row in rows[:8]:
        for cell in row[:3]:
            m = re.search(r"(20\d{2})\s*[/\-]\s*(20\d{2})", str(cell))
            if m:
                return int(m.group(1)), int(m.group(2))
    return None


def _parse_parity(rows: list) -> Optional[bool]:
    """'Нечетная'/'Четная' из шапки. Сначала проверяем 'нечет' — оно длиннее."""
    for row in rows[:8]:
        for cell in row[:3]:
            text = str(cell).lower().replace("ё", "е")
            if "нечет" in text:
                return False
            if "чет" in text:
                return True
    return None


def _parse_day(text: str, years: Optional[Tuple[int, int]]) -> Optional[date_cls]:
    """'07 сентября\\nпонедельник' -> date(2026, 9, 7)."""
    if not text:
        return None
    low = str(text).lower().replace("ё", "е")
    m = re.search(r"(\d{1,2})[.\s]+([а-я]{3,})", low)
    if not m:
        return None
    day = int(m.group(1))
    month = MONTH_PREFIXES.get(m.group(2)[:3])
    if not month:
        return None

    if years:
        # учебный год: сентябрь-декабрь = первый год, январь-август = второй
        year = years[0] if month >= 9 else years[1]
        try:
            return date_cls(year, month, day)
        except ValueError:
            return None

    # запасной вариант: берём год, при котором дата ближе всего к сегодня
    today = datetime.now(TZ).date()
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidate = date_cls(year, month, day)
        except ValueError:
            continue
        if best is None or abs((candidate - today).days) < abs((best - today).days):
            best = candidate
    return best


def parse_schedule(rows: list) -> Optional[ParsedSchedule]:
    if not rows:
        return None

    parsed = ParsedSchedule(
        rows=rows,
        parity_even=_parse_parity(rows),
    )
    years = _parse_years(rows)

    # --- шапка с группами ---
    header_idx = -1
    for i, row in enumerate(rows):
        if len(row) > 2 and "день" in _norm(row[0]).lower() and "часы" in _norm(row[1]).lower():
            header_idx = i
            for col in range(2, len(row)):
                name = _norm(row[col])
                if name:
                    parsed.groups[col] = name
            break
    if header_idx == -1 or not parsed.groups:
        return None

    # --- блоки дней ---
    for i in range(header_idx + 1, len(rows)):
        row = rows[i]
        if not row or not _norm(row[0]):
            continue
        day = _parse_day(_norm(row[0]), years)
        if day:
            if parsed.days:
                parsed.days[-1].end = i
            parsed.days.append(DayBlock(day=day, start=i, end=len(rows)))

    return parsed if parsed.days else None


# ===================== ДОСТУП К ФАЙЛАМ =====================

def get_schedule_urls(faculty: str, course: int, is_even: bool) -> list:
    week_folder = "Четная неделя" if is_even else "Нечетная неделя"
    urls = SCHEDULE_URLS.get(week_folder, {}).get(faculty, {}).get(course)
    if not urls:
        return []
    return [urls] if isinstance(urls, str) else list(urls)


async def get_parsed(url: str) -> Optional[ParsedSchedule]:
    cached = _PARSED_CACHE.get(url)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    rows = await get_rows(url)
    if not rows:
        return None
    parsed = parse_schedule(rows)
    if parsed:
        _PARSED_CACHE[url] = (time.time(), parsed)
    return parsed


async def get_course_files(faculty: str, course: int) -> List[ParsedSchedule]:
    """Оба файла курса (чётная + нечётная), качаются параллельно."""
    urls = []
    for is_even in (True, False):
        urls.extend(get_schedule_urls(faculty, course, is_even))
    if not urls:
        return []
    results = await asyncio.gather(*(get_parsed(u) for u in urls))
    return [r for r in results if r]


async def get_available_groups(faculty: str, course: int) -> List[str]:
    """Список групп курса из актуальных файлов."""
    files = await get_course_files(faculty, course)
    groups: List[str] = []
    for parsed in files:
        for name in parsed.groups.values():
            if name not in groups:
                groups.append(name)
    return groups


# ===================== ДАТЫ =====================

def resolve_target_date(command: str, now: Optional[datetime] = None) -> date_cls:
    """
    'сегодня' / 'завтра' / 'пн'..'сб'.
    Дни недели — это дни ТЕКУЩЕЙ недели (пн-сб), а не ближайшее будущее.
    В воскресенье показываем уже следующую неделю: учебная неделя закончилась.
    """
    now = now or datetime.now(TZ)
    cmd = command.lower().strip()

    if cmd == "сегодня":
        return now.date()
    if cmd == "завтра":
        return (now + timedelta(days=1)).date()

    idx = WEEKDAY_COMMANDS.get(cmd)
    if idx is None:
        return now.date()

    monday = now.date() - timedelta(days=now.weekday())
    if now.weekday() == 6:          # воскресенье
        monday += timedelta(days=7)
    return monday + timedelta(days=idx)


def guess_parity(day: date_cls, files: List[ParsedSchedule]) -> Optional[bool]:
    """
    Чётность недели для даты, которой нет ни в одном файле:
    берём известную неделю и считаем разницу в неделях.
    """
    for parsed in files:
        if parsed.parity_even is None or not parsed.days:
            continue
        known = parsed.first_day
        known_monday = known - timedelta(days=known.weekday())
        target_monday = day - timedelta(days=day.weekday())
        weeks = (target_monday - known_monday).days // 7
        return parsed.parity_even if weeks % 2 == 0 else not parsed.parity_even
    return None


# ===================== РАСПИСАНИЕ ГРУППЫ =====================

async def get_day_schedule(faculty: str, course: int, group: str, command: str) -> str:
    target = resolve_target_date(command)
    files = await get_course_files(faculty, course)

    if not files:
        return _msg_error(group, target,
                          "Не удалось получить файл расписания\\. "
                          "Скорее всего, сайт вуза сейчас недоступен — попробуй позже\\.")

    group_seen = False
    same_week_file = None
    for parsed in files:
        col = parsed.group_column(group)
        if col == -1:
            continue
        group_seen = True
        lessons = parsed.lessons(target, col)
        if lessons is not None:
            return format_schedule(lessons, parsed.parity_even, target, group)
        if parsed.covers_week_of(target):
            same_week_file = parsed

    # файл на эту неделю есть, а строк для этого дня в таблице нет => пар нет
    if same_week_file is not None:
        return format_schedule([], same_week_file.parity_even, target, group)

    if not group_seen:
        return _msg_error(
            group, target,
            "Группа не найдена в файлах расписания\\. "
            "Возможно, её переименовали — нажми /start и выбери группу заново\\."
        )

    # группа есть, но такого дня в выложенных файлах нет
    parity = guess_parity(target, files)
    known = sorted({b.day for p in files for b in p.days})
    hint = ""
    if known:
        hint = (f"\nВыложено расписание с {escape_markdown(_short_date(known[0]))} "
                f"по {escape_markdown(_short_date(known[-1]))}\\.")
    return _msg_error(
        group, target,
        "Расписание на этот день ещё не выложено на сайте вуза\\." + hint,
        parity=parity,
    )


def _short_date(day: date_cls) -> str:
    return f"{day.day} {RUS_MONTHS[day.month]}"


def _header(group: str, day: date_cls, parity: Optional[bool]) -> List[str]:
    date_str = f"{RUS_DAYS_SHORT[day.weekday()]} {day.day} {RUS_MONTHS[day.month]}"
    lines = []
    if parity is not None:
        lines.append(f"*📅 {'Четная' if parity else 'Нечетная'} неделя*")
    lines.append(f"*👥 {escape_markdown(group)}*")
    lines.append(f"\n🟢__*{escape_markdown(date_str)}*__\n")
    return lines


def _msg_error(group: str, day: date_cls, text: str, parity: Optional[bool] = None) -> str:
    return "\n".join(_header(group, day, parity) + [f"ℹ️ {text}"])


def format_schedule(lessons, parity: Optional[bool], day: date_cls, group: str) -> str:
    result = _header(group, day, parity)

    if not lessons:
        result.append("🎉 *Пар нет, можно отдыхать\\!*")
    else:
        for time_str, subject_lines in lessons:
            result.append(f"*⏰ {escape_markdown(time_str)}*")
            for line in subject_lines:
                result.append(f"• {escape_markdown(line)}")
            result.append("")

    return "\n".join(result)


# ===================== ПОИСК ПРЕПОДАВАТЕЛЯ =====================

async def get_teacher_schedule(teacher_name: str, target_date) -> str:
    """Ищет преподавателя во всех файлах всех факультетов на указанную дату."""
    if isinstance(target_date, datetime):
        day = target_date.date()
    else:
        day = target_date

    needle = teacher_name.lower().strip()

    urls = []
    for week_type, faculties in SCHEDULE_URLS.items():
        for faculty, courses in faculties.items():
            for course, value in courses.items():
                for url in ([value] if isinstance(value, str) else value):
                    urls.append((faculty, course, url))

    parsed_list = await asyncio.gather(*(get_parsed(u) for _, _, u in urls))

    findings = []
    seen = set()
    for (faculty, course, _url), parsed in zip(urls, parsed_list):
        if not parsed or not parsed.has_day(day):
            continue
        for col, group_name in parsed.groups.items():
            lessons = parsed.lessons(day, col) or []
            for time_str, lines in lessons:
                if not any(needle in line.lower() for line in lines):
                    continue
                # одна и та же лекция у нескольких групп -> одна запись
                key = (time_str, tuple(lines))
                if key in seen:
                    existing = next(f for f in findings if (f["time"], tuple(f["details"])) == key)
                    if group_name not in existing["groups"]:
                        existing["groups"].append(group_name)
                    continue
                seen.add(key)
                findings.append({
                    "time": time_str,
                    "groups": [group_name],
                    "faculty": faculty,
                    "course": course,
                    "details": lines,
                    "parity": parsed.parity_even,
                })

    findings.sort(key=lambda f: (_time_key((f["time"],)), f["groups"][0]))
    return format_teacher_schedule(teacher_name, day, findings)


def format_teacher_schedule(teacher_name: str, day: date_cls, findings: list) -> str:
    date_str = f"{RUS_DAYS_SHORT[day.weekday()]} {day.day} {RUS_MONTHS[day.month]}"
    result = [
        f"*{escape_markdown('🧑‍🏫 Расписание преподавателя:')}*",
        f"*{escape_markdown(teacher_name)}*",
    ]

    parity = next((f["parity"] for f in findings if f["parity"] is not None), None)
    if parity is not None:
        result.append(f"*📅 {'Четная' if parity else 'Нечетная'} неделя*")

    result.append(f"\n🟢__*{escape_markdown(date_str)}*__\n")

    if not findings:
        result.append("❌ *На эту дату пары не найдены\\.*")
        result.append("_Проверь написание фамилии — искать можно и по одной фамилии\\._")
    else:
        for item in findings:
            result.append(f"*⏰ {escape_markdown(item['time'])}*")
            groups_str = ", ".join(item["groups"])
            label = "Группы" if len(item["groups"]) > 1 else "Группа"
            result.append(f"👥 *{label}:* {escape_markdown(groups_str)}")
            for line in item["details"]:
                result.append(f"• {escape_markdown(line)}")
            result.append("")

    return "\n".join(result)
