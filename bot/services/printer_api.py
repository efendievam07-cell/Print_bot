import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.connection import async_session_factory
from bot.database.models import PrintJob, PrintJobStatus
from bot.utils.label_paths import LABELS_DIR

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Держит одно активное WebSocket-подключение офисного принтера."""

    def __init__(self) -> None:
        self._websocket: WebSocket | None = None

    async def connect(self, websocket: WebSocket) -> None:
        if self._websocket is not None:
            try:
                await self._websocket.close(code=1008, reason="Another printer is connected")
            except Exception:
                logger.exception("Не удалось закрыть предыдущее подключение принтера")

        await websocket.accept()
        self._websocket = websocket
        logger.info("Принтер подключён по WebSocket")

    def disconnect(self, websocket: WebSocket) -> None:
        if self._websocket is websocket:
            self._websocket = None
            logger.info("Принтер отключён от WebSocket")

    @property
    def is_connected(self) -> bool:
        return self._websocket is not None

    async def notify_new_job(self, job_id: str, file_name: str) -> bool:
        if self._websocket is None:
            logger.warning("Принтер не подключён — задание %s останется в очереди", job_id)
            return False

        await self._websocket.send_json(
            {
                "event": "new_job",
                "job_id": job_id,
                "file_name": file_name,
            }
        )
        logger.info("Задание %s отправлено принтеру", job_id)
        return True


printer_manager = ConnectionManager()


@router.get("/download/{job_id}")
async def download_label(job_id: str) -> FileResponse:
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Некорректный job_id") from error

    async with async_session_factory() as session:
        print_job = await session.scalar(
            select(PrintJob).where(PrintJob.id == job_uuid)
        )

    if print_job is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")

    file_path = Path(print_job.image_path).resolve()
    labels_root = LABELS_DIR.resolve()

    if not file_path.is_relative_to(labels_root):
        raise HTTPException(status_code=400, detail="Некорректный путь к файлу")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл этикетки не найден")

    return FileResponse(
        path=file_path,
        media_type="image/png",
        filename=file_path.name,
    )


@router.websocket("/ws/printer")
async def printer_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    if not token or token != settings.api_secret_token:
        await websocket.close(code=1008, reason="Unauthorized")
        logger.warning("Отклонено WebSocket-подключение принтера: неверный токен")
        return

    await printer_manager.connect(websocket)

    try:
        while True:
            raw_message = await websocket.receive_text()
            await _handle_printer_report(raw_message, websocket)
    except WebSocketDisconnect:
        printer_manager.disconnect(websocket)
    except Exception:
        logger.exception("Ошибка WebSocket-соединения с принтером")
        printer_manager.disconnect(websocket)
        await websocket.close(code=1011, reason="Internal error")


async def _handle_printer_report(raw_message: str, websocket: WebSocket) -> None:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.warning("Принтер прислал невалидный JSON: %s", raw_message)
        return

    job_id_raw = payload.get("job_id")
    status_raw = payload.get("status")

    if not job_id_raw or status_raw not in ("SUCCESS", "ERROR"):
        logger.warning("Принтер прислал неполный отчёт: %s", payload)
        return

    try:
        job_uuid = uuid.UUID(str(job_id_raw))
    except ValueError:
        logger.warning("Принтер прислал некорректный job_id: %s", job_id_raw)
        return

    new_status = (
        PrintJobStatus.SUCCESS if status_raw == "SUCCESS" else PrintJobStatus.ERROR
    )

    async with async_session_factory() as session:
        print_job = await session.scalar(
            select(PrintJob)
            .where(PrintJob.id == job_uuid)
            .options(selectinload(PrintJob.user))
        )
        if print_job is None:
            logger.warning("Отчёт принтера для неизвестного job_id: %s", job_uuid)
            return

        print_job.status = new_status
        if new_status == PrintJobStatus.SUCCESS:
            print_job.printed_at = datetime.now(timezone.utc)
        await session.commit()

        user_telegram_id = print_job.user.telegram_id
        order_numbers = print_job.order_numbers

    bot = websocket.app.state.bot

    if new_status == PrintJobStatus.SUCCESS:
        user_message = "Этикетка успешно напечатана!"
        control_message = (
            f"✅ Печать завершена\n"
            f"Job: {job_uuid}\n"
            f"Заказы: {order_numbers}\n"
            f"Пользователь: {user_telegram_id}"
        )
    else:
        user_message = "Ошибка печати, проверьте принтер!"
        control_message = (
            f"❌ Ошибка печати\n"
            f"Job: {job_uuid}\n"
            f"Заказы: {order_numbers}\n"
            f"Пользователь: {user_telegram_id}"
        )

    try:
        await bot.send_message(chat_id=user_telegram_id, text=user_message)
    except Exception:
        logger.exception("Не удалось отправить уведомление пользователю %s", user_telegram_id)

    try:
        await bot.send_message(chat_id=settings.control_chat_id, text=control_message)
    except Exception:
        logger.exception("Не удалось отправить уведомление в контрольный чат")
