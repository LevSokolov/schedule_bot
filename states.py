from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    choosing_faculty = State()
    choosing_course = State()
    choosing_group = State()
    typing_group = State()      # ручной ввод группы, когда расписания нет


class TeacherSearch(StatesGroup):
    choosing_date = State()
