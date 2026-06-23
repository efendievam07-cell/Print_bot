from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User


class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)

        session: AsyncSession = data["session"]
        telegram_user = event.from_user

        db_user = await session.scalar(
            select(User).where(User.telegram_id == telegram_user.id)
        )
        if db_user is None:
            await event.answer("У вас нет доступа к боту")
            return None

        if telegram_user.username and db_user.username != telegram_user.username:
            db_user.username = telegram_user.username
            await session.commit()

        data["db_user"] = db_user
        return await handler(event, data)
