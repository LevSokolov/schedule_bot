import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, create_tables, init_db_pool, close_db_pool
from handlers import router
from aiohttp import web

async def handle(request):
    return web.Response(text="✅ Bot is alive!", content_type="text/plain")

async def main():
    # 1. Сначала запускаем пул соединений
    await init_db_pool()
    
    # 2. Создаем таблицы
    await create_tables()
    
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    # aiohttp сервер
    app = web.Application()
    app.router.add_get("/", handle)

    # Запуск Telegram бота и веб-сервера параллельно
    async def run_bot():
        try:
            await dp.start_polling(bot)
        finally:
            await close_db_pool() # Закрываем базу при остановке бота

    async def run_web():
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 10000)
        await site.start()
        print("🌐 Web server запущен на порту 10000")
        # Веб-сервер будет работать вечно, пока не упадет

    await asyncio.gather(run_bot(), run_web())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
