import asyncio

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramConflictError
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config import BOT_TOKEN, close_db_pool, create_tables, init_db_pool
from handlers import router


async def handle(request):
    return web.Response(text="✅ Bot is alive!", content_type="text/plain")


async def run_bot(bot: Bot, dp: Dispatcher):
    """
    Polling с переживанием конфликта.

    При деплое Render запускает новый инстанс, пока старый ещё жив.
    Два процесса одновременно дёргают getUpdates -> Telegram отдаёт 409,
    и раньше новая версия просто падала. Теперь она подождёт, пока старый
    инстанс умрёт, и продолжит работу сама.
    """
    delay = 5
    while True:
        try:
            await dp.start_polling(bot)
            return
        except TelegramConflictError:
            print(f"⚠️ Другой инстанс бота ещё жив, жду {delay} с...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
        except Exception as e:
            print(f"❌ Polling упал: {e}. Перезапуск через 10 с")
            await asyncio.sleep(10)


async def run_web(app: web.Application):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    print("🌐 Web server запущен на порту 10000")


async def main():
    await init_db_pool()
    await create_tables()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    app = web.Application()
    app.router.add_get("/", handle)

    try:
        await run_web(app)
        await run_bot(bot, dp)
    finally:
        await close_db_pool()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
