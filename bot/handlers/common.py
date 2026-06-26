from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="common")


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    await message.answer(
        f"Ваш Telegram ID: <code>{user.id}</code>\n"
        "Передайте его администратору, чтобы он добавил вас в whitelist."
    )
