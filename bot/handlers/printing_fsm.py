import uuid
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import PrintJob, PrintJobStatus, User
from bot.services.image_processor import LabelGenerator
from bot.services.printer_api import printer_manager
from bot.states.printing import PrintingStates
from bot.utils.label_paths import build_label_output_path

router = Router()

SCREENSHOTS_DIR = Path("data/labels/screenshots")
DEFAULT_LOGO_PATH = Path("data/assets/logo.png")
DEFAULT_QR_IOS_PATH = Path("data/assets/qr_ios.png")
DEFAULT_QR_ANDROID_PATH = Path("data/assets/qr_android.png")

PHOTO_RECEIVED_TEXT = (
    "Фото получено. Теперь отправьте номера заказов (можно несколько строк)."
)
PHOTO_REPLACED_TEXT = "Новое фото сохранено. Отправьте номера заказов."


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Optop — генерация этикеток для печати.\n\n"
        "Отправьте фото отправления или используйте /print.\n"
        "После фото бот попросит номера заказов."
    )


@router.message(Command("print"))
async def cmd_print(message: Message, state: FSMContext) -> None:
    await _clear_screenshot_data(state)
    await state.clear()
    await state.set_state(PrintingStates.waiting_for_screenshot)
    await message.answer("Отправьте фото отправления (скриншот).")


@router.message(StateFilter(None), F.photo | F.document)
async def handle_screenshot_auto_start(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db_user: User,
) -> None:
    await _accept_screenshot(message, state, bot, db_user)


@router.message(PrintingStates.waiting_for_screenshot, F.photo | F.document)
async def handle_screenshot(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db_user: User,
) -> None:
    await _accept_screenshot(message, state, bot, db_user)


@router.message(PrintingStates.waiting_for_order_numbers, F.photo | F.document)
async def handle_screenshot_replace(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db_user: User,
) -> None:
    await _accept_screenshot(message, state, bot, db_user, is_replacement=True)


@router.message(PrintingStates.waiting_for_screenshot)
async def handle_screenshot_wrong_type(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте фото отправления.")


@router.message(PrintingStates.waiting_for_order_numbers, F.text)
async def handle_order_numbers(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
) -> None:
    order_numbers = (message.text or "").strip()
    if not order_numbers:
        await message.answer("Отправьте текст с номерами заказов.")
        return

    data = await state.get_data()
    screenshot_file_id = data.get("screenshot_file_id")
    if not screenshot_file_id:
        await state.clear()
        await message.answer("Сессия сброшена. Отправьте фото или используйте /print")
        return

    extension = data.get("screenshot_extension", ".jpg")
    job_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc)
    output_path = build_label_output_path(job_id, created_at)
    screenshot_path = SCREENSHOTS_DIR / f"{job_id}_source{extension}"

    try:
        await _download_screenshot(bot, screenshot_file_id, screenshot_path)
    except ValueError:
        await message.answer("Не удалось загрузить фото. Отправьте скриншот заново.")
        await _clear_screenshot_data(state)
        await state.set_state(PrintingStates.waiting_for_screenshot)
        return

    generator = LabelGenerator()
    try:
        preview_path = generator.generate_label(
            screenshot_path=str(screenshot_path),
            order_numbers_text=order_numbers,
            logo_path=str(DEFAULT_LOGO_PATH),
            qr_ios_path=str(DEFAULT_QR_IOS_PATH),
            qr_android_path=str(DEFAULT_QR_ANDROID_PATH),
            output_path=str(output_path),
        )
    except FileNotFoundError as error:
        await message.answer(f"Ошибка генерации: не найден файл ассета ({error}).")
        _safe_unlink(screenshot_path)
        return
    except Exception:
        await message.answer("Не удалось сгенерировать этикетку. Попробуйте снова.")
        _safe_unlink(screenshot_path)
        await state.clear()
        return

    print_job = PrintJob(
        id=job_id,
        user_id=db_user.id,
        order_numbers=order_numbers,
        image_path=str(output_path),
        status=PrintJobStatus.PENDING,
        created_at=created_at,
    )
    session.add(print_job)
    await session.commit()

    job_sent = await printer_manager.notify_new_job(str(job_id), output_path.name)
    if job_sent:
        print_job.status = PrintJobStatus.PRINTING
        await session.commit()

    label_file = FSInputFile(preview_path)
    await message.answer_photo(photo=label_file, caption="Этикетка готова.")

    username_display = f"@{db_user.username}" if db_user.username else "без username"
    control_caption = (
        f"Создал: {username_display} ({db_user.telegram_id}) | Заказы: {order_numbers}"
    )
    await bot.send_photo(
        chat_id=settings.control_chat_id,
        photo=FSInputFile(preview_path),
        caption=control_caption,
    )

    await _clear_screenshot_data(state)
    await state.clear()
    _safe_unlink(screenshot_path)


@router.message(PrintingStates.waiting_for_order_numbers)
async def handle_order_numbers_wrong_type(message: Message) -> None:
    await message.answer("Отправьте номера заказов текстом.")


async def _clear_screenshot_data(state: FSMContext) -> None:
    data = await state.get_data()
    old_path = data.get("screenshot_path")
    if old_path:
        _safe_unlink(Path(old_path))

    await state.update_data(
        screenshot_path=None,
        screenshot_file_id=None,
        screenshot_extension=None,
    )


async def _accept_screenshot(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db_user: User,
    *,
    is_replacement: bool = False,
) -> None:
    data = await state.get_data()
    last_msg_id = data.get("last_msg_id")

    await _clear_screenshot_data(state)

    if message.document is not None:
        mime_type = message.document.mime_type or ""
        if not mime_type.startswith("image/"):
            await message.answer("Пожалуйста, отправьте изображение (фото).")
            return
        file_id = message.document.file_id
        extension = _extension_from_mime(mime_type)
    elif message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        extension = ".jpg"
    else:
        await message.answer("Пожалуйста, отправьте фото отправления.")
        return

    screenshot_token = uuid.uuid4().hex
    screenshot_path = SCREENSHOTS_DIR / f"{db_user.telegram_id}_{screenshot_token}{extension}"

    try:
        await _download_screenshot(bot, file_id, screenshot_path)
    except ValueError:
        await message.answer("Не удалось загрузить файл. Попробуйте ещё раз.")
        return

    await state.update_data(
        screenshot_path=str(screenshot_path),
        screenshot_file_id=file_id,
        screenshot_extension=extension,
    )
    await state.set_state(PrintingStates.waiting_for_order_numbers)
    await _notify_photo_status(
        message=message,
        bot=bot,
        state=state,
        last_msg_id=last_msg_id if is_replacement else None,
        is_replacement=is_replacement,
    )


async def _notify_photo_status(
    message: Message,
    bot: Bot,
    state: FSMContext,
    last_msg_id: int | None,
    is_replacement: bool,
) -> None:
    prompt_text = PHOTO_REPLACED_TEXT if is_replacement else PHOTO_RECEIVED_TEXT

    if is_replacement and last_msg_id:
        try:
            await bot.edit_message_text(
                text=prompt_text,
                chat_id=message.chat.id,
                message_id=last_msg_id,
            )
            await state.update_data(last_msg_id=last_msg_id)
            return
        except TelegramBadRequest:
            pass

    sent = await message.answer(prompt_text)
    await state.update_data(last_msg_id=sent.message_id)


async def _download_screenshot(bot: Bot, file_id: str, destination: Path) -> None:
    file = await bot.get_file(file_id)
    if file.file_path is None:
        raise ValueError("Telegram file path is missing")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    await bot.download_file(file.file_path, destination=destination)


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _extension_from_mime(mime_type: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
    }
    return mapping.get(mime_type, ".jpg")
