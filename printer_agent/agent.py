"""Локальный агент печати Optop для Windows."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
import websockets
from dotenv import load_dotenv

from printer_win32 import print_label

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5
DOWNLOAD_TIMEOUT_SECONDS = 30


def _load_settings() -> tuple[str, str, str]:
    load_dotenv()

    vds_url = os.getenv("VDS_URL", "").strip()
    api_token = os.getenv("API_SECRET_TOKEN", "").strip()
    printer_name = os.getenv("PRINTER_NAME", "").strip()

    missing = [
        name
        for name, value in (
            ("VDS_URL", vds_url),
            ("API_SECRET_TOKEN", api_token),
            ("PRINTER_NAME", printer_name),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Не заданы переменные окружения: {', '.join(missing)}")

    return vds_url.rstrip("/"), api_token, printer_name


def _normalize_base_url(vds_url: str, default_scheme: str) -> str:
    if "://" in vds_url:
        return vds_url.rstrip("/")

    return f"{default_scheme}://{vds_url}".rstrip("/")


def build_ws_url(vds_url: str, api_token: str) -> str:
    if vds_url.startswith("ws://") or vds_url.startswith("wss://"):
        base = vds_url.rstrip("/")
    elif vds_url.startswith("http://"):
        base = "ws://" + vds_url[len("http://") :]
    elif vds_url.startswith("https://"):
        base = "wss://" + vds_url[len("https://") :]
    else:
        base = f"ws://{vds_url}"

    return f"{base.rstrip('/')}/ws/printer?token={api_token}"


def build_download_url(vds_url: str, job_id: str) -> str:
    if vds_url.startswith("http://") or vds_url.startswith("https://"):
        base = vds_url.rstrip("/")
    else:
        base = _normalize_base_url(vds_url, "http")

    return f"{base}/download/{job_id}"


def _download_label(download_url: str, file_name: str) -> str:
    response = requests.get(download_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()

    suffix = Path(file_name).suffix or ".png"
    file_descriptor, temp_path = tempfile.mkstemp(prefix="optop_label_", suffix=suffix)
    os.close(file_descriptor)

    path = Path(temp_path)
    path.write_bytes(response.content)
    return str(path)


async def _send_status(websocket: websockets.WebSocketClientProtocol, job_id: str, status: str) -> None:
    await websocket.send(json.dumps({"job_id": job_id, "status": status}))


async def _process_new_job(
    websocket: websockets.WebSocketClientProtocol,
    payload: dict,
    vds_url: str,
    printer_name: str,
) -> None:
    job_id = str(payload.get("job_id", "")).strip()
    file_name = str(payload.get("file_name", "label.png")).strip()

    if not job_id:
        logger.warning("Получено событие new_job без job_id: %s", payload)
        return

    temp_path: str | None = None
    try:
        download_url = build_download_url(vds_url, job_id)
        logger.info("Скачивание этикетки %s", download_url)
        temp_path = await asyncio.to_thread(_download_label, download_url, file_name)

        logger.info("Печать задания %s на принтере %s", job_id, printer_name)
        await asyncio.to_thread(print_label, temp_path, printer_name)

        await _send_status(websocket, job_id, "SUCCESS")
        logger.info("Задание %s успешно напечатано", job_id)
    except Exception:
        logger.exception("Ошибка обработки задания %s", job_id)
        await _send_status(websocket, job_id, "ERROR")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


async def _handle_message(
    raw_message: str,
    websocket: websockets.WebSocketClientProtocol,
    vds_url: str,
    printer_name: str,
) -> None:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.warning("Получено невалидное JSON-сообщение: %s", raw_message)
        return

    if payload.get("event") == "new_job":
        await _process_new_job(websocket, payload, vds_url, printer_name)
    else:
        logger.debug("Пропущено неизвестное событие: %s", payload)


async def _listen(
    websocket: websockets.WebSocketClientProtocol,
    vds_url: str,
    printer_name: str,
) -> None:
    async for message in websocket:
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        await _handle_message(message, websocket, vds_url, printer_name)


async def _connect_once(vds_url: str, api_token: str, printer_name: str) -> None:
    ws_url = build_ws_url(vds_url, api_token)
    host = urlparse(ws_url).netloc
    logger.info("Подключение к серверу %s", host)

    async with websockets.connect(
        ws_url,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=5,
    ) as websocket:
        logger.info("WebSocket-подключение установлено")
        await _listen(websocket, vds_url, printer_name)


async def run_agent() -> None:
    vds_url, api_token, printer_name = _load_settings()
    logger.info("Агент Optop запущен. Принтер: %s", printer_name)

    while True:
        try:
            await _connect_once(vds_url, api_token, printer_name)
            logger.warning("WebSocket-соединение закрыто сервером")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Потеряно соединение с сервером")

        logger.info("Повторное подключение через %s сек...", RECONNECT_DELAY_SECONDS)
        await asyncio.sleep(RECONNECT_DELAY_SECONDS)


def main() -> None:
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        logger.info("Агент остановлен")


if __name__ == "__main__":
    main()
