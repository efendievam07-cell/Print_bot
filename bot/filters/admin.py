from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.database.models import User


class IsAdminFilter(BaseFilter):
    async def __call__(self, message: Message, db_user: User) -> bool:
        return db_user.is_admin
