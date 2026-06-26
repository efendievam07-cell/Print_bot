from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.database.models import User


class IsAdminFilter(BaseFilter):
    async def __call__(self, message: Message, db_user: User | None = None) -> bool:
        # db_user кладёт WhitelistMiddleware (outer). Если его нет в контексте —
        # пользователь не прошёл whitelist, админом он быть не может.
        return bool(db_user and db_user.is_admin)
