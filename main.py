import asyncio
import os
import threading
import http.server
import socketserver
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import router


# 🔹 Фейковый HTTP-сервер для Render (если используешь Web Service)
def fake_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"🌐 Фейковый сервер запущен на порту {port} (для Render)")
        httpd.serve_forever()


async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    print("✅ Бот запущен с системой регистрации и файловым хранилищем")
    await dp.start_polling(bot)


if __name__ == "__main__":
    # 🔹 Запускаем фейковый HTTP-сервер в отдельном потоке
    threading.Thread(target=fake_server, daemon=True).start()

    # 🔹 Запускаем Telegram-бота
    asyncio.run(main())
