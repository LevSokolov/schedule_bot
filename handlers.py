import re
from datetime import datetime, timedelta

from aiogram import Bot, F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove)

from config import (FACULTIES, GROUP_CHAT_ID, TZ, get_user_data,
                    load_known_groups, remove_user_data, save_known_groups,
                    update_user_data)
from schedule_parser import (RUS_DAYS_SHORT, get_available_groups,
                             get_day_schedule, get_teacher_schedule)
from states import Registration, TeacherSearch

router = Router()

CHANNEL_USERNAME = "@smartschedule0"
MANUAL_GROUP_BUTTON = "✍️ Ввести группу вручную"
DAY_COMMANDS = {"сегодня", "завтра", "пн", "вт", "ср", "чт", "пт", "сб"}

# Название группы: буквы/цифры и дефис, например СОа-423, ИТм-116
GROUP_PATTERN = re.compile(r"^[А-Яа-яЁёA-Za-z]{1,6}[-–—]?\d{2,4}[а-яА-Я]?$")


# --- Клавиатуры ---

def get_subscription_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал",
                                  url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")]
        ]
    )


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


def get_groups_keyboard(groups: list):
    """Кнопки групп + запасной вариант «ввести вручную»."""
    buttons = [[KeyboardButton(text=g) for g in groups[i:i + 3]]
               for i in range(0, len(groups), 3)]
    buttons.append([KeyboardButton(text=MANUAL_GROUP_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def get_schedule_keyboard():
    buttons = [
        [KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")],
        [KeyboardButton(text="Пн"), KeyboardButton(text="Вт"), KeyboardButton(text="Ср")],
        [KeyboardButton(text="Чт"), KeyboardButton(text="Пт"), KeyboardButton(text="Сб")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=False)


async def check_user_subscription(bot: Bot, user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False


async def require_subscription(message: Message, bot: Bot) -> bool:
    if await check_user_subscription(bot, message.from_user.id):
        return True
    await message.answer(
        "⚠️ Для использования бота необходимо подписаться на наш канал!",
        reply_markup=get_subscription_keyboard()
    )
    return False


# --- Основные хендлеры ---

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback_query: types.CallbackQuery, bot: Bot):
    user_id = callback_query.from_user.id
    if await check_user_subscription(bot, user_id):
        await callback_query.message.delete()
        if await get_user_data(user_id):
            await callback_query.message.answer("Теперь вы можете посмотреть расписание:",
                                                reply_markup=get_schedule_keyboard())
        else:
            await callback_query.message.answer("Для начала работы используйте команду /start",
                                                reply_markup=ReplyKeyboardRemove())
    else:
        await callback_query.answer("❌ Вы еще не подписались на канал!", show_alert=True)


@router.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return

    user_id = message.from_user.id
    old_user_data = await get_user_data(user_id)

    if old_user_data:
        try:
            await bot.send_message(chat_id=GROUP_CHAT_ID, text=(
                f"🗑 Удалена старая запись пользователя:\n"
                f"Имя: {old_user_data.get('full_name', 'Неизвестно')}\n"
                f"Username: {old_user_data.get('username', 'Нет')}\n"
                f"Факультет: {old_user_data.get('faculty', '-')}\n"
                f"Курс: {old_user_data.get('course', '-')}\n"
                f"Группа: {old_user_data.get('group', '-')}"
            ))
        except Exception as e:
            print(f"❌ Не удалось отправить лог удаления: {e}")
        await remove_user_data(user_id)

    await message.answer("Добро пожаловать! Выберите ваш факультет:",
                         reply_markup=get_faculties_keyboard())
    await state.set_state(Registration.choosing_faculty)


@router.message(Registration.choosing_faculty, F.text.in_(FACULTIES.keys()))
async def faculty_chosen(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return
    await state.update_data(faculty=message.text)
    await message.answer("Отлично! Теперь выберите ваш курс:", reply_markup=get_courses_keyboard())
    await state.set_state(Registration.choosing_course)


@router.message(Registration.choosing_faculty)
async def wrong_faculty(message: Message):
    await message.answer("Пожалуйста, выберите факультет из предложенных вариантов:",
                         reply_markup=get_faculties_keyboard())


@router.message(Registration.choosing_course, F.text.in_(["1", "2", "3", "4", "5"]))
async def course_chosen(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return

    course = message.text
    data = await state.get_data()
    faculty = data['faculty']

    # 1) пробуем взять группы из свежего расписания
    groups = await get_available_groups(faculty, int(course))
    if groups:
        await save_known_groups(faculty, course, groups)
        hint = "Отлично! Теперь выберите вашу группу:"
    else:
        # 2) расписания нет (каникулы, сайт лежит) — берём то, что запомнили
        groups = await load_known_groups(faculty, course)
        hint = ("Расписание на сайте сейчас недоступно (возможно, каникулы).\n"
                "Вот группы, которые бот видел раньше — или введи название вручную:")

    await state.update_data(course=course, available_groups=groups)
    await state.set_state(Registration.choosing_group)

    if not groups:
        # 3) вообще ничего нет — просим ввести руками, а не оставляем без кнопок
        await state.set_state(Registration.typing_group)
        await message.answer(
            "Расписания для этого курса сейчас нет на сайте, поэтому список групп пуст.\n"
            "Напиши название своей группы текстом, например: СОа-423",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    await message.answer(hint, reply_markup=get_groups_keyboard(groups))


@router.message(Registration.choosing_course)
async def wrong_course(message: Message):
    await message.answer("Пожалуйста, выберите курс от 1 до 5:", reply_markup=get_courses_keyboard())


@router.message(Registration.choosing_group, F.text == MANUAL_GROUP_BUTTON)
async def manual_group_requested(message: Message, state: FSMContext):
    await state.set_state(Registration.typing_group)
    await message.answer(
        "Напиши название группы ровно так, как оно написано в расписании.\n"
        "Например: СОа-423",
        reply_markup=ReplyKeyboardRemove()
    )


async def _finish_registration(message: Message, state: FSMContext, bot: Bot, group: str):
    data = await state.get_data()
    user_info = {
        'faculty': data['faculty'],
        'course': data['course'],
        'group': group,
        'username': f"@{message.from_user.username}" if message.from_user.username else "нет username",
        'full_name': message.from_user.full_name or "Неизвестно"
    }
    await update_user_data(message.from_user.id, user_info)
    await save_known_groups(data['faculty'], data['course'], [group])

    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=(
            f"✅ Новый пользователь зарегистрирован:\n"
            f"Имя: {user_info['full_name']}\n"
            f"Username: {user_info['username']}\n"
            f"Факультет: {user_info['faculty']}\n"
            f"Курс: {user_info['course']}\n"
            f"Группа: {user_info['group']}"
        ))
    except Exception as e:
        print(f"❌ Не удалось отправить лог регистрации: {e}")

    await message.answer(
        f"✅ Регистрация завершена!\n"
        f"Факультет: {data['faculty']}\nКурс: {data['course']}\nГруппа: {group}\n\n"
        f"Теперь вы можете посмотреть расписание:",
        reply_markup=get_schedule_keyboard()
    )
    await state.clear()


@router.message(Registration.choosing_group)
async def group_chosen(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return

    group = (message.text or "").strip()
    data = await state.get_data()

    if group not in data.get('available_groups', []):
        await message.answer(
            "Такой группы нет в списке. Выбери кнопкой или нажми "
            f"«{MANUAL_GROUP_BUTTON}»."
        )
        return

    await _finish_registration(message, state, bot, group)


@router.message(Registration.typing_group)
async def group_typed(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return

    group = (message.text or "").strip()
    if not GROUP_PATTERN.match(group):
        await message.answer(
            "Не похоже на название группы. Формат такой: СОа-423, ИТ-126, ИБм-116.\n"
            "Попробуй ещё раз:"
        )
        return

    await _finish_registration(message, state, bot, group)


@router.message(F.text.lower().in_(DAY_COMMANDS))
async def day_selected(message: Message, state: FSMContext, bot: Bot):
    # выходим из режима поиска преподавателя, если он был
    if await state.get_state() is not None:
        await state.clear()

    user_id = message.from_user.id
    if not await require_subscription(message, bot):
        return

    user_info = await get_user_data(user_id)
    if not user_info:
        await message.answer("Сначала зарегистрируйтесь с помощью команды /start",
                             reply_markup=ReplyKeyboardRemove())
        return

    schedule_text = await get_day_schedule(
        user_info['faculty'], int(user_info['course']),
        user_info['group'], message.text.lower()
    )
    await message.answer(schedule_text, parse_mode=ParseMode.MARKDOWN_V2)


@router.message(Command("reset"))
async def reset_cmd(message: Message, state: FSMContext):
    if await remove_user_data(message.from_user.id):
        await message.answer("Регистрация сброшена. Используйте /start для новой регистрации.",
                             reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("Вы еще не зарегистрированы. Используйте /start для регистрации.",
                             reply_markup=ReplyKeyboardRemove())
    await state.clear()


@router.message(Command("me"))
async def me_cmd(message: Message):
    user_info = await get_user_data(message.from_user.id)
    if user_info:
        response = (f"Ваши данные:\n"
                    f"Факультет: {user_info['faculty']}\n"
                    f"Курс: {user_info['course']}\n"
                    f"Группа: {user_info['group']}")
    else:
        response = "Вы еще не зарегистрированы. Используйте /start для регистрации."
    await message.answer(response)


@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "Что я умею:\n"
        "• Кнопки Пн–Сб — расписание на день ТЕКУЩЕЙ недели\n"
        "• Сегодня / Завтра — как понятно\n"
        "• Напиши фамилию преподавателя (например «Попов Антон») — покажу его пары\n"
        "• /me — твоя группа, /start — сменить группу, /reset — удалить регистрацию"
    )


# ===== ПОИСК ПРЕПОДАВАТЕЛЯ =====

def get_teacher_search_keyboard():
    """Кнопки с днями текущей недели."""
    now = datetime.now(TZ)
    monday = now.date() - timedelta(days=now.weekday())
    if now.weekday() == 6:
        monday += timedelta(days=7)

    buttons = []
    for i in range(6):  # Пн..Сб
        day = monday + timedelta(days=i)
        buttons.append(InlineKeyboardButton(
            text=f"{RUS_DAYS_SHORT[i]} {day.strftime('%d.%m')}",
            callback_data=f"teacher_date_{day.strftime('%Y-%m-%d')}"
        ))
    return InlineKeyboardMarkup(inline_keyboard=[buttons[:3], buttons[3:]])


@router.message(F.text, lambda msg: msg.text and len(msg.text.split()) >= 2
                and msg.text not in FACULTIES and not msg.text.startswith("/"))
async def handle_teacher_name(message: Message, state: FSMContext, bot: Bot):
    if not await require_subscription(message, bot):
        return

    teacher_name = message.text.strip()
    await state.set_state(TeacherSearch.choosing_date)
    await state.update_data(teacher_name=teacher_name)
    await message.answer(
        f"🧑‍🏫 Ищу преподавателя: {teacher_name}\n\nВыбери день:",
        reply_markup=get_teacher_search_keyboard()
    )


@router.callback_query(TeacherSearch.choosing_date, F.data.startswith("teacher_date_"))
async def handle_teacher_date_selection(callback_query: types.CallbackQuery, state: FSMContext):
    date_str = callback_query.data.replace("teacher_date_", "")
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    data = await state.get_data()
    teacher_name = data.get("teacher_name")
    if not teacher_name:
        await callback_query.message.edit_text("Ошибка: имя преподавателя потерялось. Напиши его ещё раз.")
        await state.clear()
        return

    await callback_query.answer()
    await callback_query.message.edit_text("⏳ Ищу расписание, это займёт несколько секунд...")

    try:
        schedule_text = await get_teacher_schedule(teacher_name, target_date)
        await callback_query.message.edit_text(schedule_text, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        print(f"❌ Ошибка поиска преподавателя: {e}")
        await callback_query.message.edit_text("😔 Не получилось выполнить поиск. Попробуй ещё раз.")

    await state.clear()
