from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User

router = Router()

MY_TELEGRAM_ID = 1385570396


@router.message(Command("add_user"), lambda msg: msg.from_user.id == MY_TELEGRAM_ID)
async def cmd_add_user(message: Message, session: AsyncSession) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /add_user <telegram_id>")
        return

    try:
        telegram_id = int(args[1].strip())
    except ValueError:
        await message.answer("Telegram ID должен быть числом.")
        return

    existing = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if existing:
        await message.answer(f"Пользователь {telegram_id} уже есть в whitelist.")
        return

    session.add(User(telegram_id=telegram_id))
    await session.commit()
    await message.answer(f"Пользователь {telegram_id} добавлен.")


@router.message(Command("remove_user"), lambda msg: msg.from_user.id == MY_TELEGRAM_ID)
async def cmd_remove_user(message: Message, session: AsyncSession, db_user: User) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /remove_user <telegram_id>")
        return

    try:
        telegram_id = int(args[1].strip())
    except ValueError:
        await message.answer("Telegram ID должен быть числом.")
        return

    if telegram_id == db_user.telegram_id:
        await message.answer("Нельзя удалить самого себя.")
        return

    target = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if target is None:
        await message.answer(f"Пользователь {telegram_id} не найден.")
        return

    await session.delete(target)
    await session.commit()
    await message.answer(f"Пользователь {telegram_id} удалён.")


@router.message(Command("users"), lambda msg: msg.from_user.id == MY_TELEGRAM_ID)
async def cmd_users(message: Message, session: AsyncSession) -> None:
    users = (await session.scalars(select(User).order_by(User.id))).all()
    if not users:
        await message.answer("Список сотрудников пуст.")
        return

    lines = ["Сотрудники в whitelist:"]
    for user in users:
        username = f"@{user.username}" if user.username else "—"
        admin_mark = " [admin]" if user.is_admin else ""
        lines.append(f"• {user.telegram_id} | {username}{admin_mark}")

    await message.answer("\n".join(lines))
