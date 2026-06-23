import logging

from sqlalchemy import select

from bot.config import settings
from bot.database.connection import async_session_factory
from bot.database.models import User

logger = logging.getLogger(__name__)


async def ensure_admin_user() -> None:
    if not settings.admin_id:
        logger.info("ADMIN_ID не задан — автосоздание администратора пропущено")
        return

    async with async_session_factory() as session:
        admin = await session.scalar(
            select(User).where(User.telegram_id == settings.admin_id)
        )
        if admin is None:
            session.add(User(telegram_id=settings.admin_id, is_admin=True))
            await session.commit()
            logger.info("Администратор %s добавлен в whitelist", settings.admin_id)
            return

        if not admin.is_admin:
            admin.is_admin = True
            await session.commit()
            logger.info("Пользователю %s выдан статус администратора", settings.admin_id)
