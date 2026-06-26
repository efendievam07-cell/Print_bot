import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.api import create_app
from bot.config import settings
from bot.handlers import main_router
from bot.middlewares import DbSessionMiddleware, WhitelistMiddleware
from bot.utils.assets import ensure_default_assets
from bot.utils.startup import ensure_admin_user

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

API_HOST = "0.0.0.0"
API_PORT = 8000


def create_bot() -> Bot:
    """Единственная точка инициализации транспорта Telegram.

    SOCKS5/HTTP-прокси передаётся в aiogram строкой — aiogram сам собирает
    ProxyConnector из aiohttp-socks. Ручной ProxyConnector здесь не нужен.
    """
    default = DefaultBotProperties(parse_mode=ParseMode.HTML)

    session = None
    if settings.telegram_proxy:
        session = AiohttpSession(proxy=settings.telegram_proxy)
        scheme = settings.telegram_proxy.split("://", 1)[0]
        logger.info("Telegram-сессия через прокси (%s)", scheme)
    else:
        logger.info("Telegram-сессия без прокси (прямое подключение)")

    return Bot(token=settings.bot_token, session=session, default=default)


async def verify_connection(bot: Bot) -> None:
    """Честная проверка туннеля до запуска polling.

    Если прокси-стек или версии библиотек битые, упадём здесь с понятной
    ошибкой, а не повиснем молча после ложного 'Start polling'.
    """
    me = await bot.get_me()
    logger.info("Подключение к Telegram OK: @%s (id=%s)", me.username, me.id)


async def on_startup(bot: Bot) -> None:
    """Снимаем возможный зависший вебхук и чистим висящие апдейты.

    Закрывает класс багов '409 Conflict' и 'getUpdates не работает, пока
    активен webhook'.
    """
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook удалён, pending updates сброшены")
    await ensure_admin_user()


async def run_bot(dispatcher: Dispatcher, bot: Bot) -> None:
    await dispatcher.start_polling(bot)


async def run_api(fastapi_app) -> None:
    config = uvicorn.Config(
        fastapi_app,
        host=API_HOST,
        port=API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    ensure_default_assets()

    bot = create_bot()
    dispatcher = Dispatcher(storage=MemoryStorage())

    dispatcher.update.middleware(DbSessionMiddleware())
    dispatcher.message.middleware(WhitelistMiddleware())

    dispatcher.include_router(main_router)
    dispatcher.startup.register(on_startup)

    await verify_connection(bot)

    fastapi_app = create_app()
    fastapi_app.state.bot = bot

    logger.info("Optop запущен: Telegram-бот + FastAPI на %s:%s", API_HOST, API_PORT)

    await asyncio.gather(
        run_bot(dispatcher, bot),
        run_api(fastapi_app),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановка по сигналу")
