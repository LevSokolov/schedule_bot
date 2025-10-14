from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
import os

from config import FACULTIES, GROUP_CHAT_ID, add_or_update_user, get_user, remove_user, create_db_pool
from states import Registration
from schedule_parser import get_day_schedule, get_available_groups

router = Router()
bot = Bot(token=os.getenv("BOT_TOKEN"))

# ====================== КЛАВИАТУРЫ ======================
def get_faculties_keyboard():
    buttons, row = [], []
    for faculty in FACULTIES.keys():
        row.append(KeyboardButton(text=faculty))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_courses_keyboard():
    buttons = [
        [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")],
        [KeyboardButton(text="4"), KeyboardButton(text="5")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_schedule_keyboard():
    buttons = [
        [KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")],
        [KeyboardButton(text="Пн"), KeyboardButton(text="Вт"), KeyboardButton(text="Ср")],
        [KeyboardButton(text="Чт"), KeyboardButton(text="Пт"), KeyboardButton(text="Сб")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=False)

# ====================== РЕГИСТРАЦИЯ ======================
@router.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    pool = await create_db_pool()
    user_id = message.from_user.id
    old_user = await get_user(pool, user_id)

    if old_user:
        await remove_user(pool, user_id)
        try:
            await bot.send_message(
                GROUP_CHAT_ID,
                f"🗑 Удалена старая запись пользователя:\n"
                f"Имя: {old_user['full_name']}\n"
                f"Username: {old_user['username']}\n"
                f"Факультет: {old_user['faculty']}\n"
                f"Курс: {old_user['course']}\n"
                f"Группа: {old_user['user_group']}"
            )
        except Exception as e:
            print(f"Ошибка при отправке уведомления: {e}")

    await message.answer("Добро пожаловать! Выберите ваш факультет:", reply_markup=get_faculties_keyboard())
    await state.set_state(Registration.choosing_faculty)

@router.message(Registration.choosing_faculty, F.text.in_(FACULTIES.keys()))
async def faculty_chosen(message: Message, state: FSMContext):
    await state.update_data(faculty=message.text)
    await message.answer("Теперь выберите ваш курс:", reply_markup=get_courses_keyboard())
    await state.set_state(Registration.choosing_course)

@router.message(Registration.choosing_faculty)
async def wrong_faculty(message: Message):
    await message.answer("Выберите факультет из предложенных:", reply_markup=get_faculties_keyboard())

@router.message(Registration.choosing_course, F.text.in_(["1", "2", "3", "4", "5"]))
async def course_chosen(message: Message, state: FSMContext):
    course = message.text
    data = await state.get_data()
    faculty = data["faculty"]

    groups = get_available_groups(faculty, int(course))
    if not groups:
        await message.answer(
            f"Для {faculty} {course} курса не найдено расписания.\nПопробуйте другой курс.",
            reply_markup=get_courses_keyboard()
        )
        return

    await state.update_data(course=course, available_groups=groups)

    # создаём клавиатуру групп
    group_buttons, row = [], []
    for group in groups:
        row.append(KeyboardButton(text=group))
        if len(row) == 3:
            group_buttons.append(row)
            row = []
    if row:
        group_buttons.append(row)

    await message.answer("Выберите вашу группу:", reply_markup=ReplyKeyboardMarkup(keyboard=group_buttons, resize_keyboard=True, one_time_keyboard=True))
    await state.set_state(Registration.choosing_group)

@router.message(Registration.choosing_course)
async def wrong_course(message: Message):
    await message.answer("Выберите курс от 1 до 5:", reply_markup=get_courses_keyboard())

@router.message(Registration.choosing_group)
async def group_chosen(message: Message, state: FSMContext):
    pool = await create_db_pool()
    group = message.text
    data = await state.get_data()
    available_groups = data.get("available_groups", [])

    if group not in available_groups:
        await message.answer("Пожалуйста, выберите группу из предложенных.")
        return

    user_info = {
        "faculty": data["faculty"],
        "course": data["course"],
        "user_group": group,
        "username": f"@{message.from_user.username}" if message.from_user.username else "нет username",
        "full_name": message.from_user.full_name or "Неизвестно",
    }

    await add_or_update_user(pool, message.from_user.id, user_info)

    admin_message = (
        f"✅ Новый пользователь зарегистрирован:\n"
        f"Имя: {user_info['full_name']}\n"
        f"Username: {user_info['username']}\n"
        f"Факультет: {user_info['faculty']}\n"
        f"Курс: {user_info['course']}\n"
        f"Группа: {user_info['user_group']}"
    )

    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=admin_message)
    except Exception as e:
        print(f"Не удалось отправить сообщение в группу: {e}")

    await message.answer(
        f"✅ Регистрация завершена!\n"
        f"Факультет: {user_info['faculty']}\n"
        f"Курс: {user_info['course']}\n"
        f"Группа: {user_info['user_group']}\n\n"
        f"Теперь можно посмотреть расписание:",
        reply_markup=get_schedule_keyboard()
    )
    await state.clear()

# ====================== РАСПИСАНИЕ ======================
@router.message(F.text.lower().in_({"сегодня", "завтра", "пн", "вт", "ср", "чт", "пт", "сб"}))
async def day_selected(message: Message):
    pool = await create_db_pool()
    user = await get_user(pool, message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start", reply_markup=ReplyKeyboardRemove())
        return

    schedule_text = get_day_schedule(user["faculty"], int(user["course"]), user["user_group"], message.text.lower())
    await message.answer(schedule_text, parse_mode=ParseMode.MARKDOWN_V2)

# ====================== ПРОЧЕЕ ======================
@router.message(Command("reset"))
async def reset_cmd(message: Message, state: FSMContext):
    pool = await create_db_pool()
    deleted = await remove_user(pool, message.from_user.id)
    if deleted:
        await message.answer("Регистрация сброшена. Используйте /start заново.", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("Вы ещё не зарегистрированы.", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@router.message(Command("me"))
async def me_cmd(message: Message):
    pool = await create_db_pool()
    user = await get_user(pool, message.from_user.id)
    if user:
        text = (
            f"Ваши данные:\n"
            f"Факультет: {user['faculty']}\n"
            f"Курс: {user['course']}\n"
            f"Группа: {user['user_group']}"
        )
    else:
        text = "Вы ещё не зарегистрированы. Используйте /start."
    await message.answer(text)
