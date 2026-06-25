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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_HOST = "0.0.0.0"
API_PORT = 8000


def create_bot() -> Bot:
    default = DefaultBotProperties(parse_mode=ParseMode.HTML)

    if settings.telegram_proxy:
        session = AiohttpSession(proxy=settings.telegram_proxy)
        bot = Bot(token=settings.bot_token, session=session, default=default)
        logger.info("Telegram-бот подключён через HTTP-прокси")
        return bot

    return Bot(token=settings.bot_token, default=default)


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
    dispatcher.startup.register(ensure_admin_user)

    fastapi_app = create_app()
    fastapi_app.state.bot = bot

    logger.info("Optop запущен: Telegram-бот + FastAPI на %s:%s", API_HOST, API_PORT)

    await asyncio.gather(
        run_bot(dispatcher, bot),
        run_api(fastapi_app),
    )


if __name__ == "__main__":
    asyncio.run(main())
