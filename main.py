import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import router

async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    print("✅ Бот запущен с системой регистрации и файловым хранилищем")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())